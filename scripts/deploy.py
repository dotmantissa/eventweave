from pathlib import Path
import os
from eth_account import Account
from studio import ROOT,Journal,client,atomic,encode

# Each consumer gets an independent key. Generated once, stored only in the ignored owner environment.
keys=ROOT/'.secrets/consumer-owners.env'
keys.parent.mkdir(parents=True, exist_ok=True)
if not keys.exists():
    keys.write_text('INCIDENT_OWNER_PRIVATE_KEY='+Account.create().key.hex()+'\nRELEASE_OWNER_PRIVATE_KEY='+Account.create().key.hex()+'\n');keys.chmod(0o600)
from dotenv import load_dotenv
load_dotenv(keys)
import sys
revision = next((int(arg.split('=')[1]) for arg in sys.argv if arg.startswith('--revision=')), 1)
journal=Journal('verification/deployment-receipts' + ('.v' + str(revision) if revision > 1 else '') + '.json');path=ROOT/'deployments/studionet.json'
if path.exists() and revision < __import__('json').loads(path.read_text()).get('revision', 1):
    raise RuntimeError('Deployment revision cannot move backwards')
if revision > 1 and path.exists() and not (ROOT/f'deployments/studionet.v{revision-1}.json').exists():
    (ROOT/f'deployments/studionet.v{revision-1}.json').write_text(path.read_text())
deployment={'network':'studionet','chain_id':61999,'revision':revision,'signer':client().local_account.address,'incident_owner':client('INCIDENT_OWNER_PRIVATE_KEY').local_account.address,'release_owner':client('RELEASE_OWNER_PRIVATE_KEY').local_account.address}
if path.exists():
    prior = __import__('json').loads(path.read_text())
    deployment = {**prior, **deployment}
for name,file,args,signer in [('registry','event_registry.py',[],'DEPLOYER_PRIVATE_KEY'),('court','identity_court.py',[deployment.get('registry')],'DEPLOYER_PRIVATE_KEY'),('directory','consumer_directory.py',[deployment.get('court'),deployment.get('registry')],'DEPLOYER_PRIVATE_KEY'),('incident','incident_history.py',[deployment.get('directory'),deployment.get('registry'),'occurrence.v1',1,1000],'INCIDENT_OWNER_PRIVATE_KEY'),('release','release_evidence.py',[deployment.get('directory'),deployment.get('registry'),'occurrence.v1',1,1000],'RELEASE_OWNER_PRIVATE_KEY')]:
    if revision > 1 and name == 'registry' and '--fresh-registry' not in sys.argv:
        continue
    # Build constructor arguments from the verified addresses as deployments progress.
    if name=='court':args=[deployment['registry']]
    if name=='directory':args=[deployment['court'],deployment['registry']]
    if name in ('incident','release'):args=[deployment['directory'],deployment['registry'],'occurrence.v1',1,1000]
    code_digest = __import__('hashlib').sha256((ROOT/'contracts/deployable'/file).read_bytes()).hexdigest()
    prior_entry = journal.operations.get('deploy.'+name, {})
    if prior_entry and (prior_entry.get('code_digest', code_digest) != code_digest or prior_entry.get('constructor_args', args) != args):
        raise RuntimeError('Deployment journal binding changed; use a new revision')
    result=journal.perform('deploy.'+name,lambda c:c.deploy_contract(code=(ROOT/'contracts/deployable'/file).read_bytes(),args=args),signer,binding={'code_digest':code_digest,'constructor_args':args})
    result.update(code_digest=code_digest, constructor_args=args)
    atomic(journal.path, journal.operations)
    deployment[name]=result['receipt']['contract_address'];atomic(path,deployment)
if not journal.operations.get('bind.directory',{}).get('success'):
    journal.perform('bind.directory',lambda c:c.write_contract(deployment['court'],'bind_directory',args=[deployment['directory']]))
policy={'schema_id':'occurrence.v1','revision':1,'scope':'public.occurrence','mandatory':['issuer','place','interval','occurrence_type','official_reference'],'rules':['All mandatory identity attributes require explicit support from authentic public sources.','Compare the actual occurrence interval in UTC, including amended names and timezone shifts.','Recurring incidents with different intervals or official references are DISTINCT.','Common cause never establishes occurrence identity. Missing or vague evidence remains UNKNOWN.','Software releases require the same official version and release publication interval.']}
journal.perform('schema.occurrence.v1',lambda c:c.write_contract(deployment['registry'],'register_schema',args=[encode(policy)]))
print('Deployment manifest:',path.relative_to(ROOT),flush=True)
