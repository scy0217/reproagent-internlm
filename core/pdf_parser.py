import pymupdf

from core.text_normalizer import normalize_scientific_text


def extract_pdf(file_bytes: bytes) -> list[dict]:
    """提取PDF每一页的文字。"""

    document = pymupdf.open(
        stream=file_bytes,
        filetype="pdf",
    )

    pages = []

    for page_number, page in enumerate(document, start=1):
        text = normalize_scientific_text(
            page.get_text("text")
        ).strip()

        pages.append(
            {
                "page_number": page_number,
                "text": text,
            }
        )

    document.close()
    return pages
