"use client";

import { PublicShell } from "../public-shell";
import { useWebT } from "../ui/web-i18n";
import Image from "next/image";

export default function AboutPage() {
  const tt = useWebT();

  return (
    <PublicShell
      activeTab="about"
      kicker={tt("about.kicker", "Biz haqimizda")}
      title={tt("about.title", "Diamond Education - kelajagingiz poydevori")}
      subtitle={tt("about.subtitle", "Eng yaxshi kelajak shu yerdan boshlanadi")}
    >
      <div className="mx-auto max-w-6xl space-y-12 pb-16">

        <section aria-label={tt("about.founder.role", "Bosh direktor")} className="mx-auto grid max-w-5xl items-center gap-8 md:grid-cols-[minmax(260px,380px)_1fr] md:gap-12">
          <div className="relative mx-auto aspect-[9/16] w-full max-w-[380px] overflow-hidden rounded-2xl shadow-lg">
            <Image
              src="/team/ceo.webp"
              alt={tt("about.founder.name", "Akbarxo'ja Anvarxo'jayev — Bosh direktor")}
              fill
              sizes="(max-width: 767px) 100vw, 380px"
              fetchPriority="high"
              className="object-contain"
            />
          </div>
          <div className="space-y-5 text-center md:text-left">
            <div>
              <p className="text-sm font-bold uppercase tracking-[0.16em] text-blue-700">{tt("about.founder.role", "Bosh direktor")}</p>
              <h2 className="mt-2 text-3xl font-black text-slate-900 md:text-4xl">{tt("about.founder.name", "Akbarxo'ja Anvarxo'jayev")}</h2>
              <p className="mt-2 text-lg font-semibold text-slate-600">{tt("about.founder.title", "Birgalikda yorqin kelajak quramiz")}</p>
            </div>
            <blockquote className="space-y-4 text-base leading-8 text-slate-700 md:text-lg">
              <p>{tt("about.founder.quote1", "Ta'lim – bu faqatgina bilim berish emas, balki yoshlarga ishonch ulashish, ularning ongida katta maqsadlar sari ilk qadamni qo'yishga yordam berishdir.")}</p>
              <p>{tt("about.founder.quote2", "Diamond Education markazini yaratishda bizning eng asosiy maqsadimiz har bir bilim oluvchining imkoniyatlarini maksimal ochib beradigan sifatli muhit va tizim yaratish edi. Maqsad qanchalik katta bo'lmasin, unga to'g'ri tayyorgarlik va kuchli jamoa bilan yetib borish mumkin.")}</p>
            </blockquote>
          </div>
        </section>

        {/* ── BIZNING JAMOA ──────────────────────────────────────── */}
        <section className="mt-4">
          <div className="flex flex-col items-center text-center gap-3 mb-10">
            <span className="text-blue-600 dark:text-blue-400 font-bold tracking-widest uppercase text-xs flex items-center gap-2">
              <span className="w-6 h-px bg-blue-600 dark:bg-blue-400" />
              {tt("about.team.kicker", "Professional O'qituvchilar")}
              <span className="w-6 h-px bg-blue-600 dark:bg-blue-400" />
            </span>
            <h2 className="text-3xl md:text-4xl font-black text-gray-900 dark:text-white">
              {tt("about.team.title", "Bizning Jamoa")}
            </h2>
            <p className="text-gray-500 dark:text-gray-400 max-w-xl leading-relaxed">
              {tt("about.team.subtitle", "Har biri o'z sohasida yetuk mutaxassis bo'lgan, tajribali va fidokor o'qituvchilarimiz bilan tanishing.")}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-5 lg:gap-7">
            {[
              ["/team/rushana-abidova.webp", "Rushana Abidova"],
              ["/team/diyor-abdugaliyev.webp", "Diyor Abdugaliyev"],
              ["/team/dinora-sobirova.webp", "Dinora Sobirova"],
              ["/team/shaxzoda-begmatova.webp", "Shaxzoda Begmatova"],
              ["/team/baxtiyor-musurmonov.webp", "Baxtiyor Musurmonov"],
              ["/team/muhsina-xasanboyeva.webp", "Muhsina Xasanboyeva"],
            ].map(([src, name]) => (
              <div key={src} className="relative aspect-[9/16] overflow-hidden rounded-xl sm:rounded-2xl">
                <Image
                  src={src}
                  alt={name}
                  fill
                  sizes="(max-width: 639px) 50vw, (max-width: 1023px) 33vw, 360px"
                  className="object-contain"
                />
              </div>
            ))}
          </div>
        </section>

        {/* ── FILIALLAR / LOCATION SECTION ────────────────────────────────────── */}
        <section className="branches-section mt-16" id="location">
          <div className="flex flex-col items-center text-center gap-4 mb-12">
            <h2 className="section-v2-h2">{tt("landing.branches.title", "Filiallarimiz")}</h2>
            <p className="section-v2-subtitle text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
              {tt("landing.branches.subtitle", "Qulay joylashgan ikki filialimizdan biriga tashrif buyuring va bepul trial darsga yoziling.")}
            </p>
          </div>

          <div className="branches-grid">
            {/* Filial 1 */}
            <div className="branch-card">
              <div className="branch-card-header">
                <div className="branch-icon-wrap">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                    <circle cx="12" cy="10" r="3"/>
                  </svg>
                </div>
                <div>
                  <p className="branch-num">01</p>
                  <h3 className="branch-title">{tt("landing.branches.branch1", "1-Filial")}</h3>
                </div>
              </div>
              <div className="branch-map-wrap">
                <iframe
                  title="Diamond Education 1-filial"
                  src="https://www.google.com/maps?q=41.110455,69.052183&z=18&output=embed"
                  width="100%"
                  height="220"
                  style={{ border: 0, borderRadius: "12px" }}
                  allowFullScreen
                  loading="lazy"
                  referrerPolicy="no-referrer-when-downgrade"
                />
              </div>
              <div className="branch-info">
                <div className="branch-contacts">
                  <a href="tel:+998977483634" className="branch-phone">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 13a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 2.22h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8 9.91a16 16 0 0 0 6 6l1.27-.85a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 17z"/></svg>
                    +998 (97) 748-36-34
                  </a>
                  <a href="tel:+998977443634" className="branch-phone">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 13a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 2.22h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8 9.91a16 16 0 0 0 6 6l1.27-.85a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 17z"/></svg>
                    +998 (97) 744-36-34
                  </a>
                </div>
                <a
                  href="https://maps.app.goo.gl/2scoxEwH4eEUeXbg7"
                  target="_blank"
                  rel="noreferrer"
                  className="branch-map-btn"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                  {tt("landing.branches.map", "Xaritada ko'rish")}
                </a>
              </div>
            </div>

            {/* Filial 2 */}
            <div className="branch-card">
              <div className="branch-card-header">
                <div className="branch-icon-wrap">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                    <circle cx="12" cy="10" r="3"/>
                  </svg>
                </div>
                <div>
                  <p className="branch-num">02</p>
                  <h3 className="branch-title">{tt("landing.branches.branch2", "2-Filial")}</h3>
                </div>
              </div>
              <div className="branch-map-wrap">
                <iframe
                  title="Diamond Education 2-filial"
                  src="https://www.google.com/maps?q=41.111575,69.062431&z=18&output=embed"
                  width="100%"
                  height="220"
                  style={{ border: 0, borderRadius: "12px" }}
                  allowFullScreen
                  loading="lazy"
                  referrerPolicy="no-referrer-when-downgrade"
                />
              </div>
              <div className="branch-info">
                <div className="branch-contacts">
                  <a href="tel:+998977483634" className="branch-phone">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 13a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 2.22h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8 9.91a16 16 0 0 0 6 6l1.27-.85a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 17z"/></svg>
                    +998 (97) 748-36-34
                  </a>
                  <a href="tel:+998977443634" className="branch-phone">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 13a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 2.22h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8 9.91a16 16 0 0 0 6 6l1.27-.85a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 17z"/></svg>
                    +998 (97) 744-36-34
                  </a>
                </div>
                <a
                  href="https://maps.app.goo.gl/XDnNsx3FQfj7LRQU6"
                  target="_blank"
                  rel="noreferrer"
                  className="branch-map-btn"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                  {tt("landing.branches.map", "Xaritada ko'rish")}
                </a>
              </div>
            </div>
          </div>
        </section>
      </div>
    </PublicShell>
  );
}
