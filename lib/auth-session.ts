export const COOKIE_SESSION_TOKEN_PREFIX = "cookie-session:";

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
  if (localStorage.getItem("diamond_token") !== current) return current;
  try {
    const response = await fetch(`${apiBase}/auth/session/cookie`, {
      method: "POST",
      credentials: "include",
      headers: { Authorization: `Bearer ${current}` },
    });
    if (!response.ok) return current;
    return storeBrowserSessionToken("");
  } catch {
    return current;
  }
}
