# SPDX-FileCopyrightText: 2026 OpenShot Studios, LLC
# SPDX-License-Identifier: LGPL-3.0-or-later

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from xml.etree import ElementTree


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "installer" / "package_msix.ps1"
BUILD_DIR = REPO_ROOT / "build"
MSIX_DIR = BUILD_DIR / "msix"
FIXTURE_DIR = BUILD_DIR / "test-package-msix-staging"
INSTALLER_PATH = FIXTURE_DIR / "OpenShot-msix-staging-arm64.exe"
TEMPLATE_PATH = FIXTURE_DIR / "OpenShot_template.xml"
REPORT_PATH = MSIX_DIR / "prepare-report.json"
WORKING_TEMPLATE_PATH = MSIX_DIR / "OpenShot_template.generated.xml"
STAGED_INSTALLER_PATH = MSIX_DIR / "installer-source" / INSTALLER_PATH.name
VERSION_FILE = BUILD_DIR / "install-arm64" / "share" / "openshot-qt.env"
INSTALL_ARM64_DIR = BUILD_DIR / "install-arm64"


def remove_path(path):
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink()


# Exact set of paths this suite creates/manages. setUp and tearDown must only
# ever touch these paths so that unrelated, pre-existing files under
# build/msix (for example real packaging outputs dropped there by a prior,
# non-test packaging run) are never destroyed. Do not recursively wipe
# MSIX_DIR itself: only remove it afterwards if it happens to be empty.
OWNED_PATHS = (
    REPORT_PATH,
    WORKING_TEMPLATE_PATH,
    STAGED_INSTALLER_PATH,
    MSIX_DIR / "installer-source",
    MSIX_DIR / "old-package.msix",
    MSIX_DIR / "msix-packaging-tool.log",
    FIXTURE_DIR,
    VERSION_FILE,
)


class PackageMsixStagingTests(unittest.TestCase):
    def setUp(self):
        for path in OWNED_PATHS:
            remove_path(path)

        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        MSIX_DIR.mkdir(parents=True, exist_ok=True)
        VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        VERSION_FILE.write_text("VERSION:4.0.0\n", encoding="utf-8")

    def tearDown(self):
        for path in OWNED_PATHS:
            remove_path(path)
        # VERSION_FILE lives under build/install-arm64/share/. That directory
        # can also hold a real, non-test installed payload (from `cmake
        # --install`), so never rmtree it wholesale -- only remove the
        # now-empty directories this suite itself created.
        if VERSION_FILE.parent.exists() and not any(VERSION_FILE.parent.iterdir()):
            VERSION_FILE.parent.rmdir()
        if INSTALL_ARM64_DIR.exists() and not any(INSTALL_ARM64_DIR.iterdir()):
            INSTALL_ARM64_DIR.rmdir()
        if MSIX_DIR.exists() and not any(MSIX_DIR.iterdir()):
            MSIX_DIR.rmdir()
        if BUILD_DIR.exists() and not any(BUILD_DIR.iterdir()):
            BUILD_DIR.rmdir()

    def test_prepare_only_preserves_existing_packaging_outputs_and_refreshes_owned_staging(self):
        INSTALLER_PATH.write_bytes(b"fresh-arm64-installer")
        TEMPLATE_PATH.write_text(
            "\n".join(
                [
                    "<MsixPackagingToolTemplate>",
                    '  <SaveLocation PackagePath="C:\\OpenShot-MSIX\\OpenShot.msix" TemplatePath="C:\\OpenShot-MSIX\\OpenShot-template.xml" />',
                    '  <Installer Path="C:\\OpenShot-MSIX\\source\\OpenShot-original-arm64.exe" Arguments="/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-" InstallLocation="C:\\Program Files\\OpenShot Video Editor" />',
                    '  <PackageInformation PackageName="Old.Name" PublisherName="CN=Old Publisher" PublisherDisplayName="Old Publisher" Version="1.0.0.0">',
                    "    <Applications />",
                    "  </PackageInformation>",
                    "</MsixPackagingToolTemplate>",
                ]
            ),
            encoding="utf-8",
        )

        stale_msix = MSIX_DIR / "old-package.msix"
        stale_msix.write_bytes(b"stale-msix")
        stale_log = MSIX_DIR / "msix-packaging-tool.log"
        stale_log.write_text("stale-log", encoding="utf-8")
        stale_report = REPORT_PATH
        stale_report.write_text('{"stale": true}', encoding="utf-8")
        stale_working_template = WORKING_TEMPLATE_PATH
        stale_working_template.write_text("stale-template", encoding="utf-8")
        stale_source_dir = MSIX_DIR / "installer-source"
        stale_source_dir.mkdir(parents=True, exist_ok=True)
        (stale_source_dir / "stale.txt").write_text("stale", encoding="utf-8")
        (stale_source_dir / INSTALLER_PATH.name).write_bytes(b"old-installer")

        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT_PATH),
                "-Architecture",
                "arm64",
                "-InstallerPath",
                str(INSTALLER_PATH),
                "-TemplatePath",
                str(TEMPLATE_PATH),
                "-PrepareOnly",
                "-PreparationReportPath",
                str(REPORT_PATH),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )

        self.assertTrue(stale_msix.exists())
        self.assertEqual(stale_msix.read_bytes(), b"stale-msix")
        self.assertTrue(stale_log.exists())
        self.assertEqual(stale_log.read_text(encoding="utf-8"), "stale-log")
        self.assertFalse((stale_source_dir / "stale.txt").exists())

        self.assertTrue(STAGED_INSTALLER_PATH.exists())
        self.assertEqual(STAGED_INSTALLER_PATH.read_bytes(), INSTALLER_PATH.read_bytes())

        self.assertTrue(REPORT_PATH.exists())
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8-sig"))
        self.assertNotEqual(REPORT_PATH.read_text(encoding="utf-8-sig"), '{"stale": true}')
        self.assertEqual(report["output_dir"], str(MSIX_DIR))
        self.assertEqual(report["source_installer_dir"], str(MSIX_DIR / "installer-source"))
        self.assertEqual(report["source_installer_path"], str(STAGED_INSTALLER_PATH))
        self.assertEqual(report["working_template_path"], str(WORKING_TEMPLATE_PATH))
        self.assertEqual(report["processor_architecture"], "arm64")
        self.assertEqual(report["publisher"], "CN=5FE34B8B-A62B-4594-911F-0D6CFC87D00F")
        self.assertEqual(report["publisher_display_name"], "OpenShot Studios")

        self.assertTrue(WORKING_TEMPLATE_PATH.exists())
        working_template = WORKING_TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertNotEqual(working_template, "stale-template")
        self.assertIn(str(STAGED_INSTALLER_PATH), working_template)
        self.assertNotIn(r"C:\OpenShot-MSIX\source\OpenShot-original-arm64.exe", working_template)
        template_xml = ElementTree.fromstring(working_template)
        package_info = template_xml.find(".//PackageInformation")
        self.assertEqual(package_info.attrib["Version"], "4.0.0.0")
        self.assertEqual(package_info.attrib["PackageName"], "OpenShotStudios.OpenShotforWindows")
        self.assertEqual(
            package_info.attrib["PublisherName"],
            "CN=5FE34B8B-A62B-4594-911F-0D6CFC87D00F",
        )
        self.assertEqual(package_info.attrib["PublisherDisplayName"], "OpenShot Studios")

    def test_teardown_preserves_unrelated_preexisting_build_msix_output(self):
        """Regression for OSQT-MSIX-TEARDOWN-001.

        tearDown() must remove only the exact paths this suite owns
        (OWNED_PATHS, plus VERSION_FILE's now-empty parent directories) and
        must never recursively delete build/msix or build/install-arm64
        wholesale, because a real (non-test) packaging/install run can leave
        genuine artifacts in either directory. This proves sentinel files
        that setUp/tearDown do not own survive a full tearDown() pass, while
        owned fixture paths are still cleaned up.
        """
        sentinel_path = MSIX_DIR / "sentinel-real-packaging-output.msix"
        sentinel_path.write_bytes(b"real-signed-msix-package-not-owned-by-tests")

        unrelated_subdir = MSIX_DIR / "unrelated-real-output"
        unrelated_subdir.mkdir(parents=True, exist_ok=True)
        (unrelated_subdir / "notes.txt").write_text("not owned by tests", encoding="utf-8")

        owned_source_dir = MSIX_DIR / "installer-source"
        owned_source_dir.mkdir(parents=True, exist_ok=True)
        (owned_source_dir / "owned.txt").write_text("owned", encoding="utf-8")
        REPORT_PATH.write_text('{"owned": true}', encoding="utf-8")

        # Use a test-unique filename (never the real production binary name)
        # so this fixture cannot collide with, and overwrite, a genuine
        # installed openshot-qt.exe.
        install_sentinel = (
            INSTALL_ARM64_DIR / "bin" / "unrelated-real-preexisting-payload.bin"
        )
        install_sentinel.parent.mkdir(parents=True, exist_ok=True)
        install_sentinel.write_bytes(b"real-installed-arm64-binary-not-owned-by-tests")

        real_payload = (
            INSTALL_ARM64_DIR / "lib" / "unrelated-real-preexisting-lib-fixture.bin"
        )
        real_payload.parent.mkdir(parents=True, exist_ok=True)
        real_payload.write_bytes(b"real-preexisting-lib-payload-not-owned-by-tests")

        try:
            self.tearDown()

            self.assertTrue(
                sentinel_path.exists(),
                "tearDown must not delete unrelated pre-existing build/msix output",
            )
            self.assertEqual(
                sentinel_path.read_bytes(),
                b"real-signed-msix-package-not-owned-by-tests",
            )
            self.assertTrue(unrelated_subdir.exists())
            self.assertTrue((unrelated_subdir / "notes.txt").exists())

            self.assertTrue(
                install_sentinel.exists(),
                "tearDown must not delete unrelated pre-existing build/install-arm64 output",
            )
            self.assertEqual(
                install_sentinel.read_bytes(),
                b"real-installed-arm64-binary-not-owned-by-tests",
            )
            self.assertTrue(
                real_payload.exists(),
                "tearDown must not delete unrelated pre-existing build/install-arm64 payload",
            )
            self.assertEqual(
                real_payload.read_bytes(),
                b"real-preexisting-lib-payload-not-owned-by-tests",
            )

            self.assertFalse(owned_source_dir.exists())
            self.assertFalse(REPORT_PATH.exists())
            self.assertFalse(VERSION_FILE.exists())
        finally:
            # Remove only the exact fixture paths this test itself created;
            # never recursively delete INSTALL_ARM64_DIR, which may still
            # hold the unrelated real payload this test just proved survives.
            remove_path(sentinel_path)
            remove_path(unrelated_subdir)
            remove_path(install_sentinel)
            if install_sentinel.parent.exists() and not any(install_sentinel.parent.iterdir()):
                install_sentinel.parent.rmdir()
            remove_path(real_payload)
            if real_payload.parent.exists() and not any(real_payload.parent.iterdir()):
                real_payload.parent.rmdir()
            if INSTALL_ARM64_DIR.exists() and not any(INSTALL_ARM64_DIR.iterdir()):
                INSTALL_ARM64_DIR.rmdir()
            # Restore MSIX_DIR so the outer, real tearDown() (invoked again by
            # the test runner after this method returns) has a directory to
            # operate on, matching the fixture state other tests expect.
            MSIX_DIR.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    unittest.main()
