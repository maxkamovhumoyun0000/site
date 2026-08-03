with open('app/ui/student-attendance.tsx', 'r') as f:
    content = f.read()

replacement = """export function StudentAttendance() {
  const tt = useWebT();
  const [items, setItems] = useState<AttendanceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedGroupId, setSelectedGroupId] = useState<string>("all");

  async function requestJson<T>(path: string, options?: { token?: string | null; method?: string }): Promise<T> {
    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
    const headers: Record<string, string> = {};
    if (options?.token) headers["Authorization"] = `Bearer ${options.token}`;
    const res = await fetch(`${API_BASE}${path}`, {
      method: options?.method || "GET",
      headers,
    });
    if (!res.ok) {
      let errText = tt("errors.generic", "Xatolik");
      try { errText = (await res.json())?.detail || errText; } catch (e) {}
      throw new Error(errText);
    }
    return res.json();
  }

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const res = await requestJson<{ items: AttendanceItem[] }>("/student/attendance", {
          token: localStorage.getItem("diamond_token") || "",
        });
        if (mounted && res && res.items) {
          setItems(res.items);
        }
      } catch (err: any) {
        if (mounted) setError(err.message || tt("errors.occurred", "Xatolik yuz berdi"));
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => { mounted = false; };
  }, []);

  // 1. Get unique groups
  const groups = React.useMemo(() => {
    const map = new Map<number, string>();
    items.forEach(item => {
      if (item.group_id) {
        map.set(item.group_id, item.group_name || `Guruh #${item.group_id}`);
      }
    });
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [items]);

  // 2. Filter items by selected group
  const filteredItems = React.useMemo(() => {
    if (selectedGroupId === "all") return items;
    return items.filter(i => String(i.group_id) === selectedGroupId);
  }, [items, selectedGroupId]);

  // 3. Group by YYYY-MM
  const monthsData: Record<string, Record<number, AttendanceItem>> = {};
  filteredItems.forEach(item => {
    if (!item.date) return;
    const parts = item.date.split(" ")[0].split("-");
    if (parts.length >= 3) {
      const ym = `${parts[0]}-${parts[1]}`;
      const day = parseInt(parts[2], 10);
      if (!monthsData[ym]) monthsData[ym] = {};
      if (!monthsData[ym][day]) monthsData[ym][day] = item;
    }
  });

  const sortedMonths = Object.keys(monthsData).sort((a, b) => b.localeCompare(a));
"""

import re
old_func_start = re.search(r'export function StudentAttendance\(\) \{.*?const sortedMonths = Object.keys\(monthsData\)\.sort\(\(a, b\) => b.localeCompare\(a\)\);', content, re.DOTALL).group(0)
content = content.replace(old_func_start, replacement)

# Now we need to add the Group Select drop down in the UI
ui_insertion = """      <div className="flex flex-col gap-2">
        <h1 className="text-2xl sm:text-3xl font-black text-navy-900 dark:text-white font-display">{tt("attendance.my_attendance", "Mening davomatim")}</h1>
        <p className="text-sm sm:text-base text-ink-500 dark:text-navy-400">{tt("attendance.calendar_desc", "Davomat kalendari.")}</p>
        
        {groups.length > 0 && (
          <div className="mt-4">
            <label className="text-xs font-bold text-ink-500 dark:text-navy-400 uppercase tracking-wider mb-2 block">Guruhni tanlang:</label>
            <select
              value={selectedGroupId}
              onChange={(e) => setSelectedGroupId(e.target.value)}
              className="w-full sm:max-w-xs px-4 py-3 rounded-xl border border-line dark:border-white/10 bg-white dark:bg-navy-900 text-navy-900 dark:text-white font-semibold outline-none focus:ring-2 focus:ring-cyan-500"
            >
              <option value="all">Barcha guruhlar</option>
              {groups.map(g => (
                <option key={g.id} value={String(g.id)}>{g.name}</option>
              ))}
            </select>
          </div>
        )}

        <div className="flex flex-wrap gap-4 mt-2">"""

old_ui_start = """      <div className="flex flex-col gap-2">
        <h1 className="text-2xl sm:text-3xl font-black text-navy-900 dark:text-white font-display">{tt("attendance.my_attendance", "Mening davomatim")}</h1>
        <p className="text-sm sm:text-base text-ink-500 dark:text-navy-400">{tt("attendance.calendar_desc", "Davomat kalendari.")}</p>
        <div className="flex flex-wrap gap-4 mt-2">"""

content = content.replace(old_ui_start, ui_insertion)

with open('app/ui/student-attendance.tsx', 'w') as f:
    f.write(content)
print("attendance updated")
