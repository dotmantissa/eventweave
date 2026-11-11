class EventRegistry(gl.Contract):
    owner: Address
    schemas: TreeMap[str, str]
    authorities: TreeMap[str, str]
    events: TreeMap[str, str]
    event_order: DynArray[str]
    history: DynArray[str]
    schema_revisions: TreeMap[str, u32]
    source_index: TreeMap[str, str]
    quarantines: TreeMap[str, bool]
    count: u32

    def __init__(self):
        self.owner = gl.message.sender_address
        self.count = u32(0)

    @gl.public.write
    def register_schema(self, schema_json: str) -> None:
        if gl.message.sender_address != self.owner:
            fail('Only registry owner may register schemas')
        value = parse(schema_json)
        if set(value) != {'schema_id', 'revision', 'mandatory', 'scope', 'rules'}:
            fail('Invalid schema fields')
        text(value['schema_id']); text(value['scope']); number(value['revision'])
        if value['mandatory'] != list(ATTRIBUTES) or not isinstance(value['rules'], list) or not 1 <= len(value['rules']) <= 12:
            fail('All identity discriminators are mandatory')
        for rule in value['rules']:
            text(rule, 1000)
        key = value['schema_id'] + ':' + str(value['revision'])
        data = encoded(value)
        if key in self.schemas:
            if self.schemas[key] != data:
                fail('Conflicting schema revision')
            return
        latest = int(self.schema_revisions.get(value['schema_id'], u32(0)))
        if value['revision'] != latest + 1:
            fail('Schema revisions must be consecutive')
        self.schemas[key] = data
        self.schema_revisions[value['schema_id']] = u32(value['revision'])
        append(self.history, {'operation': 'schema', 'key': key, 'value': value})

    @gl.public.write
    def register_authority(self, authority_json: str) -> None:
        if gl.message.sender_address != self.owner:
            fail('Only registry owner may configure authority')
        value = parse(authority_json)
        if set(value) != {'authority_id', 'principal', 'channel', 'url_prefix', 'evidence_url', 'evidence_hash', 'evidence_bytes', 'scope', 'revision'}:
            fail('Invalid authority fields')
        for key in ('authority_id', 'channel', 'scope'):
            text(value[key])
        value['principal'] = address(value['principal'])
        for key in ('url_prefix', 'evidence_url'):
            text(value[key], 2048)
            if not value[key].startswith('https://'):
                fail('Authority URLs require HTTPS')
        hash_text(value['evidence_hash']); number(value['evidence_bytes'], MAX_SOURCE_BYTES)
        if value['evidence_bytes'] < 1:
            fail('Authority evidence cannot be empty')
        number(value['revision'])
        key = value['authority_id'] + ':' + str(value['revision'])
        if key in self.authorities:
            if self.authorities[key] != encoded(value):
                fail('Conflicting authority revision')
            return
        if value['revision'] > 1 and value['authority_id'] + ':' + str(value['revision'] - 1) not in self.authorities:
            fail('Missing previous authority revision')
        self.authorities[key] = encoded(value)
        append(self.history, {'operation': 'authority', 'key': key, 'value': value})

    @gl.public.write
    def open_event(self, descriptor_json: str) -> str:
        value = parse(descriptor_json)
        keys = {'event_id', 'schema_id', 'schema_revision', 'title', 'issuer', 'place', 'interval_start', 'interval_end', 'occurrence_type', 'official_reference', 'source'}
        if set(value) != keys:
            fail('Invalid descriptor fields')
        for key in ('event_id', 'schema_id', 'issuer', 'place', 'official_reference'):
            text(value[key])
        text(value['title'], 180); number(value['schema_revision'])
        start = timestamp(value['interval_start']); end = timestamp(value['interval_end'])
        if end < start or value['occurrence_type'] not in KINDS:
            fail('Invalid occurrence interval or type')
        schema = self.get_schema(value['schema_id'], value['schema_revision'])
        source = source_record(value['source'])
        authority = self.get_authority(source['authority_id'])
        sender = str(gl.message.sender_address).lower()
        if authority['principal'] != sender:
            fail('Only configured authority principal may attest a record')
        if self.quarantines.get(source['authority_id'], False):
            fail('Authority is quarantined')
        if source['scope'] != schema['scope'] or authority['scope'] != schema['scope'] or source['channel'] != authority['channel']:
            fail('Source scope or channel mismatch')
        if not source['url'].startswith(authority['url_prefix']):
            fail('Source is outside configured authority channel')
        request_digest = digest(value)
        key = value['event_id']
        if key in self.events:
            old = json.loads(self.events[key])
            if old['descriptor_digest'] != request_digest or old['owner'] != sender:
                fail('Conflicting event ID reuse')
            return key
        source_key = source['record_id'] + ':' + source['revision']
        if source_key in self.source_index:
            fail('Source revision already registered; use its original event')
        value.update(owner=sender, descriptor_digest=request_digest, status='pending', authority_revision=authority['revision'])
        self.events[key] = encoded(value)
        self.source_index[source_key] = key
        append(self.event_order, {'event_id': key})
        append(self.history, {'operation': 'event', 'event_id': key, 'owner': sender})
        self.count = u32(int(self.count) + 1)
        return key

    @gl.public.write
    def quarantine_authority(self, authority_id: str, reason: str) -> None:
        if gl.message.sender_address != self.owner:
            fail('Only registry owner may quarantine authority')
        self.get_authority(authority_id); text(reason, 2000)
        self.quarantines[authority_id] = True
        append(self.history, {'operation': 'quarantine', 'authority_id': authority_id, 'reason': reason})

    @gl.public.view
    def get_schema(self, schema_id: str, revision: int) -> dict:
        key = schema_id + ':' + str(revision)
        if key not in self.schemas:
            fail('Unknown schema revision')
        return json.loads(self.schemas[key])

    @gl.public.view
    def get_authority(self, authority_id: str) -> dict:
        if ':' not in authority_id:
            fail('Authority ID must include its revision')
        if authority_id not in self.authorities:
            fail('Unknown authority revision')
        return json.loads(self.authorities[authority_id])

    @gl.public.view
    def get_identity(self, event_id: str) -> dict:
        if event_id not in self.events:
            fail('Unknown event')
        value = json.loads(self.events[event_id])
        value['quarantined'] = self.quarantines.get(value['source']['authority_id'], False)
        return value

    @gl.public.view
    def list_events(self, offset: int, limit: int) -> list:
        return [self.get_identity(item['event_id']) for item in page(self.event_order, offset, limit)]

    @gl.public.view
    def get_history(self, offset: int, limit: int) -> list:
        return page(self.history, offset, limit)
