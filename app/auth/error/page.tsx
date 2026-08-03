export default function AuthErrorPage() {
  return (
    <main className="auth-page">
      <section className="auth-card compact">
        <p className="pill-label">Autentifikatsiya</p>
        <h1>Kirishda xatolik yuz berdi</h1>
        <p>Tizimga kirish jarayonida muammo kuzatildi. Iltimos, qayta urinib ko&apos;ring.</p>
        <a href="/login" className="btn btn-primary">Kirish sahifasiga qaytish</a>
      </section>
    </main>
  );
}
