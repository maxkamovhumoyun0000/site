"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";

type GenericRow = Record<string, any>;

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const API_REQUEST_TIMEOUT_MS = 25000;

async function requestJson<T>(path: string, token: string, options?: { method?: "GET" | "POST"; body?: unknown }): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), API_REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: options?.method || "GET",
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      ...(options?.body ? { body: JSON.stringify(options.body) } : {}),
    });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      let detail = "Request failed";
      if (text) {
        try {
          const parsed = JSON.parse(text);
          detail = String(parsed?.detail || parsed?.message || detail);
        } catch {
          detail = text;
        }
      }
      throw new Error(detail);
    }
    return (await response.json()) as T;
  } finally {
    window.clearTimeout(timeout);
  }
}

function currentMonthKey() {
  return new Date().toISOString().slice(0, 7);
}

function asMoney(value: unknown) {
  return Number(value || 0).toFixed(2);
}

function friendlyErrorMessage(raw: unknown) {
  const text = String(raw || "").trim().toLowerCase();
  if (!text) return "Amal bajarilmadi. Qayta urinib ko'ring.";
  if (text.includes("permission") || text.includes("403")) return "Sizda bu ma'lumotni ko'rish huquqi yo'q";
  if (text.includes("not found")) return "Ma'lumot topilmadi.";
  if (text.includes("invalid")) return "Kiritilgan ma'lumot noto'g'ri.";
  if (text.includes("duplicate")) return "Bir xil so'rov qayta yuborildi, iltimos kuting.";
  if (text.includes("exceeds refundable")) return "Refund summasi mumkin bo'lgan limitdan oshib ketdi.";
  if (text.includes("required")) return "Majburiy maydonlarni to'ldiring.";
  return "Amal bajarilmadi. Qayta urinib ko'ring.";
}

function statusTone(status: string) {
  const value = String(status || "").trim().toLowerCase();
  if (value.includes("kechikkan")) return "chip chip-danger";
  if (value.includes("qisman")) return "chip chip-warning";
  if (value.includes("ortiqcha")) return "chip chip-success";
  if (value.includes("to'langan")) return "chip chip-success";
  return "chip";
}

export default function AdminStudentPaymentDetailPage() {
  const params = useParams<{ studentId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const studentId = Number(params?.studentId || 0);
  const queryYm = String(searchParams.get("ym") || "").trim();
  const queryGroupId = Number(searchParams.get("group_id") || 0);

  const [monthKey, setMonthKey] = useState(queryYm || currentMonthKey());
  const [monthTouched, setMonthTouched] = useState(Boolean(queryYm));
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [refundSubmitting, setRefundSubmitting] = useState(false);
  const [errorText, setErrorText] = useState("");
  const [noticeText, setNoticeText] = useState("");
  const [detail, setDetail] = useState<GenericRow | null>(null);
  const [preview, setPreview] = useState<GenericRow | null>(null);
  const [penaltyPreview, setPenaltyPreview] = useState<GenericRow | null>(null);
  const [penaltyLoading, setPenaltyLoading] = useState(false);
  const [form, setForm] = useState<{
    ym: string;
    groupId: number;
    amount: string;
    paymentMethod: "cash" | "card";
    cardId: number;
    note: string;
  }>({
    ym: queryYm || currentMonthKey(),
    groupId: queryGroupId > 0 ? queryGroupId : 0,
    amount: "",
    paymentMethod: "cash",
    cardId: 0,
    note: "",
  });
  const [refundDraft, setRefundDraft] = useState<{
    transactionId: number;
    amount: string;
    mode: "full" | "partial";
    note: string;
  } | null>(null);

  const activeMonth = useMemo(() => {
    const months = ((detail?.overview?.months || []) as GenericRow[]);
    return months.find((row) => String(row.ym || "") === String(monthKey || "")) || detail?.overview?.current_month || null;
  }, [detail, monthKey]);

  const monthRows = ((activeMonth?.items || []) as GenericRow[]);
  const paymentRowsForForm = (
    monthRows.length
      ? monthRows
      : ((((preview?.items || []) as GenericRow[]).filter((row) => Number(row.group_id || 0) > 0))
          .map((row) => ({
            group_id: Number(row.group_id || 0),
            group_name: row.group_name || `Group #${row.group_id}`,
            debt_amount: Number(row.debt_amount || 0),
            status: String(row.status || "To'lanmagan"),
            overdue: Boolean(row.overdue),
          } as GenericRow)))
  ) as GenericRow[];
  const selectedGroupRow = paymentRowsForForm.find((row) => Number(row.group_id || 0) === Number(form.groupId || 0)) || paymentRowsForForm[0] || null;
  const remainingDebt = Number(selectedGroupRow?.debt_amount || 0);
  const isSelectedOverdue = Boolean(selectedGroupRow && (selectedGroupRow.overdue || String(selectedGroupRow.status || "") === "Kechikkan"));

  const transactions = ((detail?.overview?.transactions || []) as GenericRow[]).slice(0, 100);
  const refunds = ((detail?.overview?.refunds || []) as GenericRow[]).slice(0, 100);
  const bonusHistory = ((detail?.overview?.bonus_history || []) as GenericRow[]).slice(0, 100);
  const referralStatus = (detail?.referral_status || detail?.overview?.referral_status || null) as GenericRow | null;
  const paymentMethods = ((detail?.overview?.payment_methods || []) as GenericRow[]).filter((row) => Number(row.id || 0) > 0);
  const defaultCard = paymentMethods.find((row) => Boolean(row.is_default)) || paymentMethods[0] || null;
  const quickRefundTx = transactions.find((tx) => {
    if (Number(form.groupId || 0) > 0 && Number(tx.group_id || 0) !== Number(form.groupId || 0)) return false;
    const total = Number(tx.amount || tx.payment_dcoin_amount || tx.paid_amount || 0);
    const refunded = Number(tx.refunded_amount || 0);
    return total - refunded > 1e-9;
  }) || transactions.find((tx) => Number(tx.amount || tx.payment_dcoin_amount || tx.paid_amount || 0) - Number(tx.refunded_amount || 0) > 1e-9);
  const quickRefundable = quickRefundTx
    ? Math.max(0, Number(quickRefundTx.amount || quickRefundTx.payment_dcoin_amount || quickRefundTx.paid_amount || 0) - Number(quickRefundTx.refunded_amount || 0))
    : 0;

  useEffect(() => {
    setForm((prev) => ({ ...prev, ym: monthKey }));
  }, [monthKey]);

  async function reloadDetailAndPreview(token: string, keepNotice = true) {
    const [detailPayload, previewPayload] = await Promise.all([
      requestJson<GenericRow>(`/admin/payments/students/${studentId}/detail?ym=${encodeURIComponent(monthKey)}`, token),
      requestJson<GenericRow>(`/admin/payments/preview?user_id=${studentId}&ym=${encodeURIComponent(monthKey)}`, token),
    ]);
    setDetail(detailPayload || null);
    setPreview(previewPayload || null);
    const rowsFromDetail = ((((detailPayload || {}).overview || {}).months || []) as GenericRow[])
      .find((row) => String(row.ym || "") === String(monthKey || ""))?.items || [];
    const rowsFromPreview = (((previewPayload || {}).items || []) as GenericRow[]).filter((row) => Number(row.group_id || 0) > 0);
    const rows = (rowsFromDetail && rowsFromDetail.length ? rowsFromDetail : rowsFromPreview) as GenericRow[];
    const nextRows = rows as GenericRow[];
    const preferredGroup = nextRows.find((row) => Number(row.group_id || 0) === Number(form.groupId || queryGroupId || 0)) || nextRows[0] || null;
    const nextGroupId = Number(preferredGroup?.group_id || 0);
    const nextDebt = Number(preferredGroup?.debt_amount || 0);
    setForm((prev) => ({
      ...prev,
      ym: monthKey,
      groupId: nextGroupId,
      amount: nextDebt > 0 ? nextDebt.toFixed(2) : "",
      cardId: prev.paymentMethod === "card" && Number(prev.cardId || 0) > 0 ? prev.cardId : Number(defaultCard?.id || 0),
    }));
    if (!keepNotice) setNoticeText("");
  }

  useEffect(() => {
    const token = localStorage.getItem("diamond_token");
    if (!token || !studentId) {
      setErrorText("Admin session topilmadi.");
      return;
    }
    let alive = true;
    setLoading(true);
    setErrorText("");
    setNoticeText("");
    Promise.all([
      requestJson<GenericRow>(`/admin/payments/students/${studentId}/detail?ym=${encodeURIComponent(monthKey)}`, token),
      requestJson<GenericRow>(`/admin/payments/preview?user_id=${studentId}&ym=${encodeURIComponent(monthKey)}`, token),
    ])
      .then(([detailPayload, previewPayload]) => {
        if (!alive) return;
        const suggested = String(detailPayload?.default_ym || "").trim();
        if (!monthTouched && suggested && suggested !== monthKey) {
          setMonthKey(suggested);
          return;
        }
        setDetail(detailPayload || null);
        setPreview(previewPayload || null);
        const rowsFromDetail = ((((detailPayload || {}).overview || {}).months || []) as GenericRow[])
          .find((row) => String(row.ym || "") === String(monthKey || ""))?.items || [];
        const rowsFromPreview = (((previewPayload || {}).items || []) as GenericRow[]).filter((row) => Number(row.group_id || 0) > 0);
        const rows = (rowsFromDetail && rowsFromDetail.length ? rowsFromDetail : rowsFromPreview) as GenericRow[];
        const nextRows = rows as GenericRow[];
        const preferredGroup = nextRows.find((row) => Number(row.group_id || 0) === Number(form.groupId || queryGroupId || 0)) || nextRows[0] || null;
        const nextGroupId = Number(preferredGroup?.group_id || 0);
        const nextDebt = Number(preferredGroup?.debt_amount || 0);
        setForm((prev) => ({
          ...prev,
          ym: monthKey,
          groupId: nextGroupId,
          amount: nextDebt > 0 ? nextDebt.toFixed(2) : "",
          cardId: prev.paymentMethod === "card" && Number(prev.cardId || 0) > 0 ? prev.cardId : Number(defaultCard?.id || 0),
        }));
      })
      .catch((error) => {
        if (!alive) return;
        setErrorText(friendlyErrorMessage(error instanceof Error ? error.message : ""));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [studentId, monthKey, monthTouched, queryGroupId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (form.paymentMethod !== "card") return;
    if (Number(form.cardId || 0) > 0) return;
    if (!defaultCard) return;
    setForm((prev) => ({ ...prev, cardId: Number(defaultCard.id || 0) }));
  }, [form.paymentMethod, form.cardId, defaultCard]);

  useEffect(() => {
    const token = localStorage.getItem("diamond_token");
    const gid = Number(form.groupId || 0);
    if (!token || !studentId || !gid) {
      setPenaltyPreview(null);
      return;
    }
    let alive = true;
    setPenaltyLoading(true);
    requestJson<GenericRow>(
      `/admin/payments/students/${studentId}/penalty-preview?group_id=${gid}&ym=${encodeURIComponent(monthKey)}`,
      token,
    )
      .then((payload) => {
        if (!alive) return;
        setPenaltyPreview(payload || null);
      })
      .catch(() => {
        if (!alive) return;
        setPenaltyPreview(null);
      })
      .finally(() => {
        if (alive) setPenaltyLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [studentId, form.groupId, monthKey]);

  async function submitPayment(mode: "full" | "partial") {
    const token = localStorage.getItem("diamond_token");
    if (!token || !studentId) return;
    const groupId = Number(form.groupId || 0);
    const amount = mode === "full" ? Number(remainingDebt || 0) : Number(String(form.amount || "").replace(",", "."));
    if (!groupId) {
      setErrorText("Guruhni tanlang.");
      return;
    }
    if (!Number.isFinite(amount) || amount <= 0) {
      setErrorText("To'lov summasi musbat bo'lishi kerak.");
      return;
    }
    if (form.paymentMethod === "card" && Number(form.cardId || 0) <= 0) {
      setErrorText("Karta tanlang.");
      return;
    }
    if (penaltyPreview?.will_apply) {
      const ok = window.confirm(
        `Bu to'lov KECHIKKAN.\n-5% D'coin jarima qo'llanadi.\nBalans: ${asMoney(penaltyPreview.current_dcoin_balance)}\nJarima: ${asMoney(penaltyPreview.penalty_amount)}\nQoladi: ${asMoney(penaltyPreview.remaining_dcoin_after_penalty)}\n\nTasdiqlaysizmi?`,
      );
      if (!ok) return;
    }
    setSubmitting(true);
    setErrorText("");
    setNoticeText("");
    try {
      const result = await requestJson<GenericRow>(`/admin/payments/students/${studentId}/confirm`, token, {
        method: "POST",
        body: {
          ym: String(form.ym || monthKey),
          group_id: groupId,
          amount: Number(amount.toFixed(2)),
          payment_method: form.paymentMethod,
          card_id: form.paymentMethod === "card" ? Number(form.cardId || 0) : null,
          note: String(form.note || "").trim() || null,
          is_advance: false,
        },
      });
      const penaltyText = result?.penalty_applied
        ? ` Jarima: -${asMoney(result?.penalty_amount)} D'coin.`
        : "";
      setNoticeText(`To'lov saqlandi.${penaltyText}`);
      setForm((prev) => ({ ...prev, note: "" }));
      await reloadDetailAndPreview(token);
    } catch (error) {
      setErrorText(friendlyErrorMessage(error instanceof Error ? error.message : ""));
    } finally {
      setSubmitting(false);
    }
  }

  function openRefund(tx: GenericRow, mode: "full" | "partial") {
    const total = Number(tx.amount || 0);
    const refunded = Number(tx.refunded_amount || 0);
    const refundable = Math.max(0, total - refunded);
    if (refundable <= 0) return;
    setRefundDraft({
      transactionId: Number(tx.id || 0),
      mode,
      amount: mode === "full" ? refundable.toFixed(2) : "",
      note: "",
    });
  }

  async function submitRefund() {
    const token = localStorage.getItem("diamond_token");
    if (!token || !studentId || !refundDraft) return;
    const amount = Number(String(refundDraft.amount || "").replace(",", "."));
    if (!Number.isFinite(amount) || amount <= 0) {
      setErrorText("Refund summasi musbat bo'lishi kerak.");
      return;
    }
    if (!String(refundDraft.note || "").trim()) {
      setErrorText("Refund uchun izoh majburiy.");
      return;
    }
    setRefundSubmitting(true);
    setErrorText("");
    setNoticeText("");
    try {
      await requestJson<GenericRow>(`/admin/payments/transactions/${refundDraft.transactionId}/refund`, token, {
        method: "POST",
        body: {
          amount: Number(amount.toFixed(2)),
          note: String(refundDraft.note || "").trim(),
        },
      });
      setNoticeText("Refund muvaffaqiyatli bajarildi.");
      setRefundDraft(null);
      await reloadDetailAndPreview(token);
    } catch (error) {
      setErrorText(friendlyErrorMessage(error instanceof Error ? error.message : ""));
    } finally {
      setRefundSubmitting(false);
    }
  }

  const previewRows = useMemo(() => {
    const fromPreview = (((preview?.items || []) as GenericRow[]).filter((row) => Number(row.group_id || 0) > 0));
    if (fromPreview.length > 0) return fromPreview;
    return monthRows
      .filter((row) => Number(row.group_id || 0) > 0)
      .map((row) => ({
        group_id: row.group_id,
        group_name: row.group_name,
        subject_name: row.subject,
        subject: row.subject,
        course_title: row.course_title,
        course_price: row.original_amount,
        course_monthly_price: row.original_amount,
        total_lesson_count_in_month: row.total_lesson_count_in_month ?? row.planned_lessons ?? 0,
        student_active_lesson_count: row.student_active_lesson_count ?? row.active_lessons ?? 0,
        price_per_lesson: row.price_per_lesson ?? 0,
        calculated_group_amount: row.original_amount,
        calculated_amount: row.final_amount,
        final_payable_amount: row.final_amount,
        paid_amount: row.paid_amount,
        debt_amount: row.debt_amount,
        overpayment_amount: row.overpayment_amount,
        discount_type: row.discount_type,
        discount_percent: row.discount_percent,
        discount_amount: row.discount_amount,
        status: row.status,
        overdue: row.overdue,
      } as GenericRow));
  }, [preview, monthRows]);
  const hasGroup = detail?.has_group !== false;
  const noGroupMessage = String(detail?.no_group_message || "").trim() || "Student hech qaysi guruhga biriktirilmagan";

  return (
    <div className="page-stack">
      <section className="panel-card">
        <div className="row-between">
          <h3>Student Payment Detail</h3>
          <div className="button-grid inline">
            <button className="btn btn-soft" type="button" onClick={() => router.push("/?role=admin&section=payments")}>
              Payments page
            </button>
            <Link className="btn btn-soft" href={`/?role=admin&section=users&user=${studentId}`}>
              User profile
            </Link>
          </div>
        </div>
        <div className="grid grid-3 compact-cards">
          <label>
            Month
            <input
              type="month"
              value={monthKey}
              onChange={(event) => {
                setMonthTouched(true);
                setMonthKey(event.target.value);
              }}
            />
          </label>
          <div className="kv"><span>Student</span><strong>{detail?.user?.full_name || detail?.user?.login_id || `#${studentId}`}</strong></div>
          <div className="kv"><span>Status</span><strong><span className={statusTone(String(activeMonth?.status || "-"))}>{String(activeMonth?.status || "-")}</span></strong></div>
          <div className="kv"><span>Original</span><strong>{asMoney(preview?.original_total_amount)}</strong></div>
          <div className="kv"><span>Discount</span><strong>{String(preview?.discount_type || "none")} ({Number(preview?.discount_percent || 0).toFixed(1)}%)</strong></div>
          <div className="kv"><span>Final payable</span><strong>{asMoney(preview?.final_payable_amount || preview?.total_payable_amount)}</strong></div>
          <div className="kv"><span>Paid</span><strong>{asMoney(activeMonth?.total_paid_amount)}</strong></div>
          <div className="kv"><span>Debt</span><strong>{asMoney(activeMonth?.total_debt_amount)}</strong></div>
          <div className="kv"><span>Overpayment</span><strong>{asMoney(activeMonth?.total_overpayment_amount)}</strong></div>
        </div>
        {referralStatus ? (
          <article className="panel-card">
            <div className="row-between">
              <strong>Referral status</strong>
              <span className="chip">{String(referralStatus.status || "-")}</span>
            </div>
            <p>Source: {String(referralStatus.referral_user_name || referralStatus.referral_user_id || "-")}</p>
            <p>Bonus: {asMoney(referralStatus.bonus_amount)} D&apos;point</p>
          </article>
        ) : null}
      </section>

      <section className="panel-card">
        <h3>Group-by-group calculation</h3>
        {!hasGroup ? <p className="text-sm text-ink-500">{noGroupMessage}</p> : null}
        <div className="mobile-card-list">
          {previewRows.map((row, index) => (
            <article className="panel-card" key={`preview-row-${row.group_id || index}`}>
              <div className="row-between">
                <strong>{row.group_name || row.group_id || "-"}</strong>
                <span className={statusTone(String(row.status || row.payment_status || "To'lanmagan"))}>{String(row.status || row.payment_status || "To'lanmagan")}</span>
              </div>
              <p>Subject: {row.subject_name || row.subject || "-"}</p>
              <p>Kurs: {row.course_title || "-"}</p>
              <p>Teacher: {row.teacher_name || "-"}</p>
              <p>Price: {asMoney(row.course_monthly_price || row.course_price)}</p>
              <p>Lessons: {Number(row.total_lesson_count_in_month || row.planned_lessons || 0)} / Active: {Number(row.student_active_lesson_count || row.active_lessons || 0)}</p>
              <p>Per lesson: {Number(row.price_per_lesson || 0).toFixed(4)}</p>
              <p>Group amount: {asMoney(row.calculated_group_amount || row.calculated_amount)}</p>
              {row.overdue ? <p className="text-sm text-danger">Kechikkan oy. Qoldiq: {asMoney(row.debt_amount)}</p> : null}
            </article>
          ))}
          {hasGroup && !previewRows.length ? <p className="text-sm text-ink-500">Hisoblash ma'lumotlari yo'q.</p> : null}
        </div>
      </section>

      <section className="panel-card">
        <h3>Payment confirmation</h3>
        {!hasGroup ? <p className="text-sm text-ink-500">{noGroupMessage}</p> : null}
        <div className="grid grid-3 compact-cards">
          <label>
            Group
            <select
              value={form.groupId || 0}
              onChange={(event) => {
                const gid = Number(event.target.value || 0);
                const row = paymentRowsForForm.find((item) => Number(item.group_id || 0) === gid) || null;
                const debt = Number(row?.debt_amount || 0);
                setForm((prev) => ({ ...prev, groupId: gid, amount: debt > 0 ? debt.toFixed(2) : "" }));
              }}
            >
              <option value={0} disabled>Select group</option>
              {paymentRowsForForm.map((row) => (
                <option value={row.group_id} key={`group-opt-${row.group_id}`}>
                  {row.group_name || `Group #${row.group_id}`}
                </option>
              ))}
            </select>
          </label>
          <label>
            Payment method
            <select
              value={form.paymentMethod}
              onChange={(event) => {
                const method = event.target.value === "card" ? "card" : "cash";
                setForm((prev) => ({
                  ...prev,
                  paymentMethod: method,
                  cardId: method === "card" ? Number(defaultCard?.id || 0) : 0,
                }));
              }}
            >
              <option value="cash">Naqd</option>
              <option value="card">Plastik karta</option>
            </select>
          </label>
          {form.paymentMethod === "card" ? (
            <label>
              Card
              <select
                value={Number(form.cardId || 0)}
                onChange={(event) => setForm((prev) => ({ ...prev, cardId: Number(event.target.value || 0) }))}
              >
                <option value={0} disabled>Select card</option>
                {paymentMethods.map((row) => (
                  <option key={`pay-card-${row.id}`} value={Number(row.id || 0)}>
                    {String(row.owner_first_name || "").trim()} {String(row.owner_last_name || "").trim()} · {String(row.card_number_masked || row.card_number || "-")}
                    {Boolean(row.is_default) ? " (default)" : ""}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label>
            Amount
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.amount}
              onChange={(event) => setForm((prev) => ({ ...prev, amount: event.target.value }))}
              placeholder="0.00"
            />
          </label>
          <label>
            Note (optional)
            <input value={form.note} onChange={(event) => setForm((prev) => ({ ...prev, note: event.target.value }))} placeholder="Izoh" />
          </label>
          <div className="kv"><span>Remaining debt</span><strong>{asMoney(remainingDebt)}</strong></div>
        </div>

        {isSelectedOverdue ? (
          <article className="panel-card" style={{ borderColor: "rgba(220,38,38,0.35)" }}>
            <div className="row-between">
              <strong>Kechikkan to'lov</strong>
              <span className="chip chip-danger">Kechikkan</span>
            </div>
            <p>Oy: {monthKey}</p>
            <p>Qoldiq: {asMoney(remainingDebt)}</p>
            {penaltyLoading ? <p>Jarima hisoblanmoqda...</p> : null}
            {!penaltyLoading && penaltyPreview?.will_apply ? (
              <>
                <p>Jarima: -{asMoney(penaltyPreview.penalty_amount)} ({Number(penaltyPreview.penalty_percent || 0).toFixed(1)}%)</p>
                <p>Hozirgi D&apos;coin: {asMoney(penaltyPreview.current_dcoin_balance)}</p>
                <p>Jarimadan keyin: {asMoney(penaltyPreview.remaining_dcoin_after_penalty)}</p>
              </>
            ) : null}
            {!penaltyLoading && penaltyPreview?.already_applied ? <p>Bu oy uchun jarima avval qo&apos;llangan.</p> : null}
            {!penaltyLoading && penaltyPreview && !penaltyPreview.will_apply && !penaltyPreview.already_applied ? <p>Jarima qo&apos;llanmaydi.</p> : null}
          </article>
        ) : null}

        <div className="button-grid">
          <button
            className="btn btn-primary"
            type="button"
            disabled={!hasGroup || submitting || !form.groupId || remainingDebt <= 0 || (form.paymentMethod === "card" && Number(form.cardId || 0) <= 0)}
            onClick={() => {
              setForm((prev) => ({ ...prev, amount: Number(remainingDebt || 0).toFixed(2) }));
              submitPayment("full").catch(() => null);
            }}
          >
            {submitting ? "Saving..." : "Full payment"}
          </button>
          <button
            className="btn btn-soft"
            type="button"
            disabled={!quickRefundTx || refundSubmitting || quickRefundable <= 0}
            onClick={() => quickRefundTx && openRefund(quickRefundTx, "full")}
          >
            {refundSubmitting ? "Refunding..." : "Refund"}
          </button>
        </div>
        {errorText ? <p className="text-sm text-danger">{errorText}</p> : null}
        {noticeText ? <p className="text-sm text-success">{noticeText}</p> : null}
      </section>

      <section className="panel-card">
        <h3>Transaction history</h3>
        <div className="mobile-card-list">
          {transactions.map((row) => {
            const total = Number(row.amount || 0);
            const refunded = Number(row.refunded_amount || 0);
            const refundable = Math.max(0, total - refunded);
            const isActiveRefund = Number(refundDraft?.transactionId || 0) === Number(row.id || 0);
            return (
              <article className="panel-card" key={`tx-card-${row.id}`}>
                <div className="row-between">
                  <strong>{String(row.ym || "-")}</strong>
                  <span className={statusTone(String(row.status_after || "-"))}>{String(row.status_after || "-")}</span>
                </div>
                <p>Paid: {asMoney(row.amount)}</p>
                <p>Refunded: {asMoney(refunded)}</p>
                <p>Refundable: {asMoney(refundable)}</p>
                <p>Debt after: {asMoney(row.remaining_after)}</p>
                <p>Overpayment after: {asMoney(row.overpayment_after)}</p>
                <p>Method: {row.payment_method === "card" ? "Plastik karta" : row.payment_method === "cash" ? "Naqd" : row.payment_method || "-"}</p>
                {row.card_owner_name || row.card_number_masked ? (
                  <p>Card: {row.card_owner_name ? `${row.card_owner_name} · ` : ""}{row.card_number_masked || "-"}</p>
                ) : null}
                {Math.abs(Number(row.bonus_dpoints || 0)) > 1e-9 ? <p>D&apos;point bonus: {asMoney(row.bonus_dpoints)}</p> : null}
                <p>Admin: {row.confirmed_by_admin_name || "-"}</p>
                <p>Time: {String(row.created_at || "-")}</p>
                {row.note ? <p>Note: {String(row.note)}</p> : null}
                {refundable > 0 ? (
                  <div className="button-grid inline">
                    <button className="btn btn-soft" type="button" onClick={() => openRefund(row, "full")}>Full refund</button>
                    <button className="btn btn-soft" type="button" onClick={() => openRefund(row, "partial")}>Partial refund</button>
                  </div>
                ) : (
                  <p className="text-sm text-ink-500">Refund limiti qolmagan.</p>
                )}
                {isActiveRefund ? (
                  <article className="panel-card">
                    <div className="row-between">
                      <strong>Refund</strong>
                      <span className="chip">{refundDraft?.mode === "full" ? "Full" : "Partial"}</span>
                    </div>
                    <label>
                      Amount
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={refundDraft?.amount || ""}
                        onChange={(event) => setRefundDraft((prev) => (prev ? { ...prev, amount: event.target.value } : prev))}
                      />
                    </label>
                    <label>
                      Note (required)
                      <input
                        value={refundDraft?.note || ""}
                        onChange={(event) => setRefundDraft((prev) => (prev ? { ...prev, note: event.target.value } : prev))}
                        placeholder="Refund sababi"
                      />
                    </label>
                    <div className="button-grid inline">
                      <button className="btn btn-primary" type="button" disabled={refundSubmitting} onClick={() => submitRefund().catch(() => null)}>
                        {refundSubmitting ? "Saving..." : "Confirm refund"}
                      </button>
                      <button className="btn btn-soft" type="button" disabled={refundSubmitting} onClick={() => setRefundDraft(null)}>
                        Cancel
                      </button>
                    </div>
                  </article>
                ) : null}
              </article>
            );
          })}
          {!transactions.length ? <p className="text-sm text-ink-500">Hozircha tranzaksiya yo&apos;q.</p> : null}
        </div>
      </section>

      <section className="panel-card">
        <h3>D&apos;point bonus history</h3>
        <div className="mobile-card-list">
          {bonusHistory.map((row) => (
            <article className="panel-card" key={`bonus-card-${row.id}`}>
              <div className="row-between">
                <strong>{String(row.ym || "-")}</strong>
                <span className="chip">{String(row.bonus_type || "-")}</span>
              </div>
              <p>Amount: {asMoney(row.amount)} D&apos;point</p>
              <p>Reversed: {Number(row.reversed || 0) === 1 ? "Yes" : "No"}</p>
              {row.reversed_at ? <p>Reversed at: {String(row.reversed_at)}</p> : null}
              <p>Time: {String(row.created_at || "-")}</p>
            </article>
          ))}
          {!bonusHistory.length ? <p className="text-sm text-ink-500">Bonus yozuvlari yo&apos;q.</p> : null}
        </div>
      </section>

      <section className="panel-card">
        <h3>Refund history</h3>
        <div className="mobile-card-list">
          {refunds.map((row) => (
            <article className="panel-card" key={`refund-card-${row.id}`}>
              <div className="row-between">
                <strong>Refund #{row.id}</strong>
                <span className="chip">{String(row.refund_type || "partial")}</span>
              </div>
              <p>Month: {row.ym || "-"}</p>
              <p>Amount: {asMoney(row.amount)}</p>
              <p>Tx: #{row.transaction_id || "-"}</p>
              <p>Status: {String(row.status_before || "-")} → {String(row.status_after || "-")}</p>
              <p>Debt after: {asMoney(row.debt_after)}</p>
              <p>Overpayment after: {asMoney(row.overpayment_after)}</p>
              <p>Admin: {row.refunded_by_admin_name || "-"}</p>
              <p>Time: {String(row.created_at || "-")}</p>
              <p>Note: {String(row.note || "-")}</p>
            </article>
          ))}
          {!refunds.length ? <p className="text-sm text-ink-500">Refund yozuvlari yo&apos;q.</p> : null}
        </div>
      </section>

      {loading ? <p className="text-sm text-ink-500">Loading...</p> : null}
    </div>
  );
}
