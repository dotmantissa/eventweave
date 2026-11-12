"""Verify authenticated revocation replay on authentic Studio certificates."""
import json
import time
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from studio import ROOT, Journal, atomic, client, digest, encode

load_dotenv(ROOT / '.secrets/consumer-owners.env')
deployment = json.loads((ROOT / 'deployments/studionet.json').read_text())
revision = deployment['revision']
journal = Journal(f'verification/revocation-receipts.v{revision}.json')
results_path = ROOT / f'verification/revocation-results.v{revision}.json'
progress = json.loads(results_path.read_text()) if results_path.exists() else {}
request_id = f'public.v{revision}.releases.distinct'
court = deployment['court']; directory = deployment['directory']; consumer = deployment['release']
key = 'RELEASE_OWNER_PRIVATE_KEY'


def read(address, method, *args):
    return client().read_contract(address, method, args=list(args))


def wait_read(address, method, args, predicate):
    for _ in range(20):
        value = read(address, method, *args)
        if predicate(value):
            return value
        time.sleep(5)
    raise RuntimeError('Callback state did not settle: ' + method)


original = read(court, 'get_result', request_id)
if original['decision'] != 'DISTINCT':
    raise RuntimeError('The authentic public release pair must be DISTINCT')
notice_id = read(directory, 'get_latest_delivery', request_id)
if not notice_id:
    raise RuntimeError('Run the public-source verifier first')

journal.perform('quarantine', lambda c: c.write_contract(court, 'quarantine_request', args=[request_id, 'Exercise authenticated revocation and replay of the public release certificate.']), key)
invalidation_ack = wait_read(directory, 'get_consumer_ack', ['invalidate:' + notice_id], lambda v: v.get('status') == 'superseded')
# Persist the observed count before restoration so an interrupted run retains
# actual evidence rather than reconstructing an earlier count from assumptions.
if 'invalidated_stats' not in progress:
    invalidated_stats = wait_read(consumer, 'get_stats', [], lambda v: v['accepted_count'] == 1)
    progress.update(invalidation_ack=invalidation_ack, invalidated_stats=invalidated_stats)
    atomic(results_path, progress)
else:
    invalidated_stats = progress['invalidated_stats']

repeated = journal.perform('quarantine.repeated', lambda c: c.write_contract(court, 'quarantine_request', args=[request_id, 'Replay the already finalized court quarantine.']), key)
court_retry = journal.perform('court.replay', lambda c: c.write_contract(court, 'retry_revocation', args=[request_id]))
directory_retry = journal.perform('directory.replay', lambda c: c.write_contract(directory, 'retry_invalidation', args=[request_id]))
for operation in (repeated, court_retry, directory_retry):
    if not operation['receipt']['triggered_transactions']:
        raise RuntimeError('Finalized replay emitted no callback')

records = sorted([read(deployment['registry'], 'get_identity', original['left']), read(deployment['registry'], 'get_identity', original['right'])], key=lambda v: v['event_id'])
successor_id = f'public.v{revision}.releases.recertified'
compare_entry = journal.operations.get('compare.successor')
if compare_entry:
    # Preserve the exact immutable request packet across interrupted runs.
    packet = compare_entry['binding']['packet']
elif 'packet' in progress:
    packet = progress['packet']
else:
    env = {k: original[k] for k in ('request_id', 'owner', 'parties', 'policy_id', 'policy_revision', 'subject_id', 'subject_digest', 'source_manifest_digest', 'consumer_address', 'consequence_digest', 'generation', 'deadline')}
    env.update(request_id=successor_id, generation=2, source_manifest_digest=digest([r['source'] for r in records]), deadline=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat().replace('+00:00', 'Z'))
    packet = {'envelope': env, 'left': original['left'], 'right': original['right']}
    progress['packet'] = packet
    atomic(results_path, progress)
journal.perform('compare.successor', lambda c: c.write_contract(court, 'compare_records', args=[encode(packet)]), key, binding={'packet': packet})
journal.perform('assess.successor', lambda c: c.write_contract(court, 'assess', args=[successor_id]), key)
successor = read(court, 'get_result', successor_id)
if successor['decision'] != 'DISTINCT' or successor['unresolved']:
    raise RuntimeError('Real source recertification did not confirm DISTINCT')
wait_read(directory, 'get_acknowledgement', [successor_id], lambda v: v.get('status') == 'finalized')
journal.perform('supersede', lambda c: c.write_contract(court, 'supersede_relation', args=[request_id, successor_id, 'Restore the same authentic release distinction with a fresh certified generation.']), key)
supersede_replay = journal.perform('supersede.repeated', lambda c: c.write_contract(court, 'supersede_relation', args=[request_id, successor_id, 'Replay the finalized certificate correction.']), key)
if not supersede_replay['receipt']['triggered_transactions']:
    raise RuntimeError('Repeated supersession emitted no callback')
journal.perform('publish.successor', lambda c: c.write_contract(directory, 'publish_alias', args=[successor_id]))
restored_notice = wait_read(directory, 'get_latest_delivery', [successor_id], bool)
restored_ack = wait_read(directory, 'get_consumer_ack', [restored_notice], lambda v: v.get('status') == 'finalized')
restored_stats = wait_read(consumer, 'get_stats', [], lambda v: v['accepted_count'] == 3)
atomic(results_path, {
    'classification': 'Actual signed Studio revocation/replay and successor recertification on authentic Node.js releases. Dropped callbacks are tested separately in controlled regressions.',
    'deployment': deployment, 'request_id': request_id, 'notice_id': notice_id,
    'invalidation_ack': invalidation_ack, 'invalidated_stats': invalidated_stats,
    'repeated_quarantine_emitted': True, 'court_replay_emitted': True,
    'directory_replay_emitted': True, 'repeated_supersession_emitted': True,
    'successor': successor, 'restored_ack': restored_ack, 'restored_stats': restored_stats,
    'interrupted_compare_recovered': progress.get('interrupted_compare_recovered'),
    'passed': True,
})
print('Actual revocation replay finalized and acknowledged; release count restored to 3', flush=True)
