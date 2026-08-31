"use client";

import { useEffect, useState } from "react";
import { ModalPortal } from "./modal-portal";

function assetUrl(raw: unknown) {
  const value = String(raw || "").trim();
  if (!value) return "";
  if (/^(https?:|data:|blob:)/i.test(value)) return value;
  return value.startsWith("/") ? `/api${value}` : `/api/${value}`;
}

function when(raw: unknown) {
  if (!raw) return "Hali ma’lumot yo‘q";
  const date = new Date(String(raw));
  if (Number.isNaN(date.getTime())) return String(raw);
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

export function StudentPresenceProfile({
  userId,
  onApiCall,
  onClose,
}: {
  userId: number;
  onApiCall: any;
  onClose: () => void;
}) {
  const [data, setData] = useState<any | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    onApiCall(`/users/${userId}/presence-profile`, undefined, "GET")
      .then((result: any) => { if (!cancelled) setData(result); })
      .catch((err: any) => { if (!cancelled) setError(err?.message || "Profilni yuklab bo'lmadi"); });
    return () => { cancelled = true; };
  }, [userId, onApiCall]);

  const user = data?.user || {};
  const presence = data?.presence || {};
  const balance = data?.balance || {};
  const online = Boolean(presence.is_online || user.is_online);
  const groups = Array.isArray(data?.groups) ? data.groups : [];
  const gifts = Array.isArray(data?.purchased_gifts) ? data.purchased_gifts : [];
  const name = String(user.full_name || "Student");
  const avatar = assetUrl(user.avatar_url || user.profile_image_url);

  return (
    <ModalPortal open>
      <div className="overlay-modal-backdrop" onClick={onClose}>
        <article className="overlay-modal-card max-w-xl" onClick={(event) => event.stopPropagation()}>
          <div className="row-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="relative shrink-0">
                {avatar ? <img src={avatar} alt={name} className="h-16 w-16 rounded-full object-cover border-2 border-cyan-400/50" /> : <div className="h-16 w-16 rounded-full bg-cyan-500/15 text-cyan-500 flex items-center justify-center text-xl font-black">{name.slice(0, 1).toUpperCase()}</div>}
                <span className={`absolute bottom-0 right-0 h-4 w-4 rounded-full border-2 border-white dark:border-navy-900 ${online ? "bg-emerald-500" : "bg-ink-300 dark:bg-navy-500"}`} />
              </div>
              <div className="min-w-0">
                <h3 className="truncate">{name}</h3>
                <p className={`text-sm font-semibold ${online ? "text-emerald-500" : "text-ink-500 dark:text-navy-300"}`}>{online ? "Hozir online" : `Oxirgi online: ${when(presence.last_online_at || user.last_online_at)}`}</p>
              </div>
            </div>
            <button type="button" className="admin-modal-close" onClick={onClose}>×</button>
          </div>
          {error ? <p className="error-box mt-4">{error}</p> : null}
          {!data && !error ? <p className="py-12 text-center text-sm font-semibold text-ink-500">Yuklanmoqda...</p> : null}
          {data ? <div className="mt-5 space-y-4">
            <div className="grid grid-cols-3 gap-2">
              {[["D’Coin", balance.dcoin], ["D’Point", balance.dpoints], ["Ticket", data.ticket_count || 0]].map(([label, value]) => <div key={String(label)} className="rounded-xl bg-surface-soft dark:bg-white/5 border border-line dark:border-white/10 p-3 text-center"><strong className="block text-cyan-500">{Number(value || 0).toFixed(1)}</strong><span className="text-[11px] font-bold text-ink-500 dark:text-navy-300">{label}</span></div>)}
            </div>
            <section><h4 className="font-black mb-2">O‘qiyotgan guruhlari</h4>{groups.length ? groups.map((group: any) => <div key={group.id || group.name} className="rounded-lg bg-surface-soft dark:bg-white/5 px-3 py-2 text-sm font-semibold mb-1">👥 {group.name || "-"}{group.subject ? ` · ${group.subject}` : ""}</div>) : <p className="text-sm text-ink-500">Guruh ma’lumoti yo‘q</p>}</section>
            <section><h4 className="font-black mb-2">Sotib olgan sovg‘alari</h4>{gifts.length ? gifts.slice(0, 10).map((gift: any, idx: number) => <div key={gift.id || idx} className="rounded-lg bg-surface-soft dark:bg-white/5 px-3 py-2 text-sm font-semibold mb-1">🎁 {gift.item_title || gift.gift?.title || "Sovg‘a"}</div>) : <p className="text-sm text-ink-500">Hali sovg‘a olmagan</p>}</section>
          </div> : null}
        </article>
      </div>
    </ModalPortal>
  );
}
