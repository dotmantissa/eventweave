# Deployment

Vercel serves the Vite build and the Fastify function at `/api`. GenLayer Studio chain 61999 runs the pinned Python contracts. Neon PostgreSQL stores the operation journal and the derived event index.

## Server configuration

Set PRIVY_APP_ID, PRIVY_APP_SECRET, DATABASE_URL, WEB_ORIGIN and CRON_SECRET in Vercel's encrypted environment configuration. WEB_ORIGIN is a comma separated list of exact permitted origins. VITE_PRIVY_APP_ID is public and belongs in the build environment. GENLAYER_RPC_URL defaults to https://studio.genlayer.com/api. No private signing key belongs in Vercel: the user's embedded signing provider broadcasts their signed operations.

The deployer and consumer owner keys are needed only for signed configuration, contract deployment and integration verification. The two consumer keys are separately generated and stored locally in the ignored `.secrets/consumer-owners.env`. Preserve that file securely between runs; replacing the keys changes ownership.

Configure Privy's email login, embedded Ethereum signing accounts and allowed production origins in its dashboard. GenLayer Studio is the supported custom chain. The application code admits email authentication only. A real person must complete their email verification before a browser signing session exists.

## Application deployment

Run the database migrations before first launch:

```sh
npm run db:migrate
vercel deploy --prod
```

The root `vercel.json` builds the web workspace and packages `api/index.ts` as a server function. Root rewrites keep client routes accessible on refresh. Keep private variables on the server; Vite exports only its public app ID and public API base.

The build first compiles the shared workspaces to JavaScript. Their runtime exports
must resolve to `dist/index.js`, and relative API imports use `.js` extensions for
Node ESM. Node is bounded to version 22 in both the package manifest and Vercel
settings. For a local packaged-function check, run `vercel build --prod`, inspect
`.vercel/output/functions/api/index.func`, then deploy with
`vercel deploy --prebuilt --prod`. The active deployment manifest is explicitly
included in the function; `.vercelignore` excludes environment files and keys.

The included Vercel schedule runs reconciliation daily to fit the basic scheduler allowance. Interactive delivery state is read directly from the contracts. For continuous index and journal refresh, run `npm run worker` in a persistent service, or configure a more frequent authenticated Vercel schedule on a plan that supports it. A worker can inspect, schedule or reconcile transactions; it cannot author an identity verdict.

## Contract deployment

```sh
npm run deploy:contracts -- --revision=3 --fresh-registry
```

Deployments are journaled before waiting for finalization. Resume with the same command and the same secure key sources. Existing successful operations are not repeated. A new revision archives the preceding address manifest. Constructor and consumer configuration bindings are explicit.

The current application manifest is `deployments/studionet.json`. Keep earlier manifests because original consumer histories remain at their original addresses. An incompatible deployment does not migrate storage or make an older certificate current. API operation journals retain their original target and directory addresses so reconciliation cannot accidentally attach an old broadcast to a replacement deployment.

## Recovery

A browser prepares an operation before signing. The server stores the signer, nonce, exact payload digest and operation ID. If the browser or worker ends after broadcast, reconciliation searches the signer's transaction history and accepts only the exact matching transaction. It checks execution as well as protocol status. An accepted transaction is not finality proof.

Court delivery can be replayed with `retry_delivery`. Consumer delivery can be replayed with `publish_alias`. Revoked notices can be replayed with `retry_invalidation`. These methods retain the original certificate or revocation bindings. Consumers persist acknowledgements and reject conflicting, stale or restricted generations.

After a mistaken merge, obtain a newer delivered DISTINCT certificate, supersede the original relation, wait for invalidation, then recover the affected component and publish the successor notice. Original consumer references and source commitments remain attributed throughout. The web challenge flow exposes these actions.

The deterministic index can be discarded and rebuilt from registry event order. Reconciliation also cycles through existing records to refresh alias state. Index search is advisory; cached rows never authorize consumer effects.
