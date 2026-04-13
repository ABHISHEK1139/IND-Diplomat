"""System bootstrapper for IND-Diplomat runtime environment."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / "diplomat_env"
REQ_PATH = ROOT / "system_bootstrap" / "requirements.txt"

WINDOWS_WINGET_PACKAGES = {
    "tesseract": [
        "tesseract-ocr.tesseract",
        "UB-Mannheim.TesseractOCR",
    ],
    "poppler": [
        "oschwartz10612.Poppler",
    ],
    "git": ["Git.Git"],
    "curl": ["cURL.cURL"],
    "ollama": ["Ollama.Ollama"],
}

LINUX_APT_PACKAGES = {
    "tesseract": ["tesseract-ocr"],
    "poppler": ["poppler-utils"],
    "git": ["git"],
    "curl": ["curl"],
    "ollama": [],
}

WINDOWS_BINARY_CANDIDATES = {
    "tesseract": [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ],
    "pdftoppm": [
        Path(r"C:\Program Files\poppler\Library\bin\pdftoppm.exe"),
        Path(r"C:\Program Files\poppler\bin\pdftoppm.exe"),
    ],
    "git": [
        Path(r"C:\Program Files\Git\cmd\git.exe"),
        Path(r"C:\Program Files\Git\bin\git.exe"),
    ],
    "curl": [
        Path(r"C:\Windows\System32\curl.exe"),
        Path(r"C:\Program Files\Git\mingw64\bin\curl.exe"),
    ],
    "ollama": [
        Path(r"C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama.exe"),
        Path(r"C:\Program Files\Ollama\ollama.exe"),
    ],
}


def run_cmd(cmd: List[str], timeout: int = 900, shell: bool = False) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(
            cmd if not shell else " ".join(cmd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=shell,
            check=False,
        )
        return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip()
    except Exception as exc:
        return 1, "", str(exc)


def print_step(message: str) -> None:
    print(f"[bootstrap] {message}")


def detect_os() -> str:
    system = platform.system().strip()
    if system not in {"Windows", "Linux"}:
        raise RuntimeError(f"Unsupported OS: {system}. Only Windows/Linux are supported.")
    print_step(f"OS detected: {system}")
    return system


def ensure_python_version() -> None:
    if sys.version_info < (3, 10):
        raise RuntimeError(
            f"Python >= 3.10 required. Current: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
    print_step(f"Python version OK: {sys.version.split()[0]}")


def ensure_venv_exists() -> None:
    if VENV_DIR.exists():
        return
    print_step(f"Creating virtual environment at {VENV_DIR}")
    rc, out, err = run_cmd([sys.executable, "-m", "venv", str(VENV_DIR)], timeout=600)
    if rc != 0:
        raise RuntimeError(f"Failed to create venv at {VENV_DIR}.\nstdout: {out}\nstderr: {err}")


def ensure_venv_active() -> None:
    current_prefix = Path(sys.prefix).resolve()
    expected = VENV_DIR.resolve()
    in_venv = sys.prefix != sys.base_prefix and current_prefix == expected
    if not in_venv:
        raise RuntimeError(
            "Virtual environment is not active.\n"
            f"Expected active env: {expected}\n"
            f"Current sys.prefix: {current_prefix}\n"
            "Windows: system_bootstrap\\bootstrap.bat\n"
            "Linux: source system_bootstrap/bootstrap.sh"
        )
    print_step(f"Virtual environment active: {current_prefix}")


def ensure_pip_works() -> None:
    rc, out, err = run_cmd([sys.executable, "-m", "pip", "--version"], timeout=60)
    if rc != 0:
        raise RuntimeError(f"pip check failed.\nstdout: {out}\nstderr: {err}")
    print_step(f"pip OK: {out}")


def install_python_requirements() -> None:
    if not REQ_PATH.exists():
        raise RuntimeError(f"Missing requirements file: {REQ_PATH}")
    print_step(f"Installing Python dependencies from {REQ_PATH}")
    rc, out, err = run_cmd([sys.executable, "-m", "pip", "install", "-r", str(REQ_PATH)], timeout=3600)
    if rc != 0:
        raise RuntimeError(f"pip install failed.\nstdout: {out}\nstderr: {err}")
    print_step("Python dependencies installed")

    print_step("Installing spaCy model: en_core_web_sm")
    rc, out, err = run_cmd([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], timeout=1200)
    if rc != 0:
        raise RuntimeError(f"spaCy model install failed.\nstdout: {out}\nstderr: {err}")
    print_step("spaCy model installed")


def has_binary(name: str) -> bool:
    return shutil.which(name) is not None


def _expand_windows_user(path: Path) -> Path:
    return Path(os.path.expandvars(str(path)))


def resolve_binary(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    if platform.system().strip() != "Windows":
        return None

    candidates = WINDOWS_BINARY_CANDIDATES.get(name, [])
    for candidate in candidates:
        expanded = _expand_windows_user(candidate)
        if expanded.exists():
            return str(expanded)
    return None


def _append_path_if_exists(paths: Iterable[Path]) -> None:
    current = os.environ.get("PATH", "")
    path_entries = current.split(os.pathsep) if current else []
    changed = False
    for p in paths:
        try:
            resolved = str(p.resolve())
        except Exception:
            resolved = str(p)
        if p.exists() and resolved not in path_entries:
            path_entries.append(resolved)
            changed = True
    if changed:
        os.environ["PATH"] = os.pathsep.join(path_entries)


def _windows_post_install_path_fix() -> None:
    tesseract_candidates = [
        Path(r"C:\Program Files\Tesseract-OCR"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR"),
    ]
    poppler_candidates = [
        Path(r"C:\Program Files\poppler\Library\bin"),
        Path(r"C:\Program Files\poppler\bin"),
    ]
    git_candidates = [
        Path(r"C:\Program Files\Git\cmd"),
        Path(r"C:\Program Files\Git\bin"),
    ]
    ollama_candidates = [
        _expand_windows_user(Path(r"C:\Users\%USERNAME%\AppData\Local\Programs\Ollama")),
        Path(r"C:\Program Files\Ollama"),
    ]
    _append_path_if_exists(
        tesseract_candidates + poppler_candidates + git_candidates + ollama_candidates
    )


def _install_with_winget(package_ids: List[str]) -> Tuple[bool, str]:
    if not has_binary("winget"):
        return False, "winget not available"
    for package_id in package_ids:
        cmd = [
            "winget",
            "install",
            "--id",
            package_id,
            "-e",
            "--accept-source-agreements",
            "--accept-package-agreements",
            "--silent",
        ]
        rc, out, err = run_cmd(cmd, timeout=1800)
        if rc == 0:
            return True, f"Installed via winget: {package_id}"
        last_err = err or out
    return False, f"winget install failed for ids: {package_ids} | last error: {last_err if 'last_err' in locals() else 'unknown'}"


def _install_with_apt(packages: List[str]) -> Tuple[bool, str]:
    if not packages:
        return True, "No apt packages requested"
    if not has_binary("apt-get"):
        return False, "apt-get not available"

    update_cmd = ["sudo", "apt-get", "update"]
    rc, out, err = run_cmd(update_cmd, timeout=1200)
    if rc != 0:
        return False, f"apt-get update failed: {err or out}"

    install_cmd = ["sudo", "apt-get", "install", "-y"] + packages
    rc, out, err = run_cmd(install_cmd, timeout=2400)
    if rc != 0:
        return False, f"apt-get install failed: {err or out}"
    return True, f"Installed with apt: {' '.join(packages)}"


def ensure_native_software(os_name: str) -> None:
    required = ["tesseract", "poppler", "git", "curl"]
    for tool in required:
        if tool == "poppler":
            found = resolve_binary("pdftoppm") is not None
        else:
            found = resolve_binary(tool) is not None
        if found:
            print_step(f"Native software OK: {tool}")
            continue

        print_step(f"Native software missing: {tool}. Installing...")
        if os_name == "Windows":
            ok, msg = _install_with_winget(WINDOWS_WINGET_PACKAGES.get(tool, []))
            _windows_post_install_path_fix()
            if not ok:
                raise RuntimeError(f"Failed to install {tool} on Windows. {msg}")
        else:
            ok, msg = _install_with_apt(LINUX_APT_PACKAGES.get(tool, []))
            if not ok:
                raise RuntimeError(f"Failed to install {tool} on Linux. {msg}")
        print_step(msg)

    tesseract_bin = resolve_binary("tesseract") or "tesseract"
    rc, out, err = run_cmd([tesseract_bin, "--version"], timeout=30)
    if rc != 0:
        raise RuntimeError(f"Tesseract verification failed.\nstdout: {out}\nstderr: {err}")
    first_line = out.splitlines()[0] if out else "unknown"
    print_step(f"Tesseract verified: {first_line}")


def ensure_ollama(os_name: str) -> None:
    ollama_bin = resolve_binary("ollama")
    if not ollama_bin:
        print_step("Ollama missing. Installing...")
        if os_name == "Windows":
            ok, msg = _install_with_winget(WINDOWS_WINGET_PACKAGES["ollama"])
            if not ok:
                raise RuntimeError(f"Failed to install Ollama on Windows. {msg}")
            print_step(msg)
            _windows_post_install_path_fix()
        else:
            cmd = ["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"]
            rc, out, err = run_cmd(cmd, timeout=1800)
            if rc != 0:
                raise RuntimeError(f"Failed to install Ollama on Linux.\nstdout: {out}\nstderr: {err}")
            print_step("Installed Ollama via install script")
        ollama_bin = resolve_binary("ollama")
        if not ollama_bin:
            raise RuntimeError("Ollama install completed but binary is still not discoverable on PATH.")

    rc, out, err = run_cmd([ollama_bin, "--version"], timeout=30)
    if rc != 0:
        raise RuntimeError(f"Ollama not usable.\nstdout: {out}\nstderr: {err}")
    print_step(f"Ollama OK: {out}")

    print_step("Pulling model deepseek-r1:8b")
    rc, out, err = run_cmd([ollama_bin, "pull", "deepseek-r1:8b"], timeout=3600)
    if rc != 0:
        raise RuntimeError(f"Failed to pull model deepseek-r1:8b.\nstdout: {out}\nstderr: {err}")

    print_step("Running model smoke test")
    rc, out, err = run_cmd([ollama_bin, "run", "deepseek-r1:8b", "Say OK"], timeout=300)
    if rc != 0:
        raise RuntimeError(f"Ollama inference failed.\nstdout: {out}\nstderr: {err}")
    combined = f"{out}\n{err}".strip()
    if "ok" not in combined.lower():
        raise RuntimeError(f"Ollama test returned unexpected output: {combined[:500]}")
    print_step("Ollama model validation passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap runtime environment for IND-Diplomat.")
    parser.add_argument(
        "--skip-native-install",
        action="store_true",
        help="Skip native binary installation checks (for constrained environments).",
    )
    args = parser.parse_args()

    try:
        os_name = detect_os()
        ensure_python_version()
        ensure_venv_exists()
        ensure_venv_active()
        ensure_pip_works()
        install_python_requirements()
        if not args.skip_native_install:
            ensure_native_software(os_name)
        ensure_ollama(os_name)
        print_step("Bootstrap completed successfully")
        return 0
    except Exception as exc:
        print_step(f"BOOTSTRAP_FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
