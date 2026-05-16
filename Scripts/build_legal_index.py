import sys
from core.legal.legal_indexer import build_legal_index


if __name__ == "__main__":
    wipe = "--wipe" in sys.argv or "--rebuild" in sys.argv
    build_legal_index(include_nested=True, wipe_first=wipe)
