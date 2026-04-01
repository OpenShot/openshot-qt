"""Unit tests for project file extension constants and save-path normalization."""

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from classes import info  # noqa: E402


def test_canonical_ext_is_zvn_legacy_includes_osp_and_flow():
    assert info.PROJECT_EXT == ".zvn"
    assert info.ALL_PROJECT_EXTS[0] == ".zvn"
    assert ".osp" in info.ALL_PROJECT_EXTS
    assert ".flow" in info.ALL_PROJECT_EXTS
    assert "/tmp/a.zvn".endswith(info.ALL_PROJECT_EXTS)
    assert "/tmp/a.osp".endswith(info.ALL_PROJECT_EXTS)
    assert "/tmp/a.flow".endswith(info.ALL_PROJECT_EXTS)
    assert not "/tmp/a.mp4".endswith(info.ALL_PROJECT_EXTS)


def test_save_append_rule_matches_main_window():
    """Append .zvn only when path has no recognised suffix (no double extensions)."""

    def resolve_save_path(file_path: str) -> str:
        if not file_path.endswith(info.ALL_PROJECT_EXTS):
            return "%s%s" % (file_path, info.PROJECT_EXT)
        return file_path

    assert resolve_save_path("/home/user/untitled") == "/home/user/untitled.zvn"
    assert resolve_save_path("/home/user/untitled.zvn") == "/home/user/untitled.zvn"
    assert resolve_save_path("/home/user/old.osp") == "/home/user/old.osp"
    assert resolve_save_path("/home/user/old.flow") == "/home/user/old.flow"
    assert not resolve_save_path("/home/user/old.osp").endswith(".osp.zvn")


if __name__ == "__main__":
    test_canonical_ext_is_zvn_legacy_includes_osp_and_flow()
    test_save_append_rule_matches_main_window()
    print("test_project_ext: ok")
