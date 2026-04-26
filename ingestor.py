"""
ingestor.py - PDF to Markdown conversion (Windows-safe, no emoji in output)
"""
import os, re, sys
import pdfplumber
import fitz  # PyMuPDF

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _sanitize_unicode(text: str) -> str:
    """Remove characters that Windows charmap codec cannot encode.
    Strips non-BMP characters (code points > 0xFFFF) such as emoji
    (e.g. U+1F4C4 = 📄) that cause 'charmap' codec errors on Windows.
    """
    sanitized = "".join(
        ch if ord(ch) <= 0xFFFF else " "
        for ch in text
    )
    # Remove stray control characters (keep tab, newline, CR)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", sanitized)
    return sanitized


def _clean_cell(cell) -> str:
    if cell is None:
        return ""
    return _sanitize_unicode(str(cell).replace("\n", " ").strip())


def _is_heading(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    if re.match(r"^[A-Z][A-Z\s\-&/()]{4,59}$", line) and len(line) < 60:
        return True
    if re.match(r"^(\d+\.)+\s+[A-Z]", line):
        return True
    return False


def _extract_with_pdfplumber(pdf_path: str) -> str:
    md_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            md_parts.append(f"\n\n## Page {page_num}\n")
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    if not table or len(table) < 1:
                        continue
                    header = [_clean_cell(c) for c in table[0]]
                    if not any(header):
                        continue
                    rows = table[1:]
                    md_parts.append("\n")
                    md_parts.append("| " + " | ".join(header) + " |")
                    md_parts.append("| " + " | ".join(["---"] * len(header)) + " |")
                    for row in rows:
                        clean_row = [_clean_cell(c) for c in row]
                        while len(clean_row) < len(header):
                            clean_row.append("")
                        clean_row = clean_row[:len(header)]
                        md_parts.append("| " + " | ".join(clean_row) + " |")
                    md_parts.append("\n")
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                for line in text.split("\n"):
                    line = _sanitize_unicode(line.strip())
                    if not line:
                        continue
                    if _is_heading(line):
                        md_parts.append(f"\n### {line}\n")
                    else:
                        md_parts.append(line)
    return "\n".join(md_parts)


def process_to_markdown(pdf_path: str, output_folder: str = "data/markdown") -> str:
    os.makedirs(output_folder, exist_ok=True)
    print(f"Processing: {pdf_path}")
    try:
        markdown_text = _extract_with_pdfplumber(pdf_path)
    except Exception as e:
        print(f"pdfplumber failed ({e}), falling back to PyMuPDF")
        doc = fitz.open(pdf_path)
        markdown_text = ""
        for page in doc:
            markdown_text += page.get_text("text") + "\n\n"
        markdown_text = _sanitize_unicode(markdown_text)

    base_name = os.path.basename(pdf_path).replace(".pdf", "")
    save_path = os.path.join(output_folder, f"{base_name}.md")
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(f"# {base_name}\n\n")
        f.write(markdown_text)
    print(f"Saved Markdown: {save_path} ({len(markdown_text)} chars)")
    return save_path


def extract_text_only(pdf_path: str) -> str:
    try:
        text = _extract_with_pdfplumber(pdf_path)
        if len(text.strip()) < 100:
            raise ValueError("Extracted text too short")
        return text
    except Exception as e:
        print(f"pdfplumber failed ({e}), using PyMuPDF")
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text("text") + "\n\n"
            return _sanitize_unicode(text)
        except Exception as e2:
            return f"[PDF extraction failed: {e2}. Please paste the RFP text manually.]"


if __name__ == "__main__":
    found = False
    for file in os.listdir("data"):
        if file.endswith(".pdf"):
            found = True
            process_to_markdown(f"data/{file}")
    if not found:
        print("No PDF files found in /data.")