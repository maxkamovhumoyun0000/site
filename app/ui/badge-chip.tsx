"use client";

interface BadgeChipProps {
  badgeAssetUrl?: string;
  badgeTitle?: string;
  size?: "sm" | "md";
}

export function BadgeChip({ badgeAssetUrl, badgeTitle, size = "sm" }: BadgeChipProps) {
  const dim = size === "sm" ? 16 : 22;

  if (!badgeAssetUrl && !badgeTitle) return null;

  return (
    <span
      title={badgeTitle}
      className="inline-flex items-center justify-center rounded-full overflow-hidden bg-gradient-to-br from-yellow-400 to-orange-500 shadow-sm"
      style={{ width: dim, height: dim, minWidth: dim }}
    >
      {badgeAssetUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={badgeAssetUrl} alt={badgeTitle} width={dim} height={dim} className="object-cover" />
      ) : (
        <span className="text-white font-bold" style={{ fontSize: dim * 0.5 }}>⭐</span>
      )}
    </span>
  );
}
