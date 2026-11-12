# Verification evidence

EventWeave is deployed at https://eventweave.vercel.app. This directory records
controlled tests, signed network operations and authentic public-source exercises.
Public verification records do not represent adoption by Node.js or another issuer.

## Deterministic verification

The current suites pass 49 TypeScript tests and 52 Python tests. They exercise API
authentication, request limits, private source rejection, exact signed operation
recovery, execution/finality classification, source commitments, immutable
revisions, merge bounds, DISTINCT constraints, correction invalidation and replay.
Lifecycle regressions cover complete six-record recovery partitions, outstanding
callbacks, consumed authorization provenance, component-wide count updates,
late references, owner-only requests and reversible DISTINCT constraints.
Captured validator tests reject wrong vectors, omitted exceptions, forged spans,
changed source bytes, injected instructions and fabricated model-error outcomes.

Build, typecheck, ESLint, formatting and all seven deployable-contract lint checks
pass. The dependencies are locked and a clean installation completed. Browser
review covers the public registry, comparison workspace, registration, challenges,
applications, record history, guide and activity at mobile, tablet and desktop
sizes. Screenshots stay in the ignored local review directory.
The same 24 route checks also passed against Vite's compiled production preview;
development rendering alone did not catch a React chunk initialization failure.
Automatic Rollup chunking replaces that failing manual split.
The final Vercel deployment also passes all 24 browser route checks and eight
HTTP checks, including refusal of unauthenticated protected actions and scheduler
calls. `web-deployment.json`, `production-checks.json` and `ui-review.json` record
the deployment and results. The email sign-in form opens without a page error;
`email-ui-check.json` distinguishes automated form inspection from the user's
completed email sign-in and actual embedded-wallet signing. The signed browser
publication finalized and its consumer acknowledgement was recovered; see
`browser-signing.v6.json`.

## Studio evidence and deployment revisions

The active manifest is `deployments/studionet.json`, revision 6 on Studio chain
61999. Earlier manifests retain their original contract addresses and owners.
The revision 4 registry is retained; four revision 6 replacement contracts and
their configuration transactions finalized successfully. Source and constructor
commitments are retained in `deployment-receipts.v4.json` and
`deployment-receipts.v6.json`.

The source exercise commits complete Node.js public Markdown documents at Git
revision `c09d4686360dd88cd41fd048b0e9ebd9045c3d5a` for releases, and published
notice amendments at `5f194a11346275b1187ef66ec4d2c230e587f328` and
`642c2c232041b06d5bfb9ee65c90b83e4c79bc47`. The amendments have different
URLs, hashes and complete bytes (4,388 and 4,921). The manifests record exact
URLs, byte lengths, hashes, authority bindings and witness spans.

- Revision 2 finalized both renamed-notice comparisons as SAME and the two
  release versions as DISTINCT, with court, directory and consumer delivery.
  The independent consumers reached accepted counts of one and three. See
  `public-source-receipts.v2.json` and the archived revision 2 manifest.
- Revision 3 finalized both renamed-notice comparisons as SAME and acknowledged
  delivery into both independently owned consumers. See
  `public-source-results.v3.json` and `public-source-receipts.v3.json`.
- All three bounded revision 3 release-assessment attempts finalized with
  MAJORITY_DISAGREE. Their leaders executed successfully, but independent
  validators refused their proposals. The failed attempts remain in the journal;
  no DISTINCT certificate or release delivery is claimed for this revision.
  These release references remain reserved. Network disagreement is a remaining
  verification limitation, not permission to substitute a deterministic verdict.
- Revisions 5 and 6 finalized both independently published notice-amendment
  comparisons as SAME and separate releases as DISTINCT, with delivery into
  the independently owned consumers. Revision 6 accepted counts are one and
  three, with two and four original references. See
  `public-source-results.v6.json` and `public-source-receipts.v6.json`.

`consumer-state.json` confirms the current state at both sets of addresses:
revision 2 accepted counts are one and three; revision 3 accepted counts are one
and one, with two and five original reserved references respectively. One of the
revision 3 release references belongs to the interrupted-broadcast recovery probe.

`consumer-state.json` also retains the revision 6 bindings and verified counts.
The signed JavaScript client separately reserved both authentic release references
with their independent owner. `signed-client-receipts.v3.json` binds each hash to
the active consumer address and checks successful finalized execution. The older
unversioned signed journal belongs to the earlier verification run.

## Interrupted broadcast recovery

The recovery probe prepared an owner-authorized reference reservation and stopped
after broadcast, before attaching its hash to the API journal. The worker recovered
the original transaction by matching signer, destination, nonce and decoded binary
calldata against the prepared digest. `recovery-result.json` records the matching
hash, finalized execution and acknowledgement. Recovery never rebinds an existing
operation to a replacement deployment.

The revision 6 SDK probe deliberately omitted attachment of a signed, idempotent
publication. `recovery-broadcast.v6.json` and `recovery-result.v6.json` retain the
exact original transaction and finalized acknowledgement. The real browser's
first signed transaction independently exposed numeric nonce zero being dropped
by the SDK's Ethereum formatter. Attachment now checks the original RPC response;
`browser-signing.v6.json` confirms exact recovery and successful raw attachment.

## Actual adversarial correction verification

`injection-results.v6.json` records an actual multi-validator assessment on
explicitly controlled, published fixtures in isolated contracts assembled from
the same deployed source. The probe establishes SAME, revises one committed
source, and obtains DISTINCT despite an embedded instruction demanding SAME.
Consumed references are invalidated and acknowledged; complete recovery restores
two distinct occurrences, and recovery replay leaves the count unchanged.
Deployment commitments and receipts remain in `injection-deployment.v6.json` and
`injection-receipts.v6.json`. Controlled fixtures never enter the production
registry. This finite probe does not establish universal prompt-injection resistance.

## Remaining limits

Studio imposed 30-read-per-minute and 500-request-per-hour limits during combined
verification. Runs resume from immutable receipt journals; receipt polling now
runs every fifteen seconds. Repeating an exhausted assessment requires investigation
and a successor request; the scripts will not perform a fourth blind retry.

The user completed email authentication and signed a production publication.
Automated browser checks inspect the email form without sending a challenge;
they do not impersonate that human session. Privy signing also requires a correct
device clock: an expired request header was reported before the successful
transaction. Configure the production origin in Privy's dashboard as described
in the deployment guide.

The updated pinned dependency tree passes clean installation, build and tests.
The current retained npm audit reports zero vulnerabilities. This is the package
manager's advisory result, rather than proof that dependencies have no defects.

Vercel's included schedule reconciles daily. Continuous refresh requires the
persistent worker or a scheduler plan with a higher frequency. Studio availability,
model disagreement and changing public sources can leave an assessment unresolved.
