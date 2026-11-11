# Verification evidence

EventWeave is deployed at https://eventweave.vercel.app. This directory records
controlled tests, signed network operations and authentic public-source exercises.
Public verification records do not represent adoption by Node.js or another issuer.

## Deterministic verification

The current suites pass 27 TypeScript tests and 29 Python tests. They exercise API
authentication, request limits, private source rejection, exact signed operation
recovery, execution/finality classification, source commitments, immutable
revisions, merge bounds, DISTINCT constraints, correction invalidation and replay.
Captured validator tests reject wrong vectors, omitted exceptions, forged spans,
changed source bytes, injected instructions and fabricated model-error outcomes.

Build, typecheck, ESLint, formatting and all six deployable-contract lint checks
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
`email-ui-check.json` explicitly records that no email was sent or challenge
completed.

## Studio evidence and deployment revisions

The active manifest is `deployments/studionet.json`, revision 3 on Studio chain
61999. Earlier manifests retain their original contract addresses and owners.
Five revision 3 deployments and their configuration transactions finalized with
successful execution; see `deployment-receipts.v3.json`.

The source exercise commits complete Node.js public Markdown documents at Git
revision `c09d4686360dd88cd41fd048b0e9ebd9045c3d5a`. The manifests record exact
URLs, byte lengths, hashes, authority bindings and witness spans.

- Revision 2 finalized both renamed-notice comparisons as SAME and the two
  release versions as DISTINCT, with court, directory and consumer delivery.
  The independent consumers reached accepted counts of one and three. See
  `public-source-receipts.v2.json` and the archived revision 2 manifest.
- Revision 3 finalized both renamed-notice comparisons as SAME and acknowledged
  delivery into both independently owned consumers. See
  `public-source-results.json` and `public-source-receipts.v3.json`.
- All three bounded revision 3 release-assessment attempts finalized with
  MAJORITY_DISAGREE. Their leaders executed successfully, but independent
  validators refused their proposals. The failed attempts remain in the journal;
  no DISTINCT certificate or release delivery is claimed for this revision.
  These release references remain reserved. Network disagreement is a remaining
  verification limitation, not permission to substitute a deterministic verdict.

`consumer-state.json` confirms the current state at both sets of addresses:
revision 2 accepted counts are one and three; revision 3 accepted counts are one
and one, with two and five original reserved references respectively. One of the
revision 3 release references belongs to the interrupted-broadcast recovery probe.

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

## Remaining limits

Studio imposed a 30-read-per-minute limit during the combined browser and network
checks. Verification resumes from immutable receipt journals, and bounded polling
runs every five seconds. Repeating an exhausted assessment requires investigation
and a successor request; the scripts will not perform a fourth blind retry.

A real email verification and embedded-account browser signing session still
require a person to complete Privy's email challenge. Signed SDK transactions and
unauthenticated API refusal have been verified; a completed human login is not
claimed. Configure the production origin in Privy's dashboard as described in the
deployment guide.

The retained npm audit reports 35 upstream dependency findings: 18 moderate and
17 high, largely in authentication and wallet dependency trees. Direct application
packages were updated during implementation, but this is not a zero-advisory
release. The authentication dependencies need a separately validated upgrade.

Vercel's included schedule reconciles daily. Continuous refresh requires the
persistent worker or a scheduler plan with a higher frequency. Studio availability,
model disagreement and changing public sources can leave an assessment unresolved.
