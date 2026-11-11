class ConsumerDirectory(gl.Contract):
    owner: Address
    court: Address
    registry: Address
    certificates: TreeMap[str, str]
    edges: TreeMap[str, str]
    distinct_index: TreeMap[str, str]
    memberships: TreeMap[str, str]
    canonical_ids: TreeMap[str, str]
    aliases: TreeMap[str, str]
    alias_history: DynArray[str]
    history: DynArray[str]
    witnesses: TreeMap[str, str]
    quarantined: TreeMap[str, bool]
    acknowledgements: TreeMap[str, str]
    operations: TreeMap[str, str]
    alias_generation: TreeMap[str, u32]
    consumer_acks: TreeMap[str, str]
    pair_consumers: TreeMap[str, str]
    revocation_notices: TreeMap[str, str]

    def __init__(self, court_address: str, registry_address: str):
        self.owner = gl.message.sender_address
        self.court = Address(court_address)
        self.registry = Address(registry_address)

    def _node(self, scope: str, event_id: str) -> str:
        return scope + ':' + event_id

    def _members(self, scope: str, event_id: str) -> list:
        key = self._node(scope, event_id)
        return json.loads(self.memberships[key]) if key in self.memberships else [event_id]

    def _live(self, certificate: dict) -> dict:
        live = gl.get_contract_at(self.court).view().get_result(certificate['request_id'])
        for key in ENVELOPE_KEYS:
            if live[key] != certificate[key]:
                fail('Certificate binding mismatch')
        if live['quarantined'] or live['status'] == 'superseded':
            fail('Certificate is stale or quarantined')
        generation = gl.get_contract_at(self.court).view().get_generation(certificate['subject_id'])
        if generation != certificate['generation']:
            fail('Certificate generation is stale')
        records = []
        for event_id in sorted((certificate['left'], certificate['right'])):
            record = gl.get_contract_at(self.registry).view().get_identity(event_id)
            if record['quarantined']:
                fail('Source is quarantined')
            records.append(record)
        if digest([r['source'] for r in records]) != certificate['source_manifest_digest']:
            fail('Source revision is stale; a successor request is required')
        return live

    @gl.public.write
    def receive_certificate(self, certificate_json: str) -> None:
        if gl.message.sender_address != self.court:
            fail('Only finalized court messages may deliver certificates')
        certificate = parse(certificate_json)
        self._live(certificate)
        request_id = certificate['request_id']
        if request_id in self.certificates:
            old = json.loads(self.certificates[request_id])
            if old['generation'] != certificate['generation'] or old['decision'] != certificate['decision']:
                fail('Conflicting certificate delivery')
            return
        certificate['status'] = 'unresolved' if certificate['unresolved'] else 'finalized'
        if certificate.get('controlling_rules') == ['DEADLINE']:
            certificate['status'] = 'timeout'
        self.certificates[request_id] = encoded(certificate)
        key = pair_key(certificate['left'], certificate['right'], certificate['scope'])
        consumers = json.loads(self.pair_consumers.get(key, '{}'))
        if certificate['consumer_address'] not in consumers and len(consumers) >= 8:
            fail('At most eight consumer bindings per pair')
        prior_consumer_relation = consumers.get(certificate['consumer_address'], '')
        if certificate['decision'] == 'DISTINCT' and prior_consumer_relation:
            prior_consumer = json.loads(self.certificates[prior_consumer_relation])
            if prior_consumer['decision'] == 'SAME':
                self._revoke_certificate(prior_consumer, request_id, self._members(certificate['scope'], certificate['left']))
        consumers[certificate['consumer_address']] = request_id
        self.pair_consumers[key] = encoded(consumers)
        if key in self.edges:
            prior = json.loads(self.certificates[self.edges[key]])
            if prior['generation'] >= certificate['generation']:
                fail('Reordered stale certificate')
        self.edges[key] = request_id
        if certificate['decision'] == 'DISTINCT':
            self.distinct_index[key] = request_id
            if certificate['right'] in self._members(certificate['scope'], certificate['left']):
                self._quarantine_component(certificate['scope'], certificate['left'], request_id)
        elif key in self.distinct_index:
            # A contrary SAME never silently removes a finalized non merge edge.
            certificate['status'] = 'quarantined'
            self.certificates[request_id] = encoded(certificate)
        ack = {'request_id': request_id, 'generation': certificate['generation'], 'status': certificate['status']}
        self.acknowledgements[request_id] = encoded(ack)
        append(self.history, {'operation': 'certificate', **ack, 'decision': certificate['decision']})

    @gl.public.write
    def propose_merge(self, proof_json: str) -> dict:
        proof = parse(proof_json)
        if set(proof) != {'operation_id', 'left', 'right', 'scope', 'relations'}:
            fail('Invalid merge proof fields')
        for key in ('operation_id', 'left', 'right', 'scope'):
            text(proof[key], 512)
        if not isinstance(proof['relations'], list) or len(proof['relations']) > 15:
            fail('At most fifteen complete pair certificates')
        if proof['left'] == proof['right']:
            fail('A merge requires two distinct records')
        for event_id in (proof['left'], proof['right']):
            record = gl.get_contract_at(self.registry).view().get_identity(event_id)
            policy = gl.get_contract_at(self.registry).view().get_schema(record['schema_id'], record['schema_revision'])
            expected_scope = 'scope:' + digest({'scope': policy['scope'], 'policy_id': record['schema_id'], 'policy_revision': record['schema_revision']})
            if proof['scope'] != expected_scope:
                fail('Merge scope is incompatible with the records')
        fingerprint = digest(proof)
        if proof['operation_id'] in self.operations:
            stored = json.loads(self.operations[proof['operation_id']])
            if stored['fingerprint'] != fingerprint:
                fail('Conflicting operation ID reuse')
            return stored
        left = self._members(proof['scope'], proof['left']); right = self._members(proof['scope'], proof['right'])
        combined = sorted(set(left + right))
        witness = ''
        status = 'pending'
        if len(combined) > 6:
            status = 'unresolved'
        elif any(self.quarantined.get(self._node(proof['scope'], event_id), False) for event_id in combined):
            status = 'quarantined'
        else:
            required = {pair_key(a, b, proof['scope']) for i, a in enumerate(combined) for b in combined[i + 1:]}
            supplied = {}
            for relation_id in proof['relations']:
                text(relation_id)
                if relation_id not in self.certificates:
                    fail('Proof contains an undelivered certificate')
                certificate = json.loads(self.certificates[relation_id])
                key = pair_key(certificate['left'], certificate['right'], certificate['scope'])
                if key in supplied:
                    fail('Duplicate proof pair')
                supplied[key] = certificate
            # Inspect every non merge edge before considering affirmative support.
            for key in sorted(required):
                if key in self.distinct_index:
                    witness = self.distinct_index[key]
                    status = 'refused'
                    break
            if status != 'refused':
                if set(supplied) != required:
                    status = 'unresolved'
                else:
                    for key in sorted(required):
                        certificate = supplied[key]
                        self._live(certificate)
                        if self.edges.get(key, '') != certificate['request_id'] or certificate['status'] != 'finalized' or certificate['decision'] != 'SAME' or not certificate['coverage'] or certificate['unresolved'] or any(certificate['vector'][a] != 'SAME' for a in ATTRIBUTES):
                            status = 'unresolved'
                            break
        result = {**proof, 'fingerprint': fingerprint, 'members': combined, 'status': status, 'witness': witness, 'canonical_id': min(combined)}
        self.operations[proof['operation_id']] = encoded(result)
        if witness:
            self.witnesses[proof['operation_id']] = witness
        append(self.history, {'operation': 'merge_proposal', 'operation_id': proof['operation_id'], 'status': status, 'witness': witness})
        return result

    @gl.public.write
    def finalize_alias(self, operation_id: str) -> None:
        if operation_id not in self.operations:
            fail('Unknown merge proposal')
        result = json.loads(self.operations[operation_id])
        if result['status'] == 'finalized':
            return
        if result['status'] != 'pending':
            fail('Complete compatible merge proof required')
        scope = result['scope']; members = result['members']
        actual = sorted(set(self._members(scope, result['left']) + self._members(scope, result['right'])))
        if actual != members:
            fail('Cluster changed; submit a fresh complete proof')
        for i, left in enumerate(members):
            if self.quarantined.get(self._node(scope, left), False):
                fail('Cluster is quarantined')
            for right in members[i + 1:]:
                key = pair_key(left, right, scope)
                if key in self.distinct_index:
                    fail('Finalized DISTINCT witness refuses merge')
                relation = self.edges.get(key, '')
                if relation not in result['relations']:
                    fail('Proof is stale')
                certificate = json.loads(self.certificates[relation]); self._live(certificate)
                if certificate['decision'] != 'SAME' or certificate['status'] != 'finalized':
                    fail('Merge lacks finalized mandatory coverage')
        canonical_id = min(members)
        for event_id in members:
            node = self._node(scope, event_id)
            self.memberships[node] = encoded(members)
            self.canonical_ids[node] = canonical_id
            generation = int(self.alias_generation.get(node, u32(0))) + 1
            self.alias_generation[node] = u32(generation)
            alias = {'event_id': event_id, 'canonical_id': canonical_id, 'members': members, 'scope': scope, 'operation_id': operation_id, 'generation': generation, 'status': 'finalized'}
            self.aliases[node] = encoded(alias)
            append(self.alias_history, alias)
        result['status'] = 'finalized'
        self.operations[operation_id] = encoded(result)
        append(self.history, {'operation': 'merge_finalized', 'operation_id': operation_id, 'canonical_id': canonical_id})

    @gl.public.write
    def publish_alias(self, request_id: str) -> None:
        if request_id not in self.certificates:
            fail('Certificate has not crossed finalized delivery')
        certificate = json.loads(self.certificates[request_id]); self._live(certificate)
        if certificate['status'] in ('quarantined', 'superseded'):
            fail('Certificate cannot authorize alias reuse')
        mapping = {}
        for event_id in (certificate['left'], certificate['right']):
            identity = self.get_identity(event_id, certificate['scope'])
            if identity['status'] == 'quarantined':
                fail('Identity is quarantined')
            if certificate['decision'] == 'SAME' and (identity['status'] != 'finalized' or certificate['right'] not in identity['members']):
                fail('SAME reuse requires a complete finalized cluster proof')
            mapping[event_id] = identity['canonical_id']
        notice = {**certificate, 'canonical_mappings': mapping, 'operation_id': 'delivery:' + request_id, 'directory': str(gl.message.contract_address).lower()}
        gl.get_contract_at(Address(certificate['consumer_address'])).emit(on='finalized').apply_identity(encoded(notice))
        append(self.history, {'operation': 'alias_published', 'request_id': request_id, 'generation': certificate['generation']})

    def _quarantine_component(self, scope: str, event_id: str, successor_id: str):
        members = self._members(scope, event_id)
        for member in members:
            node = self._node(scope, member)
            self.quarantined[node] = True
            if node in self.aliases:
                alias = json.loads(self.aliases[node]); alias.update(status='superseded', superseded_by=successor_id)
                self.aliases[node] = encoded(alias); append(self.alias_history, alias)
            # Original descriptors remain untouched; reuse returns original IDs while restricted.
            self.canonical_ids[node] = member
        # Retire every affected SAME relation, including independently owned consumers.
        # The bounded reverse index covers at most fifteen pairs and eight consumers per pair.
        for i, left in enumerate(members):
            for right in members[i + 1:]:
                key = pair_key(left, right, scope)
                consumers = json.loads(self.pair_consumers.get(key, '{}'))
                for relation_id in consumers.values():
                    certificate = json.loads(self.certificates[relation_id])
                    if certificate['decision'] == 'SAME':
                        self._revoke_certificate(certificate, successor_id, members)
        append(self.history, {'operation': 'component_quarantined', 'event_id': event_id, 'scope': scope, 'successor_id': successor_id})

    def _revoke_certificate(self, certificate: dict, successor_id: str, members: list):
        relation_id = certificate['request_id']
        if relation_id in self.revocation_notices:
            return
        certificate.update(status='superseded', superseded_by=successor_id)
        self.certificates[relation_id] = encoded(certificate)
        notice = {**certificate, 'canonical_mappings': {r: r for r in members}, 'operation_id': 'invalidate:' + relation_id, 'directory': str(gl.message.contract_address).lower()}
        self.revocation_notices[relation_id] = encoded(notice)
        gl.get_contract_at(Address(certificate['consumer_address'])).emit(on='finalized').invalidate_identity(encoded(notice))

    @gl.public.write
    def invalidate_relation(self, relation_id: str, successor_id: str) -> None:
        if gl.message.sender_address != self.court:
            fail('Only finalized court messages may invalidate relations')
        if relation_id not in self.certificates:
            fail('Unknown finalized relation')
        if relation_id in self.revocation_notices:
            notice = json.loads(self.revocation_notices[relation_id])
            gl.get_contract_at(Address(notice['consumer_address'])).emit(on='finalized').invalidate_identity(encoded(notice))
            return
        certificate = json.loads(self.certificates[relation_id])
        live = gl.get_contract_at(self.court).view().get_result(relation_id)
        if not live['quarantined'] and live['status'] != 'superseded':
            fail('No court revocation')
        self._quarantine_component(certificate['scope'], certificate['left'], successor_id)
        self._revoke_certificate(certificate, successor_id, self._members(certificate['scope'], certificate['left']))

    @gl.public.write
    def retry_invalidation(self, relation_id: str) -> None:
        if relation_id not in self.revocation_notices:
            fail('No finalized invalidation to retry')
        notice = json.loads(self.revocation_notices[relation_id])
        gl.get_contract_at(Address(notice['consumer_address'])).emit(on='finalized').invalidate_identity(encoded(notice))

    @gl.public.write
    def recover_component(self, scope: str, event_id: str, correction_id: str) -> None:
        if correction_id not in self.certificates:
            fail('Recovery needs delivered correction')
        certificate = json.loads(self.certificates[correction_id]); self._live(certificate)
        if certificate['scope'] != scope or certificate['decision'] != 'DISTINCT' or certificate['status'] != 'finalized' or event_id not in (certificate['left'], certificate['right']):
            fail('Recovery requires current finalized DISTINCT')
        members = self._members(scope, event_id)
        # Conservative split: all original histories become singleton identities. Old SAME edges stay unusable.
        for member in members:
            node = self._node(scope, member)
            self.memberships[node] = encoded([member]); self.canonical_ids[node] = member
            self.quarantined[node] = False
            self.alias_generation[node] = u32(int(self.alias_generation.get(node, u32(0))) + 1)
        append(self.history, {'operation': 'component_recovered', 'scope': scope, 'members': members, 'correction_id': correction_id})

    @gl.public.write
    def acknowledge(self, operation_id: str, acknowledgement_json: str) -> None:
        acknowledgement = parse(acknowledgement_json)
        request_id = acknowledgement.get('request_id', '')
        if request_id not in self.certificates:
            fail('Unknown acknowledgement')
        certificate = json.loads(self.certificates[request_id])
        if str(gl.message.sender_address).lower() != certificate['consumer_address'] or acknowledgement.get('generation') != certificate['generation']:
            fail('Only bound consumer may acknowledge current generation')
        value = encoded(acknowledgement)
        if operation_id in self.consumer_acks and self.consumer_acks[operation_id] != value:
            fail('Conflicting acknowledgement')
        self.consumer_acks[operation_id] = value

    @gl.public.view
    def get_identity(self, event_id: str, scope: str) -> dict:
        gl.get_contract_at(self.registry).view().get_identity(event_id)
        node = self._node(scope, event_id)
        return {'event_id': event_id, 'canonical_id': self.canonical_ids.get(node, event_id), 'members': self._members(scope, event_id), 'scope': scope, 'generation': int(self.alias_generation.get(node, u32(0))), 'status': 'quarantined' if self.quarantined.get(node, False) else ('finalized' if node in self.aliases else 'pending')}

    @gl.public.view
    def get_acknowledgement(self, request_id: str) -> dict:
        return json.loads(self.acknowledgements[request_id]) if request_id in self.acknowledgements else {}

    @gl.public.view
    def get_consumer_ack(self, operation_id: str) -> dict:
        return json.loads(self.consumer_acks[operation_id]) if operation_id in self.consumer_acks else {}

    @gl.public.view
    def get_history(self, offset: int, limit: int) -> list:
        return page(self.history, offset, limit)

    @gl.public.view
    def get_alias_history(self, offset: int, limit: int) -> list:
        return page(self.alias_history, offset, limit)

    @gl.public.view
    def get_relation(self, request_id: str) -> dict:
        if request_id not in self.certificates:
            fail('Unknown delivered relation')
        return json.loads(self.certificates[request_id])

    @gl.public.view
    def get_merge(self, operation_id: str) -> dict:
        if operation_id not in self.operations:
            fail('Unknown merge operation')
        return json.loads(self.operations[operation_id])

    @gl.public.view
    def is_current(self, request_id: str) -> bool:
        if request_id not in self.certificates:
            return False
        try:
            self._live(json.loads(self.certificates[request_id]))
            return True
        except Exception:
            return False
