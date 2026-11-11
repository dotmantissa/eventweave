import type {
  Identity,
  Certificate,
  Operation,
  Deployment,
} from "@eventweave/protocol";
const base = import.meta.env.VITE_API_URL || "";
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(base + "/api" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
    signal: options.signal ?? AbortSignal.timeout(25000),
  });
  const body = await response
    .json()
    .catch(() => ({ error: "The service returned an unreadable response." }));
  if (!response.ok)
    throw new Error(body.error || "The request could not be completed.");
  return body as T;
}
export const api = {
  events: (query = "", kind = "", signal?: AbortSignal) =>
    request<{ items: Identity[]; total: number; indexed_at: string | null }>(
      "/events?q=" +
        encodeURIComponent(query) +
        "&kind=" +
        encodeURIComponent(kind),
      { signal },
    ),
  identity: (id: string) =>
    request<{
      identity: Identity;
      relations: Certificate[];
      aliases: unknown[];
    }>("/events/" + encodeURIComponent(id)),
  config: () =>
    request<{
      deployment: Deployment | null;
      network: string;
      ready: boolean;
      limits: Record<string, number>;
    }>("/config"),
  activity: (token: string) =>
    request<{ items: Operation[] }>("/operations", {
      headers: { Authorization: "Bearer " + token },
    }),
};
