"""Normalization layer: encoding detection/decoding and newline handling.

Design: DECODE-POLICY.md. Never silently miscount and never silently drop:
undecodable files raise DecodeError and are quarantined by the caller.
Line splitting is CR / LF / CRLF only (never str.splitlines(), which would
also split on U+2028, U+2029, NEL, FF and break the invariance rule).
"""
from __future__ import annotations

from dataclasses import dataclass, field


class DecodeError(Exception):
    """Raised when a file cannot be decoded with any candidate encoding."""


@dataclass
class Decoded:
    text: str
    encoding: str
    source: str  # "bom" | "explicit" | "heuristic"
    score: int = 0
    margin: int = 0
    ambiguous: bool = False
    candidates: list = field(default_factory=list)


def is_binary(data: bytes) -> bool:
    """F3 check: NUL byte in the first 8KB. UTF-16 (with BOM) legitimately
    contains NUL bytes, so it is exempted."""
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return False
    return b"\x00" in data[:8192]


def _japanese_score(text: str) -> int:
    score = 0
    for ch in text:
        o = ord(ch)
        if 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF:
            score += 2  # hiragana / katakana / kanji
        elif 0xFF00 <= o <= 0xFF60:
            score += 1  # fullwidth forms
        elif 0xFF61 <= o <= 0xFF9F:
            score -= 3  # halfwidth katakana: typical mojibake symptom
        elif o < 0x20 and ch not in "\t\n\r":
            score -= 5  # stray control characters
    return score


_CANDIDATES = ("utf-8", "cp932", "euc_jp")


def decode_bytes(data: bytes, explicit: str | None = None) -> Decoded:
    if explicit:
        try:
            return Decoded(data.decode(explicit), explicit, "explicit")
        except (UnicodeDecodeError, LookupError) as exc:
            raise DecodeError(f"explicit encoding {explicit} failed: {exc}") from exc

    # BOM first.
    if data.startswith(b"\xef\xbb\xbf"):
        return Decoded(data.decode("utf-8-sig"), "utf-8", "bom")
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        try:
            return Decoded(data.decode("utf-16"), "utf-16", "bom")
        except UnicodeDecodeError as exc:
            raise DecodeError(f"utf-16 BOM but undecodable: {exc}") from exc

    # ISO-2022-JP announces itself with escape sequences.
    if b"\x1b$" in data or b"\x1b(" in data:
        try:
            return Decoded(data.decode("iso2022_jp"), "iso2022_jp", "heuristic",
                           score=_japanese_score(data.decode("iso2022_jp")))
        except UnicodeDecodeError:
            pass

    scored: list[tuple[int, str, str]] = []
    for enc in _CANDIDATES:
        try:
            text = data.decode(enc)
        except UnicodeDecodeError:
            continue
        scored.append((_japanese_score(text), enc, text))
    if not scored:
        raise DecodeError("no candidate encoding could decode the file")

    # Highest score wins; ties resolve in candidate order (utf-8 first).
    order = {enc: i for i, enc in enumerate(_CANDIDATES)}
    scored.sort(key=lambda s: (-s[0], order[s[1]]))
    best_score, best_enc, best_text = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0
    margin = best_score - second
    return Decoded(
        text=best_text,
        encoding=best_enc,
        source="heuristic",
        score=best_score,
        margin=margin,
        ambiguous=len(scored) > 1 and best_score > 0 and margin < 3,
        candidates=[{"encoding": enc, "score": s} for s, enc, _ in scored],
    )


def decode_replace(data: bytes):
    """Best-effort decode for --on-error replace: try candidates with
    errors='replace'. Returns (text, encoding, replacement_count,
    replacement_line_numbers)."""
    for enc in ("utf-8", "cp932", "euc_jp"):
        text = data.decode(enc, errors="replace")
        bad = text.count("�")
        if enc == "utf-8" and bad > max(4, len(text) // 20):
            continue  # too damaged; another candidate may do better
        line_numbers = [i + 1 for i, line in enumerate(to_lines(text))
                        if "�" in line][:20]
        return text, enc, bad, line_numbers
    text = data.decode("utf-8", errors="replace")
    return text, "utf-8", text.count("�"), [
        i + 1 for i, line in enumerate(to_lines(text)) if "�" in line][:20]


def to_lines(text: str) -> list[str]:
    """Normalize CRLF / CR to LF, then split. A trailing newline does not
    create a phantom final line."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines
