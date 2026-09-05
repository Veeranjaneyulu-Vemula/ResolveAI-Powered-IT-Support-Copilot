def build_ticket_embedding_text(
    *,
    title: str,
    description: str,
    resolution: str | None = None,
) -> str:
    sections = [
        f"Title:\n{title.strip()}",
        f"Description:\n{description.strip()}",
    ]

    if resolution and resolution.strip():
        sections.append(f"Resolution:\n{resolution.strip()}")

    return "\n\n".join(sections)


def build_troubleshooting_query(
    *,
    title: str,
    description: str,
    question: str | None = None,
) -> str:
    sections = [
        f"Ticket title:\n{title.strip()}",
        f"Ticket description:\n{description.strip()}",
    ]

    if question and question.strip():
        sections.append(f"Support question:\n{question.strip()}")

    return "\n\n".join(sections)
