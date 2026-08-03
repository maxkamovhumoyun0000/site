"use client";

import React, { useState, useEffect } from "react";
import { useWebT } from "./web-i18n";

type GenericRow = any;

export function SupportBroadcastsPanel({
  onSupportCall,
}: {
  onSupportCall: (path: string, payload?: any, method?: "GET" | "POST" | "PATCH" | "DELETE", successText?: string) => Promise<any>;
}) {
  const tt = useWebT();
  const [broadcasts, setBroadcasts] = useState<GenericRow[]>([]);
  const [targetType, setTargetType] = useState("all_students");
  const [messageText, setMessageText] = useState("");
  const [buttonText, setButtonText] = useState("");
  const [buttonUrl, setButtonUrl] = useState("");
  const [buttonType, setButtonType] = useState("auto");
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
    loadBroadcasts();
  }, []);

  async function loadBroadcasts() {
    setLoading(true);
    try {
      const res = await onSupportCall("/support/broadcasts", undefined, "GET");
      if (res && res.items) {
        setBroadcasts(res.items);
      }
    } catch (err) {
      console.error("Failed to load broadcasts", err);
    }
    setLoading(false);
  }

  async function createBroadcast() {
    if (!messageText.trim()) {
      alert("Xabar matnini kiriting");
      return;
    }
    if ((buttonText && !buttonUrl) || (!buttonText && buttonUrl)) {
      alert("Tugma matni va havolasi birga kiritilishi kerak");
      return;
    }
    if (buttonUrl && !buttonUrl.startsWith("http://") && !buttonUrl.startsWith("https://")) {
      alert("Tugma havolasi http:// yoki https:// bilan boshlanishi kerak");
      return;
    }
    setLoading(true);
    const payload = {
      target_type: targetType,
      message_text: messageText,
      button_text: buttonText || undefined,
      button_url: buttonUrl || undefined,
      button_type: buttonType,
      group_ids: [],
      user_ids: []
    };
    try {
      const res = await onSupportCall("/support/broadcasts", payload, "POST", "Xabar muvaffaqiyatli jo'natildi");
      if (res && res.broadcast_id) {
        setMessageText("");
        setButtonText("");
        setButtonUrl("");
        setButtonType("auto");
        loadBroadcasts();
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Xabar yuborishda xatolik yuz berdi");
    }
    setLoading(false);
  }

  return (
    <div className="page-stack">
      <section className="panel-card">
        <h3>Yangi Ommaviy Xabar (Broadcast)</h3>
        <p className="text-sm text-ink-500 mb-4">Mavjud support dars o'quvchilariga Telegram bot orqali xabar yuborish.</p>
        
        <div className="grid grid-1 gap-4 max-w-[600px]">
          <label>
            Kimlarga jo'natiladi
            <select value={targetType} onChange={(e) => setTargetType(e.target.value)}>
              <option value="all_students">Support darsim o'quvchilariga</option>
            </select>
          </label>
          
          <label>
            Xabar matni
            <textarea 
              rows={5} 
              value={messageText} 
              onChange={(e) => setMessageText(e.target.value)} 
              placeholder="Xabar matnini kiriting..." 
            />
          </label>
          
          <div className="grid grid-2 gap-4">
            <label>
              Tugma matni (Ixtiyoriy)
              <input 
                value={buttonText} 
                onChange={(e) => setButtonText(e.target.value)} 
                placeholder="Masalan: So'rovnomani to'ldirish" 
              />
            </label>
            <label>
              Tugma turi
              <select value={buttonType} onChange={(e) => setButtonType(e.target.value)}>
                <option value="auto">Avtomatik</option>
                <option value="regular">Oddiy havola</option>
                <option value="webapp">Telegram Mini App</option>
              </select>
            </label>
          </div>
          <label>
            Tugma havolasi (Link)
            <input 
              value={buttonUrl} 
              onChange={(e) => setButtonUrl(e.target.value)} 
              placeholder="https://..." 
            />
          </label>
          
          <div className="mt-2">
            <button className="btn btn-primary" onClick={createBroadcast} disabled={loading}>
              Xabarni Jo'natish
            </button>
          </div>
        </div>
      </section>
      
      <section className="panel-card mt-6">
        <h3>Yuborilgan Xabarlar Tarixi</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Sana</th>
                <th>Xabar</th>
                <th>Qabul qiluvchilar</th>
                <th>Holati</th>
              </tr>
            </thead>
            <tbody>
              {broadcasts.map(row => (
                <tr key={row.id}>
                  <td>{row.id}</td>
                  <td>{new Date(row.created_at).toLocaleString()}</td>
                  <td className="max-w-[300px] truncate">{row.message_text}</td>
                  <td>{row.total_recipients} ta</td>
                  <td>
                    <span className={`badge ${row.status === 'completed' ? 'green' : 'gray'}`}>
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))}
              {broadcasts.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center">Xabarlar topilmadi</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
