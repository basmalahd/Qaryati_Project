def escape_like(value: str) -> str:
    """Treat user input literally: '%' and '_' must not act as wildcards in LIKE/ILIKE."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
