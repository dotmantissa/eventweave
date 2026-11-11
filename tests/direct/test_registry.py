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
