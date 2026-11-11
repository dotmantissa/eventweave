import { writeFileSync } from "node:fs";
import { z } from "zod";
import {
  descriptorSchema,
  envelopeSchema,
  sourceSchema,
  spanSchema,
  compareSchema,
  mergeProofSchema,
  prepareSchema,
  broadcastSchema,
  challengeSchema,
  decisionSchema,
  lifecycleSchema,
  limits,
} from "@eventweave/protocol";
const schemas = {
  envelope: envelopeSchema,
  descriptor: descriptorSchema,
  source: sourceSchema,
  witness: spanSchema,
  comparison: compareSchema,
  merge_proof: mergeProofSchema,
  operation: prepareSchema,
  broadcast: broadcastSchema,
  challenge: challengeSchema,
  decision: decisionSchema,
  lifecycle: lifecycleSchema,
};
writeFileSync(
  "docs/api-schemas.json",
  JSON.stringify(
    {
      limits,
      schemas: Object.fromEntries(
        Object.entries(schemas).map(([name, schema]) => [
          name,
          z.toJSONSchema(schema, { io: "input", unrepresentable: "any" }),
        ]),
      ),
    },
    null,
    2,
  ) + "\n",
);
