/** Resolve backend API base URL for browser fetches.

Next.js inlines NEXT_PUBLIC_* at build time. If the bundle still points at
127.0.0.1 while users open the dashboard via a public host, the browser
talks to *their own* localhost — NetworkError, often misread as CORS.

When the page host is not localhost and env still points local, prefer
same-hostname:8004 at runtime.
*/
export function resolveApiBase(): string {
  const fromEnv = (
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE ||
    ""
  )
    .trim()
    .replace(/\/$/, "");

  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;
    const isLocalPage =
      hostname === "localhost" ||
      hostname === "127.0.0.1" ||
      hostname === "[::1]";
    const envIsLocal =
      !fromEnv ||
      fromEnv.includes("127.0.0.1") ||
      fromEnv.includes("localhost");

    if (!isLocalPage && envIsLocal) {
      return `${protocol}//${hostname}:8004`;
    }
  }

  return fromEnv || "http://127.0.0.1:8004";
}
