import re

def clean_domain(text: str) -> str:
    text = text.lower().strip()
    text = text.replace(" ", "-").replace(".", "-").replace("/", "-")
    return re.sub(r"[^a-z0-9\-]", "", text)