import re

def strip_markdown_fence(text: str) -> str:
    if not text:
        return text
    text = text.strip()
    pattern = r"^```(?:markdown|md)?\s*([\s\S]*?)\s*```$"
    match = re.match(pattern, text, re.MULTILINE)
    return (
        match.group(1).strip()
        if match
        else re.sub(r"^```(?:markdown|md)?|```$", "", text, flags=re.MULTILINE).strip()
    )