import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# 1. Change memberPageSize
content = content.replace("const memberPageSize = 24;", "const memberPageSize = 5;")

# 2. Extract Temporary Teacher Assignment section
start_marker = '<h3 className="relative z-10 text-base md:text-xl font-bold font-display mb-4 md:mb-6 flex items-center gap-2"><span>🔄</span> Temporary Teacher Assignment</h3>'
section_start = content.rfind('<section className="p-4 md:p-8 bg-white border border-line', 0, content.find(start_marker))
section_end = content.find('</section>', section_start) + len('</section>')

extracted_section = content[section_start:section_end]
content = content[:section_start] + content[section_end:]

# Replace static texts with i18n
extracted_section = extracted_section.replace('Temporary Teacher Assignment', '{t(locale, "temp_teacher.title", "Vaqtincha o\'qituvchi belgilash")}')
extracted_section = extracted_section.replace('Temp Teacher / Support', '{t(locale, "temp_teacher.role", "O\'qituvchi / Yordamchi")}')
extracted_section = extracted_section.replace('<th>Teacher</th>', '<th>{t(locale, "temp_teacher.teacher", "O\'qituvchi")}</th>')
extracted_section = extracted_section.replace('<th>Role</th>', '<th>{t(locale, "temp_teacher.role_table", "Rol")}</th>')
extracted_section = extracted_section.replace('<th>Fanlar</th>', '<th>{t(locale, "temp_teacher.subjects", "Fanlar")}</th>')
extracted_section = extracted_section.replace('<th>Tanlash</th>', '<th>{t(locale, "temp_teacher.select", "Tanlash")}</th>')
extracted_section = extracted_section.replace('"Tanlash"', 't(locale, "temp_teacher.select", "Tanlash")')
extracted_section = extracted_section.replace('"Tanlangan"', 't(locale, "temp_teacher.selected", "Tanlangan")')
extracted_section = extracted_section.replace('fani bo\'yicha teacher/support teacher topilmadi.', '{t(locale, "temp_teacher.not_found_subject", "fani bo\'yicha o\'qituvchi topilmadi.")}')
extracted_section = extracted_section.replace('"Teacher/support teacher topilmadi."', 't(locale, "temp_teacher.not_found", "O\'qituvchi topilmadi.")')
extracted_section = extracted_section.replace('Upcoming Lessons', '{t(locale, "temp_teacher.upcoming", "Kelgusi darslar soni")}')
extracted_section = extracted_section.replace('>Assign<', '>{t(locale, "temp_teacher.assign", "Biriktirish")}<')
extracted_section = extracted_section.replace('<th>Temp Teacher</th>', '<th>{t(locale, "temp_teacher.teacher", "O\'qituvchi")}</th>')
extracted_section = extracted_section.replace('<th>Date</th>', '<th>{t(locale, "temp_teacher.date", "Sana")}</th>')
extracted_section = extracted_section.replace('<th>Start</th>', '<th>{t(locale, "temp_teacher.start", "Boshlanishi")}</th>')
extracted_section = extracted_section.replace('<th>Actions</th>', '<th>{t(locale, "common.actions", "Harakatlar")}</th>')
extracted_section = extracted_section.replace('>Cancel<', '>{t(locale, "common.cancel", "Bekor qilish")}<')
extracted_section = extracted_section.replace('No substitutions assigned', '{t(locale, "temp_teacher.none_assigned", "Vaqtinchalik o\'qituvchi biriktirilmagan")}')

new_section_code = """
  if (section === "substitutions") {
    return (
      <div className="page-stack">
        <SectionTitle kicker="Substitutions" title={t(locale, "menu.temp_teacher", "Vaqtincha o'qituvchilar")} subtitle={t(locale, "temp_teacher.subtitle", "Guruhlar uchun vaqtinchalik o'qituvchi biriktirish")} />
        <section className="panel-card mb-6 p-6">
          <label className="text-sm font-bold text-ink-500 uppercase mb-2 block">{t(locale, "temp_teacher.select_group", "Guruhni tanlang")}</label>
          <select 
            className="w-full mt-2 p-3 rounded-xl border border-line dark:bg-navy-900 dark:border-white/10 dark:text-white font-semibold outline-none focus:ring-2 focus:ring-cyan-500"
            value={selectedGroupId}
            onChange={(e) => {
              setSelectedGroupId(Number(e.target.value));
            }}
          >
            <option value={0}>-- {t(locale, "temp_teacher.select_group_placeholder", "Guruh tanlang")} --</option>
            {teacherGroups.map((g: GenericRow) => (
              <option key={g.id} value={Number(g.id)}>{g.name || `Guruh #${g.id}`} ({g.subject})</option>
            ))}
          </select>
        </section>
        {selectedGroupId > 0 ? (
          """ + extracted_section + """
        ) : (
          <div className="p-8 text-center text-ink-500 font-bold bg-white dark:bg-navy-900 border border-line dark:border-white/10 rounded-2xl">
            {t(locale, "temp_teacher.please_select", "Iltimos, yuqoridan guruhni tanlang.")}
          </div>
        )}
      </div>
    );
  }
"""

insert_pos = content.find('if (section === "attendance") {')
content = content[:insert_pos] + new_section_code + content[insert_pos:]

content = content.replace('const blockedNav = new Set(["settings", "notifications", "support-requests", "substitutions"]);', 'const blockedNav = new Set(["settings", "notifications", "support-requests"]);')

with open('app/page.tsx', 'w') as f:
    f.write(content)

print("UI updated successfully")
