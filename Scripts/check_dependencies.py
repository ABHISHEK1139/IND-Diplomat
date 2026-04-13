import sys
print(f"Python {sys.version}")

try:
    import pypdf
    print("pypdf available")
except ImportError:
    print("pypdf MISSING")

try:
    import PyPDF2
    print("PyPDF2 available")
except ImportError:
    print("PyPDF2 MISSING")

try:
    from pdfminer.high_level import extract_text
    print("pdfminer available")
except ImportError:
    print("pdfminer MISSING")
