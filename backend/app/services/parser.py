from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class ParserUnavailable(RuntimeError):
    pass


@dataclass
class ParsedChunk:
    heading: str | None
    content: str
    page_number: int | None = None


def _chunk_text(text: str, max_chars: int = 900, overlap: int = 100) -> list[ParsedChunk]:
    text = text.replace("\r\n", "\n").strip()
    if not text:
        raise ParserUnavailable("文件中没有可解析的文字内容")
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    chunks: list[ParsedChunk] = []
    heading: str | None = None
    buffer = ""
    buffer_heading: str | None = None

    def flush() -> None:
        nonlocal buffer, buffer_heading
        if buffer:
            chunks.append(ParsedChunk(heading=buffer_heading, content=buffer))
            buffer = ""
            buffer_heading = None

    def append_piece(piece: str) -> None:
        nonlocal buffer, buffer_heading
        if len(piece) > max_chars:
            flush()
            step = max_chars - min(overlap, max_chars // 3)
            for start in range(0, len(piece), step):
                segment = piece[start : start + max_chars]
                if segment:
                    chunks.append(ParsedChunk(heading=heading, content=segment))
                if start + max_chars >= len(piece):
                    break
            return
        if buffer and len(buffer) + len(piece) + 2 > max_chars:
            flush()
        if not buffer:
            buffer_heading = heading
        buffer = f"{buffer}\n\n{piece}".strip()

    for block in blocks:
        if block.startswith("#"):
            flush()
            heading = block.lstrip("# ")[:255]
        append_piece(block)
    flush()
    return chunks


def parse_document(path: Path) -> list[ParsedChunk]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        return _chunk_text(text)

    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise ParserUnavailable(
            "当前环境未安装 Docling；Docker 完整版支持 PDF、Office 和图片解析"
        ) from exc

    result = DocumentConverter().convert(str(path))
    markdown = result.document.export_to_markdown()
    if not markdown.strip():
        raise ParserUnavailable("未能从文件中提取可检索文字，请检查扫描质量")
    return _chunk_text(markdown)
