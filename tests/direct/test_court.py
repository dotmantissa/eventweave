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
    successor=request_factory('a','b',generation=2);third=request_factory('a','b',generation=3)
    with pytest.raises(Exception,match='Three requests'):request_factory('a','b',generation=4)
    successor=third;c.vms[system.court]._datetime='2026-11-13T10:00:00Z';c.call(system.court,'assess',successor['envelope']['request_id']);assert c.call(system.court,'get_result',successor['envelope']['request_id'])['status']=='timeout'
