"use client";

import { PublicShell } from "../public-shell";
import { useWebT } from "../ui/web-i18n";

export default function AboutPage() {
  const tt = useWebT();

  return (
    <PublicShell
      activeTab="about"
      kicker={tt("about.kicker", "Biz haqimizda")}
      title={tt("about.title", "Diamond Education - kelajagingiz poydevori")}
      subtitle={tt("about.subtitle", "Eng yaxshi kelajak shu yerdan boshlanadi")}
    >
      <div className="max-w-4xl mx-auto space-y-12 pb-16">

        {/* Founder Section */}
        <section className="bg-white dark:bg-gray-800 rounded-3xl overflow-hidden shadow-xl shadow-gray-200/50 dark:shadow-none border border-gray-100 dark:border-gray-700 flex flex-col md:flex-row items-stretch">
          <div className="w-full md:w-2/5 shrink-0 bg-gray-100 dark:bg-gray-900 relative flex items-center justify-center aspect-[3/4] md:aspect-auto md:min-h-[520px]">
            <img 
              src="/founder.jpg" 
              alt={tt("about.founder.name", "Akbarxo'ja Anvarxo'jayev")} 
              className="absolute inset-0 w-full h-full object-cover object-bottom" 
            />
          </div>
          <div className="p-8 md:p-12 w-full md:w-3/5 flex flex-col justify-center bg-gradient-to-br from-white to-blue-50/50 dark:from-gray-800 dark:to-gray-800/80">
            <span className="text-blue-600 dark:text-blue-400 font-bold tracking-widest uppercase text-xs mb-3 flex items-center gap-2">
              <span className="w-6 h-px bg-blue-600 dark:bg-blue-400"></span>
              {tt("about.founder.role", "Asoschi va Bosh direktor")}
            </span>
            <h2 className="text-3xl md:text-4xl font-black text-gray-900 dark:text-white mb-6">
              {tt("about.founder.title", "Yorqin kelajakni birgalikda quramiz")}
            </h2>
            <div className="relative">
              <svg className="absolute -top-4 -left-4 w-10 h-10 text-blue-100 dark:text-gray-700 -z-10" fill="currentColor" viewBox="0 0 24 24"><path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" /></svg>
              <div className="prose prose-lg dark:prose-invert text-gray-600 dark:text-gray-400 leading-relaxed font-medium">
                <p>
                  {tt("about.founder.quote1", "Ta'lim – bu faqatgina bilim berish emas, balki yoshlarga ishonch ulashish, ularning ongida katta maqsadlar sari ilk qadamni qo'yishga yordam berishdir.")}
                </p>
                <p className="mt-4">
                  {tt("about.founder.quote2", "Diamond Education markazini yaratishda bizning eng asosiy maqsadimiz har bir bilim oluvchining imkoniyatlarini maksimal ochib beradigan sifatli muhit va tizim yaratish edi. Maqsad qanchalik katta bo'lmasin, unga to'g'ri tayyorgarlik va kuchli jamoa bilan yetib borish mumkin.")}
                </p>
              </div>
              <div className="mt-8">
                <p className="text-lg font-black text-gray-900 dark:text-white">
                  {tt("about.founder.name", "Akbarxo'ja Anvarxo'jayev")}
                </p>
                <p className="text-sm text-gray-500 font-bold uppercase tracking-wide mt-1">
                  Diamond Education
                </p>
              </div>
            </div>
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

          <div className="grid grid-cols-3 gap-2 sm:gap-6 md:gap-8">
            {/* Rushana Xayitbayevna */}
            <div className="group bg-white dark:bg-gray-800 rounded-2xl sm:rounded-3xl overflow-hidden shadow-md sm:shadow-xl border border-gray-100 dark:border-gray-700 hover:shadow-2xl hover:-translate-y-2 transition-all duration-300">
              <div className="relative aspect-[3/4] overflow-hidden bg-gray-100 dark:bg-gray-900">
                <img
                  src="/teacher-rushana.jpg"
                  alt="Rushana Xayitbayevna"
                  className="h-full w-full object-cover object-bottom transition-transform duration-500 group-hover:scale-105"
                />
              </div>
              <div className="p-2 sm:p-6">
                <h3 className="text-[11px] sm:text-xl leading-tight font-black text-gray-900 dark:text-white mb-1">Rushana Xayitbayevna</h3>
                <p className="text-blue-600 dark:text-blue-400 font-bold text-[8px] sm:text-sm uppercase tracking-normal sm:tracking-wide leading-tight mb-0 sm:mb-4">{tt("about.team.subject.russian", "Rus tili o'qituvchisi")}</p>
                <ul className="mt-2 space-y-1 sm:space-y-2">
                  {[
                    tt("about.team.exp8", "8 yillik tajriba"),
                    tt("about.team.rushana.level", "Til darajasi: C2"),
                    tt("about.team.rushana.uni1", "Toshkent Davlat Pedagogika Universiteti"),
                    tt("about.team.rushana.uni2", "Rossiya Davlat Pedagogika Universiteti — Magistratura"),
                  ].map((item) => (
                    <li key={item} className="flex items-start gap-1 sm:gap-2 text-[8px] sm:text-sm leading-tight text-gray-600 dark:text-gray-400">
                      <span className="mt-0.5 sm:mt-1 w-2.5 h-2.5 sm:w-4 sm:h-4 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center shrink-0">
                        <svg className="w-1.5 h-1.5 sm:w-2.5 sm:h-2.5 text-blue-600 dark:text-blue-400" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/></svg>
                      </span>
                      <span className="min-w-0 break-words font-medium">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Diyor Abdugaliyev */}
            <div className="group bg-white dark:bg-gray-800 rounded-2xl sm:rounded-3xl overflow-hidden shadow-md sm:shadow-xl border border-gray-100 dark:border-gray-700 hover:shadow-2xl hover:-translate-y-2 transition-all duration-300">
              <div className="relative aspect-[3/4] overflow-hidden bg-gray-100 dark:bg-gray-900">
                <img
                  src="/teacher-diyor.jpg"
                  alt="Diyor Abdugaliyev"
                  className="h-full w-full object-cover object-bottom transition-transform duration-500 group-hover:scale-105"
                />
              </div>
              <div className="p-2 sm:p-6">
                <h3 className="text-[11px] sm:text-xl leading-tight font-black text-gray-900 dark:text-white mb-1">Diyor Abdugaliyev</h3>
                <p className="text-blue-600 dark:text-blue-400 font-bold text-[8px] sm:text-sm uppercase tracking-normal sm:tracking-wide leading-tight mb-0 sm:mb-4">{tt("about.team.subject.english", "Ingliz tili o'qituvchisi")}</p>
                <ul className="mt-2 space-y-1 sm:space-y-2">
                  {[
                    tt("about.team.exp4", "4 yillik tajriba"),
                    tt("about.team.diyor.score", "IELTS 8.0"),
                    tt("about.team.diyor.uni", "UWED (Jahon iqtisodiyoti va diplomatiya universiteti)"),
                  ].map((item) => (
                    <li key={item} className="flex items-start gap-1 sm:gap-2 text-[8px] sm:text-sm leading-tight text-gray-600 dark:text-gray-400">
                      <span className="mt-0.5 sm:mt-1 w-2.5 h-2.5 sm:w-4 sm:h-4 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center shrink-0">
                        <svg className="w-1.5 h-1.5 sm:w-2.5 sm:h-2.5 text-blue-600 dark:text-blue-400" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/></svg>
                      </span>
                      <span className="min-w-0 break-words font-medium">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Dinora Sobirova */}
            <div className="group bg-white dark:bg-gray-800 rounded-2xl sm:rounded-3xl overflow-hidden shadow-md sm:shadow-xl border border-gray-100 dark:border-gray-700 hover:shadow-2xl hover:-translate-y-2 transition-all duration-300">
              <div className="relative aspect-[3/4] overflow-hidden bg-gray-100 dark:bg-gray-900">
                <img
                  src="/teacher-dinora.jpg"
                  alt="Dinora Sobirova"
                  className="h-full w-full object-cover object-bottom transition-transform duration-500 group-hover:scale-105"
                />
              </div>
              <div className="p-2 sm:p-6">
                <h3 className="text-[11px] sm:text-xl leading-tight font-black text-gray-900 dark:text-white mb-1">Dinora Sobirova</h3>
                <p className="text-blue-600 dark:text-blue-400 font-bold text-[8px] sm:text-sm uppercase tracking-normal sm:tracking-wide leading-tight mb-0 sm:mb-4">{tt("about.team.subject.english", "Ingliz tili o'qituvchisi")}</p>
                <ul className="mt-2 space-y-1 sm:space-y-2">
                  {[
                    tt("about.team.exp4", "4 yillik tajriba"),
                    tt("about.team.dinora.score", "IELTS 6.5"),
                  ].map((item) => (
                    <li key={item} className="flex items-start gap-1 sm:gap-2 text-[8px] sm:text-sm leading-tight text-gray-600 dark:text-gray-400">
                      <span className="mt-0.5 sm:mt-1 w-2.5 h-2.5 sm:w-4 sm:h-4 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center shrink-0">
                        <svg className="w-1.5 h-1.5 sm:w-2.5 sm:h-2.5 text-blue-600 dark:text-blue-400" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/></svg>
                      </span>
                      <span className="min-w-0 break-words font-medium">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
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
                  src="https://maps.google.com/maps?q=41.110455,69.052183&z=18&output=embed"
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
                  src="https://maps.google.com/maps?q=41.111575,69.062431&z=18&output=embed"
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
