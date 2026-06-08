from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class DialectPrediction:
    dialect: str
    confidence: float


class DialectClassifier:
    """
    Simple rule-based dialect classifier for Telugu.

    - Input: transcript string (assumed Telugu).
    - Output: dialect label and confidence score.
    - Dialects: telangana, andhra, standard_telugu.

    This is intentionally lightweight and fast (<500ms) and must not
    use any ML models.
    """

    DIALECTS = ("telangana", "andhra", "standard_telugu")

    # Keyword heuristics. These can be refined over time; for now we keep
    # a small set of distinctive lexical markers.
    TELANGANA_KEYWORDS = {
        # Common colloquial particles and vocabulary (examples).
        "ra",  # vocative particle often used in Telangana speech
        "emo",  # discourse particle
        "inka enduku",  # phrase example
    }

    ANDHRA_KEYWORDS = {
        # Andhra-flavored forms and particles (examples).
        "ayya",
        "andi",
        "kadha",
    }

    def detect(self, text: str) -> DialectPrediction:
        """
        Detect Telugu dialect from transcript text using keyword heuristics.

        If no clear evidence is found, falls back to `standard_telugu`
        with moderate confidence.
        """
        if not text or not text.strip():
            # For empty text, assume standard Telugu with low confidence.
            return DialectPrediction(dialect="standard_telugu", confidence=0.5)

        normalized = text.lower()

        scores: Dict[str, float] = {d: 0.0 for d in self.DIALECTS}

        # Count keyword hits for each dialect.
        for kw in self.TELANGANA_KEYWORDS:
            if kw in normalized:
                scores["telangana"] += 1.0

        for kw in self.ANDHRA_KEYWORDS:
            if kw in normalized:
                scores["andhra"] += 1.0

        # Simple smoothing: base prior for standard Telugu so that
        # it becomes the fallback when no dialect-specific cues exist.
        scores["standard_telugu"] = 1.0

        total = sum(scores.values())
        if total <= 0.0:
            # Defensive fallback; should not happen with above prior.
            return DialectPrediction(dialect="standard_telugu", confidence=0.5)

        # Convert counts to normalized confidence-like values.
        probabilities = {k: v / total for k, v in scores.items()}

        best_dialect, best_score = max(probabilities.items(), key=lambda kv: kv[1])

        return DialectPrediction(dialect=best_dialect, confidence=float(best_score))


__all__ = ["DialectClassifier", "DialectPrediction"]

