import pytest
from conftest import encode,OWNER,STRANGER

@pytest.mark.synthetic
def test_schema_immutable_and_authority_only(system,event_factory):
    c=system.chain;r=system.registry
    assert c.call(r,'register_schema',encode(system.policy)) is None
    changed={**system.policy,'scope':'changed'}
    with pytest.raises(Exception,match='Conflicting schema'):c.call(r,'register_schema',encode(changed))
    with pytest.raises(Exception,match='Only registry owner'):c.call(r,'register_schema',encode(system.policy),sender=STRANGER)
    record=event_factory('a');assert c.call(r,'open_event',encode(record))=='a'
    with pytest.raises(Exception,match='Only configured authority'):c.call(r,'open_event',encode({**record,'event_id':'b'}),sender=STRANGER)
    with pytest.raises(Exception,match='Conflicting event ID'):c.call(r,'open_event',encode({**record,'title':'different'}))
    assert c.call(r,'list_events',0,50)[0]['event_id']=='a'
    assert c.call(r,'get_history',0,50)

@pytest.mark.synthetic
def test_bounds_timezone_and_quarantine(system,event_factory):
    record=event_factory('a',interval='2026-11-10T13:00:00+01:00');c=system.chain
    with pytest.raises(Exception,match='Invalid occurrence interval'):c.call(system.registry,'open_event',encode({**record,'event_id':'b','interval_end':'2026-11-09T12:00:00Z'}))
    with pytest.raises(Exception,match='Only registry owner'):c.call(system.registry,'quarantine_authority','example:1','revoked',sender=STRANGER)
    c.call(system.registry,'quarantine_authority','example:1','revoked public channel')
    assert c.call(system.registry,'get_identity','a')['quarantined']
    with pytest.raises(Exception,match='quarantined'):c.call(system.registry,'open_event',encode({**record,'event_id':'b'}))
    with pytest.raises(Exception,match='Page limit'):c.call(system.registry,'list_events',0,0)

@pytest.mark.synthetic
def test_successor_source_preserves_original_attribution_and_locks_old_requests(system,event_factory,request_factory):
    import hashlib
    from test_directory import certify
    event_factory('a');event_factory('b');c=system.chain
    relation=certify(system,request_factory,'a','b')
    original=c.call(system.registry,'get_identity','a');source=dict(original['source']);body=b'Official correction: this occurrence has a separate incident reference INC999.'
    source.update(revision='2',raw_hash=hashlib.sha256(body).hexdigest(),byte_length=len(body))
    source['spans']=[dict(s,raw_hash=source['raw_hash'],end=len(body)) for s in source['spans']]
    with pytest.raises(Exception,match='Only original'):c.call(system.registry,'attest_source_revision','a',encode(source),'1',sender=STRANGER)
    c.call(system.registry,'attest_source_revision','a',encode(source),'1');c.call(system.registry,'attest_source_revision','a',encode(source),'1')
    current=c.call(system.registry,'get_identity','a');assert current['original_source']==original['source'];assert current['descriptor_digest']==original['descriptor_digest'];assert current['owner']==original['owner'];assert len(c.call(system.registry,'get_source_history',0,50))==1
    with pytest.raises(Exception,match='Source revision is stale'):c.call(system.directory,'publish_alias',relation['envelope']['request_id'])
    c.vms[system.court]._web_mocks = [(pattern,response) for pattern,response in c.vms[system.court]._web_mocks if pattern.pattern != 'https://example.org/a']
    c.vms[system.court].mock_web('https://example.org/a',{'body':body})
    corrected=certify(system,request_factory,'a','b','DISTINCT',generation=2)
    c.call(system.court,'supersede_relation',relation['envelope']['request_id'],corrected['envelope']['request_id'],'A committed successor source discloses the separate reference.');c.finalize()
    assert c.call(system.court,'get_result',relation['envelope']['request_id'])['status']=='superseded'
