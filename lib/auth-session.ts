export const COOKIE_SESSION_TOKEN_PREFIX = "cookie-session:";
const COOKIE_SESSION_MIGRATION_TIMEOUT_MS = 4_000;

export function createCookieSessionMarker(): string {
  const randomPart = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
  return `${COOKIE_SESSION_TOKEN_PREFIX}${randomPart}`;
}

export function isCookieSessionMarker(value: unknown): boolean {
  return String(value || "").startsWith(COOKIE_SESSION_TOKEN_PREFIX);
}

export function storeBrowserSessionToken(token: unknown): string {
  const value = String(token || "").trim() || createCookieSessionMarker();
  if (typeof window !== "undefined") {
    localStorage.setItem("diamond_token", value);
  }
  return value;
}

export async function migrateBrowserSessionToCookie(
  token: unknown,
  apiBase = "/api",
): Promise<string> {
  const current = String(token || "").trim();
  if (!current || isCookieSessionMarker(current) || typeof window === "undefined") return current;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), COOKIE_SESSION_MIGRATION_TIMEOUT_MS);
  try {
    if (window.localStorage.getItem("diamond_token") !== current) return current;
    const response = await fetch(`${apiBase}/auth/session/cookie`, {
      method: "POST",
      credentials: "include",
      headers: { Authorization: `Bearer ${current}` },
      signal: controller.signal,
    });
    if (!response.ok) return current;
    return storeBrowserSessionToken("");
  } catch {
    return current;
  } finally {
    window.clearTimeout(timeout);
  }
}
