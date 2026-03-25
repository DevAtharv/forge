def search_sources(query: str, limit: int = 3) -> dict:
    # Lightweight stub returning mock sources
    sources = []
    for i in range(1, limit + 1):
        sources.append(
            {
                "title": f"Source {i}",
                "url": f"https://example.com/source-{i}",
                "snippet": f"Snippet for {query} #{i}",
            }
        )
    return {"sources": sources}
