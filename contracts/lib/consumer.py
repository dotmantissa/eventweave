    owner: Address
    directory: Address
    registry: Address
    policy_id: str
    policy_revision: u32
    consequence_digest: str
    references: TreeMap[str, str]
    reference_order: DynArray[str]
    canonical_counts: TreeMap[str, u32]
    generations: TreeMap[str, u32]
    acknowledgements: TreeMap[str, str]
    history: DynArray[str]
    accepted_count: u32
    held_count: u32
    capacity: u32
    restrictions: TreeMap[str, u32]
    approved_types: DynArray[str]
    latest_acknowledgements: TreeMap[str, str]

    def __init__(self, directory_address: str, registry_address: str, policy_id: str, policy_revision: int, capacity: int):
        self.owner = gl.message.sender_address
        self.directory = Address(directory_address); self.registry = Address(registry_address)
        text(policy_id); number(policy_revision); number(capacity, MAX_HISTORY)
        if capacity < 1 or policy_revision < 1:
            fail('Positive capacity and policy revision required')
        self.policy_id = policy_id; self.policy_revision = u32(policy_revision)
        self.capacity = u32(capacity); self.accepted_count = u32(0); self.held_count = u32(0)
        for kind in self._types():
            self.approved_types.append(kind)
        self.consequence_digest = digest({'consumer_type': self._consumer_type(), 'policy_id': policy_id, 'policy_revision': policy_revision, 'unresolved': 'retain_pending_without_reuse', 'accepted_types': self._types()})

    @gl.public.write
    def register_reference(self, event_id: str, reference_id: str) -> None:
        if gl.message.sender_address != self.owner:
            fail('Only consumer owner may register its references')
        identifier(event_id); identifier(reference_id)
        event = gl.get_contract_at(self.registry).view().get_identity(event_id)
        if event['quarantined'] or event['schema_id'] != self.policy_id or event['schema_revision'] != int(self.policy_revision):
            fail('Consumer rules reject this event or policy')
        if reference_id in self.references:
            if json.loads(self.references[reference_id])['event_id'] != event_id:
                fail('Conflicting consumer reference')
            return
        if len(self.reference_order) >= MAX_HISTORY:
            fail('Deployment reference capacity reached')
        if int(self.held_count) >= int(self.capacity):
            fail('Capacity includes pending holds')
        self.references[reference_id] = encoded({'reference_id': reference_id, 'event_id': event_id, 'original_owner': str(self.owner).lower(), 'canonical_id': event_id, 'status': 'pending', 'generation': 0, 'evidence_hash': event['source']['raw_hash']})
        append(self.reference_order, {'reference_id': reference_id})
        append(self.history, {'operation': 'reference_reserved', 'event_id': event_id, 'reference_id': reference_id})
        self.held_count = u32(int(self.held_count) + 1)

    @gl.public.write
    def release_hold(self, reference_id: str) -> None:
        if gl.message.sender_address != self.owner:
            fail('Only reservation owner may release a hold')
        value = self.get_reference(reference_id)
        if value['status'] == 'released':
            return
        if value['status'] not in ('pending', 'unresolved', 'superseded'):
            fail('Only an unapplied hold may be released')
        value['status'] = 'released'; self.references[reference_id] = encoded(value)
        self.held_count = u32(int(self.held_count) - 1)
        append(self.history, {'operation': 'hold_released', 'reference_id': reference_id})

    def _check_notice(self, notice: dict, invalidation: bool = False):
        if gl.message.sender_address != self.directory:
            fail('Only authenticated finalized directory messages may act')
        if notice['consumer_address'] != str(gl.message.contract_address).lower() or notice['directory'] != str(self.directory).lower() or notice['policy_id'] != self.policy_id or notice['policy_revision'] != int(self.policy_revision) or notice['consequence_digest'] != self.consequence_digest:
            fail('Consumer certificate binding mismatch')
        live = gl.get_contract_at(self.directory).view().get_notice(notice['operation_id'])
        if digest(live) != digest(notice):
            fail('Notice differs from finalized operation')
        if invalidation:
            if live['status'] != 'superseded':
                fail('No finalized supersession')
        elif not gl.get_contract_at(self.directory).view().is_notice_current(notice['operation_id']):
            fail('Stale finalized delivery')
        return live

    def _remove_count(self, value: dict):
        if value['status'] != 'finalized':
            return
        key = value['canonical_id']; count = int(self.canonical_counts.get(key, u32(0)))
        if count < 1:
            fail('Invalid canonical count invariant')
        self.canonical_counts[key] = u32(count - 1)
        if count == 1:
            self.accepted_count = u32(int(self.accepted_count) - 1)

    def _add_count(self, canonical_id: str):
        count = int(self.canonical_counts.get(canonical_id, u32(0)))
        self.canonical_counts[canonical_id] = u32(count + 1)
        if count == 0:
            self.accepted_count = u32(int(self.accepted_count) + 1)

    @gl.public.write
    def apply_identity(self, notice_json: str) -> None:
        notice = parse(notice_json); self._check_notice(notice)
        operation_id = notice['operation_id']; fingerprint = digest(notice)
        if operation_id in self.acknowledgements:
            ack = json.loads(self.acknowledgements[operation_id])
            if ack['fingerprint'] != fingerprint:
                fail('Conflicting operation acknowledgement')
            gl.get_contract_at(self.directory).emit(on='finalized').acknowledge(operation_id, encoded(ack))
            return
        affected = []
        for index in range(min(notice['reference_epoch'], len(self.reference_order))):
            reference_id = json.loads(self.reference_order[index])['reference_id']
            value = json.loads(self.references[reference_id])
            if value['event_id'] not in notice['canonical_mappings'] or value['status'] == 'released' or value.get('operation_sequence', 0) > notice['operation_sequence']:
                continue
            affected.append(reference_id); self._remove_count(value)
            approved = not notice['unresolved'] and notice['certified_types'].get(value['event_id'], 'UNKNOWN') in self._types()
            value.update(status='finalized' if approved else 'unresolved', canonical_id=notice['canonical_mappings'][value['event_id']] if approved else value['event_id'], generation=notice['generation'], request_id=notice['request_id'], authorization_id=notice['authorization_id'], operation_sequence=notice['operation_sequence'], certified_type=notice['certified_types'].get(value['event_id'], 'UNKNOWN'), superseded_by='')
            if approved:
                self._add_count(value['canonical_id'])
            self.references[reference_id] = encoded(value)
            append(self.history, {'operation': 'reference_applied', **value})
        ack = {'request_id': notice['request_id'], 'generation': notice['generation'], 'status': 'unresolved' if notice['unresolved'] else 'finalized', 'operation_id': operation_id, 'fingerprint': fingerprint, 'reference_count': len(affected), 'references_digest': digest(affected)}
        self.acknowledgements[operation_id] = encoded(ack)
        self.latest_acknowledgements[notice['request_id']] = operation_id
        gl.get_contract_at(self.directory).emit(on='finalized').acknowledge(operation_id, encoded(ack))

    @gl.public.write
    def invalidate_identity(self, notice_json: str) -> None:
        notice = parse(notice_json); self._check_notice(notice, True)
        operation_id = notice['operation_id']
        if operation_id in self.acknowledgements:
            gl.get_contract_at(self.directory).emit(on='finalized').acknowledge(operation_id, self.acknowledgements[operation_id])
            return
        for item in self.reference_order:
            reference_id = json.loads(item)['reference_id']; value = json.loads(self.references[reference_id])
            if value.get('authorization_id', '') != notice['authorization_id'] or value['status'] in ('released', 'superseded'):
                continue
            self._remove_count(value)
            value.update(status='superseded', canonical_id=value['event_id'], superseded_by=notice['superseded_by'])
            self.references[reference_id] = encoded(value)
            append(self.history, {'operation': 'reference_superseded', **value})
        ack = {'request_id': notice['request_id'], 'generation': notice['generation'], 'status': 'superseded', 'operation_id': operation_id}
        self.acknowledgements[operation_id] = encoded(ack)
        gl.get_contract_at(self.directory).emit(on='finalized').acknowledge(operation_id, encoded(ack))

    @gl.public.view
    def get_configuration(self) -> dict:
        return {'owner': str(self.owner).lower(), 'directory': str(self.directory).lower(), 'registry': str(self.registry).lower(), 'policy_id': self.policy_id, 'policy_revision': int(self.policy_revision), 'consequence_digest': self.consequence_digest, 'unresolved': 'retain_pending_without_reuse', 'consumer_type': self._consumer_type(), 'accepted_types': self._types(), 'capacity': int(self.capacity)}

    @gl.public.view
    def get_reference(self, reference_id: str) -> dict:
        if reference_id not in self.references:
            fail('Unknown consumer reference')
        return json.loads(self.references[reference_id])

    @gl.public.view
    def get_stats(self) -> dict:
        return {'accepted_count': int(self.accepted_count), 'held_count': int(self.held_count), 'capacity': int(self.capacity), 'references': len(self.reference_order)}

    @gl.public.view
    def get_acknowledgement(self, operation_id: str) -> dict:
        op = self.latest_acknowledgements.get(operation_id[len('delivery:'):], operation_id) if operation_id.startswith('delivery:') else operation_id
        return json.loads(self.acknowledgements[op]) if op in self.acknowledgements else {}

    @gl.public.view
    def get_history(self, offset: int, limit: int) -> list:
        return page(self.history, offset, limit)
