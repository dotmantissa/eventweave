import Fastify from "fastify";
import cors from "@fastify/cors";
import helmet from "@fastify/helmet";
import rateLimit from "@fastify/rate-limit";
import { z } from "zod";
import { randomUUID } from "node:crypto";
import {
  limits,
  broadcastSchema,
  challengeSchema,
  prepareSchema,
  type Identity,
  type Certificate,
  canonical,
  idSchema,
  mergeProofSchema,
  type Docket,
} from "@eventweave/protocol";
import { authenticate, HttpError } from "./auth.js";
import { configuration, deployment } from "./config.js";
import { sql } from "./db.js";
import {
  read,
  identity,
  relations,
  hash,
  pairId,
  policyScope,
} from "./chain.js";
import {
  prepareOperation,
  attachBroadcast,
  userOperations,
} from "./operations.js";
import { commitSource, sourceInput } from "./sources.js";
import { reconcile } from "./worker.js";
import { rebuildIndex } from "./indexer.js";
export async function buildApp() {
  const app = Fastify({
    logger: {
      level: "info",
      redact: [
        "req.headers.authorization",
        "req.headers.cookie",
        "res.headers.set-cookie",
      ],
    },
    bodyLimit: limits.requestBytes,
  });
  await app.register(cors, {
    origin: configuration()
      .WEB_ORIGIN.split(",")
      .map((s) => s.trim()),
    credentials: false,
  });
  await app.register(helmet);
  await app.register(rateLimit, { max: 40, timeWindow: "1 minute" });
  app.setErrorHandler((error, _request, reply) => {
    if (error instanceof HttpError)
      return reply.status(error.statusCode).send({ error: error.message });
    if (error instanceof z.ZodError || error instanceof SyntaxError)
      return reply.status(400).send({
        error: "Some request fields are invalid.",
        fields:
          error instanceof z.ZodError
            ? error.issues.map((i) => ({
                path: i.path.join("."),
                message: i.message,
              }))
            : [],
      });
    const status =
      error &&
      typeof error === "object" &&
      "statusCode" in error &&
      typeof error.statusCode === "number"
        ? error.statusCode
        : 503;
    return reply.status(status).send({
      error:
        status === 429
          ? "A few too many requests. Give the service a moment."
          : "This service is temporarily unavailable. Your signed history is retained.",
    });
  });
  app.get("/api/health", async () => ({ status: "ok", service: "eventweave" }));
  app.get("/api/config", async () => ({
    deployment: deployment(),
    network: "studionet",
    ready: Boolean(deployment()),
    limits,
  }));
  app.get("/api/events", async (request) => {
    const query = z
      .object({
        q: z.string().max(180).default(""),
        kind: z
          .enum(["", "release", "security_incident", "operational_notice"])
          .default(""),
        offset: z.coerce.number().int().min(0).default(0),
        limit: z.coerce.number().int().min(1).max(50).default(25),
      })
      .parse(request.query);
    const freshness =
      await sql()`SELECT MAX(indexed_at) AS latest FROM event_index`;
    if (
      !freshness[0]?.latest ||
      Date.now() - new Date(freshness[0].latest).getTime() > 60000
    )
      await rebuildIndex();
    const result =
      await sql()`SELECT descriptor,indexed_at,count(*) OVER()::integer AS total FROM event_index WHERE (${query.q}='' OR searchable ILIKE ${"%" + query.q.replace(/[\\%_]/g, "\\$&") + "%"}) AND (${query.kind}='' OR descriptor->>'occurrence_type'=${query.kind}) ORDER BY descriptor->>'interval_start' DESC,event_id LIMIT ${query.limit} OFFSET ${query.offset}`;
    const items: Identity[] = [];
    for (const row of result) {
      const original = row.descriptor as Identity;
      items.push({
        ...original,
        canonical_id: original.canonical_id || original.event_id,
        members: original.members || [original.event_id],
        generation: original.generation || 0,
        status: original.status || "pending",
      });
    }
    return {
      items,
      total: result[0]?.total || 0,
      indexed_at: result[0]?.indexed_at || null,
    };
  });
  app.get<{ Params: { id: string } }>("/api/events/:id", async (request) => {
    const id = z.string().min(1).max(128).parse(request.params.id);
    const event = await identity(id);
    const relation = await relations(id);
    const aliases = await read<Record<string, unknown>[]>(
      "directory",
      "get_alias_history",
      [0, 50],
    );
    return {
      identity: event,
      relations: relation,
      aliases: aliases.filter((a) => a.event_id === id),
    };
  });
  app.get<{ Params: { id: string } }>("/api/relations/:id", async (request) =>
    read<Certificate>("directory", "get_relation", [
      z.string().min(1).max(128).parse(request.params.id),
    ]),
  );
  app.get<{ Params: { id: string } }>("/api/dockets/:id", async (request) => {
    const id = idSchema.parse(request.params.id);
    const docket = await read<Docket["request"]>("court", "get_request", [id]);
    const delivery = await read<Docket["delivery"]>(
      "directory",
      "get_acknowledgement",
      [id],
    );
    let result: Certificate | null = null;
    if (delivery.request_id)
      result = await read<Certificate>("directory", "get_relation", [id]);
    else {
      try {
        result = await read<Certificate>("court", "get_result", [id]);
      } catch (error) {
        if (!String(error).includes("No assessed result")) throw error;
      }
    }
    const addresses = deployment()!;
    const consumer =
      docket.envelope.consumer_address === addresses.incident.toLowerCase()
        ? "incident"
        : "release";
    const consumer_ack = await read<Docket["consumer_ack"]>(
      consumer,
      "get_acknowledgement",
      ["delivery:" + id],
    );
    return { request: docket, result, delivery, consumer_ack };
  });
  app.get<{ Params: { id: string } }>("/api/merges/:id", async (request) =>
    read("directory", "get_merge", [idSchema.parse(request.params.id)]),
  );
  app.post("/api/merges/prepare", async (request) => {
    await authenticate(request);
    const input = z
      .object({
        left: idSchema,
        right: idSchema,
        relations: z.array(idSchema).min(1).max(limits.clusterPairs),
      })
      .strict()
      .parse(request.body);
    const original = await read<Identity>("registry", "get_identity", [
      input.left,
    ]);
    const policy = await read<{ scope: string }>("registry", "get_schema", [
      original.schema_id,
      original.schema_revision,
    ]);
    const scope = policyScope(
      policy.scope,
      original.schema_id,
      original.schema_revision,
    );
    const identities = await Promise.all(
      [input.left, input.right].map((id) =>
        read<Identity>("directory", "get_identity", [id, scope]),
      ),
    );
    const members = [...new Set(identities.flatMap((i) => i.members))].sort();
    if (members.length > limits.clusterRecords)
      throw new HttpError(
        409,
        "This cluster exceeds six records. It remains unresolved; no partial merge can be submitted.",
      );
    const proof = mergeProofSchema.parse({
      ...input,
      scope,
      operation_id: "merge." + randomUUID().replaceAll("-", ""),
    });
    const required_pairs = members.flatMap((a, i) =>
      members.slice(i + 1).map((b) => [a, b]),
    );
    return { proof_json: canonical(proof), members, required_pairs };
  });
  app.get("/api/applications", async () => {
    const addresses = deployment();
    if (!addresses) return { items: [] };
    const items = [];
    for (const [key, name] of [
      ["incident", "Incident History"],
      ["release", "Release Evidence"],
    ] as const) {
      const config = await read<Record<string, unknown>>(
        key,
        "get_configuration",
      );
      const stats = await read<Record<string, number>>(key, "get_stats");
      items.push({
        name,
        address: addresses[key],
        owner: config.owner,
        stats,
        configuration: config,
      });
    }
    return { items };
  });
  app.post("/api/sources/commit", async (request) => {
    const auth = await authenticate(request);
    return {
      source: await commitSource(sourceInput.parse(request.body), auth.signer),
    };
  });
  app.post("/api/comparisons/prepare", async (request) => {
    const auth = await authenticate(request);
    const input = z
      .object({
        left: z.string().min(1).max(128),
        right: z.string().min(1).max(128),
        consumer: z.enum(["incident", "release"]),
      })
      .strict()
      .parse(request.body);
    if (input.left === input.right)
      throw new HttpError(400, "Choose two different records.");
    const records = [
      await read<Identity>("registry", "get_identity", [input.left]),
      await read<Identity>("registry", "get_identity", [input.right]),
    ].sort((a, b) => a.event_id.localeCompare(b.event_id));
    if (
      records[0].schema_id !== records[1].schema_id ||
      records[0].schema_revision !== records[1].schema_revision
    )
      throw new HttpError(400, "The records use different policy revisions.");
    const policy = await read<{ scope: string }>("registry", "get_schema", [
      records[0].schema_id,
      records[0].schema_revision,
    ]);
    const scope = policyScope(
      policy.scope,
      records[0].schema_id,
      records[0].schema_revision,
    );
    const subject_id = pairId(input.left, input.right, scope);
    const generation =
      Number(await read<number>("court", "get_generation", [subject_id])) + 1;
    const consumer = await read<{
      consequence_digest: string;
      policy_id: string;
      policy_revision: number;
    }>(input.consumer, "get_configuration");
    const addresses = deployment()!;
    const bound = {
      request_id: "request." + randomUUID().replaceAll("-", ""),
      owner: auth.signer,
      parties: [auth.signer],
      policy_id: records[0].schema_id,
      policy_revision: records[0].schema_revision,
      subject_id,
      subject_digest: hash(
        records.map((r) => ({
          event_id: r.event_id,
          descriptor_digest: r.descriptor_digest,
        })),
      ),
      source_manifest_digest: hash(records.map((r) => r.source)),
      consumer_address: addresses[input.consumer].toLowerCase(),
      consequence_digest: consumer.consequence_digest,
      generation,
      deadline: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
    };
    return {
      request_json: canonical({
        envelope: bound,
        left: input.left,
        right: input.right,
      }),
    };
  });
  app.post("/api/operations/prepare", async (request) =>
    prepareOperation(
      prepareSchema.parse(request.body),
      await authenticate(request),
    ),
  );
  app.post("/api/operations/broadcast", async (request) => {
    const input = broadcastSchema.parse(request.body);
    return attachBroadcast(
      input.operation_id,
      input.transaction_hash as `0x${string}`,
      await authenticate(request),
    );
  });
  app.get("/api/operations", async (request) => ({
    items: await userOperations((await authenticate(request)).user_id),
  }));
  app.get<{ Params: { id: string } }>(
    "/api/operations/:id",
    async (request) => {
      const auth = await authenticate(request);
      const rows =
        await sql()`SELECT operation_id,contract,method,args,status,transaction_hash FROM operation_journal WHERE operation_id=${z.string().uuid().parse(request.params.id)} AND user_id=${auth.user_id}`;
      if (!rows.length) throw new HttpError(404, "Operation not found.");
      return rows[0];
    },
  );
  app.post("/api/challenges", async (request) => {
    const auth = await authenticate(request);
    const input = challengeSchema.parse(request.body);
    const relation = await read<Certificate>("court", "get_result", [
      input.relation_id,
    ]);
    if (relation.owner !== auth.signer)
      throw new HttpError(
        403,
        "Only the original request owner can apply this correction.",
      );
    const challenge_id = randomUUID();
    await sql()`INSERT INTO challenge_journal(challenge_id,user_id,relation_id,successor_id,reason) VALUES(${challenge_id},${auth.user_id},${input.relation_id},${input.successor_id},${input.reason})`;
    return { challenge_id, status: "pending" };
  });
  app.get("/api/reconcile", async (request) => {
    const secret = process.env.CRON_SECRET;
    if (!secret || request.headers.authorization !== "Bearer " + secret)
      throw new HttpError(401, "Scheduler authentication required.");
    return { reconciled: await reconcile() };
  });
  return app;
}
