import { neon, type NeonQueryFunction } from "@neondatabase/serverless";
import { configuration } from "./config.js";
let client: NeonQueryFunction<false, false> | undefined;
export const sql = (): NeonQueryFunction<false, false> =>
  (client ??= neon(configuration().DATABASE_URL));
