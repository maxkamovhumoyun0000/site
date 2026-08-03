"use client";

function MockCard({ title, meta, value }: { title: string; meta: string; value: string }) {
  return (
    <article className="stat-card">
      <span>{meta}</span>
      <strong>{value}</strong>
      <p>{title}</p>
    </article>
  );
}

function MockTable() {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Talaba</th>
            <th>Guruh</th>
            <th>Holat</th>
            <th>Amal</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Ali Valiyev</td>
            <td>English B1-2</td>
            <td>Faol</td>
            <td><button className="btn btn-soft small">Ko&apos;rish</button></td>
          </tr>
          <tr>
            <td>Madina Rahimova</td>
            <td>Russian A2-1</td>
            <td>Kutilmoqda</td>
            <td><button className="btn btn-soft small">Ko&apos;rish</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function LoginPreview() {
  return (
    <section className="auth-page" style={{ minHeight: "auto", padding: 14 }}>
      <div className="auth-card compact">
        <p className="pill-label">Diamond Education</p>
        <h1>Tizimga Kirish</h1>
        <p>Login ID va parol orqali profilingizga xavfsiz kiring.</p>
        <div className="auth-form">
          <label>
            Login ID
            <input placeholder="Masalan: std-1024" />
          </label>
          <label>
            Parol
            <input type="password" placeholder="********" />
          </label>
          <button className="btn btn-primary">Kirish</button>
        </div>
      </div>
    </section>
  );
}

function HomePreview() {
  return (
    <div className="page-stack">
      <section className="hero-card">
        <div>
          <p className="pill-label">Bosh Sahifa</p>
          <h2>Diamond Education Platformasi</h2>
          <p>Talaba, o&apos;qituvchi va administrator uchun yagona boshqaruv markazi.</p>
        </div>
        <div className="hero-balance">
          <small>Joriy Oy</small>
          <strong>+1,284</strong>
          <span>Faol foydalanuvchi</span>
        </div>
      </section>
      <section className="grid grid-4">
        <MockCard title="Faol talabalar soni" meta="Talabalar" value="864" />
        <MockCard title="Faol guruhlar soni" meta="Guruhlar" value="52" />
        <MockCard title="Bugungi davomat" meta="Davomat" value="91%" />
        <MockCard title="Yaratilgan maqolalar" meta="Maqolalar" value="128" />
      </section>
    </div>
  );
}

function RolePreview({
  role,
  subtitle,
}: {
  role: "Admin" | "O'qituvchi" | "Talaba" | "Support Teacher";
  subtitle: string;
}) {
  return (
    <div className="page-stack">
      <section className="section-head">
        <p className="pill-label">{role}</p>
        <h2>{role} Dashboard</h2>
        <p>{subtitle}</p>
      </section>
      <section className="grid grid-3">
        <article className="panel-card accent">
          <h3>Tezkor Amal</h3>
          <p>Eng muhim vazifalarni bir bosishda bajarish uchun optimallashtirilgan blok.</p>
          <div className="button-grid">
            <button className="btn btn-primary">Yangi amal</button>
            <button className="btn btn-soft">Batafsil</button>
          </div>
        </article>
        <article className="panel-card">
          <h3>Holat Kartasi</h3>
          <p>Vizual ierarxiya yaxshilangan, asosiy metrikalar birinchi qatorda.</p>
          <p className="chip">Yangilandi: 2 daqiqa oldin</p>
        </article>
        <article className="panel-card">
          <h3>Bildirishnoma</h3>
          <p>Muhim hodisalar uchun kontrasti baland, oson o&apos;qiladigan kartalar.</p>
          <div className="notice">Bugun 18:00 da sinxronizatsiya oynasi rejalashtirilgan.</div>
        </article>
      </section>
      <section className="panel-card">
        <h3>Jadval Ko&apos;rinishi</h3>
        <MockTable />
      </section>
    </div>
  );
}

function Frame({ label, mode, children }: { label: string; mode: "desktop" | "tablet" | "mobile"; children: React.ReactNode }) {
  return (
    <article className="preview-frame">
      <strong>{label}</strong>
      <div className={`preview-viewport ${mode}`}>{children}</div>
    </article>
  );
}

export default function UiPreviewPage() {
  return (
    <main className="preview-shell">
      <section className="preview-head">
        <p className="pill-label">UI Preview</p>
        <h1>Diamond Education - Polished Interface Showcase</h1>
        <p>Logo ranglaridan olingan yangi dizayn tizimi: yengil fon, yuqori kontrast, premium kartalar va responsiv oqim.</p>
      </section>

      <section className="panel-card" style={{ maxWidth: 1280, margin: "0 auto 14px" }}>
        <h3>Dizayn Tizimi (Asosiy Ranglar)</h3>
        <div className="grid grid-4">
          {[
            "#040C68",
            "#071386",
            "#1123D6",
            "#1429F2",
            "#CAD0E9",
            "#F7F8FD",
            "#FFFFFF",
            "#283B9A",
          ].map((hex) => (
            <div key={hex} className="panel-card" style={{ gap: 8 }}>
              <div style={{ background: hex, borderRadius: 10, border: "1px solid var(--line)", height: 56 }} />
              <strong>{hex}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="preview-grid">
        <Frame label="Login - Desktop" mode="desktop"><LoginPreview /></Frame>
        <Frame label="Login - Tablet" mode="tablet"><LoginPreview /></Frame>
        <Frame label="Login - Mobile" mode="mobile"><LoginPreview /></Frame>
      </section>

      <section className="preview-grid" style={{ marginTop: 14 }}>
        <Frame label="Homepage - Desktop" mode="desktop"><HomePreview /></Frame>
        <Frame label="Homepage - Tablet" mode="tablet"><HomePreview /></Frame>
        <Frame label="Homepage - Mobile" mode="mobile"><HomePreview /></Frame>
      </section>

      <section className="preview-grid" style={{ marginTop: 14 }}>
        <Frame label="Admin Dashboard" mode="desktop"><RolePreview role="Admin" subtitle="Foydalanuvchilar, guruhlar, maqolalar va hisobotlarni boshqarish." /></Frame>
        <Frame label="Teacher Dashboard" mode="desktop"><RolePreview role="O'qituvchi" subtitle="Davomat, testlar va guruh natijalarini boshqarish." /></Frame>
        <Frame label="Student Dashboard" mode="desktop"><RolePreview role="Talaba" subtitle="O'qish progressi, testlar va support darslariga tezkor kirish." /></Frame>
      </section>

      <section className="preview-grid" style={{ marginTop: 14 }}>
        <Frame label="Support Dashboard" mode="desktop"><RolePreview role="Support Teacher" subtitle="Bronlar, kalendar va bonus jarayonlarini yuritish." /></Frame>
        <Frame label="Admin - Tablet" mode="tablet"><RolePreview role="Admin" subtitle="Mobilga yaqin o'lchamda qulay nazorat." /></Frame>
        <Frame label="Student - Mobile" mode="mobile"><RolePreview role="Talaba" subtitle="Bir qo'lda ishlashga moslashtirilgan tartib." /></Frame>
      </section>
    </main>
  );
}
