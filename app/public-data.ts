export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

function normalizeNetworkError(error: unknown) {
  if (error instanceof DOMException && error.name === "AbortError") {
    return new Error("So'rov vaqti tugadi. Qayta urinib ko'ring.");
  }
  if (error instanceof TypeError) {
    return new Error("Tarmoq xatosi. Internet aloqasini tekshiring.");
  }
  return error instanceof Error ? error : new Error("So'rov muvaffaqiyatsiz tugadi");
}

export type GenericRow = Record<string, any>;

export type PublicCourse = {
  id: number;
  title: string;
  title_uz?: string;
  title_ru?: string;
  title_en?: string;
  description?: string;
  description_uz?: string;
  description_ru?: string;
  description_en?: string;
  price_text?: string;
  individual_price_text?: string;
  cover_image_url?: string | null;
  status?: string;
  subject?: string;
};

export type PublicCourseGroup = {
  id: string;
  title: string;
  items: PublicCourse[];
};

export function getCourseGroups(courses: PublicCourse[]): PublicCourseGroup[] {
  const groups: Record<string, PublicCourse[]> = {};
  for (const course of courses) {
    const subj = (course.subject || "Boshqa fanlar").trim();
    if (!groups[subj]) groups[subj] = [];
    groups[subj].push(course);
  }
  return Object.keys(groups).sort().map((subj) => ({
    id: `course-group-${encodeURIComponent(subj)}`,
    title: subj,
    items: groups[subj],
  }));
}


export type PublicResult = {
  id: number;
  student_name: string;
  result_type?: string;
  subject?: string;
  university_name?: string;
  university_scope?: string;
  university_country?: string;
  university_city?: string;
  grant_percent?: number | null;
  score_text?: string;
  level_text?: string;
  exam_date?: string | null;
  description?: string;
  image_url?: string | null;
  media?: string[];
  status?: string;
  created_at?: string;
  updated_at?: string;
};

export type PublicArticle = {
  id: number;
  title: string;
  content?: string;
  excerpt?: string;
  category?: string;
  status?: string;
  read_minutes?: number;
  view_count?: number;
  featured_image_url?: string;
  tags?: string[];
  author_name?: string;
  publisher_name?: string;
  created_at?: string;
  updated_at?: string;
};

async function requestPublicJson<T>(path: string, method: "GET" | "POST" = "GET"): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { method, cache: "no-store" });
  } catch (error) {
    throw normalizeNetworkError(error);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "So'rov muvaffaqiyatsiz tugadi" }));
    throw new Error(String(body.detail || "So'rov muvaffaqiyatsiz tugadi"));
  }
  return response.json();
}

export async function fetchPublicCourses(limit = 300, lang?: string): Promise<PublicCourse[]> {
  const params = new URLSearchParams({ limit: String(Math.max(1, Math.min(300, limit))) });
  const safeLang = String(lang || "").trim().toLowerCase().slice(0, 2);
  if (["uz", "ru", "en"].includes(safeLang)) params.set("lang", safeLang);
  const payload = await requestPublicJson<{ items: PublicCourse[] }>(`/public/courses?${params.toString()}`);
  return payload.items || [];
}

export async function fetchPublicVideos(limit = 200): Promise<GenericRow[]> {
  const payload = await requestPublicJson<{ items: GenericRow[] }>(`/public/videos?limit=${Math.max(1, Math.min(200, limit))}`);
  return payload.items || [];
}

export async function fetchPublicVideo(id: string | number): Promise<{ video: GenericRow; related: GenericRow[] }> {
  return await requestPublicJson<{ video: GenericRow; related: GenericRow[] }>(`/public/videos/${id}`);
}

export async function recordPublicVideoView(id: string | number): Promise<{ success: boolean; view_count: number }> {
  return await requestPublicJson<{ success: boolean; view_count: number }>(`/public/videos/${id}/view`, "POST");
}

export async function recordPublicVideoLike(videoId: string, action: "like" | "unlike"): Promise<{success: boolean, like_count: number}> {
  try {
    const response = await fetch(`${API_BASE}/public/videos/${videoId}/like?action=${action}`, {
      method: "POST",
    });
    return response.json();
  } catch (error) {
    console.error("Error recording like:", error);
    return { success: false, like_count: 0 };
  }
}

export interface VideoComment {
  id: number;
  author_name: string;
  comment_text: string;
  created_at: string;
  parent_id?: number;
  like_count?: number;
  dislike_count?: number;
}

export async function fetchPublicVideoComments(videoId: string): Promise<VideoComment[]> {
  try {
    const res = await fetch(`${API_BASE}/public/videos/${videoId}/comments`);
    const data = await res.json();
    return data.items || [];
  } catch (e) {
    console.error("Error fetching comments:", e);
    return [];
  }
}

export async function postPublicVideoComment(videoId: string, commentText: string, parentId?: number): Promise<boolean> {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    try {
      const token = localStorage.getItem("diamond_token");
      if (token) headers["Authorization"] = `Bearer ${token}`;
    } catch {}
    
    const body: any = { comment_text: commentText };
    if (parentId !== undefined) {
      body.parent_id = parentId;
    }

    const res = await fetch(`${API_BASE}/public/videos/${videoId}/comments`, {
      method: "POST",
      headers,
      body: JSON.stringify(body)
    });
    const data = await res.json();
    return !!data.success;
  } catch (e) {
    console.error("Error posting comment:", e);
    return false;
  }
}

export async function votePublicVideoComment(commentId: number, action: "like" | "dislike"): Promise<{ success: boolean; like_count: number; dislike_count: number }> {
  try {
    const headers: Record<string, string> = {};
    try {
      const token = localStorage.getItem("diamond_token");
      if (token) headers["Authorization"] = `Bearer ${token}`;
    } catch {}
    
    const res = await fetch(`${API_BASE}/public/videos/comments/${commentId}/vote?action=${action}`, {
      method: "POST",
      headers
    });
    return await res.json();
  } catch (e) {
    console.error("Error voting on comment:", e);
    return { success: false, like_count: 0, dislike_count: 0 };
  }
}

export async function fetchPublicResults(limit = 400): Promise<PublicResult[]> {
  const payload = await requestPublicJson<{ items: PublicResult[] }>(`/public/results?limit=${Math.max(1, Math.min(400, limit))}`);
  return payload.items || [];
}

export async function fetchPublicArticles(): Promise<PublicArticle[]> {
  const payload = await requestPublicJson<{ items: PublicArticle[] }>("/articles?limit=120");
  return payload.items || [];
}

export async function fetchPublicArticle(articleId: number): Promise<PublicArticle> {
  return requestPublicJson<PublicArticle>(`/articles/${Number(articleId || 0)}`);
}

export async function recordPublicArticleView(articleId: number): Promise<number | null> {
  const payload = await requestPublicJson<{ view_count?: number }>(`/articles/${Number(articleId || 0)}/view`, "POST");
  return typeof payload.view_count === "number" ? payload.view_count : null;
}

export function toAssetUrl(value?: string | null): string {
  const raw = String(value || "").trim();
  if (!raw) return "";
  return raw.startsWith("/") ? `${API_BASE}${raw}` : raw;
}

export function formatPublicDate(value?: string | null, locale?: "uz" | "ru" | "en"): string {
  const raw = String(value || "").trim();
  if (!raw) return "-";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  if (locale) {
    const intlLocale = locale === "ru" ? "ru-RU" : locale === "en" ? "en-US" : "uz-UZ";
    return new Intl.DateTimeFormat(intlLocale, { day: "numeric", month: "short", year: "numeric" }).format(date);
  }
  return date.toLocaleDateString();
}

export function cutText(value: string | undefined | null, max = 180): string {
  const raw = String(value || "").trim();
  if (!raw) return "-";
  if (raw.length <= max) return raw;
  return `${raw.slice(0, max)}...`;
}
