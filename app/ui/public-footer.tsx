"use client";

import { useWebT, Locale } from "./web-i18n";

export function PublicFooter() {
  const tt = useWebT();
  const locale: Locale = "uz"; // Defaulting to uz for static, normally passed down

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <footer className="footer-v2">
      <div className="footer-v2-inner">
        <div className="footer-v2-top grid grid-cols-1 md:grid-cols-3 gap-12 lg:gap-16">
          {/* Brand */}
          <div className="flex flex-col">
            <p className="footer-v2-brand-name" style={{ display: "inline-flex", flexDirection: "column", lineHeight: 1.0, verticalAlign: "middle" }}>
              <span style={{ fontSize: "20px", fontWeight: 900, letterSpacing: "-0.02em", color: "#ffffff" }}>
                D<span style={{ position: "relative", display: "inline-block" }}>ı<svg viewBox="0 0 24 24" fill="currentColor" style={{ position: "absolute", top: "-0.1em", left: "50%", transform: "translateX(-50%)", width: "0.26em", height: "0.26em", color: "var(--ev-primary, #002DFF)" }}><path d="M12 2L3.5 12 12 22l8.5-10z" /></svg></span>amond
              </span>
              <span style={{ fontSize: "9.5px", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.14em", color: "var(--ev-primary)", marginTop: "1.5px" }}>Education</span>
            </p>
            <p className="footer-v2-tagline mt-4">
              {tt("landing.footer.about", "Kelajak texnologiyalari va mukammal metodikaga asoslangan premium ta'lim platformasi.")}
            </p>
            <div className="footer-socials mt-6">
              <a href="https://t.me/diamond_education1" target="_blank" rel="noreferrer" className="footer-social-link" title="Telegram" aria-label="Telegram">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M21.968 3.549a1.002 1.002 0 0 0-.904-.265C18.665 3.945 2.68 8.136 2.054 8.358a1 1 0 0 0-.104 1.865c1.439.513 3.328 1.144 3.328 1.144s1.146 3.492 1.733 5.235a1.003 1.003 0 0 0 1.57.51c1.233-.949 2.758-2.122 2.758-2.122s2.915 2.148 5.309 3.856a1.003 1.003 0 0 0 1.602-.519c1.68-7.915 4.093-19.167 4.093-19.167a.999.999 0 0 0-.375-.729zM7.275 12.022s8.59-5.467 11.23-7.142c.09-.06.21-.03.21.08 0 .05-.02.09-.06.12-2.583 2.37-8.156 7.502-8.156 7.502s-.226 2.33-.356 3.659c-.066-.757-.872-4.219-.872-4.219z"/>
                </svg>
              </a>
              <a href="https://www.instagram.com/diamond_education_" target="_blank" rel="noreferrer" className="footer-social-link" title="Instagram" aria-label="Instagram">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect>
                  <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path>
                  <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line>
                </svg>
              </a>
            </div>
          </div>

          {/* Navigation */}
          <div className="flex flex-col">
            <p className="footer-v2-col-title mb-4">{tt("footer.nav.title", "Sahifalar")}</p>
            <div className="footer-v2-links flex flex-col gap-3">
              {[
                { id: "courses",  label: tt("landing.nav.courses",  "Kurslar"), url: "/courses" },
                { id: "results",  label: tt("landing.nav.results",  "Natijalar"), url: "/results" },
                { id: "about",    label: tt("landing.nav.about",    "Biz haqimizda"), url: "/about" },
              ].map(item => (
                <a
                  key={item.id}
                  className="footer-v2-link"
                  href={item.url}
                >
                  {item.label}
                </a>
              ))}
            </div>
          </div>

          {/* Links & Contact */}
          <div className="flex flex-col">
            <p className="footer-v2-col-title mb-4">{tt("footer.links.title", "Havolalar va Aloqa")}</p>
            <div className="footer-v2-links flex flex-col gap-3">
              <a className="footer-v2-link" href="/login">{tt("common.login", "Kirish")}</a>
              <a className="footer-v2-link" href="/assets/ommaviy-oferta.png" target="_blank" rel="noreferrer">
                {tt("landing.footer.oferta", "Ommaviy Oferta")}
              </a>
              <div className="w-full h-px bg-white/10 my-2"></div>
              <a className="footer-v2-link" href="tel:+998977483634">+998 (97) 748-36-34</a>
              <a className="footer-v2-link" href="tel:+998977443634">+998 (97) 744-36-34</a>
              <a className="footer-v2-link" href="mailto:Admin@diamond-education.uz">Admin@diamond-education.uz</a>
              <a className="footer-v2-link" href="mailto:info@diamond-education.uz">info@diamond-education.uz</a>
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="footer-v2-bottom">
          <p>© {new Date().getFullYear()} Diamond Education. {tt("landing.footer.rights", "Barcha huquqlar himoyalangan.")}</p>
        </div>
      </div>
    </footer>
  );
}
