from dataclasses import dataclass
from typing import List

PARAGRAPH_SEP = "\n\n"
MAX_CHARS = 1000
OVERLAP = 100


@dataclass
class ChunkLike:
    chunk_index: int
    start_char: int
    end_char: int
    text: str


def chunk_text(text: str) -> List[ChunkLike]:
    """
    Deterministically split text into overlapping chunks.

    Strategy:
    - Normalize newlines.
    - Split into paragraphs on double newlines.
    - Concatenate paragraphs up to MAX_CHARS, then slide with OVERLAP.
    """
    norm = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = norm.split(PARAGRAPH_SEP)
    positions = []
    offset = 0
    for para in paragraphs:
        start = offset
        end = start + len(para)
        positions.append((para, start, end))
        offset = end + len(PARAGRAPH_SEP)

    raw_chunks: List[ChunkLike] = []
    current_text = ""
    current_start = 0

    for para, start, end in positions:
        if not current_text:
            current_text = para
            current_start = start
            continue

        candidate = current_text + PARAGRAPH_SEP + para
        if len(candidate) <= MAX_CHARS:
            current_text = candidate
        else:
            raw_chunks.append(
                ChunkLike(
                    chunk_index=len(raw_chunks),
                    start_char=current_start,
                    end_char=current_start + len(current_text),
                    text=current_text,
                )
            )
            current_text = para
            current_start = start

    if current_text:
        raw_chunks.append(
            ChunkLike(
                chunk_index=len(raw_chunks),
                start_char=current_start,
                end_char=current_start + len(current_text),
                text=current_text,
            )
        )

    if not raw_chunks:
        return []

    # Apply overlap on character indices while keeping deterministic order
    final_chunks: List[ChunkLike] = []
    for idx, ch in enumerate(raw_chunks):
        if idx == 0:
            final_chunks.append(ChunkLike(0, ch.start_char, ch.end_char, ch.text))
            continue
        prev = final_chunks[-1]
        new_start = max(ch.start_char, prev.end_char - OVERLAP)
        slice_start = new_start - ch.start_char
        new_text = ch.text[slice_start:]
        final_chunks.append(
            ChunkLike(
                chunk_index=len(final_chunks),
                start_char=new_start,
                end_char=new_start + len(new_text),
                text=new_text,
            )
        )

    return final_chunks

