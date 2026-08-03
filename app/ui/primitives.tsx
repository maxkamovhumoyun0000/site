"use client";

export function LogoMark({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const sizeClass = size === "sm" ? "logo-sm" : size === "lg" ? "logo-lg" : "logo-md";
  return (
    <div className={`logo-mark ${sizeClass}`}>
      <img
        src="/logo.jpg"
        alt="Diamond Education"
        width={size === "sm" ? 52 : size === "lg" ? 180 : 86}
        height={size === "sm" ? 52 : size === "lg" ? 180 : 86}
        className="w-full h-full object-cover"
        style={{ display: "block", width: "100%", height: "100%" }}
      />
    </div>
  );
}

export function HamburgerGlyph() {
  return (
    <svg className="w-6 h-6 text-ink-900 dark:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16m-7 6h7" />
    </svg>
  );
}

export function SectionTitle({ kicker, title, subtitle }: { kicker: string; title: string; subtitle?: string }) {
  return (
    <div className="flex flex-col items-start gap-2 mb-4 animate-fade-in">
      <span className="px-3 py-1 text-xs font-bold tracking-wider uppercase rounded-full bg-navy-700/10 text-navy-700 dark:bg-navy-700/20 dark:text-cyan-400">
        {kicker}
      </span>
      <h2 className="text-3xl md:text-4xl font-display font-extrabold text-navy-900 dark:text-white tracking-tight">
        {title}
      </h2>
      {subtitle ? <p className="text-ink-700 dark:text-ink-500 max-w-2xl text-lg">{subtitle}</p> : null}
    </div>
  );
}

export const DCOIN_ICON_SRC = "/assets/dcoin-icon.png";
export const DPOINT_ICON_SRC = "/assets/dpoint-icon.png";
export const GIFT_CHEST_ICON_SRC = "/assets/gift-chest-icon.png";

export type AssetIconType = "dcoin" | "dpoint" | "chest";

export function AssetIcon({
  type,
  size = 22,
  className = "",
  alt,
}: {
  type: AssetIconType;
  size?: number;
  className?: string;
  alt?: string;
}) {
  const src = type === "dcoin" ? DCOIN_ICON_SRC : type === "dpoint" ? DPOINT_ICON_SRC : GIFT_CHEST_ICON_SRC;
  const label = alt || (type === "dcoin" ? "D'coin" : type === "dpoint" ? "D'point" : "Sandiq");
  return (
    <img
      src={src}
      alt={label}
      width={size}
      height={size}
      className={`asset-icon asset-icon-${type} ${className}`.trim()}
      loading="lazy"
      decoding="async"
      style={{ width: size, height: size }}
    />
  );
}

function inferAssetIcon(title: string): AssetIconType | null {
  const normalized = title.toLowerCase().replace(/[’`]/g, "'");
  if (normalized.includes("d'coin") || normalized.includes("dcoin")) return "dcoin";
  if (normalized.includes("d'point") || normalized.includes("dpoint")) return "dpoint";
  return null;
}

export function StatCard({
  title,
  value,
  detail,
  tone = "navy",
  iconType,
}: {
  title: string;
  value: string | number;
  detail?: string;
  tone?: "navy" | "cyan" | "gold" | "green" | "red";
  iconType?: AssetIconType;
}) {
  const toneClasses = {
    navy: "border-navy-700/20 bg-surface/80",
    cyan: "border-cyan-500/30 bg-cyan-500/5",
    gold: "border-gold-500/30 bg-gold-500/5",
    green: "border-green-500/30 bg-green-500/5",
    red: "border-red-500/30 bg-red-500/5",
  };
  const resolvedIcon = iconType || inferAssetIcon(title);

  return (
    <article className={`p-5 rounded-2xl border backdrop-blur-md transition-premium hover:shadow-premium-hover hover:-translate-y-1 ${toneClasses[tone]}`}>
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="block text-sm font-semibold text-ink-500 uppercase tracking-wide">{title}</span>
        {resolvedIcon ? <AssetIcon type={resolvedIcon} size={34} className="stat-card-asset-icon" /> : null}
      </div>
      <strong className="block text-3xl font-display font-black text-navy-900 dark:text-white">{value}</strong>
      {detail && <p className="mt-2 text-sm text-ink-700 dark:text-ink-500">{detail}</p>}
    </article>
  );
}
