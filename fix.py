import re
with open('app/page.tsx', 'r') as f:
    content = f.read()

bad_chunk = """              <div className="flex flex-col gap-2 justify-end">
                      await loadTeacherGroups();
                      await loadSubstitutions();
                    }}
                  >Assign</button>
                  <button className="px-5 py-3 font-bold text-navy-900 dark:text-white bg-surface-soft dark:bg-white/10 border border-line dark:border-white/20 hover:bg-white/20 rounded-xl transition-all" onClick={async () => { await loadTeacherGroups(); await loadSubstitutions(); }}>Refresh</button>
                </div>
              </div>"""

good_chunk = """              <div className="flex flex-col gap-2 justify-end">
                <div className="flex gap-3">
                  <button
                    className="flex-1 px-5 py-3 font-bold text-white bg-cyan-500 hover:bg-cyan-600 rounded-xl shadow-lg transition-all"
                    onClick={async () => {
                      if (!selectedGroupId || !tempTeacherId.trim()) return;
                      await onApiCall(`/teacher/groups/${selectedGroupId}/substitutions`, { temp_teacher_id: Number(tempTeacherId), upcoming_count: Math.max(1, Number(tempUpcomingCount || 1)) }, "POST", "Temporary teacher assigned");
                      await loadTeacherGroups();
                      await loadSubstitutions();
                    }}
                  >Assign</button>
                </div>
              </div>"""

content = content.replace(bad_chunk, good_chunk)
with open('app/page.tsx', 'w') as f:
    f.write(content)
print("Fixed syntax")
