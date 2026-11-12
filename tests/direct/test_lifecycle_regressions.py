import copy
import pytest
from conftest import ATTRS, INCIDENT_OWNER, RELEASE_OWNER, STRANGER, encode
from test_directory import certify, merge

pytestmark = pytest.mark.synthetic


def reserve(s, ids, consumer=None, owner=INCIDENT_OWNER):
    for r in ids:
        s.chain.call(consumer or s.incident, 'register_reference', r, 'ref.' + r, sender=owner)


def publish(s, relation):
    s.chain.call(s.directory, 'publish_alias', relation['envelope']['request_id']); s.chain.finalize()


def finalize_merge(s, relations, left, right, operation):
    proof, result = merge(s, relations, left, right, operation)
    assert result['status'] == 'pending'
    s.chain.call(s.directory, 'finalize_alias', operation)
    return proof['scope']


def test_outsider_cannot_spend_allowance_or_stale_a_settled_certificate(system, event_factory, request_factory):
    s = system; c = s.chain
    event_factory('a'); event_factory('b')
    first = certify(s, request_factory, 'a', 'b')
    opened = request_factory('a', 'b', generation=2)
    assert c.call(s.directory, 'is_current', first['envelope']['request_id'])
    outsider = copy.deepcopy(opened); outsider['envelope'].update(owner=STRANGER, parties=[STRANGER], request_id='outsider')
    for _ in range(4):
        with pytest.raises(Exception, match='Only consumer owner'):
            c.call(s.court, 'compare_records', encode(outsider), sender=STRANGER)
    assert c.call(s.court, 'get_generation', first['envelope']['subject_id'], s.incident) == 1
    c.call(s.court, 'cancel_request', opened['envelope']['request_id'])
    release = certify(s, request_factory, 'a', 'b', consumer=s.release)
    assert c.call(s.directory, 'is_current', first['envelope']['request_id'])
    assert c.call(s.directory, 'is_current', release['envelope']['request_id'])


def test_cluster_expansion_reconciles_every_reference_and_new_reservations(system, event_factory, request_factory):
    s = system; c = s.chain
    for r in 'abc': event_factory(r)
    reserve(s, 'abc')
    bc = certify(s, request_factory, 'b', 'c')
    finalize_merge(s, [bc], 'b', 'c', 'merge.bc'); publish(s, bc)
    ab = certify(s, request_factory, 'a', 'b'); ac = certify(s, request_factory, 'a', 'c')
    finalize_merge(s, [ab, bc, ac], 'a', 'b', 'merge.abc'); publish(s, ab)
    assert [c.call(s.incident, 'get_reference', 'ref.'+r)['canonical_id'] for r in 'abc'] == ['a']*3
    assert c.call(s.incident, 'get_stats')['accepted_count'] == 1
    publish(s, bc)
    c.call(s.incident, 'register_reference', 'c', 'later.c', sender=INCIDENT_OWNER)
    publish(s, bc)
    assert c.call(s.incident, 'get_reference', 'later.c')['status'] == 'finalized'
    assert c.call(s.incident, 'get_stats')['accepted_count'] == 1


def test_publication_revalidates_every_supporting_certificate(system, event_factory, request_factory):
    s = system; c = s.chain
    for r in 'abc': event_factory(r)
    relations = [certify(s, request_factory, a, b) for a, b in [('a','b'), ('a','c'), ('b','c')]]
    scope = finalize_merge(s, [relations[0]], 'a', 'b', 'ab')
    finalize_merge(s, relations, 'a', 'c', 'abc')
    certify(s, request_factory, 'b', 'c', 'UNKNOWN', generation=2)
    with pytest.raises(Exception, match='complete finalized|stale|proof'):
        c.call(s.directory, 'publish_alias', relations[0]['envelope']['request_id'])
    assert c.call(s.directory, 'get_identity', 'a', scope)['status'] == 'unresolved'


def test_unknown_cannot_hide_consumed_same_from_distinct_invalidation(system, event_factory, request_factory):
    s = system; c = s.chain
    event_factory('a'); event_factory('b'); reserve(s, 'ab')
    ab = certify(s, request_factory, 'a', 'b'); scope = finalize_merge(s, [ab], 'a', 'b', 'ab'); publish(s, ab)
    certify(s, request_factory, 'a', 'b', 'UNKNOWN', generation=2)
    correction = certify(s, request_factory, 'a', 'b', 'DISTINCT', generation=3)
    assert c.call(s.incident, 'get_stats')['accepted_count'] == 0
    c.call(s.directory, 'recover_component', scope, 'a', correction['envelope']['request_id']); c.finalize()
    assert c.call(s.incident, 'get_stats')['accepted_count'] == 2


def test_delayed_invalidation_matches_the_reference_authorization(system, event_factory, request_factory):
    s = system; c = s.chain
    for r in 'abc': event_factory(r)
    reserve(s, 'abc')
    ab = certify(s, request_factory, 'a', 'b', 'DISTINCT'); publish(s, ab)
    old = c.call(s.incident, 'get_reference', 'ref.a')['authorization_id']
    ac = certify(s, request_factory, 'a', 'c', 'DISTINCT'); publish(s, ac)
    newer = c.call(s.incident, 'get_reference', 'ref.a')['authorization_id']; assert old != newer
    c.call(s.court, 'quarantine_request', ab['envelope']['request_id'], 'Retire old evidence')
    c.finalize()
    assert c.call(s.incident, 'get_reference', 'ref.a')['authorization_id'] == newer
    assert c.call(s.incident, 'get_reference', 'ref.a')['status'] == 'finalized'
    assert c.call(s.incident, 'get_reference', 'ref.b')['status'] == 'superseded'


def test_unrelated_recovery_and_unacknowledged_invalidation_are_rejected(system, event_factory, request_factory):
    s = system; c = s.chain
    for r in 'abc': event_factory(r)
    reserve(s, 'ab'); ab = certify(s, request_factory, 'a', 'b'); scope = finalize_merge(s, [ab], 'a', 'b', 'ab'); publish(s, ab)
    ac = certify(s, request_factory, 'a', 'c', 'DISTINCT')
    with pytest.raises(Exception, match='bound to the quarantined'):
        c.call(s.directory, 'recover_component', scope, 'a', ac['envelope']['request_id'])
    correction = request_factory('a', 'b', generation=2); key = correction['envelope']['request_id']
    c.semantic(s.court, key, vector={a:'DISTINCT' for a in ATTRS}); c.call(s.court, 'assess', key)
    sender, target, method, args = c.messages.pop(0); c.call(target, method, *args, sender=sender)
    with pytest.raises(Exception, match='Outstanding consumer invalidation'):
        c.call(s.directory, 'recover_component', scope, 'a', key)
    c.finalize(); c.call(s.directory, 'recover_component', scope, 'a', key); c.finalize()
    assert c.call(s.incident, 'get_stats')['accepted_count'] == 2


@pytest.mark.parametrize('ac_decision,expected_count', [('SAME', 2), ('DISTINCT', 3)])
def test_recovery_restores_all_three_records_and_consumers(system, event_factory, request_factory, ac_decision, expected_count):
    s = system; c = s.chain
    for r in 'abc': event_factory(r)
    reserve(s, 'abc'); reserve(s, 'abc', s.release, RELEASE_OWNER)
    ab, ac, bc = [certify(s, request_factory, a,b) for a,b in [('a','b'),('a','c'),('b','c')]]
    finalize_merge(s, [ab], 'a','b','ab'); scope = finalize_merge(s,[ab,ac,bc],'a','c','abc'); publish(s,ab)
    other = certify(s, request_factory, 'a','b', consumer=s.release); publish(s,other)
    correction = certify(s, request_factory, 'a','b','DISTINCT',generation=2)
    with pytest.raises(Exception, match='complete current partition proof'):
        c.call(s.directory,'recover_component',scope,'a',correction['envelope']['request_id'])
    assert c.call(s.incident,'get_stats')['accepted_count'] == 0
    updated_ac = certify(s, request_factory, 'a','c',ac_decision,generation=2)
    updated_bc = certify(s, request_factory, 'b','c','DISTINCT',generation=2)
    proof = encode([updated_ac['envelope']['request_id'], updated_bc['envelope']['request_id']])
    c.call(s.directory,'recover_component',scope,'a',correction['envelope']['request_id'],proof); c.finalize()
    for consumer in (s.incident,s.release):
        assert c.call(consumer,'get_stats')['accepted_count'] == expected_count
        assert [c.call(consumer,'get_reference','ref.'+r)['status'] for r in 'abc'] == ['finalized']*3
    c.call(s.court,'supersede_relation',ab['envelope']['request_id'],correction['envelope']['request_id'],'Complete correction of the pair'); c.finalize()
    assert c.call(s.directory,'get_identity','a',scope)['status'] == 'finalized'


def test_public_repetition_does_not_consume_journal_capacity(system, event_factory, request_factory):
    s = system; c = s.chain
    event_factory('a'); event_factory('b'); reserve(s,'ab')
    ab=certify(s,request_factory,'a','b'); finalize_merge(s,[ab],'a','b','ab'); publish(s,ab)
    count = len(c.contracts[s.directory].history)
    for _ in range(10): publish(s,ab)
    assert len(c.contracts[s.directory].history) == count
    for i in range(10):
        with pytest.raises(Exception,match='fifteen|owner'):
            c.call(s.directory,'propose_merge',encode({'operation_id':'spam.'+str(i),'left':'a','right':'b','scope':'s','relations':[]}),sender=STRANGER)
    # The audit log no longer shares a hard ceiling with essential state transitions.
    for i in range(10001): c.contracts[s.directory].history.append(encode({'operation':'controlled_history','index':i}))
    certify(s,request_factory,'a','b','DISTINCT',generation=2)
    assert c.call(s.incident,'get_stats')['accepted_count'] == 0


def test_unresolved_reservation_can_be_released(system,event_factory,request_factory):
    s=system; c=s.chain
    event_factory('a'); event_factory('b'); reserve(s,'a')
    unknown=certify(s,request_factory,'a','b','UNKNOWN'); publish(s,unknown)
    c.call(s.incident,'release_hold','ref.a',sender=INCIDENT_OWNER)
    assert c.call(s.incident,'get_stats')['held_count'] == 0


def test_false_distinct_can_be_corrected_to_same(system,event_factory,request_factory):
    s=system; c=s.chain
    event_factory('a'); event_factory('b'); reserve(s,'ab')
    old=certify(s,request_factory,'a','b','DISTINCT'); publish(s,old)
    current=certify(s,request_factory,'a','b',generation=2)
    c.call(s.court,'supersede_relation',old['envelope']['request_id'],current['envelope']['request_id'],'The complete evidence confirms an amendment of one occurrence.'); c.finalize()
    finalize_merge(s,[current],'a','b','corrected'); publish(s,current)
    assert c.call(s.incident,'get_stats')['accepted_count'] == 1


def test_consumer_policy_uses_certified_types_instead_of_claims(system,event_factory,request_factory):
    s=system; c=s.chain
    event_factory('a'); event_factory('b'); reserve(s,'ab')
    request=request_factory('a','b'); key=request['envelope']['request_id']
    answer=c.semantic(s.court,key); answer['certified_types']={r:'release' for r in 'ab'}
    c.vms[s.court]._llm_mocks.clear(); c.vms[s.court].mock_llm('.*',encode(answer))
    c.call(s.court,'assess',key); c.finalize(); finalize_merge(s,[request],'a','b','ab'); publish(s,request)
    assert c.call(s.incident,'get_stats')['accepted_count'] == 0
    assert c.call(s.incident,'get_reference','ref.a')['certified_type'] == 'release'
    assert c.call(s.release,'get_configuration')['accepted_types'] == ['release','operational_notice']


@pytest.mark.parametrize('url', ['https://example.org.attacker.com/a','https://example.org@attacker.com/a','https://example.org/../a','https://example.org/%2e%2e/a'])
def test_direct_sources_cannot_escape_host_or_path(system,event_factory,url):
    record=event_factory('a'); record['event_id']='b'; record['source']['record_id']='b'; record['source']['url']=url
    with pytest.raises(Exception,match='authority|Authority'):
        system.chain.call(system.registry,'open_event',encode(record))


def test_recovery_cannot_clear_a_different_court_quarantine(system,event_factory,request_factory):
    s=system; c=s.chain
    for r in 'abc': event_factory(r)
    ab,ac,bc=[certify(s,request_factory,a,b) for a,b in [('a','b'),('a','c'),('b','c')]]
    finalize_merge(s,[ab],'a','b','ab'); scope=finalize_merge(s,[ab,ac,bc],'a','c','abc')
    c.call(s.court,'quarantine_request',ab['envelope']['request_id'],'Court restricts the original pair'); c.finalize()
    other=certify(s,request_factory,'a','c','DISTINCT',generation=2)
    with pytest.raises(Exception,match='every quarantine cause'):
        c.call(s.directory,'recover_component',scope,'a',other['envelope']['request_id'])
    assert c.call(s.directory,'get_identity','a',scope)['status']=='quarantined'


def test_source_revision_correction_restores_certified_successor_references(system,event_factory,request_factory):
    import hashlib
    s=system; c=s.chain
    event_factory('a'); event_factory('b'); reserve(s,'ab')
    original=certify(s,request_factory,'a','b'); scope=finalize_merge(s,[original],'a','b','ab'); publish(s,original)
    record=c.call(s.registry,'get_identity','a'); source=copy.deepcopy(record['source']); body=b'Official corrected notice with different occurrence reference.'
    source.update(revision='2',raw_hash=hashlib.sha256(body).hexdigest(),byte_length=len(body))
    for span in source['spans']: span.update(raw_hash=source['raw_hash'],end=len(body))
    c.call(s.registry,'attest_source_revision','a',encode(source),'1')
    c.vms[s.court]._web_mocks=[(pattern,response) for pattern,response in c.vms[s.court]._web_mocks if pattern.pattern!='https://example.org/a']
    c.vms[s.court].mock_web('https://example.org/a',{'body':body})
    correction=certify(s,request_factory,'a','b','DISTINCT',generation=2)
    c.call(s.directory,'recover_component',scope,'a',correction['envelope']['request_id']); c.finalize()
    assert c.call(s.incident,'get_stats')['accepted_count']==2


def test_recovery_restoration_and_its_acknowledgement_can_be_replayed(system,event_factory,request_factory):
    s=system; c=s.chain
    event_factory('a'); event_factory('b'); reserve(s,'ab')
    original=certify(s,request_factory,'a','b'); scope=finalize_merge(s,[original],'a','b','ab'); publish(s,original)
    correction=certify(s,request_factory,'a','b','DISTINCT',generation=2)
    c.call(s.directory,'recover_component',scope,'a',correction['envelope']['request_id'])
    c.messages.clear()  # Simulate a missing restoration callback after recovery finalized.
    assert c.call(s.incident,'get_stats')['accepted_count']==0
    c.call(s.directory,'recover_component',scope,'a',correction['envelope']['request_id'])
    sender,target,method,args=c.messages.pop(0); c.call(target,method,*args,sender=sender)
    assert c.call(s.incident,'get_stats')['accepted_count']==2
    notice_id=c.call(s.directory,'get_latest_delivery',original['envelope']['request_id'])
    c.messages.clear()  # The application succeeded, but its directory acknowledgement was lost.
    assert c.call(s.directory,'get_consumer_ack',notice_id)=={}
    c.call(s.directory,'retry_notice',notice_id); c.finalize()
    assert c.call(s.directory,'get_consumer_ack',notice_id)['status']=='finalized'
    assert c.call(s.incident,'get_stats')['accepted_count']==2


def test_recovery_rejects_a_contradictory_partition(system,event_factory,request_factory):
    s=system; c=s.chain
    for r in 'abc': event_factory(r)
    reserve(s,'abc')
    ab,ac,bc=[certify(s,request_factory,a,b) for a,b in [('a','b'),('a','c'),('b','c')]]
    finalize_merge(s,[ab],'a','b','ab');scope=finalize_merge(s,[ab,ac,bc],'a','c','abc');publish(s,ab)
    correction=certify(s,request_factory,'a','b','DISTINCT',generation=2)
    ac=certify(s,request_factory,'a','c','SAME',generation=2)
    bc=certify(s,request_factory,'b','c','SAME',generation=2)
    with pytest.raises(Exception,match='contradicts'):
        c.call(s.directory,'recover_component',scope,'a',correction['envelope']['request_id'],encode([ac['envelope']['request_id'],bc['envelope']['request_id']]))
    assert c.call(s.incident,'get_stats')['accepted_count']==0
    assert c.call(s.directory,'get_identity','c',scope)['status']=='quarantined'


def test_maximum_component_recovers_a_complete_two_group_partition(system,event_factory,request_factory):
    from itertools import combinations
    s=system;c=s.chain
    for r in 'abcdef':event_factory(r)
    reserve(s,'abcdef')
    original=[certify(s,request_factory,a,b) for a,b in combinations('abcdef',2)]
    for size in range(2,7):
        subset=[r for r in original if r['left'] in 'abcdef'[:size] and r['right'] in 'abcdef'[:size]]
        scope=finalize_merge(s,subset,'a','abcdef'[size-1],'original.'+str(size))
    publish(s,original[0]);assert c.call(s.incident,'get_stats')['accepted_count']==1
    correction=certify(s,request_factory,'a','d','DISTINCT',generation=2)
    repair=[correction]
    for a,b in combinations('abcdef',2):
        if (a,b)==('a','d'):continue
        decision='SAME' if (a in 'abc')==(b in 'abc') else 'DISTINCT'
        repair.append(certify(s,request_factory,a,b,decision,generation=2))
    proof=encode([r['envelope']['request_id'] for r in repair])
    c.call(s.directory,'recover_component',scope,'a',correction['envelope']['request_id'],proof);c.finalize()
    assert c.call(s.incident,'get_stats')['accepted_count']==2
    assert [c.call(s.incident,'get_reference','ref.'+r)['canonical_id'] for r in 'abcdef']==['a']*3+['d']*3
    c.call(s.incident,'register_reference','f','later.f',sender=INCIDENT_OWNER)
    publish(s,correction)
    assert c.call(s.incident,'get_reference','later.f')['canonical_id']=='d'
    assert c.call(s.incident,'get_stats')['accepted_count']==2
