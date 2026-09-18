from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.parser import ParsedChunk


@dataclass
class KnowledgeCandidate:
    title: str
    item_type: str
    content: str
    source_section: str | None
    confidence: float


ALARM_PATTERN = re.compile(r"\b(?:ALM|ALARM|ATC|SP|SV|CP|EX|ER)[-_ ]?\d{3,6}\b", re.IGNORECASE)
PART_PATTERN = re.compile(r"(?:备件号|物料号|零件号|Part\s*No\.?)[：:\s]*([A-Z0-9][A-Z0-9._/-]{4,40})", re.IGNORECASE)


def extract_candidates(chunks: list[ParsedChunk], limit: int = 50) -> list[KnowledgeCandidate]:
    """Conservative rule extraction. Candidates never publish automatically."""
    results: list[KnowledgeCandidate] = []
    seen: set[tuple[str, str]] = set()
    for chunk in chunks:
        compact = re.sub(r"\s+", " ", chunk.content).strip()
        for code in ALARM_PATTERN.findall(compact):
            normalized = code.upper().replace(" ", "-").replace("_", "-")
            key = ("alarm", normalized)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                KnowledgeCandidate(
                    title=f"待审核报警知识：{normalized}",
                    item_type="alarm_candidate",
                    content=compact[:1200],
                    source_section=chunk.heading,
                    confidence=0.62,
                )
            )
        for part_no in PART_PATTERN.findall(compact):
            key = ("part", part_no.upper())
            if key in seen:
                continue
            seen.add(key)
            results.append(
                KnowledgeCandidate(
                    title=f"待审核备件知识：{part_no}",
                    item_type="part_candidate",
                    content=compact[:1200],
                    source_section=chunk.heading,
                    confidence=0.58,
                )
            )
        if len(results) >= limit:
            break
    return results[:limit]

