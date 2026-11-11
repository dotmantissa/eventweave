import pytest
from conftest import INCIDENT_OWNER,RELEASE_OWNER,STRANGER,encode
from test_directory import certify,merge

@pytest.mark.synthetic
@pytest.mark.parametrize('consumer_name,owner',[('incident',INCIDENT_OWNER),('release',RELEASE_OWNER)])
def test_renames_count_once_and_duplicate_delivery(system,event_factory,request_factory,consumer_name,owner):
    event_factory('a');event_factory('b',title='Service disruption renamed');consumer=getattr(system,consumer_name);c=system.chain
    for id in ['a','b']:c.call(consumer,'register_reference',id,'ref.'+id,sender=owner)
    assert c.call(consumer,'get_stats')['accepted_count']==0
    with pytest.raises(Exception,match='Only consumer owner'):c.call(consumer,'register_reference','a','bad',sender=STRANGER)
    with pytest.raises(Exception,match='Only authenticated'):c.call(consumer,'apply_identity','{}',sender=owner)
    r=certify(system,request_factory,'a','b',consumer=consumer);proof,_=merge(system,[r],'a','b');c.call(system.directory,'finalize_alias',proof['operation_id']);c.call(system.directory,'publish_alias',r['envelope']['request_id']);assert c.call(consumer,'get_stats')['accepted_count']==0;c.finalize();assert c.call(consumer,'get_stats')['accepted_count']==1
    c.call(system.directory,'publish_alias',r['envelope']['request_id']);c.finalize();assert c.call(consumer,'get_stats')['accepted_count']==1;assert c.call(consumer,'get_reference','ref.b')['original_owner']==owner
    ack=c.call(consumer,'get_acknowledgement','delivery:'+r['envelope']['request_id']);assert ack['generation']==1

@pytest.mark.synthetic
def test_recurring_incidents_count_separately_and_correction(system,event_factory,request_factory):
    event_factory('a');event_factory('b');c=system.chain;consumer=system.incident
    for id in ['a','b']:c.call(consumer,'register_reference',id,'ref.'+id,sender=INCIDENT_OWNER)
    r=certify(system,request_factory,'a','b');proof,_=merge(system,[r],'a','b');c.call(system.directory,'finalize_alias',proof['operation_id']);c.call(system.directory,'publish_alias',r['envelope']['request_id']);c.finalize();assert c.call(consumer,'get_stats')['accepted_count']==1
    correction=certify(system,request_factory,'a','b','DISTINCT',generation=2);c.call(system.court,'supersede_relation',r['envelope']['request_id'],correction['envelope']['request_id'],'Official references identify two distinct incidents.');c.finalize();assert c.call(consumer,'get_stats')['accepted_count']==0
    scope=c.call(system.court,'get_result',r['envelope']['request_id'])['scope'];c.call(system.directory,'recover_component',scope,'a',correction['envelope']['request_id']);c.call(system.directory,'publish_alias',correction['envelope']['request_id']);c.finalize();assert c.call(consumer,'get_stats')['accepted_count']==2
    assert c.call(consumer,'get_reference','ref.a')['original_owner']==INCIDENT_OWNER

@pytest.mark.synthetic
def test_holds_and_unknown_remain_reserved(system,event_factory,request_factory):
    event_factory('a');event_factory('b');c=system.chain;c.call(system.incident,'register_reference','a','ref.a',sender=INCIDENT_OWNER)
    with pytest.raises(Exception,match='Only reservation owner'):c.call(system.incident,'release_hold','ref.a',sender=STRANGER)
    c.call(system.incident,'release_hold','ref.a',sender=INCIDENT_OWNER);c.call(system.incident,'release_hold','ref.a',sender=INCIDENT_OWNER);assert c.call(system.incident,'get_stats')['held_count']==0
    c.call(system.incident,'register_reference','a','ref.a2',sender=INCIDENT_OWNER);r=certify(system,request_factory,'a','b','UNKNOWN');c.call(system.directory,'publish_alias',r['envelope']['request_id']);c.finalize();assert c.call(system.incident,'get_reference','ref.a2')['status']=='unresolved';assert c.call(system.incident,'get_stats')['accepted_count']==0
