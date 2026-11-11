import { beforeEach, expect, it, vi } from "vitest";
import { attributes, sourceSchema } from "@eventweave/protocol";
const mocks = vi.hoisted(() => ({
  lookup: vi.fn(),
  fetch: vi.fn(),
  options: null as null | { connect: { lookup: (...args: unknown[]) => void } },
  close: vi.fn(),
}));
vi.mock("node:dns/promises", () => ({ lookup: mocks.lookup }));
vi.mock("undici", () => ({
  Agent: class {
    constructor(options: typeof mocks.options) {
      mocks.options = options;
    }
    close() {
      return mocks.close();
    }
  },
  ProxyAgent: class {
    constructor(options: typeof mocks.options) {
      mocks.options = options;
    }
    close() {
      return mocks.close();
    }
  },
  fetch: mocks.fetch,
}));
vi.mock("../apps/api/src/chain.js", () => ({
  read: async () => ({
    principal: "owner",
    url_prefix: "https://example.org/channel/",
    channel: "official",
    scope: "public",
  }),
}));
vi.mock("../apps/api/src/network.js", () => ({}));
import {
  channelUrl,
  commitSource,
  fetchPublicSource,
} from "../apps/api/src/sources";
beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("HTTPS_PROXY", "");
  vi.stubEnv("HTTP_PROXY", "");
  mocks.lookup.mockResolvedValue([{ address: "140.82.112.3", family: 4 }]);
  mocks.fetch.mockImplementation(
    async () => new Response("Complete official text"),
  );
});
it("pins connections to the checked DNS answer and retains hostname TLS", async () => {
  mocks.lookup
    .mockResolvedValueOnce([{ address: "140.82.112.3", family: 4 }])
    .mockResolvedValue([{ address: "127.0.0.1", family: 4 }]);
  await fetchPublicSource(new URL("https://example.org/channel/a"));
  const callback = vi.fn();
  mocks.options!.connect.lookup("example.org", { all: false }, callback);
  expect(callback).toHaveBeenCalledWith(null, "140.82.112.3", 4);
  expect(mocks.lookup).toHaveBeenCalledTimes(1);
  expect(mocks.fetch.mock.calls[0][0].hostname).toBe("example.org");
  expect(mocks.close).toHaveBeenCalledOnce();
});
it("rejects private DNS answers before connecting", async () => {
  mocks.lookup.mockResolvedValue([{ address: "127.0.0.1", family: 4 }]);
  await expect(
    fetchPublicSource(new URL("https://example.org/channel/a")),
  ).rejects.toThrow("Private network");
  expect(mocks.fetch).not.toHaveBeenCalled();
});
it("supports a complete 128-character record ID with valid committed spans", async () => {
  const source = await commitSource(
    {
      record_id: "a".repeat(128),
      authority_id: "authority:1",
      revision: "1",
      url: "https://example.org/channel/a",
    },
    "owner",
  );
  expect(sourceSchema.safeParse(source).success).toBe(true);
  expect(source.spans.map((s) => s.attribute)).toEqual(attributes);
  expect(source.spans.every((s) => s.span_id.length <= 128)).toBe(true);
});
it.each([
  "https://example.org.attacker.org/channel/a",
  "https://example.org@attacker.org/channel/a",
  "https://example.org/channel-other/a",
  "https://example.org/channel/../a",
  "https://example.org/channel/%2e%2e/a",
])("rejects an escaping source %s", (url) =>
  expect(channelUrl(url, "https://example.org/channel")).toBe(false),
);
it("allows the configured path itself and its descendants", () => {
  expect(
    channelUrl("https://example.org/channel", "https://example.org/channel"),
  ).toBe(true);
  expect(
    channelUrl("https://example.org/channel/a", "https://example.org/channel"),
  ).toBe(true);
});

it("uses a pinned IP for proxy CONNECT while retaining source TLS and Host", async () => {
  vi.stubEnv("HTTPS_PROXY", "http://configured-proxy.example:8080");
  await fetchPublicSource(new URL("https://example.org/channel/a"));
  expect(mocks.fetch.mock.calls[0][0].hostname).toBe("140.82.112.3");
  expect(mocks.fetch.mock.calls[0][1].headers.Host).toBe("example.org");
  expect(mocks.options).toMatchObject({
    requestTls: { servername: "example.org" },
  });
});
