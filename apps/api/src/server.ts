import { buildApp } from "./app.js";
import { configuration } from "./config.js";
const app = await buildApp();
await app.listen({ port: configuration().API_PORT, host: "0.0.0.0" });
