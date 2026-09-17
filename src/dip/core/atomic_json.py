"""Atomic JSON snapshots for single-process stores (not a database lock)."""
import json
import os
from pathlib import Path
import tempfile


def write_json(path, payload):
    """Serialize before replacing; a failed write leaves the old snapshot intact."""
    path = Path(path)
    encoded = json.dumps(payload, indent=2, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
