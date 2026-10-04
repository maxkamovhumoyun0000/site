export type ServerPrintDocument = { receipt_id?: unknown; document_base64?: unknown };

export const LOCAL_PRINT_AGENT_URL = "http://127.0.0.1:18765";
export type LocalPrintAgentSettings = {
  paper_width_mm: number;
  side_padding_mm: number;
  line_width: number;
  agent_id?: string;
  agent_token?: string;
  branch_name?: string;
  station_name?: string;
  server_url?: string;
  registered?: boolean;
};

async function agentFetch(path: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 3500);
  try {
    return await fetch(`${LOCAL_PRINT_AGENT_URL}${path}`, { ...init, signal: controller.signal, cache: "no-store" });
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function localPrintAgentHealth(): Promise<{ online: boolean; printer?: string; printer_error?: string; settings?: LocalPrintAgentSettings }> {
  try {
    const response = await agentFetch("/health");
    const payload = await response.json() as { ok?: boolean; printer?: string; printer_error?: string; settings?: LocalPrintAgentSettings };
    return { online: response.ok && payload.ok === true, printer: payload.printer, printer_error: payload.printer_error, settings: payload.settings };
  } catch {
    return { online: false };
  }
}

export async function printReceiptWithLocalAgent(document: ServerPrintDocument): Promise<{ printed: boolean; error?: string }> {
  const documentBase64 = String(document.document_base64 || "").trim();
  if (!documentBase64) return { printed: false, error: "server print document is missing" };
  try {
    const response = await agentFetch("/v1/print", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ receipt_id: String(document.receipt_id || ""), document_base64: documentBase64 }),
    });
    const result = await response.json().catch(() => ({})) as { ok?: boolean; error?: string };
    return { printed: response.ok && result.ok === true, error: result.error };
  } catch {
    return { printed: false, error: "local agent is unavailable" };
  }
}

export async function saveLocalPrintAgentSettings(settings: Partial<LocalPrintAgentSettings>): Promise<{ saved: boolean; settings?: LocalPrintAgentSettings; error?: string }> {
  try {
    const response = await agentFetch("/v1/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    const result = await response.json().catch(() => ({})) as { ok?: boolean; settings?: LocalPrintAgentSettings; error?: string };
    return { saved: response.ok && result.ok === true, settings: result.settings, error: result.error };
  } catch {
    return { saved: false, error: "local agent is unavailable" };
  }
}
