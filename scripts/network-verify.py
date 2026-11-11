"""Authentic public source exercise on Studio. These are verification records, not adoption."""
import os
import json
import hashlib
import time
from pathlib import Path
import requests
from dotenv import load_dotenv
from studio import ROOT,Journal,client,encode,digest,atomic
load_dotenv(ROOT/'.secrets/consumer-owners.env')
deployment=json.loads((ROOT/'deployments/studionet.json').read_text())
revision=deployment.get('revision',2)
journal=Journal(f'verification/public-source-receipts.v{revision}.json')
source_commit='c09d4686360dd88cd41fd048b0e9ebd9045c3d5a'
base='https://raw.githubusercontent.com/nodejs/nodejs.org/'
attrs=['issuer','place','interval','occurrence_type','official_reference']

def retrieve(path, version=source_commit):
    response=requests.get(base+version+'/'+path,timeout=25);response.raise_for_status();raw=response.content
    if len(raw)>49152:raise RuntimeError('Complete record exceeds 48 KiB: '+path)
    raw.decode('utf-8',errors='strict');return raw

authority_raw=retrieve('README.md')
authority={'authority_id':'nodejs.public','principal':deployment['signer'].lower(),'channel':'official.website','url_prefix':base,'evidence_url':base+source_commit+'/README.md','evidence_hash':hashlib.sha256(authority_raw).hexdigest(),'evidence_bytes':len(authority_raw),'scope':'public.occurrence','revision':1}
journal.perform('authority.nodejs.public',lambda c:c.write_contract(deployment['registry'],'register_authority',args=[encode(authority)]))

specifications=[
 ('nodejs.notice.jan2025','Node.js January 2025 security release notice','apps/site/pages/en/blog/vulnerability/january-2025-security-releases.md','operational_notice','january-2025-security-releases','5f194a11346275b1187ef66ec4d2c230e587f328'),
 ('nodejs.notice.jan2025.amended','January security update for Node.js','apps/site/pages/en/blog/vulnerability/january-2025-security-releases.md','operational_notice','january-2025-security-releases','642c2c232041b06d5bfb9ee65c90b83e4c79bc47'),
 ('nodejs.release.22.13.1','Node.js 22.13.1','apps/site/pages/en/blog/release/v22.13.1.md','release','v22.13.1',source_commit),
 ('nodejs.release.22.11.0','Node.js 22.11.0','apps/site/pages/en/blog/release/v22.11.0.md','release','v22.11.0',source_commit),
]
records={}
for event_id,title,path,kind,reference,version in specifications:
    raw=retrieve(path,version);raw_hash=hashlib.sha256(raw).hexdigest()
    import re
    date=re.search(r"^date: ['\"]?([0-9T:.+Z-]+)",raw.decode(),re.M)
    if not date:raise RuntimeError('Public source has no explicit publication interval')
    interval=date.group(1)
    source={'record_id':event_id,'authority_id':'nodejs.public:1','channel':'official.website','url':base+version+'/'+path,'raw_hash':raw_hash,'revision':version,'scope':'public.occurrence','byte_length':len(raw),'spans':[{'span_id':event_id+'.'+attribute,'attribute':attribute,'start':0,'end':len(raw),'raw_hash':raw_hash} for attribute in attrs]}
    descriptor={'event_id':event_id,'schema_id':'occurrence.v1','schema_revision':1,'title':title,'issuer':'Node.js','place':'Node.js ecosystem','interval_start':interval,'interval_end':interval,'occurrence_type':kind,'official_reference':reference,'source':source}
    journal.perform('event.'+event_id,lambda c,d=descriptor:c.write_contract(deployment['registry'],'open_event',args=[encode(d)]));records[event_id]=descriptor
if (ROOT/'verification/public-source-manifests.json').exists() and not (ROOT/'verification/public-source-manifests.v3.json').exists():
    (ROOT/'verification/public-source-manifests.v3.json').write_text((ROOT/'verification/public-source-manifests.json').read_text())
atomic(ROOT/'verification/public-source-manifests.json',{'classification':'authentic public source verification, not real adoption','source_commit':source_commit,'authority':authority,'descriptors':records})

for consumer,keyname in [('incident','INCIDENT_OWNER_PRIVATE_KEY'),('release','RELEASE_OWNER_PRIVATE_KEY')]:
    for event_id in (['nodejs.notice.jan2025','nodejs.notice.jan2025.amended'] + (['nodejs.release.22.13.1','nodejs.release.22.11.0'] if consumer == 'release' else [])):
        journal.perform('reference.'+consumer+'.'+event_id,lambda c,e=event_id:c.write_contract(deployment[consumer],'register_reference',args=[e,consumer+'.'+e]),keyname)

def request(left,right,consumer,generation,request_id):
    c=client();event_records=sorted([c.read_contract(deployment['registry'],'get_identity',args=[left]),c.read_contract(deployment['registry'],'get_identity',args=[right])],key=lambda r:r['event_id'])
    scope='scope:'+digest({'scope':'public.occurrence','policy_id':'occurrence.v1','policy_revision':1});subject='pair:'+digest({'scope':scope,'records':sorted([left,right])})
    config=c.read_contract(deployment[consumer],'get_configuration')
    env={'request_id':request_id,'owner':config['owner'],'parties':[config['owner']],'policy_id':'occurrence.v1','policy_revision':1,'subject_id':subject,'subject_digest':digest([{'event_id':e['event_id'],'descriptor_digest':e['descriptor_digest']} for e in event_records]),'source_manifest_digest':digest([e['source'] for e in event_records]),'consumer_address':deployment[consumer].lower(),'consequence_digest':config['consequence_digest'],'generation':generation,'deadline':(__import__('datetime').datetime.now(__import__('datetime').timezone.utc)+__import__('datetime').timedelta(days=2)).isoformat().replace('+00:00','Z')}
    return {'envelope':env,'left':left,'right':right},scope

results_path=ROOT/'verification/public-source-results.json'
if results_path.exists() and not (ROOT/'verification/public-source-results.v3.json').exists():
    (ROOT/'verification/public-source-results.v3.json').write_text(results_path.read_text())
versioned_results_path=ROOT/f'verification/public-source-results.v{revision}.json'
results=json.loads(versioned_results_path.read_text()) if versioned_results_path.exists() else {}
results.pop('releases.distinct.verification', None) if results.get('releases.distinct', {}).get('consumer_ack', {}).get('status') == 'finalized' else None
for label,left,right,consumer,generation in [('notice.renamed.incident','nodejs.notice.jan2025','nodejs.notice.jan2025.amended','incident',1),('notice.renamed.release','nodejs.notice.jan2025','nodejs.notice.jan2025.amended','release',1),('releases.distinct','nodejs.release.22.13.1','nodejs.release.22.11.0','release',1)]:
    request_id=f'public.v{revision}.'+label
    previous=results.get(label,{})
    if previous.get('request_id')==request_id and previous.get('consumer_ack',{}).get('status')=='finalized' and journal.operations.get('publish.'+label,{}).get('success'):
        print(label,'verified from retained finalized delivery',flush=True)
        continue
    keyname = 'INCIDENT_OWNER_PRIVATE_KEY' if consumer == 'incident' else 'RELEASE_OWNER_PRIVATE_KEY'
    value,scope=request(left,right,consumer,generation,request_id)
    journal.perform('compare.'+label,lambda c,v=value:c.write_contract(deployment['court'],'compare_records',args=[encode(v)]),keyname)
    journal.perform('assess.'+label,lambda c,key=request_id:c.write_contract(deployment['court'],'assess',args=[key]),keyname)
    result=client().read_contract(deployment['court'],'get_result',args=[request_id]);results[label]=result;atomic(results_path,results);print(label,'decision',result['decision'],flush=True)
    expected='DISTINCT' if label=='releases.distinct' else 'SAME'
    if result['decision']!=expected:raise RuntimeError('Public case did not establish '+expected+': '+label)
    # Confirm the actual finalized message has been processed, rather than using a view as finality proof.
    for _ in range(12):
        ack=client().read_contract(deployment['directory'],'get_acknowledgement',args=[request_id])
        if ack:break
        time.sleep(3)
    if not ack:raise RuntimeError('Finalized certificate delivery remains pending: '+request_id)
    if result['decision']=='SAME':
        proof={'operation_id':'merge.'+label,'left':left,'right':right,'scope':scope,'relations':[request_id]}
        journal.perform('propose.'+label,lambda c,p=proof:c.write_contract(deployment['directory'],'propose_merge',args=[encode(p)]),keyname)
        journal.perform('finalize.'+label,lambda c,key=proof['operation_id']:c.write_contract(deployment['directory'],'finalize_alias',args=[key]))
    journal.perform('publish.'+label,lambda c,key=request_id:c.write_contract(deployment['directory'],'publish_alias',args=[key]))
    results[label]['directory_ack']=ack
    for _ in range(12):
        acknowledgement=client().read_contract(deployment[consumer],'get_acknowledgement',args=['delivery:'+request_id])
        if acknowledgement:break
        time.sleep(3)
    results[label]['consumer_ack']=acknowledgement
    if not acknowledgement or acknowledgement.get('status')!='finalized':raise RuntimeError('Consumer delivery is not acknowledged: '+request_id)
    atomic(ROOT/f'verification/public-source-results.v{revision}.json',results)
    atomic(ROOT/'verification/public-source-results.json',results)
for consumer in ['incident','release']:
    stats=client().read_contract(deployment[consumer],'get_stats');print(consumer,'decisive state',stats,flush=True);results[consumer+'.stats']=stats
    if stats['accepted_count'] != (1 if consumer=='incident' else 3):raise RuntimeError('Unexpected accepted occurrence count for '+consumer)
atomic(ROOT/'verification/public-source-results.json',results)

atomic(ROOT/f'verification/public-source-results.v{revision}.json',results)
