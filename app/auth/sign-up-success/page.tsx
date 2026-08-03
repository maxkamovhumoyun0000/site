export default function SignUpSuccessPage() {
  return (
    <main className="auth-page">
      <section className="auth-card compact">
        <p className="pill-label">Ro&apos;yxatdan o&apos;tish</p>
        <h1>Hisob muvaffaqiyatli yaratildi</h1>
        <p>Email manzilingizni tasdiqlang, so&apos;ng tizimga kirishingiz mumkin bo&apos;ladi.</p>
        <a href="/login" className="btn btn-primary">Kirish sahifasiga o&apos;tish</a>
      </section>
    </main>
  );
}
