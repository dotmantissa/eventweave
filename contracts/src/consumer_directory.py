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
    notices: TreeMap[str, str]
    latest_deliveries: TreeMap[str, str]
    active_authorizations: TreeMap[str, str]
    causes: TreeMap[str, str]
    proof_index: TreeMap[str, str]
    operation_sequence: u32
    event_relation_counts: TreeMap[str, u32]
    event_relations: TreeMap[str, str]
    event_alias_counts: TreeMap[str, u32]
    event_aliases: TreeMap[str, str]
    invalidated_relations: TreeMap[str, bool]
    recoveries: TreeMap[str, str]

    def __init__(self, court_address: str, registry_address: str):
        self.owner = gl.message.sender_address
        self.court = Address(court_address)
        self.registry = Address(registry_address)
        self.operation_sequence = u32(0)

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
        generation = gl.get_contract_at(self.court).view().get_generation(certificate['subject_id'], certificate['consumer_address'])
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
        for event_id in (certificate['left'], certificate['right']):
            node = self._node(certificate['scope'], event_id)
            count = int(self.event_relation_counts.get(node, u32(0)))
            self.event_relations[node + ':' + str(count)] = request_id
            self.event_relation_counts[node] = u32(count + 1)
        key = pair_key(certificate['left'], certificate['right'], certificate['scope'])
        consumers = json.loads(self.pair_consumers.get(key, '{}'))
        if certificate['consumer_address'] not in consumers and len(consumers) >= 8:
            fail('At most eight consumer bindings per pair')
        consumers[certificate['consumer_address']] = request_id
        self.pair_consumers[key] = encoded(consumers)
        self.edges[key] = request_id
        if certificate['decision'] == 'DISTINCT':
            self.distinct_index[key] = request_id
            if certificate['right'] in self._members(certificate['scope'], certificate['left']):
                self._quarantine_component(certificate['scope'], certificate['left'], request_id)
        elif self._distinct(key):
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
        if not isinstance(proof['relations'], list) or not 1 <= len(proof['relations']) <= 15:
            fail('At most fifteen complete pair certificates')
        if proof['left'] == proof['right']:
            fail('A merge requires two distinct records')
        for event_id in (proof['left'], proof['right']):
            record = gl.get_contract_at(self.registry).view().get_identity(event_id)
            policy = gl.get_contract_at(self.registry).view().get_schema(record['schema_id'], record['schema_revision'])
            expected_scope = 'scope:' + digest({'scope': policy['scope'], 'policy_id': record['schema_id'], 'policy_revision': record['schema_revision']})
            if proof['scope'] != expected_scope:
                fail('Merge scope is incompatible with the records')
        sender = str(gl.message.sender_address).lower()
        if not any(r in self.certificates and json.loads(self.certificates[r])['owner'] == sender for r in proof['relations']):
            fail('Only an assessed consumer owner may propose a merge')
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
                if self._distinct(key):
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
                        if certificate['status'] != 'finalized' or certificate['decision'] != 'SAME' or not certificate['coverage'] or certificate['unresolved'] or any(certificate['vector'][a] != 'SAME' for a in ATTRIBUTES):
                            status = 'unresolved'
                            break
        result = {**proof, 'fingerprint': fingerprint, 'members': combined, 'status': status, 'witness': witness, 'canonical_id': min(combined)}
        if status != 'pending':
            return result
        semantic = digest({'scope': proof['scope'], 'members': combined, 'relations': sorted(proof['relations'])})
        if semantic in self.proof_index:
            prior_id = self.proof_index[semantic]
            if prior_id != proof['operation_id']:
                fail('This complete proof already has an operation')
        self.proof_index[semantic] = proof['operation_id']
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
                if self._distinct(key):
                    fail('Finalized DISTINCT witness refuses merge')
                relation = next((r for r in result['relations'] if pair_key(json.loads(self.certificates[r])['left'], json.loads(self.certificates[r])['right'], scope) == key), '')
                if not relation:
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
            self._record_alias(alias)
        result['status'] = 'finalized'
        self.operations[operation_id] = encoded(result)
        append(self.history, {'operation': 'merge_finalized', 'operation_id': operation_id, 'canonical_id': canonical_id})

    def _record_alias(self, alias: dict):
        append(self.alias_history, alias)
        node = self._node(alias['scope'], alias['event_id'])
        count = int(self.event_alias_counts.get(node, u32(0)))
        self.event_aliases[node + ':' + str(count)] = encoded(alias)
        self.event_alias_counts[node] = u32(count + 1)

    @gl.public.view
    def get_event_relations(self, event_id: str, scope: str, offset: int, limit: int) -> list:
        number(offset); number(limit, 50)
        if not limit:
            fail('Page limit starts at one')
        node = self._node(scope, event_id)
        return [json.loads(self.certificates[self.event_relations[node + ':' + str(i)]]) for i in range(offset, min(offset + limit, int(self.event_relation_counts.get(node, u32(0)))))]

    @gl.public.view
    def get_event_alias_history(self, event_id: str, scope: str, offset: int, limit: int) -> list:
        number(offset); number(limit, 50)
        if not limit:
            fail('Page limit starts at one')
        node = self._node(scope, event_id)
        return [json.loads(self.event_aliases[node + ':' + str(i)]) for i in range(offset, min(offset + limit, int(self.event_alias_counts.get(node, u32(0)))))]

    def _active(self, node: str) -> list:
        return sorted(set(op for pending in json.loads(self.active_authorizations.get(node, '{}')).values() for op in pending))

    def _distinct(self, key: str) -> bool:
        if key not in self.distinct_index:
            return False
        certificate = json.loads(self.certificates[self.distinct_index[key]])
        try:
            self._live(certificate)
            return certificate['status'] == 'finalized'
        except Exception:
            return False

    def _proof(self, scope: str, event_id: str) -> list:
        members = self._members(scope, event_id)
        if any(self.quarantined.get(self._node(scope, r), False) for r in members):
            fail('Identity is quarantined')
        if len(members) == 1:
            return []
        alias = json.loads(self.aliases[self._node(scope, event_id)])
        operation = json.loads(self.operations[alias['operation_id']])
        required = {pair_key(a, b, scope) for i, a in enumerate(members) for b in members[i + 1:]}
        supplied = {}
        for relation_id in operation['relations']:
            cert = json.loads(self.certificates[relation_id]); self._live(cert)
            key = pair_key(cert['left'], cert['right'], scope)
            if cert['status'] != 'finalized' or cert['decision'] != 'SAME' or not cert['coverage'] or cert['unresolved'] or any(cert['vector'][a] != 'SAME' for a in ATTRIBUTES) or self._distinct(key):
                fail('Complete cluster proof is stale')
            supplied[key] = relation_id
        if set(supplied) != required:
            fail('Complete cluster proof is missing')
        return sorted(supplied.values())

    def _publish(self, certificate: dict, mapping: dict, types: dict, proofs: list, recovery: bool = False) -> str:
        versions = {r: int(self.alias_generation.get(self._node(certificate['scope'], r), u32(0))) for r in mapping}
        sources = {r: digest(gl.get_contract_at(self.registry).view().get_identity(r)['source']) for r in mapping}
        references = gl.get_contract_at(Address(certificate['consumer_address'])).view().get_stats()['references']
        payload = {**certificate, 'canonical_mappings': mapping, 'certified_types': types, 'proofs': sorted(set(proofs)), 'alias_versions': versions, 'source_hashes': sources, 'reference_epoch': references, 'recovery': recovery, 'directory': str(gl.message.contract_address).lower()}
        operation_id = 'delivery:' + digest(payload)
        if operation_id not in self.notices:
            self.operation_sequence = u32(int(self.operation_sequence) + 1)
            notice = {**payload, 'operation_id': operation_id, 'operation_sequence': int(self.operation_sequence), 'authorization_id': operation_id}
            self.notices[operation_id] = encoded(notice)
            for r in mapping:
                node = self._node(certificate['scope'], r)
                bindings = json.loads(self.active_authorizations.get(node, '{}'))
                if certificate['consumer_address'] not in bindings and len(bindings) >= 8:
                    fail('At most eight consumers per record')
                pending = bindings.get(certificate['consumer_address'], [])
                pending.append(operation_id)
                bindings[certificate['consumer_address']] = pending
                self.active_authorizations[node] = encoded(bindings)
            append(self.history, {'operation': 'alias_published', 'request_id': certificate['request_id'], 'operation_id': operation_id})
        notice = json.loads(self.notices[operation_id])
        if not self.is_notice_current(operation_id):
            fail('Application operation is stale or revoked')
        self.latest_deliveries[certificate['request_id']] = operation_id
        gl.get_contract_at(Address(certificate['consumer_address'])).emit(on='finalized').apply_identity(encoded(notice))
        return operation_id

    @gl.public.write
    def publish_alias(self, request_id: str) -> str:
        if request_id not in self.certificates:
            fail('Certificate has not crossed finalized delivery')
        certificate = json.loads(self.certificates[request_id]); self._live(certificate)
        if certificate['status'] in ('quarantined', 'superseded'):
            fail('Certificate cannot authorize alias reuse')
        mapping = {}; proofs = [request_id]; types = dict(certificate['certified_types'])
        for event_id in (certificate['left'], certificate['right']):
            identity = self.get_identity(event_id, certificate['scope'])
            if identity['status'] == 'quarantined':
                fail('Identity is quarantined')
            if certificate['decision'] == 'SAME' and (identity['status'] != 'finalized' or certificate['right'] not in identity['members']):
                fail('SAME reuse requires a complete finalized cluster proof')
            members = identity['members'] if not certificate['unresolved'] else [event_id]
            if not certificate['unresolved']:
                proofs += self._proof(certificate['scope'], event_id)
            for member in members:
                mapping[member] = identity['canonical_id'] if not certificate['unresolved'] else member
        for relation in sorted(set(proofs)):
            cert = json.loads(self.certificates[relation])
            for r, kind in cert['certified_types'].items():
                if r in types and types[r] != kind and not certificate['unresolved']:
                    fail('Cluster has conflicting certified attributes')
                types[r] = kind
        return self._publish(certificate, mapping, types, proofs)

    def _revoke_notice(self, operation_id: str, successor_id: str):
        if operation_id in self.revocation_notices:
            return
        notice = json.loads(self.notices[operation_id])
        notice.update(status='superseded', superseded_by=successor_id)
        self.notices[operation_id] = encoded(notice)
        invalidation = {**notice, 'operation_id': 'invalidate:' + operation_id}
        self.revocation_notices[operation_id] = encoded(invalidation)
        gl.get_contract_at(Address(notice['consumer_address'])).emit(on='finalized').invalidate_identity(encoded(invalidation))

    def _quarantine_component(self, scope: str, event_id: str, cause_id: str):
        members = self._members(scope, event_id)
        already_quarantined = all(self.quarantined.get(self._node(scope, r), False) for r in members)
        for member in members:
            node = self._node(scope, member)
            causes = json.loads(self.causes.get(node, '[]'))
            if cause_id not in causes:
                causes.append(cause_id); self.causes[node] = encoded(causes)
            self.quarantined[node] = True
            if node in self.aliases:
                alias = json.loads(self.aliases[node])
                if alias['status'] != 'superseded':
                    alias.update(status='superseded', superseded_by=cause_id)
                    self.aliases[node] = encoded(alias); self._record_alias(alias)
            self.canonical_ids[node] = member
            for operation_id in self._active(node):
                notice = json.loads(self.notices[operation_id])
                for relation in notice['proofs']:
                    cert = json.loads(self.certificates[relation])
                    if cert['decision'] == 'SAME' and cert['left'] in members and cert['right'] in members:
                        cert.update(status='superseded', superseded_by=cause_id)
                        self.certificates[relation] = encoded(cert)
                self._revoke_notice(operation_id, cause_id)
        for i, left in enumerate(members):
            for right in members[i + 1:]:
                key = pair_key(left, right, scope)
                for relation_id in json.loads(self.pair_consumers.get(key, '{}')).values():
                    cert = json.loads(self.certificates[relation_id])
                    if cert['decision'] == 'SAME' and not already_quarantined:
                        cert.update(status='superseded', superseded_by=cause_id)
                        self.certificates[relation_id] = encoded(cert)
        append(self.history, {'operation': 'component_quarantined', 'event_id': event_id, 'scope': scope, 'successor_id': cause_id})

    @gl.public.write
    def invalidate_relation(self, relation_id: str, successor_id: str) -> None:
        if gl.message.sender_address != self.court:
            fail('Only finalized court messages may invalidate relations')
        if relation_id not in self.certificates:
            fail('Unknown finalized relation')
        if self.invalidated_relations.get(relation_id, False):
            return
        self.invalidated_relations[relation_id] = True
        cert = json.loads(self.certificates[relation_id])
        live = gl.get_contract_at(self.court).view().get_result(relation_id)
        if not live['quarantined'] and live['status'] != 'superseded':
            fail('No court revocation')
        already_retired = cert['status'] == 'superseded'
        cert.update(status='superseded', superseded_by=successor_id)
        self.certificates[relation_id] = encoded(cert)
        key = pair_key(cert['left'], cert['right'], cert['scope'])
        if cert['decision'] == 'DISTINCT':
            if self.distinct_index.get(key, '') == relation_id:
                del self.distinct_index[key]
            for member in (cert['left'], cert['right']):
                for op in self._active(self._node(cert['scope'], member)):
                    if relation_id in json.loads(self.notices[op])['proofs']:
                        self._revoke_notice(op, successor_id)
            return
        # A repeated court callback after recovery must not quarantine the recovered component again.
        node = self._node(cert['scope'], cert['left'])
        if not already_retired and len(self._members(cert['scope'], cert['left'])) > 1 and (not self.quarantined.get(node, False) or successor_id not in json.loads(self.causes.get(node, '[]'))):
            self._quarantine_component(cert['scope'], cert['left'], successor_id or relation_id)

    @gl.public.write
    def retry_invalidation(self, relation_id: str) -> None:
        operations = [relation_id] if relation_id in self.revocation_notices else []
        if not operations:
            # Legacy request IDs still resolve active authorization notices for recovery clients.
            for member in (json.loads(self.certificates[relation_id])['left'], json.loads(self.certificates[relation_id])['right']):
                for op in self._active(self._node(json.loads(self.certificates[relation_id])['scope'], member)):
                    if op in self.revocation_notices and relation_id in json.loads(self.notices[op])['proofs']:
                        operations.append(op)
        for op in sorted(set(operations)):
            notice = json.loads(self.revocation_notices[op])
            gl.get_contract_at(Address(notice['consumer_address'])).emit(on='finalized').invalidate_identity(encoded(notice))

    @gl.public.write
    def recover_component(self, scope: str, event_id: str, correction_id: str, relations_json: str = '[]') -> None:
        if correction_id not in self.certificates:
            fail('Recovery needs delivered correction')
        certificate = json.loads(self.certificates[correction_id]); self._live(certificate)
        relations = json.loads(relations_json)
        if not isinstance(relations, list) or len(relations) > 15 or any(not isinstance(r, str) for r in relations):
            fail('Recovery proof requires at most fifteen relation IDs')
        proof_ids = sorted(set(relations + [correction_id]))
        recovery_key = scope + ':' + correction_id
        if recovery_key in self.recoveries:
            prior = json.loads(self.recoveries[recovery_key])
            if proof_ids != prior['proofs']:
                fail('Recovery proof differs from finalized recovery')
            if event_id not in prior['members']:
                fail('Recovery does not cover this event')
            for operation_id in prior['notices']:
                self.retry_notice(operation_id)
            return
        members = self._members(scope, event_id)
        if certificate['scope'] != scope or certificate['decision'] != 'DISTINCT' or certificate['status'] != 'finalized' or not all(r in members for r in (certificate['left'], certificate['right'])) or not self.quarantined.get(self._node(scope, event_id), False):
            fail('Recovery requires current finalized DISTINCT bound to the quarantined component')
        causes = sorted(set(c for member in members for c in json.loads(self.causes.get(self._node(scope, member), '[]'))))
        for cause in causes:
            if cause in proof_ids and json.loads(self.certificates[cause])['decision'] == 'DISTINCT':
                continue
            old = gl.get_contract_at(self.court).view().get_result(cause)
            successor_id = old['superseded_by']
            if successor_id not in proof_ids or old['subject_id'] != json.loads(self.certificates[successor_id])['subject_id']:
                fail('Correction does not resolve every quarantine cause')
        # Every pair must establish a coherent partition. A correction of a,b alone
        # cannot decide whether a third record belongs to a, b, or another occurrence.
        required = {pair_key(a, b, scope) for i, a in enumerate(members) for b in members[i + 1:]}
        supplied = {}; types = {}; groups = {r: [r] for r in members}
        for relation_id in proof_ids:
            if relation_id not in self.certificates:
                fail('Recovery proof contains undelivered certificate')
            cert = json.loads(self.certificates[relation_id]); self._live(cert)
            key = pair_key(cert['left'], cert['right'], cert['scope'])
            if key not in required or key in supplied or cert['status'] != 'finalized' or cert['unresolved'] or cert['decision'] not in ('SAME', 'DISTINCT'):
                fail('Recovery requires complete current partition proof')
            if cert['decision'] == 'SAME' and (not cert['coverage'] or any(cert['vector'][a] != 'SAME' for a in ATTRIBUTES) or self._distinct(key)):
                fail('Recovery SAME lacks complete mandatory coverage')
            supplied[key] = cert
            for r, kind in cert['certified_types'].items():
                if r not in members or (r in types and types[r] != kind):
                    fail('Recovery has conflicting certified attributes')
                types[r] = kind
            if cert['decision'] == 'SAME':
                combined = sorted(set(groups[cert['left']] + groups[cert['right']]))
                for r in combined:
                    groups[r] = combined
        if set(supplied) != required or set(types) != set(members):
            fail('Recovery requires complete current partition proof for every member')
        for cert in supplied.values():
            same_group = groups[cert['left']] == groups[cert['right']]
            if same_group != (cert['decision'] == 'SAME'):
                fail('Recovery partition contradicts a pair certificate')
        restore = {}
        for member in members:
            for op in self._active(self._node(scope, member)):
                consumer = json.loads(self.notices[op])['consumer_address']
                if op not in self.revocation_notices or not self.consumer_acks.get('invalidate:' + op, ''):
                    fail('Outstanding consumer invalidation must be acknowledged before recovery')
                notice = json.loads(self.notices[op])
                item = restore.get(consumer, {'certificate': notice, 'members': set()})
                item['members'].update(r for r in notice['canonical_mappings'] if r in members)
                restore[consumer] = item
        mapping = {r: min(groups[r]) for r in members}
        for member in members:
            node = self._node(scope, member); group = groups[member]
            merge_id = 'recovery:' + digest({'correction': correction_id, 'members': group, 'proofs': proof_ids})
            same_proofs = sorted(cert['request_id'] for cert in supplied.values() if cert['decision'] == 'SAME' and cert['left'] in group and cert['right'] in group)
            self.operations[merge_id] = encoded({'operation_id': merge_id, 'relations': same_proofs, 'status': 'finalized'})
            self.memberships[node] = encoded(group); self.canonical_ids[node] = mapping[member]
            self.quarantined[node] = False; self.causes[node] = '[]'
            self.alias_generation[node] = u32(int(self.alias_generation.get(node, u32(0))) + 1)
            alias = {'event_id': member, 'canonical_id': mapping[member], 'members': group, 'scope': scope, 'operation_id': merge_id, 'generation': int(self.alias_generation[node]), 'status': 'finalized'}
            self.aliases[node] = encoded(alias); self._record_alias(alias)
        recovery_notices = []
        for item in restore.values():
            prior = item['certificate']
            cert = {k: prior[k] for k in ENVELOPE_KEYS}
            cert.update(left=prior['left'], right=prior['right'], scope=scope, decision='DISTINCT', unresolved=False, status='finalized', superseded_by='', recovery_correction=correction_id)
            recovery_notices.append(self._publish(cert, {r: mapping[r] for r in sorted(item['members'])}, types, proof_ids, True))
        self.recoveries[recovery_key] = encoded({'members': members, 'proofs': proof_ids, 'notices': recovery_notices})
        append(self.history, {'operation': 'component_recovered', 'scope': scope, 'members': members, 'correction_id': correction_id, 'notices': recovery_notices})

    @gl.public.write
    def retry_notice(self, operation_id: str) -> None:
        if not self.is_notice_current(operation_id):
            fail('Application operation is stale or revoked')
        notice = json.loads(self.notices[operation_id])
        gl.get_contract_at(Address(notice['consumer_address'])).emit(on='finalized').apply_identity(encoded(notice))

    @gl.public.view
    def get_latest_delivery(self, request_id: str) -> str:
        return self.latest_deliveries.get(request_id, '')

    @gl.public.write
    def acknowledge(self, operation_id: str, acknowledgement_json: str) -> None:
        ack = parse(acknowledgement_json)
        op = operation_id[len('invalidate:'):] if operation_id.startswith('invalidate:') else operation_id
        if op not in self.notices:
            fail('Unknown acknowledgement')
        notice = json.loads(self.notices[op])
        if str(gl.message.sender_address).lower() != notice['consumer_address'] or ack.get('generation') != notice['generation'] or ack.get('request_id') != notice['request_id'] or ack.get('operation_id') != operation_id:
            fail('Only bound consumer may acknowledge exact operation')
        value = encoded(ack)
        if operation_id in self.consumer_acks and self.consumer_acks[operation_id] != value:
            fail('Conflicting acknowledgement')
        self.consumer_acks[operation_id] = value
        if not operation_id.startswith('invalidate:'):
            for r in notice['canonical_mappings']:
                node = self._node(notice['scope'], r)
                bindings = json.loads(self.active_authorizations.get(node, '{}'))
                pending = bindings.get(notice['consumer_address'], [])
                bindings[notice['consumer_address']] = [p for p in pending if int(json.loads(self.notices[p])['operation_sequence']) >= notice['operation_sequence']]
                self.active_authorizations[node] = encoded(bindings)

    @gl.public.view
    def get_notice(self, operation_id: str) -> dict:
        if operation_id.startswith('invalidate:'):
            return json.loads(self.revocation_notices[operation_id[len('invalidate:'):]])
        return json.loads(self.notices[operation_id])

    @gl.public.view
    def is_notice_current(self, operation_id: str) -> bool:
        if operation_id not in self.notices:
            return False
        notice = json.loads(self.notices[operation_id])
        if notice['status'] == 'superseded':
            return False
        try:
            for relation in notice['proofs']:
                self._live(json.loads(self.certificates[relation]))
            for r, canonical in notice['canonical_mappings'].items():
                node = self._node(notice['scope'], r)
                record = gl.get_contract_at(self.registry).view().get_identity(r)
                if record['quarantined'] or digest(record['source']) != notice['source_hashes'][r] or self.quarantined.get(node, False) or (not notice['unresolved'] and self.canonical_ids.get(node, r) != canonical) or int(self.alias_generation.get(node, u32(0))) != notice['alias_versions'][r]:
                    return False
            return True
        except Exception:
            return False

    @gl.public.view
    def get_identity(self, event_id: str, scope: str) -> dict:
        gl.get_contract_at(self.registry).view().get_identity(event_id)
        node = self._node(scope, event_id)
        status = 'quarantined' if self.quarantined.get(node, False) else ('finalized' if node in self.aliases else 'pending')
        if status == 'finalized' and len(self._members(scope, event_id)) > 1:
            try:
                self._proof(scope, event_id)
            except Exception:
                status = 'unresolved'
        return {'event_id': event_id, 'canonical_id': self.canonical_ids.get(node, event_id) if status == 'finalized' else event_id, 'members': self._members(scope, event_id), 'scope': scope, 'generation': int(self.alias_generation.get(node, u32(0))), 'status': status}

    @gl.public.view
    def get_acknowledgement(self, request_id: str) -> dict:
        return json.loads(self.acknowledgements[request_id]) if request_id in self.acknowledgements else {}

    @gl.public.view
    def get_consumer_ack(self, operation_id: str) -> dict:
        op = self.latest_deliveries.get(operation_id[len('delivery:'):], operation_id) if operation_id.startswith('delivery:') else operation_id
        return json.loads(self.consumer_acks[op]) if op in self.consumer_acks else {}

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
            certificate = json.loads(self.certificates[request_id])
            self._live(certificate)
            return certificate['status'] not in ('quarantined', 'superseded')
        except Exception:
            return False
