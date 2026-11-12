import pytest

from conftest import STRANGER
from test_directory import certify, merge
from test_lifecycle_regressions import finalize_merge, publish, reserve

pytestmark = pytest.mark.synthetic


@pytest.mark.parametrize('withdrawal', ['quarantine', 'supersede', 'generation'])
def test_withdrawing_newer_distinct_preserves_other_consumers_witness(
    system, event_factory, request_factory, withdrawal
):
    s = system; c = s.chain
    event_factory('a'); event_factory('b')
    older = certify(s, request_factory, 'a', 'b', 'DISTINCT', consumer=s.release)
    newer = certify(s, request_factory, 'a', 'b', 'DISTINCT')
    if withdrawal == 'quarantine':
        c.call(s.court, 'quarantine_request', newer['envelope']['request_id'], 'Withdraw newer witness')
        c.finalize()
    if withdrawal == 'supersede':
        correction = certify(s, request_factory, 'a', 'b', 'DISTINCT', generation=2)
        c.call(s.court, 'supersede_relation', newer['envelope']['request_id'], correction['envelope']['request_id'], 'Replace newer witness')
        c.finalize()
    generation = 3 if withdrawal == 'supersede' else 2
    affirmative = certify(s, request_factory, 'a', 'b', generation=generation)
    assert c.call(s.directory, 'is_current', older['envelope']['request_id'])
    _, result = merge(s, [affirmative], 'a', 'b')
    assert result['status'] == 'refused'
    assert result['witness'] == older['envelope']['request_id']
    # Merge becomes available only when the remaining witness is actually revoked.
    c.call(s.court, 'quarantine_request', older['envelope']['request_id'], 'Withdraw remaining witness')
    c.finalize()
    affirmative = certify(s, request_factory, 'a', 'b', generation=generation + 1)
    _, result = merge(s, [affirmative], 'a', 'b')
    assert result['status'] == 'pending'
    c.call(s.directory, 'finalize_alias', 'merge.ab')


def test_pending_merge_rechecks_remaining_distinct_at_finalization(system, event_factory, request_factory):
    s = system; c = s.chain
    event_factory('a'); event_factory('b')
    affirmative = certify(s, request_factory, 'a', 'b')
    merge(s, [affirmative], 'a', 'b')
    older = certify(s, request_factory, 'a', 'b', 'DISTINCT', consumer=s.release)
    newer = certify(s, request_factory, 'a', 'b', 'DISTINCT', generation=2)
    c.call(s.court, 'quarantine_request', newer['envelope']['request_id'], 'Withdraw newer witness')
    c.finalize()
    certify(s, request_factory, 'a', 'b', generation=3)
    assert c.call(s.directory, 'is_current', older['envelope']['request_id'])
    with pytest.raises(Exception, match='DISTINCT witness'):
        c.call(s.directory, 'finalize_alias', 'merge.ab')


def test_transitive_merge_keeps_an_older_cross_consumer_witness(system, event_factory, request_factory):
    s = system; c = s.chain
    for r in 'abc':
        event_factory(r)
    ab = certify(s, request_factory, 'a', 'b')
    finalize_merge(s, [ab], 'a', 'b', 'merge.ab')
    bc = certify(s, request_factory, 'b', 'c')
    older = certify(s, request_factory, 'a', 'c', 'DISTINCT', consumer=s.release)
    newer = certify(s, request_factory, 'a', 'c', 'DISTINCT')
    c.call(s.court, 'quarantine_request', newer['envelope']['request_id'], 'Withdraw newer cross-pair witness')
    c.finalize()
    ac = certify(s, request_factory, 'a', 'c', generation=2)
    _, result = merge(s, [ab, ac, bc], 'a', 'c', 'merge.abc')
    assert result['status'] == 'refused'
    assert result['witness'] == older['envelope']['request_id']
    assert c.call(s.directory, 'get_identity', 'c', result['scope'])['members'] == ['c']


@pytest.mark.parametrize('decision', ['SAME', 'DISTINCT'])
@pytest.mark.parametrize('replay', ['court_action', 'directory', 'directory_notice', 'court_retry'])
def test_dropped_initial_quarantine_is_recoverable(system, event_factory, request_factory, decision, replay):
    s = system; c = s.chain
    event_factory('a'); event_factory('b'); reserve(s, 'ab')
    relation = certify(s, request_factory, 'a', 'b', decision)
    request_id = relation['envelope']['request_id']
    if decision == 'SAME':
        finalize_merge(s, [relation], 'a', 'b', 'merge.ab')
    publish(s, relation)
    notice_id = c.call(s.directory, 'get_latest_delivery', request_id)
    before = c.call(s.incident, 'get_stats')['accepted_count']
    c.call(s.court, 'quarantine_request', request_id, 'Revoke accepted evidence')
    c.messages.clear()  # Drop the very first court -> directory message.
    assert c.call(s.incident, 'get_stats')['accepted_count'] == before
    assert not c.call(s.directory, 'is_current', request_id)
    if replay == 'court_action':
        c.call(s.court, 'quarantine_request', request_id, 'Retry revoked evidence')
    elif replay == 'directory':
        c.call(s.directory, 'retry_invalidation', request_id, sender=STRANGER)
    elif replay == 'directory_notice':
        c.call(s.directory, 'retry_invalidation', notice_id, sender=STRANGER)
    else:
        c.call(s.court, 'retry_revocation', request_id, sender=STRANGER)
    assert c.messages
    c.finalize()
    assert c.call(s.incident, 'get_stats')['accepted_count'] == 0
    assert c.call(s.directory, 'get_consumer_ack', 'invalidate:' + notice_id)['status'] == 'superseded'
    for r in 'ab':
        assert c.call(s.incident, 'get_reference', 'ref.' + r)['status'] == 'superseded'
    # Replaying either hop repeatedly preserves counts and audit state.
    history = len(c.contracts[s.directory].history)
    for _ in range(2):
        c.call(s.court, 'quarantine_request', request_id, 'Retry court hop')
        c.call(s.directory, 'retry_invalidation', request_id)
        c.finalize()
    assert len(c.contracts[s.directory].history) == history
    assert c.call(s.incident, 'get_stats')['accepted_count'] == 0


@pytest.mark.parametrize('replay', ['court_action', 'directory', 'quarantine'])
def test_dropped_initial_supersession_uses_bound_successor(system, event_factory, request_factory, replay):
    s = system; c = s.chain
    event_factory('a'); event_factory('b'); reserve(s, 'ab')
    original = certify(s, request_factory, 'a', 'b', 'DISTINCT'); publish(s, original)
    request_id = original['envelope']['request_id']
    successor = certify(s, request_factory, 'a', 'b', generation=2)
    successor_id = successor['envelope']['request_id']
    c.call(s.court, 'supersede_relation', request_id, successor_id, 'Correct distinct verdict')
    c.messages.clear()
    assert c.call(s.incident, 'get_stats')['accepted_count'] == 2
    if replay == 'court_action':
        c.call(s.court, 'supersede_relation', request_id, successor_id, 'Retry correction')
    elif replay == 'directory':
        c.call(s.directory, 'retry_invalidation', request_id, sender=STRANGER)
    else:
        c.call(s.court, 'quarantine_request', request_id, 'Retry retired evidence')
    assert c.messages
    c.finalize()
    assert c.call(s.incident, 'get_stats')['accepted_count'] == 0
    assert c.call(s.incident, 'get_reference', 'ref.a')['superseded_by'] == successor_id
    finalize_merge(s, [successor], 'a', 'b', 'corrected'); publish(s, successor)
    c.call(s.court, 'retry_revocation', request_id)
    c.call(s.directory, 'retry_invalidation', request_id); c.finalize()
    assert c.call(s.incident, 'get_stats')['accepted_count'] == 1


@pytest.mark.parametrize('dropped_hop', ['consumer', 'acknowledgement'])
def test_revocation_replay_recovers_later_hops(system, event_factory, request_factory, dropped_hop):
    s = system; c = s.chain
    event_factory('a'); event_factory('b'); reserve(s, 'ab')
    relation = certify(s, request_factory, 'a', 'b', 'DISTINCT'); publish(s, relation)
    request_id = relation['envelope']['request_id']
    notice_id = c.call(s.directory, 'get_latest_delivery', request_id)
    c.call(s.court, 'quarantine_request', request_id, 'Retire evidence')
    sender, target, method, args = c.messages.pop(0)
    c.call(target, method, *args, sender=sender)
    if dropped_hop == 'acknowledgement':
        sender, target, method, args = c.messages.pop(0)
        c.call(target, method, *args, sender=sender)
    c.messages.clear()
    assert c.call(s.directory, 'get_consumer_ack', 'invalidate:' + notice_id) == {}
    c.call(s.directory, 'retry_invalidation', notice_id, sender=STRANGER); c.finalize()
    assert c.call(s.incident, 'get_stats')['accepted_count'] == 0
    assert c.call(s.directory, 'get_consumer_ack', 'invalidate:' + notice_id)['status'] == 'superseded'


def test_distinct_read_failure_cannot_authorize_a_merge(system, event_factory, request_factory, monkeypatch):
    from types import SimpleNamespace
    import genlayer
    s = system; c = s.chain
    event_factory('a'); event_factory('b')
    distinct = certify(s, request_factory, 'a', 'b', 'DISTINCT', consumer=s.release)
    affirmative = certify(s, request_factory, 'a', 'b')
    original_proxy = c.proxy

    def proxy(address):
        original = original_proxy(address)
        if str(address).lower() != s.court:
            return original
        view = original.view()

        def get_result(request_id):
            if request_id == distinct['envelope']['request_id']:
                raise RuntimeError('Court state read failed')
            return view.get_result(request_id)

        return SimpleNamespace(view=lambda: SimpleNamespace(get_result=get_result), emit=original.emit)

    monkeypatch.setattr(genlayer.gl, 'get_contract_at', proxy)
    with pytest.raises(RuntimeError, match='Court state read failed'):
        merge(s, [affirmative], 'a', 'b')


def test_delayed_quarantine_callback_keeps_current_successor(system, event_factory, request_factory):
    s = system; c = s.chain
    event_factory('a'); event_factory('b'); reserve(s, 'ab')
    original = certify(s, request_factory, 'a', 'b', 'DISTINCT'); publish(s, original)
    request_id = original['envelope']['request_id']
    c.call(s.court, 'quarantine_request', request_id, 'Retire original evidence')
    delayed = c.messages.pop(0)
    successor = certify(s, request_factory, 'a', 'b', generation=2)
    successor_id = successor['envelope']['request_id']
    c.call(s.court, 'supersede_relation', request_id, successor_id, 'Finalize correction')
    c.messages.insert(0, delayed); c.finalize()
    assert c.call(s.incident, 'get_reference', 'ref.a')['superseded_by'] == successor_id
    assert c.call(s.incident, 'get_stats')['accepted_count'] == 0



def test_revocation_replay_cannot_revoke_live_certificate(system, event_factory, request_factory):
    s = system; c = s.chain
    event_factory('a'); event_factory('b'); reserve(s, 'ab')
    relation = certify(s, request_factory, 'a', 'b', 'DISTINCT'); publish(s, relation)
    request_id = relation['envelope']['request_id']
    with pytest.raises(Exception, match='No court revocation'):
        c.call(s.court, 'retry_revocation', request_id, sender=STRANGER)
    c.call(s.directory, 'retry_invalidation', request_id, sender=STRANGER)
    assert not c.messages
    with pytest.raises(Exception, match='Only finalized court'):
        c.call(s.directory, 'invalidate_relation', request_id, '', sender=STRANGER)
    assert c.call(s.incident, 'get_stats')['accepted_count'] == 2
