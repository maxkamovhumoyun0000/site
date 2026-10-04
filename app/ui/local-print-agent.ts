export type LocalPrintReceipt = {
  receipt_id?: unknown;
  snapshot?: Record<string, unknown>;
};

type AgentRow = { label: string; value: string };
type AgentPayload = {
  receipt_id: string;
  title: string;
  brand: string;
  branch?: string;
  lines: AgentRow[];
  totals: AgentRow[];
};

export const LOCAL_PRINT_AGENT_URL = "http://127.0.0.1:18765";
export type LocalPrintAgentSettings = { paper_width_mm: number; side_padding_mm: number; line_width: number };

function text(value: unknown, fallback = "-"): string {
  const normalized = String(value ?? "").trim();
  return normalized || fallback;
}

function money(value: unknown): string {
  return `${new Intl.NumberFormat("uz-UZ", { maximumFractionDigits: 2 }).format(Number(value || 0))} SO'M`;
}

export function buildLocalPrintPayload(receipt: LocalPrintReceipt): AgentPayload | null {
  const receiptId = text(receipt.receipt_id, "");
  if (!receiptId) return null;
  const snapshot = receipt.snapshot || {};
  const isRefund = snapshot.receipt_kind === "refund";
  const method = snapshot.payment_method === "card" ? "Karta" : "Naqd";
  const paymentType = snapshot.payment_type === "refund_full"
    ? "To'liq qaytarish"
    : snapshot.payment_type === "refund_partial"
      ? "Qisman qaytarish"
      : snapshot.payment_type === "advance"
        ? "Oldindan to'lov"
        : "Oylik to'lov";
  const teachers = Array.isArray(snapshot.teachers) ? snapshot.teachers.filter(Boolean).join(", ") : "-";
  const brand = text(snapshot.brand, "DIAMOND EDUCATION");
  const branch = text(snapshot.branch_name, "");
  const branchLabel = branch && branch.toLocaleLowerCase() !== brand.toLocaleLowerCase() && branch.toLocaleLowerCase() !== "diamond education" ? branch : "";
  return {
    receipt_id: receiptId,
    title: isRefund ? "QAYTARISH CHEKI" : "TO'LOV CHEKI",
    brand,
    ...(branchLabel ? { branch: branchLabel } : {}),
    lines: [
      { label: "O'quvchi", value: text(snapshot.student_name) },
      { label: "Guruh", value: text(snapshot.group_name) },
      { label: "Fan", value: text(snapshot.subject_name) },
      { label: "O'qituvchi", value: text(teachers) },
      { label: "To'lov turi", value: paymentType },
      { label: "To'lov usuli", value: method },
      { label: "Tasdiqladi", value: text(snapshot.confirmed_by_name) },
      { label: "Sana", value: text(snapshot.confirmed_at) },
      ...(isRefund && text(snapshot.refund_note, "") ? [{ label: "Izoh", value: text(snapshot.refund_note, "") }] : []),
    ],
    totals: [
      { label: isRefund ? "Qaytarildi" : "Joriy to'lov", value: money(snapshot.amount) },
      { label: "Jami to'langan", value: money(snapshot.total_paid_amount ?? snapshot.amount) },
      { label: "Qoldiq", value: money(snapshot.remaining_amount) },
    ],
  };
}

async function agentFetch(path: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 3500);
  try {
    return await fetch(`${LOCAL_PRINT_AGENT_URL}${path}`, { ...init, signal: controller.signal, cache: "no-store" });
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function localPrintAgentHealth(): Promise<{ online: boolean; printer?: string; settings?: LocalPrintAgentSettings }> {
  try {
    const response = await agentFetch("/health");
    const payload = await response.json() as { ok?: boolean; printer?: string; settings?: LocalPrintAgentSettings };
    return { online: response.ok && payload.ok === true, printer: payload.printer, settings: payload.settings };
  } catch {
    return { online: false };
  }
}

export async function printReceiptWithLocalAgent(receipt: LocalPrintReceipt): Promise<{ printed: boolean; error?: string }> {
  const payload = buildLocalPrintPayload(receipt);
  if (!payload) return { printed: false, error: "receipt_id is missing" };
  try {
    const response = await agentFetch("/v1/print", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json().catch(() => ({})) as { ok?: boolean; error?: string };
    return { printed: response.ok && result.ok === true, error: result.error };
  } catch {
    return { printed: false, error: "local agent is unavailable" };
  }
}

export async function printLocalAgentTestReceipt(): Promise<{ printed: boolean; error?: string }> {
  return printReceiptWithLocalAgent({
    receipt_id: `TEST-${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`,
    snapshot: {
      brand: "DIAMOND EDUCATION",
      student_name: "Test chek",
      group_name: "Developer tekshiruvi",
      subject_name: "Termal printer",
      teachers: ["Developer"],
      payment_method: "cash",
      payment_type: "monthly",
      confirmed_by_name: "Developer",
      confirmed_at: new Date().toLocaleString("uz-UZ"),
      amount: 0,
      total_paid_amount: 0,
      remaining_amount: 0,
    },
  });
}

export async function saveLocalPrintAgentSettings(settings: LocalPrintAgentSettings): Promise<{ saved: boolean; settings?: LocalPrintAgentSettings; error?: string }> {
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
