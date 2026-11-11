import { config as loadEnvironment } from "dotenv";
import { fileURLToPath } from "node:url";
loadEnvironment({
  path: fileURLToPath(new URL("../../../.env", import.meta.url)),
  quiet: true,
});
import "./network.js";
import { readFileSync } from "node:fs";
import { z } from "zod";
import type { Deployment } from "@eventweave/protocol";
const schema = z.object({
  PRIVY_APP_ID: z.string().min(1),
  PRIVY_APP_SECRET: z.string().min(1),
  DATABASE_URL: z.string().startsWith("postgresql://"),
  WEB_ORIGIN: z.string().default("http://localhost:5173"),
  API_PORT: z.coerce.number().default(4317),
  GENLAYER_RPC_URL: z.url().default("https://studio.genlayer.com/api"),
});
export function configuration() {
  const result = schema.safeParse(process.env);
  if (!result.success)
    throw new Error(
      "Missing server configuration: " +
        result.error.issues.map((i) => i.path.join(".")).join(", "),
    );
  return result.data;
}
export function deployment(): Deployment | null {
  try {
    return JSON.parse(
      readFileSync(
        new URL("../../../deployments/studionet.json", import.meta.url),
        "utf8",
      ),
    );
  } catch {
    return null;
  }
}
