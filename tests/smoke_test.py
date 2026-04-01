"""
Smoke tests — run before every push.
These tests must pass without the app bundle (no libopenshot dependency).
"""
import os
import sys
import importlib

# Allow importing from src/
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
_failures = []


def check(name, fn):
    try:
        fn()
        print(f"  [{PASS}] {name}")
    except Exception as e:
        print(f"  [{FAIL}] {name}: {e}")
        _failures.append(name)


def test_imports():
    """Core Python imports must work."""
    import PyQt5.QtCore
    import PyQt5.QtWidgets
    import PyQt5.QtGui


def test_project_structure():
    """Key source files must exist."""
    required = [
        "src/launch.py",
        "src/windows/main_window.py",
        "src/classes/api_client.py",
        "src/classes/timeline.py",
        "src/windows/preview_thread.py",
        "src/windows/video_widget.py",
        "src/classes/info.py",
        "src/classes/tool_handlers.py",
    ]
    for rel_path in required:
        full = os.path.join(REPO_ROOT, rel_path)
        if not os.path.isfile(full):
            raise FileNotFoundError(f"Missing: {rel_path}")


def test_video_file_exists():
    """Test video must exist at known path."""
    path = os.path.expanduser("~/Downloads/Feral - Concept Trailer.mp4")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Test video missing: {path}")
    size = os.path.getsize(path)
    if size < 1_000_000:
        raise ValueError(f"Test video too small ({size} bytes) — likely corrupt")


def test_no_conflict_markers():
    """Source files must not contain unresolved merge conflict markers."""
    src_dir = os.path.join(REPO_ROOT, "src")
    import re
    # Match exactly the patterns git uses: 7 < / = / > followed by a space or end-of-line
    conflict_re = re.compile(r'^(?:<{7} |={7}$|>{7} )', re.MULTILINE)
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                if conflict_re.search(content):
                    raise ValueError(f"Conflict marker found in {fpath}")
            except (OSError, IOError):
                pass


def test_info_constants():
    """info.py must have required constants."""
    from classes import info
    assert hasattr(info, "GITHUB_REPO"), "info.GITHUB_REPO missing"
    assert "zenvi-core" in info.GITHUB_REPO.lower() or "Zenvi" in info.GITHUB_REPO, \
        f"Unexpected GITHUB_REPO: {info.GITHUB_REPO}"
    assert hasattr(info, "BACKEND_URL"), "info.BACKEND_URL missing"


def test_api_client_init():
    """ZenviBackendClient must instantiate without crashing."""
    from classes.api_client import ZenviBackendClient
    client = ZenviBackendClient(base_url="https://api.zenvi.pro")
    assert hasattr(client, "_ssl_verify"), "Missing _ssl_verify"
    assert client._ssl_verify is True, "Production URL should verify SSL"
    dev_client = ZenviBackendClient(base_url="http://localhost:8000")
    assert dev_client._ssl_verify is False, "Non-production URL should skip SSL"


if __name__ == "__main__":
    print("Running smoke tests...\n")
    check("imports: PyQt5", test_imports)
    check("project structure: key files exist", test_project_structure)
    check("test video exists", test_video_file_exists)
    check("no merge conflict markers in src/", test_no_conflict_markers)
    check("info.py constants", test_info_constants)
    check("ZenviBackendClient init", test_api_client_init)

    print()
    if _failures:
        print(f"FAILED: {len(_failures)} test(s): {', '.join(_failures)}")
        sys.exit(1)
    else:
        print("All smoke tests PASSED.")
        sys.exit(0)
