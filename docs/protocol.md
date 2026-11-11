# Public protocol

The machine readable input schemas are in `api-schemas.json`. Every identity assessment is a pairwise docket. A deterministic merge can cover six records and all fifteen pairs. Larger packets remain unresolved.

## Constructors

| Contract | Parameters | Owner |
| :--- | :--- | :--- |
| EventRegistry | none | deployer |
| IdentityCourt | registry address | deployer |
| ConsumerDirectory | court address, registry address | deployer |
| IncidentHistory | directory address, registry address, policy ID, policy revision, capacity | independent incident application key |
| ReleaseEvidence | directory address, registry address, policy ID, policy revision, capacity | independent release application key |

The court owner binds the directory once through `bind_directory`. This binding is immutable. Consumers approve their configuration by signing their own deployments. Compatible upgrades append fields. Changing a schema or a binding requires an explicit new deployment; archived manifests retain the previous addresses.

## Write permissions

All failures below are expected deterministic errors. Repeating an identical registered ID succeeds without duplicating storage. Reusing an ID with different content fails. Write permission to assess never grants authority registration, issuer attestation or hold release permission.

| Method | Contract | Access and arguments |
| :--- | :--- | :--- |
| register_schema | Registry | Owner only. JSON with schema_id, consecutive revision, exact mandatory attribute list, scope and 1 to 12 rules. Locked requests retain their policy snapshot. |
| register_authority | Registry | Owner only. JSON with authority_id, principal, channel, URL prefix, evidence URL, SHA256 evidence commitment, byte count, scope and revision. Signed configuration authorizes attestation; public evidence must still establish the claimed source relationship. |
| quarantine_authority | Registry | Owner only. Revision qualified authority ID and public reason. Quarantine is permanent for that revision. A new authority revision is required to restore attestation. |
| open_event | Registry | Configured principal only. Descriptor JSON commits event ID, policy revision, title, issuer, place, interval, occurrence type, official reference and source. The event ID and original descriptor are immutable. |
| attest_source_revision | Registry | Original attesting principal only. Event ID, complete successor source JSON and previous revision. Record ID and scope remain bound. Original bytes and attribution remain in source history. Existing dockets remain locked; old certificates cannot authorize new actions. |
| bind_directory | Court | Court owner only, exactly once. Directory address. |
| compare_records | Court | Bound request owner, also listed in parties. Comparison JSON contains canonical envelope and two different event IDs. Policy, subject, manifest, consumer configuration, current generation and deadline must match. |
| assess | Court | Request owner only. Request ID. One substantive evaluation per participant; validators independently retrieve evidence and compare the normalized material result. Expired requests produce a timeout result. |
| supersede_relation | Court | Original request owner only. Original relation ID, newer DISTINCT successor ID and public reason. Subject digest, policy revision, consumer and consequence must match. The successor must have crossed finalized delivery and remain current. A successor manifest may contain an attested source revision. |
| quarantine_request | Court | Court owner or request owner. Assessed request ID and public reason. Emits finalized invalidation. |
| retry_delivery | Court | Permissionless. Assessed current request ID. Replays the original certificate, retaining its bindings. |
| receive_certificate | Directory | Authenticated court contract message emitted on finalized status. Private client calls are rejected. |
| propose_merge | Directory | Permissionless. Exact proof JSON: operation_id, left, right, scope and relation IDs. Every required pair must be present once. Checks direct DISTINCT indexes before affirmative support. At most six combined records, fifteen pairs and eight consumer bindings per pair. |
| finalize_alias | Directory | Permissionless. Pending merge operation ID. Rechecks complete proof, cluster membership, generation and every non merge edge at action time. |
| publish_alias | Directory | Permissionless. Delivered request ID. Requires a current certificate. SAME requires a complete finalized cluster. Emits only a finalized notice to the certificate's bound consumer. |
| recover_component | Directory | Permissionless. Scope, original event ID and delivered current DISTINCT correction ID. Conservatively restores singleton identities. Retired SAME certificates remain unusable. |
| invalidate_relation | Directory | Authenticated finalized court callback only. Relation ID and successor ID. Retains exact consumer revocation notices. |
| retry_invalidation | Directory | Permissionless. Revoked relation ID. Replays the exact stored finalized invalidation notice. |
| acknowledge | Directory | The certificate's bound consumer contract only. Operation ID and acknowledgement JSON. Conflicting acknowledgements fail. |
| register_reference | Each consumer | Its independent owner only. Event ID and reference ID. Checks approved occurrence types, policy and quarantine. Pending reservations count against capacity. |
| release_hold | Each consumer | Reservation owner only. Reference ID. Only an unapplied pending hold can be released. |
| apply_identity | Each consumer | Authenticated directory callback emitted on finalized status only. Checks original bindings, current relation and mappings, generation and restrictions. Persists operation acknowledgement. |
| invalidate_identity | Each consumer | Authenticated directory finalized callback only. Retires affected references without losing original event ID, original owner or evidence commitment. Older notices cannot remove a newer restriction. |

## Request and result

The request envelope contains request_id, owner, parties, policy_id, policy_revision, subject_id, subject_digest, source_manifest_digest, consumer_address, consequence_digest, generation and deadline. Addresses are normalized to lowercase. SHA256 digests use UTF8 JSON with sorted keys and compact separators. Arrays retain their order; records and canonical witnesses are sorted before commitment.

A result carries every envelope binding, left, right, scope, status, decision, vector, controlling_rules, witnesses, coverage, unresolved, common_cause and superseded_by. The vector has issuer, place, interval, occurrence_type and official_reference. Each entry is SAME, DISTINCT or UNKNOWN. Common cause is a separate field and never participates in union logic. Prose explanations are excluded from consensus equality.

Canonical witnesses are the committed locator for each attribute on both records, sorted by span ID. A locator contains span_id, attribute, start, end and raw_hash. Offsets are raw UTF8 bytes with an exclusive end. A complete record span is valid and includes contrary evidence; it is not a claim that every byte supports the result. Validators inspect the complete records and independently reconstruct the decision. Neither matching hashes nor URL prefixes prove authority or truth.

Controlling rule IDs are ALL_ATTRIBUTES, DISCRIMINATING_FACT, EVIDENCE_GAP, SOURCE_UNAVAILABLE, SOURCE_CHANGED, SOURCE_UNREADABLE, SOURCE_LIMIT, CONTEXT_LIMIT, AUTHORITY_UNRESOLVED and DEADLINE. Semantic exceptions are NONE, CONTRARY_FACT and EVIDENCE_GAP. Stable material fields and controlling witnesses must match; model prose need not match.

## States and consequences

| State | Meaning |
| :--- | :--- |
| pending | Request or complete merge proposal recorded; no application reuse permission. |
| accepted | Agreed assessment stored by the court. Delivery still needs the finalized message boundary. |
| finalized | Authenticated finalized callback accepted, or deterministic alias finalization completed. |
| unresolved | UNKNOWN or incomplete proof. Consumers retain reserved references with no accepted count or evidence reuse. |
| timeout | Supported transaction timestamp passed the locked deadline. No affirmative identity fact. |
| refused | Merge contradicts a known DISTINCT witness. Witness ID remains in the proposal history. |
| quarantined | Reuse is restricted. A correction cannot silently clear this state. |
| superseded | Original relation or alias retired by a correction. History remains readable. |
| delivery_failed | API operation has an execution failure or delivery recovery remains incomplete. It is a transport status, not a semantic verdict. |

Incident History accepts disclosed security incidents and operational notices. Release Evidence accepts software releases and operational notices. Each counts unique finalized canonical IDs among its own attributed references. Neither decides event outcomes, compensation or truth. Both use the explicit unresolved consequence `retain_pending_without_reuse`.

## Bounds

IDs contain at most 128 characters. Titles contain at most 180. URLs contain at most 2048. Reasons contain at most 2000. Requests contain at most 24576 UTF8 bytes. A source and its decoded text contain at most 49152 bytes or characters. Four retrievals cover two source records and two authority records. Complete retrieval context contains at most 98304 bytes. The final prompt must fit a conservative 49152 input token upper bound, using one UTF8 byte per token. There is one substantive model call per participant. The declared SDK does not expose a caller selected output token option; model output is validated by exact shape and bounded explanation lengths. Limits are rejection boundaries, not measured throughput claims.

Histories hold at most 10000 entries per deployment and have pages of 1 to 50 entries. Application attempts are bounded to three per evidence revision. Failed VM execution rolls back contract attempt increments; the application journal bounds submitted retries and the court additionally bounds successor request issuance per subject, manifest and consumer. No worker controls validator rotation or protocol finality.

Deadline evaluation uses `gl.message_raw['datetime']`, supplied by the supported runtime transaction context. The API proposes a deadline; its clock is not an oracle. Every validator uses the same supported transaction context.

## HTTP API

Public GET routes: /api/health, /api/config, /api/events, /api/events/:id, /api/relations/:id, /api/dockets/:id, /api/merges/:id and /api/applications. Search accepts q, kind, offset and limit and returns items, total and indexed_at. Index results are advisory caches.

Email authenticated POST routes: /api/sources/commit, /api/comparisons/prepare, /api/merges/prepare, /api/operations/prepare, /api/operations/broadcast and /api/challenges. Authenticated GET routes: /api/operations and /api/operations/:id. Every operation is prepared before signing and journaled by operation ID, signer, nonce, payload digest, original target address and directory address. Broadcast attachment verifies the actual transaction before recording it.

/api/reconcile accepts only the configured scheduler bearer secret. It discovers broadcasts missed during a crash, checks receipts, follows consumer acknowledgements and refreshes the derived index. It never produces an identity verdict.
