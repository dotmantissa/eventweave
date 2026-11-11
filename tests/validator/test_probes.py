import copy
import pytest
from conftest import ATTRS,encode

@pytest.fixture
def assessed(system,event_factory,request_factory):
    event_factory('a');event_factory('b');r=request_factory('a','b');c=system.chain;answer=c.semantic(system.court,r['envelope']['request_id']);c.call(system.court,'assess',r['envelope']['request_id']);return system,r,answer

def probe(system,proposal=None):
    c=system.chain;vm=c.vms[system.court];c.context(vm,system.court,'0x'+'11'*20)
    return vm.run_validator(**({'leader_result':proposal} if proposal is not None else {}))

@pytest.mark.synthetic
def test_independent_validator_accepts_grounded_vector(assessed):
    system,_,_=assessed;assert probe(system)

@pytest.mark.synthetic
@pytest.mark.parametrize('attack',['wrong_verdict','omitted_exception','forged_span','changed_source','independent_evidence_gap'])
def test_validator_refuses_materially_wrong_proposal(assessed,attack):
    system,r,answer=assessed;vm=system.chain.vms[system.court];proposal=copy.deepcopy(vm._captured_validators[-1][0])
    if attack=='wrong_verdict':proposal['decision']='DISTINCT';proposal['vector']['interval']='DISTINCT'
    if attack=='omitted_exception':
        vm._llm_mocks.clear();answer['exception']='CONTRARY_FACT';vm.mock_llm('.*',encode(answer))
    if attack=='forged_span':proposal['witnesses']['issuer']=['invented.span','another.invention']
    if attack=='changed_source':
        vm._web_mocks.clear();vm.mock_web('.*',{'body':'Changed public bytes'})
    if attack=='independent_evidence_gap':
        # A valid JSON proposal demands SAME while the independent participant derives an evidence gap.
        vm._llm_mocks.clear();answer['vector']={a:'UNKNOWN' for a in ATTRS};answer['exception']='EVIDENCE_GAP';vm.mock_llm('.*',encode(answer))
    assert not probe(system,proposal)

@pytest.mark.synthetic
def test_malformed_model_fails_validation(assessed):
    system,_,_=assessed;vm=system.chain.vms[system.court];vm._llm_mocks.clear();vm.mock_llm('.*','{"decision":"SAME"}');assert not probe(system)

@pytest.mark.synthetic
def test_error_paths_do_not_ratify_model_failures(assessed):
    system,_,_=assessed;vm=system.chain.vms[system.court];system.chain.context(vm,system.court,'0x'+'11'*20)
    assert not vm.run_validator(leader_error=Exception('[LLM_ERROR] fabricated outcome'))
