from app.pipeline.chunk import chunk_text


def test_chunking_determinism_and_overlap():
    text = (
        "Paragraph one.\n\n"
        "Paragraph two is a bit longer and will be combined with others.\n\n"
        "Paragraph three.\n\n"
        "Paragraph four."
    )

    chunks1 = chunk_text(text)
    chunks2 = chunk_text(text)

    # Deterministic output
    assert [(c.start_char, c.end_char, c.text) for c in chunks1] == [
        (c.start_char, c.end_char, c.text) for c in chunks2
    ]

    # Offsets should be non-decreasing and within bounds
    for c in chunks1:
        assert 0 <= c.start_char <= c.end_char <= len(text)

    # Overlap: each subsequent chunk should start before previous end when multiple chunks exist
    if len(chunks1) > 1:
        for prev, curr in zip(chunks1, chunks1[1:]):
            assert curr.start_char <= prev.end_char

