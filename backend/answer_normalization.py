"""Conservative English contraction equivalence for free-text answers."""
import re


def expand_english_contractions(value: str) -> str:
    text = re.sub(r"[‘’`´]", "'", str(value or "").lower())
    text = re.sub(r"\bcan't\b", "cannot", text)
    text = re.sub(r"\bcan not\b", "cannot", text)
    text = re.sub(r"\bwon't\b", "will not", text)
    text = re.sub(r"\bshan't\b", "shall not", text)
    text = re.sub(r"\bi'm\b", "i am", text)
    # Noun possessives (John's book), 'd and 's=has remain untouched;
    # ambiguous alternatives must be supplied explicitly by the author.
    text = re.sub(r"\b(he|she|it|that|there|what|where|who|how|when|why)'s\b", r"\1 is", text)
    text = re.sub(r"\b(you|we|they|what|where|who|there)'re\b", r"\1 are", text)
    text = re.sub(r"\b(i|you|we|they)'ve\b", r"\1 have", text)
    text = re.sub(r"\b(i|you|he|she|it|we|they|that|there|who)'ll\b", r"\1 will", text)
    text = re.sub(r"\b(is|are|was|were|do|does|did|has|have|had|could|would|should|must|need)n't\b", r"\1 not", text)
    return re.sub(r"\s+", " ", text).strip()
