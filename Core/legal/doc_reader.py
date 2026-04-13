from pathlib import Path

from docx import Document


def read_docx(path: Path) -> str:
    doc = Document(str(path))
    text = []
    for para in doc.paragraphs:
        if para.text:
            text.append(para.text)
    return "\n".join(text)


def read_txt(path: Path) -> str:
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def read_doc(path: Path) -> str:
    """
    Best-effort legacy .doc reader via Microsoft Word COM on Windows.
    Requires MS Word + pywin32 installed.
    """
    try:
        import win32com.client  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "DOC support requires Microsoft Word and pywin32 in this environment."
        ) from exc

    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    document = None
    try:
        document = word.Documents.Open(str(path))
        return document.Content.Text
    finally:
        if document is not None:
            document.Close(False)
        word.Quit()
