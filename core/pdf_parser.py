import pymupdf

from core.text_normalizer import normalize_scientific_text


MAX_PDF_PAGES = 500
MAX_PAGE_TEXT_CHARS = 100_000
MAX_TOTAL_TEXT_CHARS = 2_000_000


def extract_pdf(file_bytes: bytes) -> list[dict]:
    """提取PDF每一页的文字。"""

    if not file_bytes:
        raise ValueError("PDF文件为空。")

    try:
        document = pymupdf.open(
            stream=file_bytes,
            filetype="pdf",
        )
    except Exception as error:
        raise ValueError("无法打开PDF，文件可能已损坏或格式不正确。") from error

    if document.needs_pass:
        document.close()
        raise ValueError("暂不支持受密码保护的PDF。")

    if document.page_count > MAX_PDF_PAGES:
        page_count = document.page_count
        document.close()
        raise ValueError(
            f"PDF共{page_count}页，超过{MAX_PDF_PAGES}页的安全上限。"
        )

    pages = []
    total_characters = 0

    try:
        for page_number, page in enumerate(document, start=1):
            text = normalize_scientific_text(
                page.get_text("text")
            ).strip()

            if len(text) > MAX_PAGE_TEXT_CHARS:
                text = text[:MAX_PAGE_TEXT_CHARS]

            total_characters += len(text)
            if total_characters > MAX_TOTAL_TEXT_CHARS:
                raise ValueError(
                    "PDF可提取文本超过安全上限，请拆分文档后重试。"
                )

            pages.append(
                {
                    "page_number": page_number,
                    "text": text,
                }
            )
    finally:
        document.close()

    return pages
