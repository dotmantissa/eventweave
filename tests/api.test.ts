import { beforeAll, afterAll, describe, it, expect } from "vitest";
import { buildApp } from "../apps/api/src/app";
let app: Awaited<ReturnType<typeof buildApp>>;
beforeAll(async () => {
  // Controlled configuration only. No production records or authenticated user is fabricated.
  process.env.PRIVY_APP_ID ||= "controlled_test_app";
  process.env.PRIVY_APP_SECRET ||= "controlled_test_secret";
  process.env.DATABASE_URL ||= "postgresql://test:test@localhost/test";
  app = await buildApp();
});
afterAll(async () => app?.close());
describe("HTTP trust boundary", () => {
  it("serves public health and security headers", async () => {
    const r = await app.inject({ method: "GET", url: "/api/health" });
    expect(r.statusCode).toBe(200);
    expect(r.json()).toEqual({ status: "ok", service: "eventweave" });
    expect(r.headers["x-content-type-options"]).toBe("nosniff");
  });
  it.each([
    "/api/sources/commit",
    "/api/comparisons/prepare",
    "/api/challenges",
  ])("requires email authentication for %s", async (url) => {
    const r = await app.inject({ method: "POST", url, payload: {} });
    expect(r.statusCode).toBe(401);
    expect(r.json().error).toBe("Sign in with email to continue.");
  });
  it("rejects invalid docket IDs before reading network state", async () => {
    const r = await app.inject({
      method: "GET",
      url: "/api/dockets/invalid%20id",
    });
    expect(r.statusCode).toBe(400);
  });
  it("refuses a scheduler call without the configured bearer secret", async () => {
    const r = await app.inject({ method: "GET", url: "/api/reconcile" });
    expect(r.statusCode).toBe(401);
  });
  it("rejects oversized complete request bodies", async () => {
    const r = await app.inject({
      method: "POST",
      url: "/api/sources/commit",
      payload: { url: "a".repeat(24576) },
    });
    expect(r.statusCode).toBe(413);
  });
});
