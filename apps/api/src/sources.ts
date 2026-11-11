import { createHash } from "node:crypto";
import { lookup } from "node:dns/promises";
import { Agent, ProxyAgent, fetch } from "undici";
import { isIP } from "node:net";
import { z } from "zod";
import {
  attributes,
  limits,
  idSchema,
  sourceSchema,
  type Source,
} from "@eventweave/protocol";
import { read } from "./chain.js";
import { HttpError } from "./auth.js";
export const sourceInput = z
  .object({
    url: z.url().max(2048),
    authority_id: idSchema,
    record_id: idSchema,
    revision: idSchema,
  })
  .strict();
export function privateAddress(ip: string) {
  if (!isIP(ip)) return true;
  if (ip.includes(":"))
    return (
      !/^[23]/.test(ip) ||
      ip === "::1" ||
      ip === "::" ||
      /^f[cd]/i.test(ip) ||
      /^fe[89ab]/i.test(ip) ||
      ip.toLowerCase().startsWith("::ffff:")
    );
  const parts = ip.split(".").map(Number);
  return (
    parts[0] === 0 ||
    parts[0] === 10 ||
    parts[0] === 127 ||
    parts[0] >= 224 ||
    (parts[0] === 198 && (parts[1] === 18 || parts[1] === 19)) ||
    (parts[0] === 192 && parts[1] === 0) ||
    (parts[0] === 169 && parts[1] === 254) ||
    (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) ||
    (parts[0] === 192 && parts[1] === 168) ||
    (parts[0] === 100 && parts[1] >= 64 && parts[1] <= 127)
  );
}
export async function commitSource(
  input: z.infer<typeof sourceInput>,
  signer: string,
): Promise<Source> {
  const authority = await read<{
    principal: string;
    url_prefix: string;
    channel: string;
    scope: string;
  }>("registry", "get_authority", [input.authority_id]);
  if (authority.principal !== signer)
    throw new HttpError(
      403,
      "Your signing account is not the configured principal for this authority.",
    );
  const url = new URL(input.url);
  const prefix = new URL(authority.url_prefix);
  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    (url.port && url.port !== "443") ||
    url.hostname !== prefix.hostname ||
    !channelUrl(input.url, authority.url_prefix)
  )
    throw new HttpError(
      400,
      "Use a public HTTPS URL within the configured authority channel.",
    );
  const raw = await fetchPublicSource(url);
  const length = raw.length;
  let decoded: string;
  try {
    decoded = new TextDecoder("utf-8", { fatal: true }).decode(raw);
  } catch {
    throw new HttpError(422, "The source is not valid UTF 8 text.");
  }
  if (!length || decoded.length > limits.decodedChars)
    throw new HttpError(
      413,
      "The complete source is empty or exceeds the text budget.",
    );
  const raw_hash = createHash("sha256").update(raw).digest("hex");
  return sourceSchema.parse({
    ...input,
    channel: authority.channel,
    scope: authority.scope,
    raw_hash,
    byte_length: length,
    spans: attributes.map((attribute) => ({
      span_id:
        createHash("sha256").update(input.record_id).digest("hex") +
        "." +
        attribute,
      attribute,
      start: 0,
      end: length,
      raw_hash,
    })),
  });
}

export function channelUrl(value: string, channel: string) {
  const strict = (v: string) =>
    /^https:\/\/[a-zA-Z0-9.-]+(?:\/[^?#%\\\s]*)?$/.test(v) &&
    !v.split("/").some((s) => s === "." || s === "..");
  if (!strict(value) || !strict(channel)) return false;
  const url = new URL(value),
    prefix = new URL(channel);
  return (
    url.hostname === prefix.hostname &&
    (url.pathname === prefix.pathname ||
      url.pathname.startsWith(
        prefix.pathname.endsWith("/") ? prefix.pathname : prefix.pathname + "/",
      ))
  );
}
export async function fetchPublicSource(url: URL): Promise<Buffer> {
  const addresses = isIP(url.hostname)
    ? [{ address: url.hostname, family: isIP(url.hostname) }]
    : await lookup(url.hostname, { all: true });
  if (!addresses.length || addresses.some((a) => privateAddress(a.address)))
    throw new HttpError(400, "Private network sources are not accepted.");
  // TLS still authenticates the source hostname; every connection uses only checked addresses.
  const proxy = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;
  const target = new URL(url);
  if (proxy)
    target.hostname =
      addresses[0].family === 6
        ? "[" + addresses[0].address + "]"
        : addresses[0].address;
  const dispatcher = proxy
    ? new ProxyAgent({ uri: proxy, requestTls: { servername: url.hostname } })
    : new Agent({
        connect: {
          lookup: (_host, options, callback) => {
            if (options.all) callback(null, addresses);
            else callback(null, addresses[0].address, addresses[0].family);
          },
        },
      });
  try {
    const response = await fetch(target, {
      dispatcher,
      redirect: "error",
      signal: AbortSignal.timeout(12000),
      headers: {
        Accept: "text/plain,application/json,text/html",
        ...(proxy ? { Host: url.host } : {}),
      },
    });
    if (!response.ok || !response.body)
      throw new HttpError(422, "The public source is unavailable.");
    if (Number(response.headers.get("content-length")) > limits.sourceBytes)
      throw new HttpError(413, "The complete source exceeds 48 KiB.");
    const reader = response.body.getReader();
    const chunks: Uint8Array[] = [];
    let length = 0;
    try {
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        length += chunk.value.length;
        if (length > limits.sourceBytes)
          throw new HttpError(
            413,
            "The complete source exceeds 48 KiB. It cannot be truncated.",
          );
        chunks.push(chunk.value);
      }
      return Buffer.concat(chunks);
    } finally {
      await reader.cancel();
    }
  } finally {
    await dispatcher.close();
  }
}
