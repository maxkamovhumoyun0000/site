const API_REQUEST_TIMEOUT_MS = 45000;

function isHtmlPayload(value: string) {
  const trimmed = String(value || "").trim().toLowerCase();
  return trimmed.startsWith("<!doctype html") || trimmed.startsWith("<html");
}

function friendlyStatusMessage(status: number, fallback?: string) {
  if (status === 413) return "Fayl hajmi juda katta";
  if (status === 422) return fallback || "Fayl yoki so'rov formati noto'g'ri";
  if (status === 404) return fallback || "Ma'lumot topilmadi";
  if (status === 401) return "Sessiya muddati tugagan. Qayta kiring.";
  if (status === 403) return "Sizda bu amalni bajarish huquqi yo'q";
  return fallback || `Error ${status}`;
}

export async function apiFetch(path: string, options?: any) {
  const token = typeof window !== 'undefined' ? localStorage.getItem("diamond_token") : null;
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
  const url = `${baseUrl}${path}`;
  const {
    signal: externalSignal,
    body: requestBody,
    headers: providedHeaders,
    method,
    timeoutMs,
    ...fetchOptions
  } = options || {};

  const isFormData = typeof FormData !== "undefined" && requestBody instanceof FormData;
  const headers: Record<string, string> = isFormData ? {} : { "Content-Type": "application/json" };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (providedHeaders && typeof providedHeaders === "object") {
    Object.assign(headers, providedHeaders);
  }

  const controller = new AbortController();
  let abortedByExternal = false;
  const onExternalAbort = () => {
    abortedByExternal = true;
    controller.abort();
  };
  if (externalSignal) {
    if (externalSignal.aborted) {
      abortedByExternal = true;
      controller.abort();
    } else {
      externalSignal.addEventListener("abort", onExternalAbort, { once: true });
    }
  }
  const timeout = window.setTimeout(() => controller.abort(), Number(timeoutMs || API_REQUEST_TIMEOUT_MS));
  let res: Response;
  try {
    res = await fetch(url, {
      ...fetchOptions,
      method: method || "GET",
      headers,
      body: requestBody ? (isFormData ? requestBody : JSON.stringify(requestBody)) : undefined,
      signal: controller.signal,
    });
  } catch (error) {
    if (abortedByExternal) {
      throw new Error("So'rov bekor qilindi");
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Internet sekin. Qayta urinib ko'ring.");
    }
    throw error instanceof Error ? error : new Error("So'rov bajarilmadi");
  } finally {
    window.clearTimeout(timeout);
    if (externalSignal) {
      externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }

  const contentType = String(res.headers.get("content-type") || "").toLowerCase();
  const text = await res.text().catch(() => "");
  const trimmed = text.trim();

  if (!res.ok) {
    if (res.status === 413) {
      throw new Error("Fayl hajmi juda katta");
    }
    if (isHtmlPayload(trimmed)) {
      throw new Error(friendlyStatusMessage(res.status, "Server xatosi. Qayta urinib ko'ring."));
    }
    if (contentType.includes("application/json") && trimmed) {
      let detail = "";
      let message = "";
      let error = "";
      try {
        const data = JSON.parse(trimmed) as { detail?: unknown; message?: string; error?: string };
        message = String(data.message || "");
        error = String(data.error || "");
        detail =
          typeof data.detail === "string"
            ? data.detail
            : Array.isArray(data.detail)
              ? "So'rov formati noto'g'ri."
              : data.detail && typeof data.detail === "object"
                ? String(
                    (data.detail as { message?: unknown; detail?: unknown; code?: unknown }).message ||
                    (data.detail as { message?: unknown; detail?: unknown; code?: unknown }).detail ||
                    ((data.detail as { code?: unknown }).code === "face_enrollment_required"
                      ? "FaceID setup kerak. Profil sahifasidan FaceID setup qiling."
                      : ""),
                  )
              : "";
      } catch {
        detail = trimmed;
      }
      throw new Error(String(friendlyStatusMessage(res.status, detail || message || error || undefined)));
    }
    throw new Error(friendlyStatusMessage(res.status, trimmed || undefined));
  }

  if (contentType.includes("application/json")) {
    try {
      return trimmed ? JSON.parse(trimmed) : {};
    } catch {
      return {};
    }
  }

  return trimmed;
}
