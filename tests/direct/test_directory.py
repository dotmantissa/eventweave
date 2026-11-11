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
    with pytest.raises(Exception,match='Unknown merge proposal'):system.chain.call(system.directory,'finalize_alias',proof['operation_id'])
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

@pytest.mark.synthetic
def test_correction_retires_all_consumers_in_the_cluster(system,event_factory,request_factory):
    from conftest import INCIDENT_OWNER, RELEASE_OWNER
    event_factory('a');event_factory('b');c=system.chain
    for consumer,owner in [(system.incident,INCIDENT_OWNER),(system.release,RELEASE_OWNER)]:
        for id in ['a','b']:c.call(consumer,'register_reference',id,'ref.'+id,sender=owner)
    incident=certify(system,request_factory,'a','b',consumer=system.incident)
    proof,_=merge(system,[incident],'a','b');c.call(system.directory,'finalize_alias',proof['operation_id']);c.call(system.directory,'publish_alias',incident['envelope']['request_id']);c.finalize()
    release=certify(system,request_factory,'a','b',consumer=system.release,generation=1)
    c.call(system.directory,'publish_alias',release['envelope']['request_id']);c.finalize()
    correction=certify(system,request_factory,'a','b','DISTINCT',generation=2,consumer=system.incident)
    c.finalize()
    assert c.call(system.incident,'get_stats')['accepted_count']==0
    assert c.call(system.release,'get_stats')['accepted_count']==0
    assert c.call(system.release,'get_reference','ref.a')['original_owner']==RELEASE_OWNER

@pytest.mark.synthetic
def test_complete_six_record_limit_and_larger_cluster_remains_unresolved(system,event_factory,request_factory):
    from itertools import combinations
    for id in 'abcdefg':event_factory(id)
    relations=[certify(system,request_factory,a,b) for a,b in combinations('abcdef',2)]
    for size in range(2,7):
        selected=[r for r in relations if r['left'] in 'abcdef'[:size] and r['right'] in 'abcdef'[:size]]
        proof,result=merge(system,selected,'a','abcdef'[size-1],'complete.'+str(size))
        assert result['status']=='pending';system.chain.call(system.directory,'finalize_alias',proof['operation_id'])
    assert len(proof['relations'])==15
    assert len(system.chain.call(system.directory,'get_identity','a',proof['scope'])['members'])==6
    ag=certify(system,request_factory,'a','g')
    _,result=merge(system,[ag],'a','g','too.large');assert result['status']=='unresolved';assert len(result['members'])==7

@pytest.mark.synthetic
def test_old_same_edges_cannot_restore_a_corrected_cluster(system,event_factory,request_factory):
    from itertools import combinations
    for id in 'abc':event_factory(id)
    relations=[certify(system,request_factory,a,b) for a,b in combinations('abc',2)]
    ab=next(r for r in relations if r['left']=='a' and r['right']=='b')
    proof,_=merge(system,[ab],'a','b','original.ab');c=system.chain;c.call(system.directory,'finalize_alias',proof['operation_id'])
    proof,_=merge(system,relations,'a','c','original.abc');c.call(system.directory,'finalize_alias',proof['operation_id'])
    correction=certify(system,request_factory,'a','b','DISTINCT',generation=2)
    with pytest.raises(Exception,match='complete current partition proof'):
        c.call(system.directory,'recover_component',proof['scope'],'a',correction['envelope']['request_id'])
    ac=certify(system,request_factory,'a','c','DISTINCT',generation=2)
    bc=certify(system,request_factory,'b','c','DISTINCT',generation=2)
    c.call(system.directory,'recover_component',proof['scope'],'a',correction['envelope']['request_id'],encode([ac['envelope']['request_id'],bc['envelope']['request_id']]))
    ac=next(r for r in relations if r['left']=='a' and r['right']=='c')
    _,result=merge(system,[ac],'a','c','obsolete.ac');assert result['status']=='refused'
    c.call(system.directory,'retry_invalidation',ac['envelope']['request_id']);c.finalize()
    assert c.call(system.directory,'get_identity','a',proof['scope'])['members']==['a']
