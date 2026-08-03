with open('app/ui/teacher-students.tsx', 'r') as f:
    content = f.read()

import re

# 1. Replace state vars
content = re.sub(
    r'const \[resetModalOpen, setResetModalOpen\] = useState\(false\);\s*const \[resetTargetId, setResetTargetId\] = useState\(0\);\s*const \[resetPasswordVal, setResetPasswordVal\] = useState\(""\);',
    r'''const [resetPasswordInfo, setResetPasswordInfo] = useState<any>(null);
  const [resettingId, setResettingId] = useState<number | null>(null);

  const copyText = async (txt: string) => {
    try {
      await navigator.clipboard.writeText(txt);
      alert(tt("common.copied", "Nusxalandi"));
    } catch {
      alert(tt("common.copyFailed", "Nusxalash imkoni bo'lmadi"));
    }
  };''',
    content
)

# 2. Replace handleResetPassword
old_handler = r'''const handleResetPassword = async \(e: any\) => \{
    e.preventDefault\(\);
    setSaving\(true\);
    try \{
      await onApiCall\(`/teacher/my-students/\$\{resetTargetId\}/reset-password`, \{
        password: resetPasswordVal
      \}, "POST", "Parol tiklandi"\);
      setResetModalOpen\(false\);
      setResetTargetId\(0\);
      setResetPasswordVal\(""\);
    \} catch \(err: any\) \{
      alert\("Xatolik: " \+ err.message\);
    \} finally \{
      setSaving\(false\);
    \}
  \};'''

new_handler = '''const handleResetPassword = async (s: any) => {
    if (resettingId) return;
    setResettingId(s.id);
    try {
      const result = await onApiCall(`/teacher/my-students/${s.id}/reset-password`, {}, "POST", "Parol tiklandi");
      setResetPasswordInfo({
        userId: s.id,
        userName: `${s.first_name || ""} ${s.last_name || ""}`.trim() || "-",
        loginId: s.login_id || `#${s.id}`,
        password: result.password,
        qr_payload: result.qr_payload,
        qr_token: result.qr_token,
        qr_expires_at: result.qr_expires_at
      });
    } catch (err: any) {
      alert("Xatolik: " + err.message);
    } finally {
      setResettingId(null);
    }
  };'''

content = re.sub(old_handler, new_handler, content)

# 3. Replace the button in the table
old_btn = r'''<button className="btn btn-soft" onClick=\{.*?setResetModalOpen\(true\);.*?\}>
                      Parol
                    </button>'''

new_btn = '''<button className="btn btn-soft" onClick={() => handleResetPassword(s)} disabled={resettingId === s.id}>
                      {resettingId === s.id ? "..." : "Parol"}
                    </button>'''

content = re.sub(old_btn, new_btn, content, flags=re.DOTALL)

# 4. Replace the Reset Modal markup
old_modal = r'''<ModalPortal open=\{resetModalOpen\}>.*?</ModalPortal>'''

new_modal = '''<ModalPortal open={Boolean(resetPasswordInfo)}>
        {resetPasswordInfo && (
          <div className="overlay-modal-backdrop" onClick={() => setResetPasswordInfo(null)}>
            <article className="overlay-modal-card admin-wide-modal" onClick={e => e.stopPropagation()}>
              <div className="row-between gap-3 mb-4">
                <h3 className="font-bold text-lg text-green-600 dark:text-green-400 flex items-center gap-2">🔑 {tt("admin.users.resetResult", "Parolni tiklash natijasi")}</h3>
                <button className="btn btn-soft small" type="button" onClick={() => setResetPasswordInfo(null)}>{tt("common.close", "Yopish")}</button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="flex flex-col gap-1 p-4 bg-white dark:bg-navy-900/50 rounded-xl border border-green-200 dark:border-green-500/20">
                  <span className="text-xs font-bold text-ink-400 uppercase tracking-wider">{tt("common.user", "Foydalanuvchi")}</span>
                  <strong className="font-bold text-navy-900 dark:text-white">{resetPasswordInfo.userName}</strong>
                </div>
                <div className="flex flex-col gap-1 p-4 bg-white dark:bg-navy-900/50 rounded-xl border border-green-200 dark:border-green-500/20">
                  <span className="text-xs font-bold text-ink-400 uppercase tracking-wider">{tt("common.loginId", "Login ID")}</span>
                  <strong className="font-mono font-bold text-navy-900 dark:text-white">{resetPasswordInfo.loginId}</strong>
                </div>
                <div className="flex flex-col gap-1 p-4 bg-white dark:bg-navy-900/50 rounded-xl border border-green-200 dark:border-green-500/20">
                  <span className="text-xs font-bold text-ink-400 uppercase tracking-wider">{tt("common.password", "Parol")}</span>
                  <strong className="font-mono font-bold text-navy-900 dark:text-white text-lg">{resetPasswordInfo.password}</strong>
                </div>
              </div>
              {resetPasswordInfo.qr_payload && (
                <div className="flex flex-col md:flex-row gap-6 p-4 bg-surface-soft dark:bg-white/5 rounded-xl border border-line dark:border-white/10 mb-4">
                  <img src={`https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encodeURIComponent(String(resetPasswordInfo.qr_payload || ""))}`} alt="QR" className="w-48 h-48 rounded-lg bg-white p-2 shrink-0 border border-line dark:border-white/10" />
                  <div className="flex flex-col gap-2 justify-center">
                    <p className="text-sm font-medium text-ink-500 dark:text-navy-200">Ushbu QR kodni ilova yoki veb-sayt orqali skanerlang.</p>
                    <div className="kv"><span>QR expires</span><strong>{new Date(resetPasswordInfo.qr_expires_at).toLocaleString()}</strong></div>
                    <div className="kv"><span>QR token</span><strong>{resetPasswordInfo.qr_token}</strong></div>
                  </div>
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <button className="px-5 py-2.5 text-sm font-bold text-white bg-green-500 hover:bg-green-600 rounded-xl transition-all" onClick={() => copyText(resetPasswordInfo.password)}>{tt("common.copyPassword", "Parolni nusxalash")}</button>
                <button className="px-5 py-2.5 text-sm font-bold text-white bg-navy-700 hover:bg-navy-800 rounded-xl transition-all" onClick={() => copyText(`${resetPasswordInfo.loginId} / ${resetPasswordInfo.password}`)}>{tt("common.copyLoginPassword", "Login va parolni nusxalash")}</button>
                <button className="px-5 py-2.5 text-sm font-bold bg-surface-soft dark:bg-white/5 border border-line dark:border-white/10 text-ink-600 dark:text-navy-200 rounded-xl hover:border-red-400 hover:text-red-500 transition-all" onClick={() => setResetPasswordInfo(null)}>{tt("common.clear", "Tozalash")}</button>
              </div>
            </article>
          </div>
        )}
      </ModalPortal>'''

content = re.sub(old_modal, new_modal, content, flags=re.DOTALL)

with open('app/ui/teacher-students.tsx', 'w') as f:
    f.write(content)
print("Updated teacher-students.tsx")
