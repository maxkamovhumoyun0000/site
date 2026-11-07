"use client";

import { useCallback, useEffect, useState } from "react";

type RequestRow = {
  id: number;
  user_id: number;
  product_code: "english" | "russian";
  login_id: string;
  first_name: string;
  last_name: string;
  email: string;
  plan_code: "plus" | "pro";
  term_code: string;
  amount_uzs: number;
  status: "pending" | "approved" | "rejected";
  review_note: string;
  created_at: string;
  reviewed_at?: string | null;
};

type ApiFetch = (path: string, options?: { method?: string; body?: unknown }) => Promise<any>;

const termLabel: Record<string, string> = {
  week: "7 kun", month: "1 oy", quarter: "3 oy", half_year: "6 oy",
};
const planCodes = ["plus", "pro"] as const;
const termCodes = ["week", "month", "quarter", "half_year"] as const;
type PriceMatrix = Record<(typeof planCodes)[number], Record<(typeof termCodes)[number], number>>;

const emptyPrices: PriceMatrix = {
  plus: { week: 0, month: 0, quarter: 0, half_year: 0 },
  pro: { week: 0, month: 0, quarter: 0, half_year: 0 },
};

export function AdminSpeakingSubscriptions({ apiFetch }: { apiFetch: ApiFetch }) {
  const [status, setStatus] = useState("pending");
  const [productCode, setProductCode] = useState<"english" | "russian">("english");
  const [items, setItems] = useState<RequestRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [prices, setPrices] = useState<PriceMatrix>(emptyPrices);
  const [priceLoading, setPriceLoading] = useState(true);
  const [priceSaving, setPriceSaving] = useState(false);
  const [priceError, setPriceError] = useState("");
  const [priceNotice, setPriceNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await apiFetch(`/staff/speaking/subscription-requests?status=${status}&product_code=${productCode}`);
      setItems(Array.isArray(payload?.items) ? payload.items : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Tarif so‘rovlari yuklanmadi.");
    } finally {
      setLoading(false);
    }
  }, [apiFetch, productCode, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const loadPrices = useCallback(async () => {
    setPriceLoading(true);
    setPriceError("");
    try {
      const payload = await apiFetch(`/staff/speaking/subscription-prices?product_code=${productCode}`);
      const incoming = payload?.prices;
      if (!incoming?.plus || !incoming?.pro) throw new Error("Tarif narxlari javobi noto‘g‘ri.");
      setPrices({
        plus: Object.fromEntries(termCodes.map((term) => [term, Number(incoming.plus[term] ?? 0)])) as PriceMatrix["plus"],
        pro: Object.fromEntries(termCodes.map((term) => [term, Number(incoming.pro[term] ?? 0)])) as PriceMatrix["pro"],
      });
    } catch (e) {
      setPriceError(e instanceof Error ? e.message : "Narxlar yuklanmadi.");
    } finally {
      setPriceLoading(false);
    }
  }, [apiFetch, productCode]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadPrices(), 0);
    return () => window.clearTimeout(timer);
  }, [loadPrices]);

  async function savePrices() {
    setPriceSaving(true);
    setPriceError("");
    setPriceNotice("");
    try {
      const payload = await apiFetch("/staff/speaking/subscription-prices", {
        method: "PUT",
        body: { product_code: productCode, prices },
      });
      if (!payload?.prices) throw new Error("Narxlar saqlanmadi.");
      setPriceNotice("Tarif narxlari saqlandi. Yangi so‘rovlarda shu narxlar ishlatiladi.");
      await loadPrices();
    } catch (e) {
      setPriceError(e instanceof Error ? e.message : "Narxlar saqlanmadi.");
    } finally {
      setPriceSaving(false);
    }
  }

  async function review(item: RequestRow, decision: "approve" | "reject") {
    const action = decision === "approve" ? "tasdiqlash" : "rad etish";
    if (!window.confirm(`${item.login_id || item.first_name} foydalanuvchisining ${item.plan_code.toUpperCase()} tarif so‘rovini ${action}?`)) return;
    setBusyId(item.id);
    setError("");
    setNotice("");
    try {
      await apiFetch(`/staff/speaking/subscription-requests/${item.id}/review`, {
        method: "POST",
        body: { decision, note: "Speaking admin tomonidan ko‘rib chiqildi" },
      });
      setNotice(decision === "approve" ? "Tarif tasdiqlandi va aktivlashtirildi." : "So‘rov rad etildi.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Amal bajarilmadi.");
    } finally {
      setBusyId(null);
    }
  }

  const dateLabel = (value: string) => {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat("uz-UZ", { dateStyle: "medium", timeStyle: "short" }).format(date);
  };

  return (
    <section className="mx-auto w-full max-w-6xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[.18em] text-cyan-700">Speaking App</p>
          <h1 className="mt-1 text-2xl font-black text-slate-900">Tarif so‘rovlari</h1>
          <p className="mt-1 text-sm text-slate-500">To‘lovni tekshiring, so‘ng tarifni tasdiqlang yoki rad eting.</p>
        </div>
        <div className="flex gap-2">
          <select aria-label="Ilova tili" value={productCode} onChange={(event) => setProductCode(event.target.value as "english" | "russian")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700">
            <option value="english">English app</option>
            <option value="russian">Русский app</option>
          </select>
          <select aria-label="So‘rov holati" value={status} onChange={(event) => setStatus(event.target.value)} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700">
            <option value="pending">Kutilmoqda</option>
            <option value="approved">Tasdiqlangan</option>
            <option value="rejected">Rad etilgan</option>
            <option value="all">Barchasi</option>
          </select>
          <button type="button" onClick={() => void load()} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-bold text-slate-700">Yangilash</button>
        </div>
      </header>

      <section className="rounded-2xl border border-indigo-100 bg-white p-4 shadow-sm sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-black text-slate-900">{productCode === "russian" ? "Русский app — Plus / Pro narxlari" : "English app — Plus / Pro narxlari"}</h2>
            <p className="mt-1 max-w-2xl text-sm text-slate-500">Narxni Speaking admin o‘zgartiradi. Yangi tarif so‘rovlari saqlangan narxni oladi; avval yuborilgan so‘rov summasi o‘zgarmaydi.</p>
          </div>
          <button type="button" onClick={() => void loadPrices()} disabled={priceLoading || priceSaving} className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold text-slate-700 disabled:opacity-50">Narxlarni yangilash</button>
        </div>
        {priceError ? <p role="alert" className="mt-3 rounded-xl bg-rose-50 p-3 text-sm font-semibold text-rose-800">{priceError}</p> : null}
        {priceNotice ? <p role="status" className="mt-3 rounded-xl bg-emerald-50 p-3 text-sm font-semibold text-emerald-800">{priceNotice}</p> : null}
        {priceLoading ? <p className="py-6 text-center text-sm text-slate-500">Narxlar yuklanmoqda…</p> : <>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {planCodes.map((plan) => <fieldset key={plan} className="rounded-xl border border-slate-200 p-3 sm:p-4">
              <legend className="px-2 font-extrabold uppercase text-indigo-800">{plan}</legend>
              <div className="grid grid-cols-2 gap-3">
                {termCodes.map((term) => <label key={term} className="text-xs font-bold text-slate-600">
                  {termLabel[term]} · so‘m
                  <input
                    aria-label={`${plan} ${term} narxi`}
                    type="number"
                    min="0"
                    max="100000000"
                    step="1000"
                    inputMode="numeric"
                    value={prices[plan][term]}
                    onChange={(event) => setPrices((current) => ({ ...current, [plan]: { ...current[plan], [term]: Math.min(100_000_000, Math.max(0, Math.trunc(Number(event.target.value) || 0))) } }))}
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm font-extrabold text-slate-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                  />
                </label>)}
              </div>
            </fieldset>)}
          </div>
          <div className="mt-4 flex justify-end">
            <button type="button" onClick={() => void savePrices()} disabled={priceSaving || priceLoading} className="rounded-xl bg-indigo-700 px-5 py-2.5 text-sm font-extrabold text-white disabled:opacity-50">{priceSaving ? "Saqlanmoqda…" : "Narxlarni saqlash"}</button>
          </div>
        </>}
      </section>

      {notice ? <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm font-semibold text-emerald-800">{notice}</p> : null}
      {error ? <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm font-semibold text-rose-800">{error}</p> : null}

      {loading ? <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">So‘rovlar yuklanmoqda…</div> : items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">Bu holatda tarif so‘rovi yo‘q.</div>
      ) : <div className="grid gap-3">
        {items.map((item) => (
          <article key={item.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-extrabold text-slate-900">{[item.first_name, item.last_name].filter(Boolean).join(" ") || item.login_id || `User #${item.user_id}`}</h2>
                  <span className={`rounded-full px-2.5 py-1 text-[11px] font-black uppercase ${item.status === "pending" ? "bg-amber-100 text-amber-800" : item.status === "approved" ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{item.status}</span>
                </div>
                <p className="mt-1 text-sm text-slate-500">So‘rov #{item.id} · {item.login_id}{item.email ? ` · ${item.email}` : ""} · Foydalanuvchi ID {item.user_id}</p>
                <p className="mt-1 text-xs font-bold uppercase tracking-wide text-indigo-700">{item.product_code === "russian" ? "Русский app" : "English app"}</p>
                <p className="mt-3 text-sm text-slate-600">So‘rov: {dateLabel(item.created_at)}</p>
              </div>
              <div className="min-w-48 rounded-xl bg-slate-50 p-3 text-right">
                <p className="text-lg font-black text-indigo-800">{item.plan_code.toUpperCase()}</p>
                <p className="text-sm font-semibold text-slate-700">{termLabel[item.term_code] || item.term_code}</p>
                <p className="mt-1 text-sm font-bold text-slate-900">{new Intl.NumberFormat("uz-UZ").format(item.amount_uzs)} so‘m</p>
              </div>
            </div>
            {item.review_note ? <p className="mt-3 text-sm text-slate-600">Izoh: {item.review_note}</p> : null}
            {item.status === "pending" ? <div className="mt-4 flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
              <button type="button" disabled={busyId === item.id} onClick={() => void review(item, "reject")} className="rounded-xl border border-rose-200 px-4 py-2 text-sm font-bold text-rose-700 disabled:opacity-50">Rad etish</button>
              <button type="button" disabled={busyId === item.id} onClick={() => void review(item, "approve")} className="rounded-xl bg-indigo-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">{busyId === item.id ? "Saqlanmoqda…" : "To‘lov tasdiqlandi · tarifni yoqish"}</button>
            </div> : null}
          </article>
        ))}
      </div>}
    </section>
  );
}
