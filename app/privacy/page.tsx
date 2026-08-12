import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy | Diamond Education Mobile Applications",
  description: "Official Privacy Policy for Diamond Education mobile applications: Diamond Student App, Diamond Teacher App, and Diamond Support App.",
  robots: "index, follow",
};

export default function PrivacyPolicyPage() {
  const lastUpdated = "August 12, 2026";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500 selection:text-white pb-20">
      {/* Top Header */}
      <header className="sticky top-0 z-50 backdrop-blur-md bg-slate-950/80 border-b border-slate-800/80">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm font-medium text-slate-300 hover:text-white transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            <span>Asosiy sahifaga qaytish</span>
          </Link>
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            <span className="text-sm font-semibold tracking-wide text-slate-200">Diamond Education</span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 pt-10">
        {/* Banner Card */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-900/60 via-slate-900 to-slate-950 border border-indigo-500/20 p-8 sm:p-12 mb-12 shadow-2xl">
          <div className="absolute -right-10 -bottom-10 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold uppercase tracking-wider mb-6">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            <span>Rasmiy Maxfiylik Siyosati / Privacy Policy</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight mb-4 leading-tight">
            Maxfiylik Siyosati <br className="hidden sm:inline" />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-sky-300 to-emerald-400">
              (Privacy Policy)
            </span>
          </h1>
          <p className="text-slate-300 text-base sm:text-lg max-w-3xl leading-relaxed">
            Bu maxfiylik siyosati <strong>Diamond Education</strong> tomonidan ishlab chiqilgan mobil ilovalar —{" "}
            <span className="text-white font-semibold">Diamond Student App</span>,{" "}
            <span className="text-white font-semibold">Diamond Teacher App</span> va{" "}
            <span className="text-white font-semibold">Diamond Support App</span> tomonidan shaxsiy ma&apos;lumotlarni to&apos;plash, ishlatish hamda himoya qilish tartibini tushuntiradi.
          </p>
          <div className="mt-6 pt-6 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-4 text-xs text-slate-400">
            <div>So&apos;nggi yangilanish sanasi: <span className="text-slate-200 font-medium">{lastUpdated}</span></div>
            <div>Qamrovi: Google Play Store & Apple App Store</div>
          </div>
        </div>

        {/* Quick App Badges */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 hover:border-indigo-500/40 transition-colors">
            <div className="text-xs font-mono text-indigo-400 mb-1">uz.diamondeducation.diamond_students</div>
            <h3 className="text-lg font-bold text-white mb-2">Diamond Student App</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              O&apos;quvchilar uchun davomat, testlar, uy vazifalari, reyting, Voice Room hamda qo&apos;llab-quvvatlash darslarini band qilish tizimi.
            </p>
          </div>
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 hover:border-indigo-500/40 transition-colors">
            <div className="text-xs font-mono text-emerald-400 mb-1">uz.diamondeducation.diamond_teachers</div>
            <h3 className="text-lg font-bold text-white mb-2">Diamond Teacher App</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              O&apos;qituvchilar uchun dars jadvallari, o&apos;quvchilar davomati, uy vazifalarini baholash va o&apos;quv materiallarini boshqarish tizimi.
            </p>
          </div>
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 hover:border-indigo-500/40 transition-colors">
            <div className="text-xs font-mono text-sky-400 mb-1">uz.diamondeducation.diamond_support</div>
            <h3 className="text-lg font-bold text-white mb-2">Diamond Support App</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Qo&apos;llab-quvvatlash o&apos;qituvchilari (Support Teachers) uchun o&apos;quvchilar bandlovlarini qabul qilish va mashg&apos;ulotlarni o&apos;tkazish tizimi.
            </p>
          </div>
        </div>

        {/* Detailed Content Sections */}
        <div className="space-y-10 text-slate-300 text-sm sm:text-base leading-relaxed">
          {/* Section 1 */}
          <section className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-white">1. Qanday ma&apos;lumotlar to&apos;planadi? (Information We Collect)</h2>
            </div>
            <p>
              Biz ta&apos;lim xizmatlarini sifatli taqdim etish va ilovalarning to&apos;g&apos;ri ishlashini ta&apos;minlash uchun faqat zaruriy ma&apos;lumotlarni to&apos;playmiz:
            </p>
            <ul className="list-disc list-inside space-y-2 pl-2 text-slate-300">
              <li>
                <strong className="text-white">Shaxsiy identifikatsiya ma&apos;lumotlari:</strong> Foydalanuvchining ismi, familiyasi, telefon raqami, o&apos;quvchi/o&apos;qituvchi ID raqami va profil rasmi.
              </li>
              <li>
                <strong className="text-white">O&apos;quv va faoliyat ma&apos;lumotlari:</strong> Yechilgan test natijalari, gramatika va so&apos;z o&apos;yinlari ballari, darslarga davomat tarixi, topshirilgan uy vazifalari (fayllar/rasmlar) hamda reyting ko&apos;rsatkichlari.
              </li>
              <li>
                <strong className="text-white">Texnik va qurilma ma&apos;lumotlari:</strong> IP manzil, operatsion tizim versiyasi, bildirishnomalar (Push Notifications) uchun Firebase Cloud Messaging tokeni hamda ilova xatolik jurnallari (Crash Logs).
              </li>
            </ul>
          </section>

          {/* Section 2 */}
          <section className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-white">2. Ma&apos;lumotlardan qanday foydalaniladi? (How We Use Information)</h2>
            </div>
            <p>To&apos;plangan ma&apos;lumotlar quyidagi maqsadlarda ishlatiladi:</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <h4 className="font-semibold text-white mb-1">📚 Ta&apos;lim jarayoni</h4>
                <p className="text-xs text-slate-400">Darslar, testlar, uy vazifalari hamda o&apos;quvchilar bilim darajasini tahlil qilish.</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <h4 className="font-semibold text-white mb-1">🔔 Bildirishnomalar</h4>
                <p className="text-xs text-slate-400">Yangi darslar, support bandlovlari va muhim e&apos;lonlar haqida eslatma yuborish.</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <h4 className="font-semibold text-white mb-1">🎤 Ovozli muloqot</h4>
                <p className="text-xs text-slate-400">Voice Room xonalarida o&apos;quvchilar va o&apos;qituvchilar o&apos;rtasida muloqotni ta&apos;minlash.</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <h4 className="font-semibold text-white mb-1">🛡 Xavfsizlik va Himoya</h4>
                <p className="text-xs text-slate-400">Platformada ruxsat etilmagan kirishlarning oldini olish va tizim barqarorligini saqlash.</p>
              </div>
            </div>
          </section>

          {/* Section 3 */}
          <section className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-sky-500/10 text-sky-400">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-white">3. Ilova ruxsatlari (App Permissions)</h2>
            </div>
            <p>
              Ilovalar to&apos;g&apos;ri ishlashi uchun foydalanuvchidan quyidagi ixtiyoriy ruxsatlar so&apos;ralishi mumkin:
            </p>
            <div className="space-y-3 pt-2">
              <div className="flex items-start gap-3 p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 shrink-0 mt-0.5">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 100-6 3 3 0 000 6z" />
                  </svg>
                </div>
                <div>
                  <h4 className="font-semibold text-white text-sm">Mikrofon (Microphone)</h4>
                  <p className="text-xs text-slate-400">Voice Room jonli ovozli suhbatlarda va so&apos;zlashuv amaliyotida qatnashish uchun.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 shrink-0 mt-0.5">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                  </svg>
                </div>
                <div>
                  <h4 className="font-semibold text-white text-sm">Kamera va Galereya (Camera & Photos)</h4>
                  <p className="text-xs text-slate-400">Uy vazifasi yechimlarini rasmga olib yuklash va profil rasmini yangilash uchun.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 shrink-0 mt-0.5">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                </div>
                <div>
                  <h4 className="font-semibold text-white text-sm">Bildirishnomalar (Push Notifications)</h4>
                  <p className="text-xs text-slate-400">Support dars bandlovlari, yangi vazifalar va muhim xabarnomalarni olish uchun.</p>
                </div>
              </div>
            </div>
          </section>

          {/* Section 4 */}
          <section className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-purple-500/10 text-purple-400">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-white">4. Uchinchi tomon xizmatlari (Third-Party Services)</h2>
            </div>
            <p>
              Diamond Education foydalanuvchilarning shaxsiy ma&apos;lumotlarini tijoriy maqsadda uchinchi shaxslarga <strong>sotmaydi va ijaraga bermaydi</strong>.
              Ilovaning infratuzilmasi uchun faqat quyidagi ishonchli xizmatlardan foydalaniladi:
            </p>
            <ul className="list-disc list-inside space-y-2 pl-2 text-slate-300">
              <li>
                <strong className="text-white">Google Play Services & Apple App Store Services:</strong> Tizim integratsiyasi hamda xavfsizlik uchun.
              </li>
              <li>
                <strong className="text-white">Firebase Cloud Messaging (Google LLC):</strong> Bildirishnomalarni yetkazish uchun.
              </li>
            </ul>
          </section>

          {/* Section 5 - Data Deletion */}
          <section className="bg-gradient-to-r from-red-950/40 via-slate-900 to-slate-900 border border-red-500/30 rounded-2xl p-6 sm:p-8 space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-red-500/10 text-red-400">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-white">
                5. Akkaunt va ma&apos;lumotlarni o&apos;chirish huquqi (Account & Data Deletion)
              </h2>
            </div>
            <p className="text-slate-300">
              Google Play Store va Apple App Store talablariga mos holda, har bir foydalanuvchi o&apos;z akkauntini hamda unga bog&apos;liq barcha shaxsiy ma&apos;lumotlarni o&apos;chirish huquqiga ega.
            </p>
            <div className="bg-slate-950/80 rounded-xl p-4 border border-red-500/20 text-xs sm:text-sm space-y-2">
              <h4 className="font-bold text-red-300">Akkauntni o&apos;chirish tartibi:</h4>
              <ol className="list-decimal list-inside space-y-1.5 text-slate-300">
                <li>Ilova ichidagi Profil bo&apos;limiga kiring hamda &quot;Akkauntni o&apos;chirish&quot; tugmasini bosing.</li>
                <li>
                  Yoki rasmiy qo&apos;llab-quvvatlash pochtamizga (<strong>support@diamond-education.uz</strong> yoki <strong>maxkamovhumoyun121@gmail.com</strong>) o&apos;zingiz ro&apos;yxatdan o&apos;tgan telefon raqamingizni ko&apos;rsatgan holda so&apos;rov yuboring.
                </li>
              </ol>
              <p className="text-slate-400 pt-1">
                So&apos;rov qabul qilingandan so&apos;ng 14 ish kuni ichida shaxsiy ma&apos;lumotlaringiz va faoliyat tarixi ma&apos;lumotlar bazasidan to&apos;liq va qaytarib bo&apos;lmaydigan tarzda o&apos;chiriladi.
              </p>
            </div>
          </section>

          {/* Section 6 - Contact Info */}
          <section className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-4">
            <h2 className="text-xl sm:text-2xl font-bold text-white">6. Bog&apos;lanish (Contact Us)</h2>
            <p>
              Ushbu Maxfiylik Siyosati bo&apos;yicha savollaringiz, takliflaringiz yoki ma&apos;lumotlarni o&apos;chirish bo&apos;yicha murojaatingiz bo&apos;lsa, biz bilan bog&apos;lanishingiz mumkin:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              <div className="flex items-center gap-3 p-4 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 shrink-0">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                </div>
                <div>
                  <div className="text-xs text-slate-400">Elektron pochta:</div>
                  <div className="text-xs font-semibold text-white">maxkamovhumoyun121@gmail.com</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-4 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 shrink-0">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                  </svg>
                </div>
                <div>
                  <div className="text-xs text-slate-400">Telefon:</div>
                  <div className="text-xs font-semibold text-white">+998 97 748 36 34</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-4 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 shrink-0">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <div>
                  <div className="text-xs text-slate-400">Manzil:</div>
                  <div className="text-xs font-semibold text-white">Yangiyo&apos;l sh., Toshkent viloyati</div>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* Footer info */}
        <div className="mt-12 text-center text-xs text-slate-500 border-t border-slate-800/80 pt-8">
          © {new Date().getFullYear()} Diamond Education. Barcha huquqlar himoyalangan.
        </div>
      </main>
    </div>
  );
}
