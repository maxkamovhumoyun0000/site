/** Only unambiguous common English expansions; keep noun possessives intact. */
export function expandEnglishContractions(value: string): string {
  return value.toLowerCase().replace(/[‘’`´]/g, "'")
    .replace(/\bcan't\b/g, "cannot").replace(/\bcan not\b/g, "cannot")
    .replace(/\bwon't\b/g, "will not").replace(/\bshan't\b/g, "shall not")
    .replace(/\bi'm\b/g, "i am")
    .replace(/\b(he|she|it|that|there|what|where|who|how|when|why)'s\b/g, "$1 is")
    .replace(/\b(you|we|they|what|where|who|there)'re\b/g, "$1 are")
    .replace(/\b(i|you|we|they)'ve\b/g, "$1 have")
    .replace(/\b(i|you|he|she|it|we|they|that|there|who)'ll\b/g, "$1 will")
    .replace(/\b(is|are|was|were|do|does|did|has|have|had|could|would|should|must|need)n't\b/g, "$1 not")
    .replace(/\s+/g, " ").trim();
}
