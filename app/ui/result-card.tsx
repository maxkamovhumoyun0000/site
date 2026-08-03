"use client";

import type { PublicResult } from "../public-data";
import { formatPublicDate, toAssetUrl } from "../public-data";
import { useWebLocale, useWebT } from "./web-i18n";

export const RESULT_TYPES = ["IELTS", "CEFR", "Milliy Sertifikat", "Rus tili", "Universitet"] as const;
export const NATIONAL_CERTIFICATE_SUBJECTS = ["Matematika", "Rus tili", "Ona tili"] as const;

const VIDEO_EXTENSIONS = [".mp4", ".webm", ".mov", ".m4v", ".ogg"];
const IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp", ".svg"];

function normalizedPath(value?: string | null) {
  return String(value || "").trim().split("?", 1)[0].toLowerCase();
}

export function isResultVideoUrl(value?: string | null) {
  const path = normalizedPath(value);
  return VIDEO_EXTENSIONS.some((ext) => path.endsWith(ext));
}

export function isResultImageUrl(value?: string | null) {
  const path = normalizedPath(value);
  return IMAGE_EXTENSIONS.some((ext) => path.endsWith(ext));
}



export function getResultPrimaryMedia(item: PublicResult | Record<string, any>) {
  const imageUrl = String(item?.image_url || "").trim();
  if (imageUrl) return imageUrl;
  const media = Array.isArray(item?.media) ? item.media : [];
  return String(media.find((entry) => String(entry || "").trim()) || "").trim();
}

export function getResultAllMedia(item: PublicResult | Record<string, any>) {
  const imageUrl = String(item?.image_url || "").trim();
  const media = Array.isArray(item?.media) ? item.media : [];
  const all = [imageUrl, ...media].map(m => String(m || "").trim()).filter(Boolean);
  return Array.from(new Set(all)).filter(m => !isResultVideoUrl(m));
}

export function getResultVideoUrl(item: PublicResult | Record<string, any>) {
  const imageUrl = String(item?.image_url || "").trim();
  if (isResultVideoUrl(imageUrl)) return imageUrl;
  const media = Array.isArray(item?.media) ? item.media : [];
  const videoMedia = media.find((entry) => {
    const str = String(entry || "").trim();
    return isResultVideoUrl(str);
  });
  return videoMedia ? String(videoMedia).trim() : null;
}

export function resultMetricLabel(item: PublicResult | Record<string, any>) {
  const type = String(item?.result_type || "").trim();
  const score = String(item?.score_text || "").trim();
  if (type === "IELTS") return `IELTS: ${score || "-"}`;
  if (type === "CEFR") return `CEFR: ${score || "-"}`;
  if (type === "Milliy Sertifikat") return `Milliy Sertifikat: ${score || "-"}`;
  if (type === "Rus tili") return "Rus tili (Video)";
  if (type === "Universitet") {
    const grant = Number(item?.grant_percent);
    if (Number.isFinite(grant)) {
      return `Grant: ${Number.isInteger(grant) ? grant.toFixed(0) : grant.toFixed(1)}%`;
    }
    return "Universitet";
  }
  return score || "-";
}

export function resultSubjectLabel(item: PublicResult | Record<string, any>) {
  const type = String(item?.result_type || "").trim();
  if (type === "Universitet") {
    return String(item?.university_name || "").trim();
  }
  if (type === "Milliy Sertifikat") {
    return String(item?.subject || "").trim();
  }
  return "";
}

export function resultUniversityMeta(item: PublicResult | Record<string, any>) {
  // Universitet removed as per request, keep stub for compatibility if needed elsewhere
  return "";
}

export function ResultCard({
  item,
  href,
  compact = false,
}: {
  item: PublicResult | Record<string, any>;
  href?: string;
  compact?: boolean;
}) {
  const locale = useWebLocale();
  const tt = useWebT();
  const id = Number(item?.id || 0);
  const cardHref = href || (id > 0 ? `/results/${id}` : "/results");
  const videoUrl = getResultVideoUrl(item);
  const media = videoUrl || getResultPrimaryMedia(item);
  const allImages = getResultAllMedia(item);
  const resolvedMedia = toAssetUrl(media);
  const isVideo = isResultVideoUrl(media);
  const isImage = isResultImageUrl(media) || (!isVideo && Boolean(resolvedMedia));
  const hasMultipleImages = !isVideo && allImages.length > 1;
  const subject = resultSubjectLabel(item);
  const type = String(item?.result_type || "").trim();
  const title = String(item?.student_name || tt("common.student", "Talaba")).trim();
  const score = String(item?.score_text || "").trim();
  const translatedSubject = subject ? tt(`public.subject.${subject}`, subject) : "";
  const displayDate = formatPublicDate(String(item?.exam_date || item?.updated_at || item?.created_at || ""), locale);
  const metric = (() => {
    if (type === "IELTS") return `IELTS: ${score || "-"}`;
    if (type === "CEFR") return `CEFR: ${score || "-"}`;
    if (type === "Milliy Sertifikat") return `${tt("admin.results.type.Milliy Sertifikat", "Milliy Sertifikat")}: ${score || "-"}`;
    if (type === "Rus tili") return tt("admin.results.studentVideo", "Talaba videosi");
    return resultMetricLabel(item);
  })();

  return (
    <a 
      href={cardHref}
      className="group flex flex-col h-full bg-white dark:bg-gray-800 rounded-3xl overflow-hidden border border-gray-100 dark:border-gray-700 shadow-md hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
    >
      <div className="relative aspect-[3/4] overflow-hidden shrink-0 bg-gray-50 dark:bg-gray-900">
        {resolvedMedia && isVideo ? (
          <>
              <video
              className="w-full h-full object-cover block transition-transform duration-500 group-hover:scale-105"
              src={`${resolvedMedia}#t=0.001`}
              muted
              playsInline
              loop
              preload="metadata"
            />
            <div className="absolute inset-0 bg-black/20 group-hover:bg-black/10 transition-colors flex items-center justify-center">
              <div className="w-14 h-14 bg-white/90 rounded-full flex items-center justify-center text-blue-600 shadow-lg group-hover:scale-110 transition-transform">
                <svg className="w-6 h-6 ml-1" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
              </div>
            </div>
          </>
        ) : hasMultipleImages ? (
          <>
            <div 
              className="w-full h-full flex overflow-x-auto snap-x snap-mandatory [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
            >
              {allImages.map((img, idx) => (
                <img
                  key={idx}
                  src={toAssetUrl(img)}
                  alt={`${title} - ${tt("public.results.mediaNumber", "Media {number}", { number: idx + 1 })}`}
                  className="w-full h-full object-cover block shrink-0 snap-center"
                  loading="lazy"
                />
              ))}
            </div>
            <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-1.5 z-10 pointer-events-none">
              {allImages.map((_, idx) => (
                <div key={idx} className="w-1.5 h-1.5 rounded-full bg-white/70 shadow-sm" />
              ))}
            </div>
          </>
        ) : resolvedMedia && isImage ? (
          <img
            src={resolvedMedia}
            alt={title}
            className="w-full h-full object-cover block transition-transform duration-500 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-gray-400">
            <div className="w-16 h-16 bg-blue-50 dark:bg-gray-800 rounded-full flex items-center justify-center mb-4 text-blue-500">
               <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
            </div>
            <span className="text-sm font-bold uppercase tracking-widest text-gray-300 dark:text-gray-600">{tt("public.results.noMedia", "Media yo'q")}</span>
          </div>
        )}
        
        {/* Floating date badge */}
        {!compact && (
          <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm px-3 py-1.5 rounded-full shadow-sm">
            <span className="text-xs font-bold text-gray-700">{displayDate}</span>
          </div>
        )}
      </div>

      <div className="p-3 md:p-4 flex flex-col flex-1">
        <h3 className="text-lg md:text-xl font-black text-gray-900 dark:text-white mb-2 line-clamp-2">{title}</h3>
        {type !== "Universitet" ? (
          <div className="flex flex-wrap items-center gap-2 mt-auto">
            <span className="inline-flex items-center px-3 py-1 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 text-sm font-bold uppercase tracking-wide">
              {metric}
            </span>
            {subject ? (
              <span className="inline-flex items-center px-3 py-1 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-sm font-bold">
                {tt("common.subject", "Fan")}: {translatedSubject}
              </span>
            ) : null}
          </div>
        ) : null}
        {!compact && item?.description ? (
          <p className="mt-4 text-gray-500 dark:text-gray-400 text-sm font-medium line-clamp-2 leading-relaxed">
            {String(item.description)}
          </p>
        ) : null}
      </div>
    </a>
  );
}
