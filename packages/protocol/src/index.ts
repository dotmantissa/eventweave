import { z } from "zod";

export const limits = {
  sourceBytes: 49152,
  decodedChars: 49152,
  contextBytes: 98304,
  sourceCount: 4,
  clusterRecords: 6,
  clusterPairs: 15,
  requestBytes: 24576,
  promptChars: 110000,
  inputTokenUpperBound: 49152,
  retries: 3,
  pageSize: 50,
} as const;
export const attributes = [
  "issuer",
  "place",
  "interval",
  "occurrence_type",
  "official_reference",
] as const;
export const decisionSchema = z.enum(["SAME", "DISTINCT", "UNKNOWN"]);
export const lifecycleSchema = z.enum([
  "pending",
  "accepted",
  "finalized",
  "unresolved",
  "timeout",
  "superseded",
  "quarantined",
  "delivery_failed",
]);
export const kindSchema = z.enum([
  "release",
  "security_incident",
  "operational_notice",
]);
export const idSchema = z
  .string()
  .min(1)
  .max(128)
  .regex(/^[a-zA-Z0-9_.:]+$/);
export const hashSchema = z.string().regex(/^[a-f0-9]{64}$/);
export const addressSchema = z
  .string()
  .regex(/^0x[a-fA-F0-9]{40}$/)
  .transform((s) => s.toLowerCase());
const revision = z.number().int().min(1).max(4294967295);
export const envelopeSchema = z
  .object({
    request_id: idSchema,
    owner: addressSchema,
    parties: z.array(addressSchema).min(1).max(6),
    policy_id: idSchema,
    policy_revision: revision,
    subject_id: idSchema,
    subject_digest: hashSchema,
    source_manifest_digest: hashSchema,
    consumer_address: addressSchema,
    consequence_digest: hashSchema,
    generation: revision,
    deadline: z.iso.datetime({ offset: true }),
  })
  .strict();
export const spanSchema = z
  .object({
    span_id: idSchema,
    attribute: z.enum(attributes),
    start: z.number().int().min(0),
    end: z.number().int().min(1).max(limits.sourceBytes),
    raw_hash: hashSchema,
  })
  .strict()
  .refine((v) => v.start < v.end, "A span must contain bytes");
export const sourceSchema = z
  .object({
    record_id: idSchema,
    authority_id: idSchema,
    channel: idSchema,
    url: z
      .url()
      .max(2048)
      .refine((v) => v.startsWith("https://"), "Use a public HTTPS source"),
    raw_hash: hashSchema,
    revision: idSchema,
    scope: idSchema,
    byte_length: z.number().int().min(1).max(limits.sourceBytes),
    spans: z.array(spanSchema).length(5),
  })
  .strict()
  .superRefine((s, c) => {
    if (
      new Set(s.spans.map((v) => v.attribute)).size !== 5 ||
      s.spans.some((v) => v.raw_hash !== s.raw_hash || v.end > s.byte_length)
    )
      c.addIssue({
        code: "custom",
        message: "Every identity attribute needs a valid committed span",
      });
  });
export const descriptorSchema = z
  .object({
    event_id: idSchema,
    schema_id: idSchema,
    schema_revision: revision,
    title: z.string().min(3).max(180),
    issuer: z.string().min(1).max(128),
    place: z.string().min(1).max(128),
    interval_start: z.iso.datetime({ offset: true }),
    interval_end: z.iso.datetime({ offset: true }),
    occurrence_type: kindSchema,
    official_reference: z.string().min(1).max(128),
    source: sourceSchema,
  })
  .strict()
  .refine(
    (v) => Date.parse(v.interval_end) >= Date.parse(v.interval_start),
    "The interval ends before it begins",
  );
export const compareSchema = z
  .object({ envelope: envelopeSchema, left: idSchema, right: idSchema })
  .strict()
  .refine((v) => v.left !== v.right, "Choose two different records");
export const challengeSchema = z
  .object({
    relation_id: idSchema,
    successor_id: idSchema,
    reason: z.string().min(20).max(2000),
  })
  .strict();
export const prepareSchema = z
  .object({
    operation_id: z.string().uuid(),
    contract: z.enum(["registry", "court", "directory", "incident", "release"]),
    method: idSchema,
    args: z.array(z.union([z.string(), z.number().int(), z.boolean()])).max(10),
  })
  .strict();
export const broadcastSchema = z
  .object({
    operation_id: z.string().uuid(),
    transaction_hash: z.string().regex(/^0x[a-fA-F0-9]{64}$/),
  })
  .strict();
export type Envelope = z.infer<typeof envelopeSchema>;
export type Descriptor = z.infer<typeof descriptorSchema>;
export type Source = z.infer<typeof sourceSchema>;
export type Lifecycle = z.infer<typeof lifecycleSchema>;
export type Decision = z.infer<typeof decisionSchema>;
export interface Identity extends Descriptor {
  owner: string;
  descriptor_digest: string;
  canonical_id: string;
  generation: number;
  status: Lifecycle;
  members: string[];
  quarantined: boolean;
  original_source: Source;
}
export interface Certificate extends Envelope {
  status: Lifecycle;
  decision: Decision;
  vector: Record<(typeof attributes)[number], Decision>;
  controlling_rules: string[];
  witnesses: Record<string, string[]>;
  coverage: boolean;
  unresolved: boolean;
  superseded_by: string;
  left: string;
  right: string;
  scope: string;
}
export interface Operation {
  operation_id: string;
  contract: string;
  method: string;
  transaction_hash: string | null;
  status: Lifecycle;
  error: string | null;
  created_at: string;
  acknowledged: boolean;
  args: (string | number | boolean)[];
}
export interface Docket {
  request: {
    envelope: Envelope;
    left: string;
    right: string;
    attempts: number;
  };
  result: Certificate | null;
  delivery: { request_id?: string; status?: Lifecycle; generation?: number };
  consumer_ack: {
    request_id?: string;
    status?: Lifecycle;
    generation?: number;
  };
}
export const mergeProofSchema = z
  .object({
    operation_id: idSchema,
    left: idSchema,
    right: idSchema,
    scope: z.string().min(1).max(512),
    relations: z.array(idSchema).min(1).max(limits.clusterPairs),
  })
  .strict()
  .refine(
    (v) =>
      v.left !== v.right && new Set(v.relations).size === v.relations.length,
    "Choose distinct records and unique certificates",
  );
export interface MergeProposal extends z.infer<typeof mergeProofSchema> {
  members: string[];
  canonical_id: string;
  status: Lifecycle | "refused";
  witness: string;
}
export interface Deployment {
  network: string;
  revision?: number;
  chain_id: number;
  registry: `0x${string}`;
  court: `0x${string}`;
  directory: `0x${string}`;
  incident: `0x${string}`;
  release: `0x${string}`;
  signer: string;
  incident_owner: string;
  release_owner: string;
}
export const canonical = (value: unknown): string => {
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  if (value && typeof value === "object")
    return (
      "{" +
      Object.entries(value)
        .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
        .map(([k, v]) => JSON.stringify(k) + ":" + canonical(v))
        .join(",") +
      "}"
    );
  return JSON.stringify(value);
};
