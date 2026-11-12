"""Signed Studio deployment and receipt journal. No private keys are printed."""
import json
import os
import time
import hashlib
from pathlib import Path
from dotenv import load_dotenv
from genlayer_py import create_client, create_account, studionet
from genlayer_py.types.transactions import TransactionStatus

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')

def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',', ':'),ensure_ascii=False)

def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()

def atomic(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2,default=str)+'\n');temp.replace(path)

def account(name='DEPLOYER_PRIVATE_KEY'):
    return create_account(os.environ[name])

def client(name='DEPLOYER_PRIVATE_KEY'):
    return create_client(chain=studionet,account=account(name))

def receipt_summary(receipt):
    consensus=receipt.get('consensus_data',{})
    leaders=consensus.get('leader_receipt',[])
    if not isinstance(leaders,list):leaders=[leaders]
    # Whitelist verification evidence and exclude provider configurations or raw signed transaction material.
    return {'hash':receipt.get('hash'),'status':receipt.get('status_name',receipt.get('status')),'result':receipt.get('result_name',receipt.get('result')),'contract_address':receipt.get('data',{}).get('contract_address'),'triggered_transactions':receipt.get('triggered_transactions',[]),'votes':consensus.get('votes',{}),'validators':[{'address':v.get('node_config',{}).get('address'),'vote':v.get('vote'),'execution_result':v.get('execution_result'),'processing_time':v.get('processing_time'),'execution_stats':v.get('execution_stats'),'stderr':v.get('genvm_result',{}).get('stderr','')[:3000]} for v in consensus.get('validators',[])], 'leaders':[{'execution_result':l.get('execution_result'),'result':l.get('result'),'processing_time':l.get('processing_time'),'execution_stats':l.get('execution_stats'),'stderr':l.get('genvm_result',{}).get('stderr','')[:5000],'stdout':l.get('genvm_result',{}).get('stdout','')[:3000]} for l in leaders]}

def succeeded(receipt):
    consensus=receipt.get('consensus_data',{});leaders=consensus.get('leader_receipt',[])
    if not isinstance(leaders,list):leaders=[leaders]
    leaders = [x for x in leaders if 'execution cancelled after quorum' not in json.dumps(x).lower() and 'execution canceled after quorum' not in json.dumps(x).lower()]
    return receipt.get('result_name') == 'MAJORITY_AGREE' and bool(leaders) and leaders[-1].get('execution_result') == 'SUCCESS'

class Journal:
    def __init__(self,path):
        self.path=ROOT/path;self.path.parent.mkdir(parents=True,exist_ok=True)
        self.operations=json.loads(self.path.read_text()) if self.path.exists() else {}
    def perform(self,operation_id,callback,signer='DEPLOYER_PRIVATE_KEY',binding=None):
        c=client(signer);entry=self.operations.get(operation_id)
        if entry and binding is not None and entry.get('binding') != binding:
            if entry.get('binding') is None and all(entry.get(k) == v for k, v in binding.items()):
                entry['binding'] = binding; atomic(self.path, self.operations)
            else:
                raise RuntimeError('Journal payload changed: ' + operation_id)
        if entry and entry.get('success'):
            return entry
        if entry and entry.get('status') == 'finalized' and not entry.get('success'):
            failures = sum(key.startswith(operation_id + '.failed.') for key in self.operations)
            if failures >= 2:
                raise RuntimeError('Three deployment attempts reached for ' + operation_id)
            self.operations[operation_id + '.failed.' + str(failures + 1)] = entry
            entry = None
        if not entry:
            started=time.monotonic();tx=callback(c)
            entry={'transaction_hash':str(tx),'signer':c.local_account.address,'status':'broadcast','binding':binding,'started_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'broadcast_seconds':round(time.monotonic()-started,3)}
            self.operations[operation_id]=entry;atomic(self.path,self.operations)
            print(operation_id,'broadcast',entry['transaction_hash'],flush=True)
        try:
            receipt=c.wait_for_transaction_receipt(entry['transaction_hash'],status=TransactionStatus.FINALIZED,retries=30,interval=15000,full_transaction=True)
        except Exception:
            observed=c.get_transaction(entry['transaction_hash'])
            entry['observed_receipt']=receipt_summary(observed)
            atomic(self.path,self.operations)
            if str(observed.get('status_name', observed.get('status'))).upper() == 'FINALIZED' and observed.get('consensus_data', {}).get('leader_receipt'):
                receipt = observed
            else:
                raise RuntimeError('Still awaiting finalization: ' + operation_id + ' ' + entry['transaction_hash']) from None
        entry.update(receipt=receipt_summary(receipt),success=succeeded(receipt),status='finalized')
        atomic(self.path,self.operations)
        print(operation_id,'finalized','success' if entry['success'] else 'EXECUTION FAILED',flush=True)
        if not entry['success']:
            print(json.dumps(entry['receipt']['leaders'],indent=2)[:8000],flush=True)
            raise RuntimeError('Execution failed: '+operation_id)
        return entry
