import pytest
from conftest import encode,ATTRS,STRANGER

def certify(system,request_factory,left,right,decision='SAME',generation=1,consumer=None):
    r=request_factory(left,right,generation=generation,consumer=consumer);c=system.chain;vector={a:'SAME' for a in ATTRS}
    if decision=='DISTINCT':vector['interval']='DISTINCT';vector['official_reference']='DISTINCT'
    if decision=='UNKNOWN':vector['official_reference']='UNKNOWN'
    c.semantic(system.court,r['envelope']['request_id'],vector=vector);c.call(system.court,'assess',r['envelope']['request_id']);c.vms[system.court]._llm_mocks.clear();c.finalize();return r

def merge(system,relations,left,right,operation_id='merge.ab'):
    proof={'operation_id':operation_id,'left':left,'right':right,'scope':relations[0]['envelope']['subject_id'],'relations':[r['envelope']['request_id'] for r in relations]}
    proof['scope']=system.chain.call(system.court,'get_result',relations[0]['envelope']['request_id'])['scope']
    result=system.chain.call(system.directory,'propose_merge',encode(proof));return proof,result

@pytest.mark.synthetic
def test_complete_proof_and_non_merge_witness(system,event_factory,request_factory):
    for id in ['a','b','c']:event_factory(id)
    ab=certify(system,request_factory,'a','b');proof,result=merge(system,[ab],'a','b');assert result['status']=='pending';system.chain.call(system.directory,'finalize_alias',proof['operation_id'])
    bc=certify(system,request_factory,'b','c');ac=certify(system,request_factory,'a','c','DISTINCT')
    proof,result=merge(system,[ab,bc,ac],'a','c','merge.abc');assert result['status']=='refused';assert result['witness']==ac['envelope']['request_id']
    with pytest.raises(Exception,match='Complete compatible'):system.chain.call(system.directory,'finalize_alias',proof['operation_id'])
    assert system.chain.call(system.directory,'get_alias_history',0,50)[0]['event_id']=='a'

@pytest.mark.synthetic
def test_favorable_pair_does_not_prove_cluster(system,event_factory,request_factory):
    for id in ['a','b','c']:event_factory(id)
    ab=certify(system,request_factory,'a','b');proof,_=merge(system,[ab],'a','b');system.chain.call(system.directory,'finalize_alias',proof['operation_id']);bc=certify(system,request_factory,'b','c')
    _,result=merge(system,[ab,bc],'b','c','incomplete');assert result['status']=='unresolved'
    with pytest.raises(Exception,match='Only finalized court'):system.chain.call(system.directory,'receive_certificate','{}',sender=STRANGER)

@pytest.mark.synthetic
def test_supersession_preserves_history_and_recovery(system,event_factory,request_factory):
    event_factory('a');event_factory('b');ab=certify(system,request_factory,'a','b');proof,_=merge(system,[ab],'a','b');c=system.chain;c.call(system.directory,'finalize_alias',proof['operation_id'])
    correction=certify(system,request_factory,'a','b','DISTINCT',generation=2)
    scope=c.call(system.court,'get_result',ab['envelope']['request_id'])['scope'];assert c.call(system.directory,'get_identity','a',scope)['status']=='quarantined'
    c.call(system.court,'supersede_relation',ab['envelope']['request_id'],correction['envelope']['request_id'],'Recurring incident reference was omitted.');c.finalize()
    assert c.call(system.court,'get_result',ab['envelope']['request_id'])['superseded_by']==correction['envelope']['request_id']
    with pytest.raises(Exception,match='stale|quarantined'):c.call(system.directory,'publish_alias',ab['envelope']['request_id'])
    c.call(system.directory,'recover_component',scope,'a',correction['envelope']['request_id']);assert c.call(system.directory,'get_identity','a',scope)['members']==['a'];assert len(c.call(system.directory,'get_alias_history',0,50))>=4
