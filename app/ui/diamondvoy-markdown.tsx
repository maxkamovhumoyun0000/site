"use client";

/**
 * Renderer for Diamondvoy answers on the website.
 *
 * Diamondvoy replies use Markdown (headings, bold, lists, quotes, links),
 * GitHub-style tables, $$LaTeX$$ formulas, fenced code and inline
 * [[n]](url) web-search citations. This module parses them in document
 * order with no dependencies. All text goes through React, so nothing from
 * the model is injected as HTML, and links are limited to http(s).
 */

import React from "react";

export type DiamondvoyMarkdownOptions = {
  /** `[btn]Label[/btn]` quick replies send `Label` as a new message. */
  onButton?: (label: string) => void;
};

const SUPERSCRIPT: Record<string, string> = {
  "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
  "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾", n: "ⁿ", i: "ⁱ", x: "ˣ", y: "ʸ",
};
const SUBSCRIPT: Record<string, string> = {
  "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
  "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎", a: "ₐ", e: "ₑ", i: "ᵢ", n: "ₙ", o: "ₒ", x: "ₓ",
};
const LATEX_SYMBOLS: Record<string, string> = {
  times: "×", cdot: "·", div: "÷", pm: "±", mp: "∓", leq: "≤", le: "≤", geq: "≥", ge: "≥", neq: "≠", ne: "≠",
  approx: "≈", equiv: "≡", infty: "∞", to: "→", rightarrow: "→", leftarrow: "←", Rightarrow: "⇒", iff: "⇔",
  sum: "∑", prod: "∏", int: "∫", partial: "∂", nabla: "∇", in: "∈", notin: "∉", subset: "⊂", cup: "∪", cap: "∩",
  forall: "∀", exists: "∃", angle: "∠", degree: "°", circ: "°", perp: "⊥", parallel: "∥", ldots: "…", cdots: "⋯",
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", varepsilon: "ε", theta: "θ", lambda: "λ", mu: "μ",
  pi: "π", rho: "ρ", sigma: "σ", tau: "τ", phi: "φ", varphi: "φ", omega: "ω", Delta: "Δ", Sigma: "Σ", Omega: "Ω", Pi: "Π",
  quad: " ", qquad: "  ", ",": " ", ";": " ", "!": "",
};

function mapScript(value: string, table: Record<string, string>, marker: string): string {
  const chars = [...value];
  if (chars.every((ch) => table[ch])) return chars.map((ch) => table[ch]).join("");
  return `${marker}(${value})`;
}

/** Readable plain-text form of common LaTeX (the site has no KaTeX). */
export function prettyMath(source: string): string {
  let s = String(source || "").trim();
  s = s.replace(/\\(?:left|right|displaystyle|limits)\b/g, "");
  s = s.replace(/\\(?:text|mathrm|mathbf|mathit|operatorname)\{([^{}]*)\}/g, "$1");
  // Innermost-first so nested fractions and roots resolve.
  for (let pass = 0; pass < 6; pass++) {
    const before = s;
    s = s.replace(/\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}/g, (_, a: string, b: string) => {
      // Only a lone number or letter stays unbracketed: "2a" must not read as "/2 · a".
      const wrap = (v: string) => (/^(\d+(\.\d+)?|[A-Za-z])$/.test(v.trim()) ? v.trim() : `(${v.trim()})`);
      return `${wrap(a)}/${wrap(b)}`;
    });
    s = s.replace(/\\sqrt\[([^\]]*)\]\{([^{}]*)\}/g, (_, n: string, v: string) => `${mapScript(n, SUPERSCRIPT, "")}√(${v})`);
    s = s.replace(/\\sqrt\{([^{}]*)\}/g, "√($1)");
    if (s === before) break;
  }
  s = s.replace(/\^\{([^{}]*)\}/g, (_, v: string) => mapScript(v, SUPERSCRIPT, "^"));
  s = s.replace(/_\{([^{}]*)\}/g, (_, v: string) => mapScript(v, SUBSCRIPT, "_"));
  s = s.replace(/\^([0-9a-z+-])/gi, (_, v: string) => SUPERSCRIPT[v] || `^${v}`);
  s = s.replace(/_([0-9a-z])/gi, (_, v: string) => SUBSCRIPT[v] || `_${v}`);
  s = s.replace(/\\([A-Za-z]+|[,;!])/g, (match, name: string) => (name in LATEX_SYMBOLS ? LATEX_SYMBOLS[name] : name));
  s = s.replace(/[{}]/g, "");
  return s.replace(/[ \t]{2,}/g, " ").trim();
}

function safeHref(url: string): string | null {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

const INLINE_RE =
  /(\[btn\][\s\S]*?\[\/btn\])|(\[\[(\d+)\]\]\((https?:\/\/[^)\s]+)\))|(`[^`\n]+`)|(\*\*[^*\n]+?\*\*|__[^_\n]+?__)|(\$[^$\n]+?\$)|(\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\))|((?<![\w*])\*(?!\s)[^*\n]+?(?<!\s)\*(?![\w*]))|(https?:\/\/[^\s<>()]+[^\s<>().,;:!?'"])/g;

export function renderDiamondvoyInline(value: string, keyPrefix: string, options: DiamondvoyMarkdownOptions = {}): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let index = 0;
  const text = String(value || "");
  for (const match of text.matchAll(INLINE_RE)) {
    const start = match.index ?? 0;
    if (start > last) nodes.push(text.slice(last, start));
    const key = `${keyPrefix}-${index++}`;
    const [whole] = match;
    if (match[1]) {
      const label = whole.slice(5, -6);
      nodes.push(
        <button key={key} type="button" onClick={() => options.onButton?.(label)} className="mr-2 mt-1 inline-block rounded-lg border border-cyan-200 bg-cyan-100 px-3 py-1.5 font-semibold text-cyan-700 transition-colors hover:bg-cyan-200 dark:border-cyan-500/30 dark:bg-cyan-500/20 dark:text-cyan-300">
          {label}
        </button>,
      );
    } else if (match[2]) {
      const href = safeHref(match[4]);
      let host = match[3];
      try { host = new URL(match[4]).hostname.replace(/^www\./, ""); } catch {}
      nodes.push(
        href ? (
          <a key={key} href={href} target="_blank" rel="noopener noreferrer" title={host} className="mx-0.5 inline-flex items-center rounded-md bg-blue-50 px-1.5 align-baseline text-[11px] font-bold text-blue-700 no-underline hover:bg-blue-100 dark:bg-blue-500/15 dark:text-blue-300">
            {match[3]}
          </a>
        ) : whole,
      );
    } else if (match[5]) {
      nodes.push(<code key={key} className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em] text-pink-700 dark:bg-white/10 dark:text-pink-300">{whole.slice(1, -1)}</code>);
    } else if (match[6]) {
      nodes.push(<strong key={key} className="font-bold">{renderDiamondvoyInline(whole.slice(2, -2), key, options)}</strong>);
    } else if (match[7]) {
      nodes.push(<span key={key} className="font-mono text-[0.95em] text-blue-800 dark:text-blue-200">{prettyMath(whole.slice(1, -1))}</span>);
    } else if (match[8]) {
      const href = safeHref(match[10]);
      nodes.push(
        href ? (
          <a key={key} href={href} target="_blank" rel="noopener noreferrer" className="font-semibold text-blue-700 underline underline-offset-2 dark:text-blue-300">
            {match[9]}
          </a>
        ) : whole,
      );
    } else if (match[11]) {
      nodes.push(<em key={key}>{renderDiamondvoyInline(whole.slice(1, -1), key, options)}</em>);
    } else if (match[12]) {
      const href = safeHref(whole);
      nodes.push(href ? <a key={key} href={href} target="_blank" rel="noopener noreferrer" className="break-all text-blue-700 underline underline-offset-2 dark:text-blue-300">{whole}</a> : whole);
    }
    last = start + whole.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

const FENCE_RE = /^\s*(```|~~~)\s*([\w+#.-]*)\s*$/;
const TABLE_SEPARATOR_RE = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;
const HEADING_RE = /^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/;
const BULLET_RE = /^\s*[-*+•]\s+(.*)$/;
const NUMBERED_RE = /^\s*(\d{1,3})[.)]\s+(.*)$/;

function tableCells(line: string): string[] {
  let row = line.trim();
  if (row.startsWith("|")) row = row.slice(1);
  if (row.endsWith("|") && !row.endsWith("\\|")) row = row.slice(0, -1);
  return row.split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, "|"));
}

function isTableStart(lines: string[], index: number): boolean {
  return lines[index].includes("|") && index + 1 < lines.length && TABLE_SEPARATOR_RE.test(lines[index + 1]) && lines[index + 1].includes("|");
}

export function renderDiamondvoyMarkdown(text: string, options: DiamondvoyMarkdownOptions = {}): React.ReactNode {
  if (!text) return null;
  const lines = String(text).replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  const inline = (value: string, key: string) => renderDiamondvoyInline(value, key, options);

  for (let index = 0; index < lines.length;) {
    const line = lines[index];
    const key = `b${index}`;

    const fence = line.match(FENCE_RE);
    if (fence) {
      const language = fence[2] || "";
      const code: string[] = [];
      index++;
      // An unclosed fence (still streaming) runs to the end of the message.
      while (index < lines.length && !new RegExp(`^\\s*${fence[1]}\\s*$`).test(lines[index])) code.push(lines[index++]);
      if (index < lines.length) index++;
      blocks.push(
        <figure key={key} className="my-2 max-w-full overflow-hidden rounded-xl border border-slate-700 bg-[#111827]">
          {language ? <figcaption className="border-b border-slate-700 px-3 py-1 font-mono text-[10px] uppercase tracking-wide text-slate-400">{language}</figcaption> : null}
          <pre className="overflow-x-auto p-3 text-xs leading-5 text-slate-100"><code>{code.join("\n")}</code></pre>
        </figure>,
      );
      continue;
    }

    if (isTableStart(lines, index)) {
      const headers = tableCells(line);
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) rows.push(tableCells(lines[index++]));
      blocks.push(
        <div key={key} className="my-2 max-w-full overflow-x-auto rounded-xl border border-slate-200 dark:border-navy-700">
          <table className="min-w-full border-collapse text-left text-xs">
            <thead className="bg-blue-50 text-navy-900 dark:bg-navy-800 dark:text-white">
              <tr>{headers.map((cell, ci) => <th key={ci} className="border-b border-slate-200 px-3 py-2 font-black dark:border-navy-700">{inline(cell, `${key}-h${ci}`)}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className="even:bg-slate-50 dark:even:bg-white/5">
                  {headers.map((_, ci) => <td key={ci} className="border-t border-slate-100 px-3 py-2 align-top dark:border-white/5">{inline(row[ci] || "", `${key}-${ri}-${ci}`)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    const trimmed = line.trim();
    if (trimmed.startsWith("$$") || trimmed.startsWith("\\[")) {
      const close = trimmed.startsWith("$$") ? "$$" : "\\]";
      const body: string[] = [trimmed.slice(2)];
      // A one-line block `$$ x $$`, or gather lines until the closing delimiter.
      if (!(body[0].includes(close))) {
        index++;
        while (index < lines.length && !lines[index].includes(close)) body.push(lines[index++]);
        if (index < lines.length) body.push(lines[index]);
      }
      const formula = body.join(" ").split(close)[0];
      blocks.push(
        <div key={key} className="my-2 overflow-x-auto rounded-xl border border-blue-100 bg-blue-50/70 px-3 py-2 text-center font-mono text-sm font-semibold text-navy-900 dark:border-blue-400/20 dark:bg-blue-500/10 dark:text-blue-100">
          {prettyMath(formula)}
        </div>,
      );
      index++;
      continue;
    }

    const heading = line.match(HEADING_RE);
    if (heading) {
      const level = heading[1].length;
      const size = level <= 1 ? "text-lg" : level === 2 ? "text-base" : "text-sm";
      blocks.push(<p key={key} role="heading" aria-level={level} className={`mt-3 mb-1 font-black ${size}`}>{inline(heading[2], key)}</p>);
      index++;
      continue;
    }

    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
      blocks.push(<hr key={key} className="my-3 border-slate-200 dark:border-white/10" />);
      index++;
      continue;
    }

    if (/^\s*>/.test(line)) {
      const quote: string[] = [];
      while (index < lines.length && /^\s*>/.test(lines[index])) quote.push(lines[index++].replace(/^\s*>\s?/, ""));
      blocks.push(
        <blockquote key={key} className="my-2 rounded-r-xl border-l-4 border-cyan-400 bg-cyan-50/60 px-3 py-2 dark:bg-cyan-500/10">
          {quote.map((item, qi) => <p key={qi} className="whitespace-pre-wrap break-words">{inline(item, `${key}-q${qi}`)}</p>)}
        </blockquote>,
      );
      continue;
    }

    if (BULLET_RE.test(line) || NUMBERED_RE.test(line)) {
      const numbered = !BULLET_RE.test(line);
      const items: { text: string; nested: boolean }[] = [];
      const start = numbered ? Number(line.match(NUMBERED_RE)?.[1] || 1) : 1;
      while (index < lines.length) {
        const current = lines[index];
        const bullet = current.match(BULLET_RE);
        const number = current.match(NUMBERED_RE);
        if (!bullet && !number) break;
        if (!numbered && !bullet && !/^\s{2,}/.test(current)) break;
        if (numbered && !number && !/^\s{2,}/.test(current)) break;
        items.push({ text: (bullet ? bullet[1] : number?.[2]) || "", nested: /^\s{2,}/.test(current) });
        index++;
      }
      const ListTag = numbered ? "ol" : "ul";
      blocks.push(
        <ListTag key={key} start={numbered ? start : undefined} className={`my-1 space-y-1 pl-5 ${numbered ? "list-decimal" : "list-disc"}`}>
          {items.map((item, li) => <li key={li} className={item.nested ? "ml-4" : ""}>{inline(item.text, `${key}-l${li}`)}</li>)}
        </ListTag>,
      );
      continue;
    }

    if (trimmed) {
      blocks.push(<p key={key} className="whitespace-pre-wrap break-words">{inline(line, key)}</p>);
    } else {
      blocks.push(<div key={key} className="h-1" />);
    }
    index++;
  }
  return <div className="break-words text-sm leading-6">{blocks}</div>;
}
