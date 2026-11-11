import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace


def test_revision_signer_and_secret_directory_survive_previous_manifest(tmp_path,monkeypatch):
    root=tmp_path; (root/'deployments').mkdir(); (root/'contracts/deployable').mkdir(parents=True)
    previous={'revision':3,'signer':'previous','network':'studionet','chain_id':61999,'registry':'old-registry','court':'old-court','directory':'old-directory','incident':'old-incident','release':'old-release'}
    (root/'deployments/studionet.json').write_text(json.dumps(previous))
    for name in ('event_registry','identity_court','consumer_directory','incident_history','release_evidence'):
        (root/f'contracts/deployable/{name}.py').write_text('controlled code')
    def atomic(path,value): path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
    class Journal:
        def __init__(self,path): self.path=root/path;self.operations={}
        def perform(self,key,callback,signer='DEPLOYER_PRIVATE_KEY',binding=None):
            self.operations[key]={'receipt':{'contract_address':'new-'+key},'success':True,'binding':binding}
            return self.operations[key]
    studio=SimpleNamespace(ROOT=root,Journal=Journal,client=lambda name=None:SimpleNamespace(local_account=SimpleNamespace(address='current-'+str(name))),atomic=atomic,encode=json.dumps)
    monkeypatch.setitem(sys.modules,'studio',studio)
    monkeypatch.setattr(sys,'argv',['deploy.py','--revision=4','--fresh-registry'])
    runpy.run_path(str(Path(__file__).resolve().parents[2]/'scripts/deploy.py'),run_name='__main__')
    current=json.loads((root/'deployments/studionet.json').read_text())
    assert current['revision']==4
    assert current['signer']=='current-None'
    assert current['registry']=='new-deploy.registry'
    assert json.loads((root/'deployments/studionet.v3.json').read_text())==previous
    assert (root/'.secrets/consumer-owners.env').exists()
    assert (root/'.secrets/consumer-owners.env').stat().st_mode & 0o777 == 0o600


def test_journal_recovers_an_authoritative_final_receipt_after_waiter_timeout(tmp_path, monkeypatch):
    import importlib.util
    path=Path(__file__).resolve().parents[2]/'scripts/studio.py'
    spec=importlib.util.spec_from_file_location('controlled_studio',path); module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    receipt={'hash':'hash','status_name':'FINALIZED','result_name':'MAJORITY_AGREE','consensus_data':{'leader_receipt':[{'execution_result':'SUCCESS'},{'execution_result':'ERROR','genvm_result':{'stderr':'Validator execution cancelled after quorum'}}]}}
    class Client:
        local_account=SimpleNamespace(address='controlled-owner')
        def wait_for_transaction_receipt(self,*args,**kwargs): raise TimeoutError('waiter interrupted')
        def get_transaction(self,*args,**kwargs): return receipt
    monkeypatch.setattr(module,'ROOT',tmp_path);monkeypatch.setattr(module,'client',lambda *args:Client())
    journal=module.Journal('verification/controlled.json')
    result=journal.perform('controlled',lambda c:'hash')
    assert result['success']
    assert result['status']=='finalized'
    assert json.loads(journal.path.read_text())['controlled']['transaction_hash']=='hash'
