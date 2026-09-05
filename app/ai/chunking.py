def chunk_text(
    text: str,
    *,
    chunk_size: int = 120,
    overlap: int = 20,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size")

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))

        if end == len(words):
            break
        start = end - overlap

    return chunks


def add_chunk_context(
    *,
    article_title: str,
    category: str,
    content: str,
) -> str:
    return (
        f"Article title:\n{article_title.strip()}\n\n"
        f"Category:\n{category.strip()}\n\n"
        f"Content:\n{content.strip()}"
    )
