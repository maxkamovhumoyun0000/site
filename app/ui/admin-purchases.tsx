"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ModalPortal } from "./modal-portal";
import { useWebT } from "./web-i18n";

type PurchaseItem = {
  id: number;
  user_full_name?: string | null;
  user_login_id?: string | null;
  user_phone?: string | null;
  item_type?: string | null;
  item_title?: string | null;
  amount_spent?: number;
  balance_before?: number | null;
  balance_after?: number | null;
  source_page?: string | null;
  meta_json?: string | null;
  gift?: {
    image_url?: string | null;
    title?: string | null;
  } | null;
  created_at?: string | null;
  created_date?: string | null;
  created_time?: string | null;
};

const ADMIN_PURCHASE_PAGE_SIZE = 100;
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

function resolvePurchaseAssetUrl(url?: string | null) {
  const cleaned = String(url || "").trim();
  if (!cleaned) return "";
  if (/^(https?:|data:|blob:)/i.test(cleaned)) return cleaned;
  return cleaned.startsWith("/") ? `${API_BASE}${cleaned}` : `${API_BASE}/${cleaned.replace(/^\/+/, "")}`;
}

function purchaseTypeLabel(tt: ReturnType<typeof useWebT>, value?: string | null) {
  const type = String(value || "other").trim().toLowerCase();
  if (type === "gift") return tt("admin.purchases.type.gift", "Sovga");
  if (type === "chest") return tt("admin.purchases.type.chest", "Sandiq");
  if (type === "book") return tt("admin.purchases.type.book", "Kitob");
  return tt("admin.purchases.type.other", "Boshqa");
}

function purchaseError(tt: ReturnType<typeof useWebT>, raw: unknown) {
  const text = String(raw instanceof Error ? raw.message : raw || "").toLowerCase();
  if (text.includes("403") || text.includes("permission")) return tt("errors.permission", "Sizda bu amal uchun ruxsat yo'q.");
  if (text.includes("timeout") || text.includes("network")) return tt("errors.network", "Internet sekin. Qayta urinib ko'ring.");
  return tt("admin.purchases.loadError", "Xaridlarni yuklab bo'lmadi.");
}

export function AdminPurchases({
  apiFetch,
}: {
  apiFetch: (path: string, options?: any) => Promise<any>;
}) {
  const tt = useWebT();
  const [items, setItems] = useState<PurchaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<PurchaseItem | null>(null);
  const [limit, setLimit] = useState(ADMIN_PURCHASE_PAGE_SIZE);
  const fetchInFlightRef = useRef(false);
  const apiFetchRef = useRef(apiFetch);
  const ttRef = useRef(tt);
  const itemsRef = useRef<PurchaseItem[]>([]);

  useEffect(() => {
    apiFetchRef.current = apiFetch;
  }, [apiFetch]);

  useEffect(() => {
    ttRef.current = tt;
  }, [tt]);

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  const fetchPurchases = useCallback(async (silent = false) => {
    if (fetchInFlightRef.current) return;
    fetchInFlightRef.current = true;
    if (!silent && itemsRef.current.length === 0) setLoading(true);
    if (!silent) setError("");
    try {
      const nextLimit = Math.max(1, Math.min(500, limit));
      const payload = await apiFetchRef.current(`/admin/purchases?limit=${nextLimit}`);
      setItems((payload?.items || []) as PurchaseItem[]);
    } catch (e) {
      if (!silent) {
        setError(purchaseError(ttRef.current, e));
        if (itemsRef.current.length === 0) setItems([]);
      }
    } finally {
      fetchInFlightRef.current = false;
      if (!silent) setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    fetchPurchases().catch(() => null);
  }, [fetchPurchases]);

  useEffect(() => {
    const refreshSilently = () => {
      if (document.visibilityState === "hidden") return;
      fetchPurchases(true).catch(() => null);
    };
    const interval = window.setInterval(refreshSilently, 8000);
    window.addEventListener("focus", refreshSilently);
    document.addEventListener("visibilitychange", refreshSilently);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", refreshSilently);
      document.removeEventListener("visibilitychange", refreshSilently);
    };
  }, [fetchPurchases]);

  const grouped = useMemo(() => items, [items]);
  const canLoadMore = grouped.length >= limit && limit < 500;

  return (
    <div className="flex flex-col gap-6 pb-10">
      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
          {error}
        </div>
      ) : null}

      {loading ? (
        <section className="panel-card">
          <div className="flex justify-center py-10">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
          </div>
        </section>
      ) : grouped.length === 0 ? (
        <section className="panel-card">
          <div className="py-10 text-center text-sm font-medium text-ink-500 dark:text-navy-300">
            {tt("admin.purchases.empty", "Hali xaridlar mavjud emas")}
          </div>
        </section>
      ) : (
        <>
          <section className="panel-card">
            <div className="row-between">
              <div>
                <h3>{tt("admin.purchases.latest", "Oxirgi xaridlar")}</h3>
                <p className="text-sm text-ink-600 dark:text-navy-300">
                  {tt("admin.purchases.latestSubtitle", "Sandiq, sovga va kitob xaridlari yangisi yuqorida.")}
                </p>
              </div>
            </div>
            <div className="admin-mobile-grid admin-purchases-grid mt-4">
              {grouped.map((row) => (
                <button
                  key={`purchase-${row.id}`}
                  type="button"
                  className="admin-mobile-card admin-purchase-detail-card text-left transition hover:-translate-y-0.5 hover:border-cyan-300 dark:hover:border-cyan-500/40"
                  onClick={() => setSelected(row)}
                >
                  {row.gift?.image_url ? (
                    <img
                      src={resolvePurchaseAssetUrl(row.gift.image_url)}
                      alt={row.item_title || "Xarid"}
                      className="admin-mobile-card-image"
                    />
                  ) : null}
                  <span className="gift-purchase-type">{purchaseTypeLabel(tt, row.item_type)}</span>
                  <h4 className="text-sm font-bold text-navy-900 dark:text-white">{row.user_full_name || "—"}</h4>
                  <p className="text-xs text-ink-600 dark:text-navy-300">
                    {row.item_title || tt("common.untitled", "Nomsiz")} · {purchaseTypeLabel(tt, row.item_type)}
                  </p>
                  <p className="text-xs text-ink-600 dark:text-navy-300">{row.created_date || "—"} {row.created_time || ""}</p>
                  <p className="text-sm font-semibold text-cyan-700 dark:text-cyan-300">-{Number(row.amount_spent || 0).toFixed(1)} D&apos;coin</p>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-ink-600 dark:text-navy-300">
                    <span>{tt("admin.purchases.before", "Oldin")}: {row.balance_before === null || row.balance_before === undefined ? "—" : Number(row.balance_before).toFixed(1)}</span>
                    <span>{tt("admin.purchases.after", "Keyin")}: {row.balance_after === null || row.balance_after === undefined ? "—" : Number(row.balance_after).toFixed(1)}</span>
                  </div>
                  <p className="text-[11px] text-ink-500 dark:text-navy-400">
                    {row.user_login_id ? `Login: ${row.user_login_id}` : ""}{row.user_phone ? ` · ${row.user_phone}` : ""}
                  </p>
                </button>
              ))}
            </div>
          </section>
          {canLoadMore ? (
            <div className="flex justify-center">
              <button className="btn btn-primary" onClick={() => setLimit((value) => Math.min(500, value + ADMIN_PURCHASE_PAGE_SIZE))}>
                {tt("common.loadMore", "Yana ko'rsatish")}
              </button>
            </div>
          ) : null}
        </>
      )}

      <ModalPortal open={Boolean(selected)}>
      {selected ? (
        <div className="overlay-modal-backdrop" onClick={() => setSelected(null)}>
          <article className="overlay-modal-card max-w-lg" onClick={(event) => event.stopPropagation()}>
            <div className="row-between gap-3">
              <div>
                <h3>{selected.item_title || tt("admin.purchases.detailTitle", "Xarid tafsiloti")}</h3>
                <p className="text-sm text-ink-600 dark:text-navy-300">{selected.user_full_name || "—"}</p>
              </div>
              <button className="btn btn-soft" type="button" onClick={() => setSelected(null)}>
                {tt("common.close", "Yopish")}
              </button>
            </div>
            <div className="grid gap-2">
              <div className="kv"><span>{tt("common.type", "Turi")}</span><strong>{purchaseTypeLabel(tt, selected.item_type)}</strong></div>
              <div className="kv"><span>{tt("common.date", "Sana")}</span><strong>{selected.created_date || "—"} {selected.created_time || ""}</strong></div>
              <div className="kv"><span>{tt("admin.purchases.amountSpent", "Sarflangan")}</span><strong>{Number(selected.amount_spent || 0).toFixed(1)} D&apos;coin</strong></div>
              <div className="kv"><span>{tt("admin.purchases.before", "Oldin")}</span><strong>{selected.balance_before === null || selected.balance_before === undefined ? "—" : Number(selected.balance_before).toFixed(1)}</strong></div>
              <div className="kv"><span>{tt("admin.purchases.after", "Keyin")}</span><strong>{selected.balance_after === null || selected.balance_after === undefined ? "—" : Number(selected.balance_after).toFixed(1)}</strong></div>
              <div className="kv"><span>{tt("common.loginId", "Login ID")}</span><strong>{selected.user_login_id || "—"}</strong></div>
              <div className="kv"><span>{tt("common.phone", "Telefon")}</span><strong>{selected.user_phone || "—"}</strong></div>
              {selected.source_page ? <div className="kv"><span>{tt("admin.purchases.source", "Manba")}</span><strong>{selected.source_page}</strong></div> : null}
            </div>
          </article>
        </div>
      ) : null}
      </ModalPortal>
    </div>
  );
}
