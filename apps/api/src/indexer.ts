import { read, policyScope } from "./chain.js";
import { sql } from "./db.js";
import type { Identity } from "@eventweave/protocol";
export async function rebuildIndex() {
  const rows =
    await sql()`SELECT offset_value FROM index_cursor WHERE name='registry'`;
  let offset = Number(rows[0]?.offset_value || 0);
  let items = await read<Identity[]>("registry", "list_events", [offset, 10]);
  if (!items.length && offset) {
    offset = 0;
    items = await read<Identity[]>("registry", "list_events", [0, 10]);
  }
  const scopes = new Map<string, string>();
  for (const original of items) {
    const key = original.schema_id + ":" + original.schema_revision;
    let scope = scopes.get(key);
    if (!scope) {
      const policy = await read<{ scope: string }>("registry", "get_schema", [
        original.schema_id,
        original.schema_revision,
      ]);
      scope = policyScope(
        policy.scope,
        original.schema_id,
        original.schema_revision,
      );
      scopes.set(key, scope);
    }
    const resolved = await read<{
      canonical_id: string;
      members: string[];
      generation: number;
      status: Identity["status"];
    }>("directory", "get_identity", [original.event_id, scope]);
    const descriptor = { ...original, ...resolved };
    await sql()`INSERT INTO event_index(event_id,descriptor,searchable) VALUES(${original.event_id},${JSON.stringify(descriptor)},${[original.title, original.issuer, original.place, original.official_reference, original.event_id].join(" ")}) ON CONFLICT(event_id) DO UPDATE SET descriptor=EXCLUDED.descriptor,searchable=EXCLUDED.searchable,indexed_at=now()`;
    offset++;
  }
  await sql()`INSERT INTO index_cursor(name,offset_value) VALUES('registry',${offset}) ON CONFLICT(name) DO UPDATE SET offset_value=EXCLUDED.offset_value,updated_at=now()`;
  return items.length;
}
export async function resetIndex() {
  await sql().transaction([
    sql()`DELETE FROM event_index`,
    sql()`DELETE FROM index_cursor WHERE name='registry'`,
  ]);
  return rebuildIndex();
}
