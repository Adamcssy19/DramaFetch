def toLocalizedError(error) -> str:
    text = error.message
    return text.format_map(error.params) if error.params else text
