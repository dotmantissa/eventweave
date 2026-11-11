"""Controlled direct mode harness. Production code never imports test fixtures."""
import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest
from gltest.direct.vm import VMContext
from gltest.direct.loader import load_contract_class, _allocate_contract, _make_contract_proxy, _patch_run_nondet_for_direct_mode
from gltest.direct import wasi_mock

ROOT = Path(__file__).resolve().parents[1]
ATTRS = ('issuer', 'place', 'interval', 'occurrence_type', 'official_reference')
OWNER = '0x' + '11' * 20
INCIDENT_OWNER = '0x' + '22' * 20
RELEASE_OWNER = '0x' + '33' * 20
STRANGER = '0x' + '44' * 20

def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',', ':'),ensure_ascii=False)

def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()

class ControlledChain:
    def __init__(self, monkeypatch):
        self.contracts = {}; self.vms = {}; self.messages = []; self.receipts = []
        self.monkeypatch = monkeypatch

    def context(self, vm, address, sender):
        import genlayer as glmodule
        gl = glmodule.gl
        gl.message = gl.MessageType(contract_address=glmodule.Address(address),sender_address=glmodule.Address(sender),origin_address=glmodule.Address(sender),value=glmodule.u256(0),chain_id=glmodule.u256(61999))
        gl.message_raw.update(contract_address=glmodule.Address(address),sender_address=glmodule.Address(sender),origin_address=glmodule.Address(sender),datetime=vm._datetime)
        wasi_mock.set_vm(vm)
        return gl

    def deploy(self, filename, sender=OWNER, args=()):
        address = '0x' + hashlib.sha256(filename.encode()).hexdigest()[:40]
        vm = VMContext(); vm._sender = bytes.fromhex(sender[2:]); vm._contract_address = bytes.fromhex(address[2:]); vm._datetime='2026-11-11T10:00:00Z'
        try:
            import genlayer.gl.genvm_contracts as runtime
            runtime.__known_contract__ = None
        except ImportError:
            pass
        klass = load_contract_class(ROOT / 'contracts/deployable' / filename, vm)
        _patch_run_nondet_for_direct_mode()
        gl = self.context(vm,address,sender)
        self.monkeypatch.setattr(gl,'get_contract_at',self.proxy)
        instance = _make_contract_proxy(_allocate_contract(klass,vm,*args))
        self.contracts[address] = instance; self.vms[address] = vm
        return address

    def call(self, address, method, *args, sender=None):
        if sender is None:
            sender = OWNER
            if method in ('assess', 'supersede_relation', 'cancel_request') and args:
                request_id = args[0]
                sender = json.loads(self.contracts[address].requests[request_id])['envelope']['owner']
            if method == 'compare_records' and args:
                sender = json.loads(args[0])['envelope']['owner']
            if method == 'propose_merge' and args:
                proof = json.loads(args[0]); relation = proof['relations'][0] if proof.get('relations') else ''
                if relation:
                    sender = json.loads(self.contracts[address].certificates[relation])['owner']
        import genlayer as glmodule
        gl = glmodule.gl; saved_message = gl.message; saved_raw = dict(gl.message_raw); saved_vm=wasi_mock.get_vm()
        vm=self.vms[address]; snapshot=vm._storage.snapshot(); messages=len(self.messages)
        self.context(vm,address,sender)
        try:
            return getattr(self.contracts[address],method)(*args)
        except Exception:
            vm._storage.restore(snapshot); self.messages=self.messages[:messages]
            raise
        finally:
            gl.message=saved_message;gl.message_raw.clear();gl.message_raw.update(saved_raw);wasi_mock.set_vm(saved_vm)

    def proxy(self, address):
        import genlayer as glmodule
        chain=self; target=str(address).lower()
        class Namespace:
            def __init__(self, write=False): self.write=write
            def __getattr__(self, method):
                def run(*args):
                    sender=str(glmodule.gl.message.contract_address).lower()
                    if self.write:
                        chain.messages.append((sender,target,method,args)); return None
                    return chain.call(target,method,*args,sender=sender)
                return run
        return SimpleNamespace(view=lambda **kw:Namespace(),emit=lambda **kw:Namespace(True))

    def finalize(self):
        while self.messages:
            sender,target,method,args=self.messages.pop(0)
            try:
                result=self.call(target,method,*args,sender=sender);self.receipts.append((method,'success',result))
            except Exception as error:
                self.receipts.append((method,'error',str(error)));raise

    def semantic(self, court, request_id, vector=None, exception='NONE', authority=True):
        request=json.loads(self.contracts[court].requests[request_id]);vector=vector or {a:'SAME' for a in ATTRS}
        witnesses={a:sorted(span['span_id'] for record in request['records'] for span in record['source']['spans'] if span['attribute']==a) for a in ATTRS}
        answer={'vector':vector,'authority_supported':authority,'exceptions_checked':True,'common_cause':'UNKNOWN','witnesses':witnesses,'facts':{a:'Controlled source supports this discriminator.' for a in ATTRS},'exception':exception,'certified_types':{r['event_id']:r['occurrence_type'] for r in request['records']}}
        self.vms[court].mock_llm('.*',encode(answer)); return answer

@pytest.fixture
def chain(direct_vm,monkeypatch):
    return ControlledChain(monkeypatch)

@pytest.fixture
def system(chain):
    registry=chain.deploy('event_registry.py');court=chain.deploy('identity_court.py',args=(registry,));directory=chain.deploy('consumer_directory.py',args=(court,registry));chain.call(court,'bind_directory',directory)
    policy={'schema_id':'occurrence.v1','revision':1,'mandatory':list(ATTRS),'scope':'public.occurrence','rules':['Every mandatory discriminator must be supported.','Separate intervals or references distinguish recurring occurrences.']}
    chain.call(registry,'register_schema',encode(policy))
    incident=chain.deploy('incident_history.py',sender=INCIDENT_OWNER,args=(directory,registry,'occurrence.v1',1,100))
    release=chain.deploy('release_evidence.py',sender=RELEASE_OWNER,args=(directory,registry,'occurrence.v1',1,100))
    authority_body=b'Controlled fixture: Example principal publishes official operational notices.'
    authority={'authority_id':'example','principal':OWNER,'channel':'official','url_prefix':'https://example.org/','evidence_url':'https://example.org/authority','evidence_hash':hashlib.sha256(authority_body).hexdigest(),'evidence_bytes':len(authority_body),'scope':'public.occurrence','revision':1}
    chain.call(registry,'register_authority',encode(authority));chain.vms[court].mock_web('https://example.org/authority',{'body':authority_body})
    return SimpleNamespace(chain=chain,registry=registry,court=court,directory=directory,incident=incident,release=release,policy=policy,authority=authority)

@pytest.fixture
def event_factory(system):
    def event(event_id,title='Amended incident notice',interval='2026-11-10T12:00:00Z',reference='INC123',body=None):
        body=body or f'Official operational notice {reference}. Example service incident on {interval}. Title: {title}.'.encode()
        raw_hash=hashlib.sha256(body).hexdigest();source={'record_id':event_id,'authority_id':'example:1','channel':'official','url':'https://example.org/'+event_id,'raw_hash':raw_hash,'revision':'1','scope':'public.occurrence','byte_length':len(body),'spans':[{'span_id':event_id+'.'+a,'attribute':a,'start':0,'end':len(body),'raw_hash':raw_hash} for a in ATTRS]}
        record={'event_id':event_id,'schema_id':'occurrence.v1','schema_revision':1,'title':title,'issuer':'Example','place':'Example service','interval_start':interval,'interval_end':interval,'occurrence_type':'operational_notice','official_reference':reference,'source':source}
        system.chain.call(system.registry,'open_event',encode(record));system.chain.vms[system.court].mock_web('https://example.org/'+event_id,{'body':body});return record
    return event

@pytest.fixture
def request_factory(system):
    def make(left,right,consumer=None,generation=1,request_id=None):
        consumer=consumer or system.incident;c=system.chain
        records=sorted([c.call(system.registry,'get_identity',left),c.call(system.registry,'get_identity',right)],key=lambda r:r['event_id'])
        scope='scope:'+digest({'scope':system.policy['scope'],'policy_id':'occurrence.v1','policy_revision':1});subject='pair:'+digest({'scope':scope,'records':sorted((left,right))})
        cfg=c.call(consumer,'get_configuration');request_id=request_id or f'r.{left}.{right}.{generation}.{consumer[-6:]}'
        env={'request_id':request_id,'owner':cfg['owner'],'parties':[cfg['owner']],'policy_id':'occurrence.v1','policy_revision':1,'subject_id':subject,'subject_digest':digest([{'event_id':r['event_id'],'descriptor_digest':r['descriptor_digest']} for r in records]),'source_manifest_digest':digest([r['source'] for r in records]),'consumer_address':consumer,'consequence_digest':cfg['consequence_digest'],'generation':generation,'deadline':'2026-11-12T10:00:00Z'}
        request={'envelope':env,'left':left,'right':right};c.call(system.court,'compare_records',encode(request),sender=cfg['owner']);return request
    return make
