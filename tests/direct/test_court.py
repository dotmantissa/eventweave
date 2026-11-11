import pytest
from conftest import encode,ATTRS,STRANGER

@pytest.mark.synthetic
def test_request_lock_and_finalized_boundary(system,event_factory,request_factory):
    event_factory('a');event_factory('b');request=request_factory('a','b');c=system.chain
    assert c.call(system.court,'compare_records',encode(request))==request['envelope']['request_id']
    with pytest.raises(Exception,match='Conflicting request ID'):c.call(system.court,'compare_records',encode({**request,'left':'b','right':'a'}))
    with pytest.raises(Exception,match='Only request owner'):c.call(system.court,'assess',request['envelope']['request_id'],sender=STRANGER)
    c.semantic(system.court,request['envelope']['request_id']);c.call(system.court,'assess',request['envelope']['request_id'])
    assert c.call(system.court,'get_result',request['envelope']['request_id'])['status']=='accepted'
    assert c.call(system.directory,'get_acknowledgement',request['envelope']['request_id'])=={}
    c.finalize();assert c.call(system.directory,'get_acknowledgement',request['envelope']['request_id'])['status']=='finalized'

@pytest.mark.synthetic
@pytest.mark.parametrize('exception',['EVIDENCE_GAP','CONTRARY_FACT'])
def test_unresolved_exception(system,event_factory,request_factory,exception):
    event_factory('a');event_factory('b');r=request_factory('a','b');c=system.chain
    c.semantic(system.court,r['envelope']['request_id'],exception=exception);c.call(system.court,'assess',r['envelope']['request_id']);assert c.call(system.court,'get_result',r['envelope']['request_id'])['decision']=='UNKNOWN'

@pytest.mark.synthetic
def test_deadline_and_retries(system,event_factory,request_factory):
    event_factory('a');event_factory('b');r=request_factory('a','b');c=system.chain;key=r['envelope']['request_id']
    c.semantic(system.court,key,vector={a:'UNKNOWN' for a in ATTRS})
    c.call(system.court,'assess',key);c.call(system.court,'assess',key)
    successor=request_factory('a','b',generation=2)
    assert c.call(system.court,'get_generation',r['envelope']['subject_id'],system.incident)==1
    with pytest.raises(Exception,match='pending'):request_factory('a','b',generation=2,request_id='parallel')
    c.call(system.court,'cancel_request',successor['envelope']['request_id'])
    replacement=request_factory('a','b',generation=2,request_id='replacement')
    c.vms[system.court]._datetime='2026-11-13T10:00:00Z';c.call(system.court,'assess','replacement');assert c.call(system.court,'get_result','replacement')['status']=='timeout'

@pytest.mark.synthetic
def test_expired_assessment_and_committed_source_outage_are_unresolved(system,event_factory,request_factory):
    event_factory('a');event_factory('b');c=system.chain
    r=request_factory('a','b');c.vms[system.court]._datetime='2026-11-13T10:00:00Z'
    c.call(system.court,'assess',r['envelope']['request_id']);c.finalize()
    result=c.call(system.directory,'get_relation',r['envelope']['request_id']);assert result['status']=='timeout';assert result['decision']=='UNKNOWN';assert not result['coverage']

@pytest.mark.synthetic
def test_full_packet_budget_is_rejected_before_model_work(system,event_factory,request_factory):
    event_factory('a',body=b'a'*49152);event_factory('b',body=b'b'*49152)
    with pytest.raises(Exception,match='Complete packet exceeds context budget'):request_factory('a','b')
    assert not system.chain.vms[system.court]._captured_validators

@pytest.mark.synthetic
def test_unavailable_source_never_establishes_a_fact(system,event_factory,request_factory):
    event_factory('a');event_factory('b');r=request_factory('a','b');c=system.chain
    c.vms[system.court]._web_mocks.clear()
    c.call(system.court,'assess',r['envelope']['request_id']);c.finalize()
    result=c.call(system.directory,'get_relation',r['envelope']['request_id'])
    assert result['decision']=='UNKNOWN';assert result['controlling_rules']==['SOURCE_UNAVAILABLE'];assert result['unresolved'];assert not result['coverage']
