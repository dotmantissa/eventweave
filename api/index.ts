import type { IncomingMessage, ServerResponse } from "node:http";
import { buildApp } from "../apps/api/src/app.js";
const ready = buildApp();
export default async function handler(
  req: IncomingMessage,
  res: ServerResponse,
) {
  const app = await ready;
  await app.ready();
  app.server.emit("request", req, res);
}
