/** Shared frontend API helpers — keep auth/error style consistent. */

export { resolveApiBase } from "./apiBase";

/** Append api_key query param (dashboard GET style). */
export function withApiKey(url: string, apiKey: string): string {
  const join = url.includes("?") ? "&" : "?";
  return `${url}${join}api_key=${encodeURIComponent(apiKey)}`;
}

/** Header for routes that use resolve_api_key (proxy / some exports). */
export function attestHeaders(apiKey: string, extra?: HeadersInit): HeadersInit {
  return { "X-Attest-Key": apiKey, ...(extra || {}) };
}

/** Normalize FastAPI `detail` (string | array | object) into a short message. */
export function formatDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return JSON.stringify(item);
      })
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }
  if (detail != null && typeof detail === "object") {
    try {
      return JSON.stringify(detail);
    } catch {
      /* ignore */
    }
  }
  return fallback;
}

export async function parseApiError(
  res: Response,
  fallback: string
): Promise<string> {
  try {
    const d = await res.json();
    return formatDetail(d?.detail, fallback);
  } catch {
    try {
      const t = await res.text();
      if (t.trim()) return t.slice(0, 240);
    } catch {
      /* ignore */
    }
    return `${fallback} (${res.status})`;
  }
}
