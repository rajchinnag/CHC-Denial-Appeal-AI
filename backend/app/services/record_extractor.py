"""
Extract plain text from an uploaded medical record so it can be passed
through PHI de-identification. Supports PDF, DOCX, and plain text.
"""
import io


def extract_text(file_bytes: bytes, filename: str) -> str:
    lower = filename.lower()

    if lower.endswith(".pdf"):
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)

    if lower.endswith(".docx"):
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)

    # Fallback: treat as plain text
    return file_bytes.decode("utf-8", errors="ignore")
