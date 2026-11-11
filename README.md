# EventWeave

A report can change its name without becoming a different occurrence. Two incidents at the same service can still be two incidents. EventWeave gives applications a shared place to make that distinction, keep the evidence and correct the record when a merge gets it wrong.

The registry covers public software releases, disclosed security incidents and official operational notices. GenLayer validators independently read committed public sources and compare the facts that identify an occurrence. A shared root cause is stored separately. It never becomes permission to merge.

## What you can do

Search the registry, put candidate records side by side, request an assessment and follow its delivery into an application. A complete merge proof checks every pair in a cluster of up to six records. One known DISTINCT witness is enough to refuse the union. Missing evidence stays unknown.

Incident History and Release Evidence are real consumer contracts with separate owners and their own acceptance rules. Finalized identity notices determine their accepted counts and evidence references. The API, the search index and the browser cannot give themselves that permission.

Email sign in uses Privy. The embedded signing account handles transactions behind the interface. There is no wallet login flow. Authority registration and issuer permissions remain explicit, so having an account does not make someone an official publisher.

## Run locally

Use Node 22.22 or newer within Node 22, and Python 3.13 or newer.

```sh
npm run setup
```

Setup installs the pinned dependencies, prepares the Python environment, checks the deployable contracts and builds the web app. It creates a private `.env` file from `.env.example` if one does not exist. Add the Privy server credentials, public Privy app ID and PostgreSQL connection there. Deployment keys belong in that ignored file or your secret manager. Never put them into frontend variables.

```sh
npm run db:migrate
npm run dev
```

The web app runs on port 5173 and the API on port 4317. In a separate process, run `npm run worker` to reconcile broadcasts and refresh the advisory index. Vercel also has an authenticated reconciliation endpoint; its scheduled frequency is described in the deployment guide.

## Repository

`apps/web` contains the React interface. `apps/api` contains the Fastify API, PostgreSQL migrations and recovery worker. `packages/protocol` owns canonical schemas, enums and limits. `packages/client` provides the GenLayer client. `contracts/src` and `contracts/lib` are the contract source; `contracts/deployable` contains the generated standalone files used on Studio. `tests`, `scripts`, `docs`, `deployments` and `verification` keep validation and operations separate from the product.

## Verify

```sh
npm run lint
npm run build
npm test
```

CI runs the same deterministic checks and captured validator probes. The controlled tests deliberately include wrong JSON verdicts, omitted exceptions, forged witnesses, changed source bytes and injected instructions. Controlled fixtures belong to tests and are never shown as production activity.

```sh
npm run network:verify
npm run verify:signed
```

These commands use real signed Studio transactions and authentic Node.js public documents. They consume network time and require configured owner keys. Their journals let an interrupted run resume without broadcasting completed operations again. Public source verification is an integration exercise, not a claim that Node.js or another application has adopted EventWeave.

The retained evidence and any outstanding limits are in [verification/README.md](verification/README.md). Deployed addresses and earlier deployments are in `deployments`. The runner is pinned to `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`.

## Deploy

The web app and API are configured for Vercel. GenLayer Studio hosts the contracts; PostgreSQL stores the derived index and operation journal. Follow [docs/deployment.md](docs/deployment.md) for environment setup and deployment recovery.

Read [docs/architecture.md](docs/architecture.md) for the trust boundaries and [docs/protocol.md](docs/protocol.md) for method permissions, canonical fields, lifecycle states and request limits. The generated [API schemas](docs/api-schemas.json) are suitable for client validation.

EventWeave resolves occurrence identity. It does not discover undisclosed incidents, establish every reported fact, decide an event outcome or award compensation. Sometimes the honest answer is still “we don’t know.” That answer keeps two histories from being woven together too soon.
