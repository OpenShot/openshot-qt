"""Implements the 'bdist_msi' command (create Windows installer packages)."""

from __future__ import annotations

import logging
import os
import re
import shutil
from msilib import (  # pylint: disable=deprecated-module
    CAB,
    PID_AUTHOR,
    PID_COMMENTS,
    PID_KEYWORDS,
    Binary,
    Dialog,
    Directory,
    Feature,
    add_data,
    add_tables,
    gen_uuid,
    init_database,
    make_id,
    schema,
    sequence,
)
from sysconfig import get_platform
from typing import ClassVar

from setuptools import Command

from cx_Freeze._packaging import Version
from cx_Freeze.command._pydialog import PyDialog
from cx_Freeze.exception import OptionError

__all__ = ["bdist_msi"]

# force the remove existing products action to happen first since Windows
# installer appears to be braindead and doesn't handle files shared between
# different "products" very well
install_execute_sequence = sequence.InstallExecuteSequence
for index, info in enumerate(install_execute_sequence):
    if info[0] == "RemoveExistingProducts":
        install_execute_sequence[index] = (info[0], info[1], 1450)


class bdist_msi(Command):
    """Create a Microsoft Installer (.msi) binary distribution."""

    description = __doc__

    user_options: ClassVar[list[tuple[str, str | None, str]]] = [
        (
            "bdist-dir=",
            None,
            "temporary directory for creating the distribution",
        ),
        ("dist-dir=", "d", "directory to put final built distributions in"),
        (
            "install-script=",
            None,
            "basename of installation script to be run after "
            "installation or before deinstallation",
        ),
        (
            "keep-temp",
            "k",
            "keep the pseudo-installation tree around after "
            "creating the distribution archive",
        ),
        (
            "pre-install-script=",
            None,
            "Fully qualified filename of a script to be run before "
            "any files are installed.  This script need not be in the "
            "distribution",
        ),
        (
            "skip-build",
            None,
            "skip rebuilding everything (for testing/debugging)",
        ),
        # cx_Freeze specific
        ("add-to-path=", None, "add target dir to PATH environment variable"),
        ("all-users=", None, "installation for all users (or just me)"),
        (
            "data=",
            None,
            "dictionary of data indexed by table name, and each value is a "
            "tuple to include in table",
        ),
        ("directories=", None, "list of 3-tuples of directories to create"),
        ("environment-variables=", None, "list of environment variables"),
        ("extensions=", None, "Extensions for which to register Verbs"),
        ("initial-target-dir=", None, "initial target directory"),
        ("install-icon=", None, "icon path to add/remove programs "),
        ("product-code=", None, "product code to use"),
        (
            "summary-data=",
            None,
            "Dictionary of data to include in msi summary data stream. "
            'Allowed keys are "author", "comments", "keywords".',
        ),
        ("target-name=", None, "name of the file to create"),
        ("target-version=", None, "version of the file to create"),
        ("upgrade-code=", None, "upgrade code to use"),
    ]

    boolean_options: ClassVar[list[str]] = [
        "keep-temp",
        "skip-build",
    ]

    x = y = 50
    width = 370
    height = 300
    title = "[ProductName] Setup"
    modeless = 1
    modal = 3
    _binary_columns: ClassVar[dict[str, int]] = {
        "Binary": 1,
        "Icon": 1,
        "Patch": 4,
        "SFPCatalog": 1,
        "MsiDigitalCertificate": 1,
        "MsiPatchHeaders": 1,
    }

    def add_config(self) -> None:
        if self.add_to_path:
            path = "Path"
            if self.all_users:
                path = "=-*" + path
            add_data(
                self.db,
                "Environment",
                [("E_PATH", path, r"[~];[TARGETDIR]", "TARGETDIR")],
            )
        if self.directories:
            add_data(self.db, "Directory", self.directories)
        if self.environment_variables:
            add_data(self.db, "Environment", self.environment_variables)
        # This is needed in case the AlwaysInstallElevated policy is set.
        # Otherwise installation will not end up in TARGETDIR.
        add_data(
            self.db,
            "Property",
            [("SecureCustomProperties", "TARGETDIR;REINSTALLMODE")],
        )
        add_data(
            self.db,
            "CustomAction",
            [
                (
                    "A_SET_TARGET_DIR",
                    256 + 51,
                    "TARGETDIR",
                    self.initial_target_dir,
                ),
                (
                    "A_SET_REINSTALL_MODE",
                    256 + 51,
                    "REINSTALLMODE",
                    "amus",
                ),
            ],
        )
        add_data(
            self.db,
            "InstallExecuteSequence",
            [
                ("A_SET_TARGET_DIR", 'TARGETDIR=""', 401),
                ("A_SET_REINSTALL_MODE", 'REINSTALLMODE=""', 402),
            ],
        )
        add_data(
            self.db,
            "InstallUISequence",
            [
                ("PrepareDlg", None, 140),
                ("A_SET_TARGET_DIR", 'TARGETDIR=""', 401),
                ("A_SET_REINSTALL_MODE", 'REINSTALLMODE=""', 402),
                ("SelectDirectoryDlg", "not Installed", 1230),
                (
                    "MaintenanceTypeDlg",
                    "Installed and not Resume and not Preselected",
                    1250,
                ),
                ("ProgressDlg", None, 1280),
            ],
        )
        for idx, executable in enumerate(self.distribution.executables):
            if (
                executable.shortcut_name is not None
                and executable.shortcut_dir is not None
            ):
                base_name = os.path.basename(executable.target_name)
                add_data(
                    self.db,
                    "Shortcut",
                    [
                        (
                            f"S_APP_{idx}",
                            os.fspath(executable.shortcut_dir),
                            executable.shortcut_name,
                            "TARGETDIR",
                            f"[TARGETDIR]{base_name}",
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            "TARGETDIR",
                        )
                    ],
                )
        for table_name, table_data in self.data.items():
            col = self._binary_columns.get(table_name)
            if col is not None:
                data = [
                    (*row[:col], Binary(row[col]), *row[col + 1 :])
                    for row in table_data
                ]
            else:
                data = table_data
            add_data(self.db, table_name, data)

        # If provided, add data to MSI's summary information stream
        if len(self.summary_data) > 0:
            for k in self.summary_data:
                if k not in ["author", "comments", "keywords"]:
                    msg = f"Unknown key provided in summary-data: {k!r}"
                    raise OptionError(msg)

            summary_info = self.db.GetSummaryInformation(5)
            if "author" in self.summary_data:
                summary_info.SetProperty(
                    PID_AUTHOR, self.summary_data["author"]
                )
            if "comments" in self.summary_data:
                summary_info.SetProperty(
                    PID_COMMENTS, self.summary_data["comments"]
                )
            if "keywords" in self.summary_data:
                summary_info.SetProperty(
                    PID_KEYWORDS, self.summary_data["keywords"]
                )
            summary_info.Persist()

    def add_cancel_dialog(self) -> None:
        dialog = Dialog(
            self.db,
            "CancelDlg",
            50,
            10,
            260,
            85,
            3,
            self.title,
            "No",
            "No",
            "No",
        )
        dialog.text(
            "Text",
            48,
            15,
            194,
            30,
            3,
            "Are you sure you want to cancel [ProductName] installation?",
        )
        button = dialog.pushbutton("Yes", 72, 57, 56, 17, 3, "Yes", "No")
        button.event("EndDialog", "Exit")
        button = dialog.pushbutton("No", 132, 57, 56, 17, 3, "No", "Yes")
        button.event("EndDialog", "Return")

    def add_error_dialog(self) -> None:
        dialog = Dialog(
            self.db,
            "ErrorDlg",
            50,
            10,
            330,
            101,
            65543,
            self.title,
            "ErrorText",
            None,
            None,
        )
        dialog.text("ErrorText", 50, 9, 280, 48, 3, "")
        for text, pos in [
            ("No", 120),
            ("Yes", 240),
            ("Abort", 0),
            ("Cancel", 42),
            ("Ignore", 81),
            ("Ok", 159),
            ("Retry", 198),
        ]:
            button = dialog.pushbutton(text[0], pos, 72, 81, 21, 3, text, None)
            button.event("EndDialog", f"Error{text}")

    def add_exit_dialog(self) -> None:
        dialog = PyDialog(
            self.db,
            "ExitDialog",
            self.x,
            self.y,
            self.width,
            self.height,
            self.modal,
            self.title,
            "Finish",
            "Finish",
            "Finish",
        )
        dialog.title("Completing the [ProductName] installer")
        dialog.backbutton("< Back", "Finish", active=False)
        dialog.cancelbutton("Cancel", "Back", active=False)
        dialog.text(
            "Description",
            15,
            235,
            320,
            20,
            0x30003,
            "Click the Finish button to exit the installer.",
        )
        button = dialog.nextbutton("Finish", "Cancel", name="Finish")
        button.event("EndDialog", "Return")

    def add_fatal_error_dialog(self) -> None:
        dialog = PyDialog(
            self.db,
            "FatalError",
            self.x,
            self.y,
            self.width,
            self.height,
            self.modal,
            self.title,
            "Finish",
            "Finish",
            "Finish",
        )
        dialog.title("[ProductName] installer ended prematurely")
        dialog.backbutton("< Back", "Finish", active=False)
        dialog.cancelbutton("Cancel", "Back", active=False)
        dialog.text(
            "Description1",
            15,
            70,
            320,
            80,
            0x30003,
            "[ProductName] setup ended prematurely because of an error. "
            "Your system has not been modified. To install this program "
            "at a later time, please run the installation again.",
        )
        dialog.text(
            "Description2",
            15,
            155,
            320,
            20,
            0x30003,
            "Click the Finish button to exit the installer.",
        )
        button = dialog.nextbutton("Finish", "Cancel", name="Finish")
        button.event("EndDialog", "Exit")

    def add_files(self) -> None:
        database = self.db
        cab = CAB("distfiles")
        feature = Feature(
            database,
            "default",
            "Default Feature",
            "Everything",
            1,
            directory="TARGETDIR",
        )
        feature.set_current()
        rootdir = os.path.abspath(self.bdist_dir)
        root = Directory(
            database, cab, None, rootdir, "TARGETDIR", "SourceDir"
        )
        database.Commit()
        todo = [root]
        while todo:
            directory = todo.pop()
            for file in os.listdir(directory.absolute):
                sep_comp = self.separate_components.get(
                    os.path.relpath(
                        os.path.join(directory.absolute, file),
                        self.bdist_dir,
                    )
                )
                if sep_comp is not None:
                    restore_component = directory.component
                    directory.start_component(
                        component=sep_comp,
                        flags=0,
                        feature=feature,
                        keyfile=file,
                    )
                    directory.add_file(file)
                    directory.component = restore_component
                elif os.path.isdir(os.path.join(directory.absolute, file)):
                    sfile = directory.make_short(file)
                    new_dir = Directory(
                        database, cab, directory, file, file, f"{sfile}|{file}"
                    )
                    todo.append(new_dir)
                else:
                    directory.add_file(file)
        cab.commit(database)

    def add_files_in_use_dialog(self) -> None:
        dialog = PyDialog(
            self.db,
            "FilesInUse",
            self.x,
            self.y,
            self.width,
            self.height,
            19,
            self.title,
            "Retry",
            "Retry",
            "Retry",
            bitmap=False,
        )
        dialog.text(
            "Title", 15, 6, 200, 15, 0x30003, r"{\DlgFontBold8}Files in Use"
        )
        dialog.text(
            "Description",
            20,
            23,
            280,
            20,
            0x30003,
            "Some files that need to be updated are currently in use.",
        )
        dialog.text(
            "Text",
            20,
            55,
            330,
            50,
            3,
            "The following applications are using files that need to be "
            "updated by this setup. Close these applications and then "
            "click Retry to continue the installation or Cancel to exit it.",
        )
        dialog.control(
            "List",
            "ListBox",
            20,
            107,
            330,
            130,
            7,
            "FileInUseProcess",
            None,
            None,
            None,
        )
        button = dialog.backbutton("Exit", "Ignore", name="Exit")
        button.event("EndDialog", "Exit")
        button = dialog.nextbutton("Ignore", "Retry", name="Ignore")
        button.event("EndDialog", "Ignore")
        button = dialog.cancelbutton("Retry", "Exit", name="Retry")
        button.event("EndDialog", "Retry")

    def add_maintenance_type_dialog(self) -> None:
        dialog = PyDialog(
            self.db,
            "MaintenanceTypeDlg",
            self.x,
            self.y,
            self.width,
            self.height,
            self.modal,
            self.title,
            "Next",
            "Next",
            "Cancel",
        )
        dialog.title("Welcome to the [ProductName] Setup Wizard")
        dialog.text(
            "BodyText",
            15,
            63,
            330,
            42,
            3,
            "Select whether you want to repair or remove [ProductName].",
        )
        group = dialog.radiogroup(
            "RepairRadioGroup",
            15,
            108,
            330,
            60,
            3,
            "MaintenanceForm_Action",
            "",
            "Next",
        )
        group.add("Repair", 0, 18, 300, 17, "&Repair [ProductName]")
        group.add("Remove", 0, 36, 300, 17, "Re&move [ProductName]")
        dialog.backbutton("< Back", None, active=False)
        button = dialog.nextbutton("Finish", "Cancel")
        button.event(
            "[REINSTALL]", "ALL", 'MaintenanceForm_Action="Repair"', 5
        )
        button.event(
            "[Progress1]", "Repairing", 'MaintenanceForm_Action="Repair"', 6
        )
        button.event(
            "[Progress2]", "repairs", 'MaintenanceForm_Action="Repair"', 7
        )
        button.event("Reinstall", "ALL", 'MaintenanceForm_Action="Repair"', 8)
        button.event("[REMOVE]", "ALL", 'MaintenanceForm_Action="Remove"', 11)
        button.event(
            "[Progress1]", "Removing", 'MaintenanceForm_Action="Remove"', 12
        )
        button.event(
            "[Progress2]", "removes", 'MaintenanceForm_Action="Remove"', 13
        )
        button.event("Remove", "ALL", 'MaintenanceForm_Action="Remove"', 14)
        button.event(
            "EndDialog", "Return", 'MaintenanceForm_Action<>"Change"', 20
        )
        button = dialog.cancelbutton("Cancel", "RepairRadioGroup")
        button.event("SpawnDialog", "CancelDlg")

    def add_prepare_dialog(self) -> None:
        dialog = PyDialog(
            self.db,
            "PrepareDlg",
            self.x,
            self.y,
            self.width,
            self.height,
            self.modeless,
            self.title,
            "Cancel",
            "Cancel",
            "Cancel",
        )
        dialog.text(
            "Description",
            15,
            70,
            320,
            40,
            0x30003,
            "Please wait while the installer prepares to guide you through "
            "the installation.",
        )
        dialog.title("Welcome to the [ProductName] installer")
        text = dialog.text(
            "ActionText", 15, 110, 320, 20, 0x30003, "Pondering..."
        )
        text.mapping("ActionText", "Text")
        text = dialog.text("ActionData", 15, 135, 320, 30, 0x30003, None)
        text.mapping("ActionData", "Text")
        dialog.backbutton("Back", None, active=False)
        dialog.nextbutton("Next", None, active=False)
        button = dialog.cancelbutton("Cancel", None)
        button.event("SpawnDialog", "CancelDlg")

    def add_progress_dialog(self) -> None:
        dialog = PyDialog(
            self.db,
            "ProgressDlg",
            self.x,
            self.y,
            self.width,
            self.height,
            self.modeless,
            self.title,
            "Cancel",
            "Cancel",
            "Cancel",
            bitmap=False,
        )
        dialog.text(
            "Title",
            20,
            15,
            200,
            15,
            0x30003,
            r"{\DlgFontBold8}[Progress1] [ProductName]",
        )
        dialog.text(
            "Text",
            35,
            65,
            300,
            30,
            3,
            "Please wait while the installer [Progress2] [ProductName].",
        )
        dialog.text("StatusLabel", 35, 100, 35, 20, 3, "Status:")
        text = dialog.text(
            "ActionText", 70, 100, self.width - 70, 20, 3, "Pondering..."
        )
        text.mapping("ActionText", "Text")
        control = dialog.control(
            "ProgressBar",
            "ProgressBar",
            35,
            120,
            300,
            10,
            65537,
            None,
            "Progress done",
            None,
            None,
        )
        control.mapping("SetProgress", "Progress")
        dialog.backbutton("< Back", "Next", active=False)
        dialog.nextbutton("Next >", "Cancel", active=False)
        button = dialog.cancelbutton("Cancel", "Back")
        button.event("SpawnDialog", "CancelDlg")

    def add_properties(self) -> None:
        metadata = self.distribution.metadata
        props = [
            ("DistVersion", metadata.get_version()),
            ("DefaultUIFont", "DlgFont8"),
            ("ErrorDialog", "ErrorDlg"),
            ("Progress1", "Install"),
            ("Progress2", "installs"),
            ("MaintenanceForm_Action", "Repair"),
            ("ALLUSERS", "2"),
        ]

        if not self.all_users:
            props.append(("MSIINSTALLPERUSER", "1"))
        email = metadata.author_email or metadata.maintainer_email
        if email:
            props.append(("ARPCONTACT", email))
        if metadata.url:
            props.append(("ARPURLINFOABOUT", metadata.url))
        if self.upgrade_code is not None:
            if not _is_valid_guid(self.upgrade_code):
                msg = "upgrade-code must be in valid GUID format"
                raise ValueError(msg)
            props.append(("UpgradeCode", self.upgrade_code.upper()))
        if self.install_icon:
            props.append(("ARPPRODUCTICON", "InstallIcon"))
        add_data(self.db, "Property", props)
        if self.install_icon:
            add_data(
                self.db,
                "Icon",
                [("InstallIcon", Binary(self.install_icon))],
            )

    def add_select_directory_dialog(self) -> None:
        dialog = PyDialog(
            self.db,
            "SelectDirectoryDlg",
            self.x,
            self.y,
            self.width,
            self.height,
            self.modal,
            self.title,
            "Next",
            "Next",
            "Cancel",
        )
        dialog.title("Select destination directory")
        dialog.backbutton("< Back", None, active=False)
        button = dialog.nextbutton("Next >", "Cancel")
        button.event("SetTargetPath", "TARGETDIR", ordering=1)
        button.event("SpawnWaitDialog", "WaitForCostingDlg", ordering=2)
        button.event("EndDialog", "Return", ordering=3)
        button = dialog.cancelbutton("Cancel", "DirectoryCombo")
        button.event("SpawnDialog", "CancelDlg")
        dialog.control(
            "DirectoryCombo",
            "DirectoryCombo",
            15,
            70,
            272,
            80,
            393219,
            "TARGETDIR",
            None,
            "DirectoryList",
            None,
        )
        dialog.control(
            "DirectoryList",
            "DirectoryList",
            15,
            90,
            308,
            136,
            3,
            "TARGETDIR",
            None,
            "PathEdit",
            None,
        )
        dialog.control(
            "PathEdit",
            "PathEdit",
            15,
            230,
            306,
            16,
            3,
            "TARGETDIR",
            None,
            "Next",
            None,
        )
        button = dialog.pushbutton("Up", 306, 70, 18, 18, 3, "Up", None)
        button.event("DirectoryListUp", "0")
        button = dialog.pushbutton("NewDir", 324, 70, 30, 18, 3, "New", None)
        button.event("DirectoryListNew", "0")

    def add_text_styles(self) -> None:
        add_data(
            self.db,
            "TextStyle",
            [
                ("DlgFont8", "Tahoma", 9, None, 0),
                ("DlgFontBold8", "Tahoma", 8, None, 1),
                ("VerdanaBold10", "Verdana", 10, None, 1),
                ("VerdanaRed9", "Verdana", 9, 255, 0),
            ],
        )

    def add_ui(self) -> None:
        self.add_text_styles()
        self.add_error_dialog()
        self.add_fatal_error_dialog()
        self.add_cancel_dialog()
        self.add_exit_dialog()
        self.add_user_exit_dialog()
        self.add_files_in_use_dialog()
        self.add_wait_for_costing_dialog()
        self.add_prepare_dialog()
        self.add_select_directory_dialog()
        self.add_progress_dialog()
        self.add_maintenance_type_dialog()

    def add_upgrade_config(self, sversion) -> None:
        if self.upgrade_code is not None:
            add_data(
                self.db,
                "Upgrade",
                [
                    (
                        self.upgrade_code,
                        None,
                        sversion,
                        None,
                        513,
                        None,
                        "REMOVEOLDVERSION",
                    ),
                    (
                        self.upgrade_code,
                        sversion,
                        None,
                        None,
                        257,
                        None,
                        "REMOVENEWVERSION",
                    ),
                ],
            )

    def add_user_exit_dialog(self) -> None:
        dialog = PyDialog(
            self.db,
            "UserExit",
            self.x,
            self.y,
            self.width,
            self.height,
            self.modal,
            self.title,
            "Finish",
            "Finish",
            "Finish",
        )
        dialog.title("[ProductName] installer was interrupted")
        dialog.backbutton("< Back", "Finish", active=False)
        dialog.cancelbutton("Cancel", "Back", active=False)
        dialog.text(
            "Description1",
            15,
            70,
            320,
            80,
            0x30003,
            "[ProductName] setup was interrupted. Your system has not "
            "been modified. To install this program at a later time, "
            "please run the installation again.",
        )
        dialog.text(
            "Description2",
            15,
            155,
            320,
            20,
            0x30003,
            "Click the Finish button to exit the installer.",
        )
        button = dialog.nextbutton("Finish", "Cancel", name="Finish")
        button.event("EndDialog", "Exit")

    def add_wait_for_costing_dialog(self) -> None:
        dialog = Dialog(
            self.db,
            "WaitForCostingDlg",
            50,
            10,
            260,
            85,
            self.modal,
            self.title,
            "Return",
            "Return",
            "Return",
        )
        dialog.text(
            "Text",
            48,
            15,
            194,
            30,
            3,
            "Please wait while the installer finishes determining your "
            "disk space requirements.",
        )
        button = dialog.pushbutton(
            "Return", 102, 57, 56, 17, 3, "Return", None
        )
        button.event("EndDialog", "Exit")

    def _append_to_data(self, table, *line) -> None:
        rows = self.data.setdefault(table, [])
        line = tuple(line)
        if line not in rows:
            rows.append(line)

    def initialize_options(self) -> None:
        self.bdist_dir = None
        self.keep_temp = 0
        self.dist_dir = None
        self.skip_build = None
        self.install_script = None
        self.pre_install_script = None
        # cx_Freeze specific
        self.upgrade_code = None
        self.product_code = None
        self.add_to_path = None
        self.initial_target_dir = None
        self.target_name = None
        self.target_version = None
        self.fullname = None
        self.directories = None
        self.environment_variables = None
        self.data = None
        self.summary_data = None
        self.install_icon = None
        self.all_users = False
        self.extensions = None

    def finalize_options(self) -> None:
        self.set_undefined_options("bdist", ("skip_build", "skip_build"))

        if self.bdist_dir is None:
            bdist_base = self.get_finalized_command("bdist").bdist_base
            self.bdist_dir = os.path.join(bdist_base, "msi")

        self.set_undefined_options("bdist", ("dist_dir", "dist_dir"))

        if self.pre_install_script:
            msg = "the pre-install-script feature is not yet implemented"
            raise OptionError(msg)

        if self.install_script:
            for script in self.distribution.scripts:
                if self.install_script == os.path.basename(script):
                    break
            else:
                msg = (
                    f"install_script '{self.install_script}' not found in "
                    "scripts"
                )
                raise OptionError(msg)
        self.install_script_key = None

        # cx_Freeze specific
        if self.target_name is None:
            self.target_name = self.distribution.get_name()
        if self.target_version is None and self.distribution.metadata.version:
            self.target_version = self.distribution.metadata.version
        name = self.target_name
        version = self.target_version or self.distribution.get_version()
        self.fullname = f"{name}-{version}"
        platform = get_platform().replace("win-amd64", "win64")
        if self.initial_target_dir is None:
            if platform == "win64" or platform.startswith("mingw_x86_64"):
                program_files_folder = "ProgramFiles64Folder"
            else:
                program_files_folder = "ProgramFilesFolder"
            self.initial_target_dir = rf"[{program_files_folder}]\{name}"
        if self.add_to_path is None:
            self.add_to_path = False
        if self.directories is None:
            self.directories = []
        if self.environment_variables is None:
            self.environment_variables = []
        if self.data is None:
            self.data = {}
        if not isinstance(self.summary_data, dict):
            self.summary_data = {}
        self.separate_components = {}
        for idx, executable in enumerate(self.distribution.executables):
            base_name = os.path.basename(executable.target_name)
            # Trying to make these names unique from any directory name
            self.separate_components[base_name] = make_id(
                f"_cx_executable{idx}_{executable}"
            )
        if self.extensions is None:
            self.extensions = []
        for extension in self.extensions:
            try:
                ext = extension["extension"]
                verb = extension["verb"]
                executable = extension["executable"]
            except KeyError:
                msg = (
                    "Each extension must have at least extension, verb, "
                    "and executable"
                )
                raise ValueError(msg) from None
            try:
                component = self.separate_components[executable]
            except KeyError:
                msg = (
                    "Executable must be the base target name of one of the "
                    "distribution's executables"
                )
                raise ValueError(msg) from None
            stem = os.path.splitext(executable)[0]
            progid = make_id(f"{name}.{stem}.{version}")
            mime = extension.get("mime", None)
            # "%1" a better default for argument?
            argument = extension.get("argument", None)
            context = extension.get("context", f"{self.fullname} {verb}")
            # Add rows via self.data to safely ignore duplicates
            self._append_to_data(
                "ProgId",
                progid,
                None,
                None,
                self.distribution.get_description() or "UNKNOWN",
                None,
                None,
            )
            self._append_to_data(
                "Extension", ext, component, progid, mime, "default"
            )
            self._append_to_data("Verb", ext, verb, 0, context, argument)
            if mime is not None:
                self._append_to_data("MIME", mime, ext, "None")
            # Registry entries that allow proper display of the app in menu
            self._append_to_data(
                "Registry",
                f"{progid}-name",
                -1,
                rf"Software\Classes\{progid}",
                "FriendlyAppName",
                name,
                component,
            )
            self._append_to_data(
                "Registry",
                f"{progid}-verb-{verb}",
                -1,
                rf"Software\Classes\{progid}\shell\{verb}",
                "FriendlyAppName",
                name,
                component,
            )
            self._append_to_data(
                "Registry",
                f"{progid}-author",
                -1,
                rf"Software\Classes\{progid}\Application",
                "ApplicationCompany",
                self.distribution.get_author() or "UNKNOWN",
                component,
            )

    def run(self) -> None:
        if not self.skip_build:
            self.run_command("build")

        # install everything from build directory in a new prefix
        install_dir = self.bdist_dir
        install = self.reinitialize_command("install", reinit_subcommands=1)
        install.prefix = install_dir
        install.skip_build = self.skip_build
        install.warn_dir = 0
        logging.info("installing to %s", install_dir)
        install.ensure_finalized()
        install.run()

        # make msi (by default in dist directory)
        self.mkpath(self.dist_dir)
        platform = get_platform().replace("win-amd64", "win64")

        msi_name: str
        if os.path.splitext(self.target_name)[1].lower() == ".msi":
            msi_name = self.target_name
        elif self.target_version:
            msi_name = f"{self.fullname}-{platform}.msi"
        else:
            msi_name = f"{self.target_name}-{platform}.msi"
        installer_name = os.path.join(self.dist_dir, msi_name)
        installer_name = os.path.abspath(installer_name)
        if os.path.exists(installer_name):
            os.unlink(installer_name)

        author = self.distribution.metadata.get_contact() or "UNKNOWN"
        version = self.target_version or self.distribution.get_version()
        # ProductVersion must be strictly numeric
        base_version = Version(version).base_version

        # msilib is reloaded in order to reset the "_directories" global member
        # in that module.  That member is used by msilib to prevent any two
        # directories from having the same logical name.  _directories might
        # already have contents due to msilib having been previously used in
        # the current instance of the python interpreter -- if so, it could
        # prevent the root from getting the logical name TARGETDIR, breaking
        # the MSI.
        # importlib.reload(msilib)

        if self.product_code is None:
            self.product_code = gen_uuid()
        self.db = init_database(
            installer_name,
            schema,
            self.target_name,
            self.product_code,
            base_version,
            author,
        )
        add_tables(self.db, sequence)
        self.add_properties()
        self.add_config()
        self.add_upgrade_config(base_version)
        self.add_ui()
        self.add_files()
        self.db.Commit()
        self.distribution.dist_files.append(
            ("bdist_msi", base_version or "any", self.target_name)
        )

        if not self.keep_temp:
            logging.info(
                "removing '%s' (and everything under it)", install_dir
            )
            if not self.dry_run:
                try:
                    shutil.rmtree(install_dir)
                except OSError as exc:
                    logging.warning("error removing %s: %s", install_dir, exc)

        # Cause the MSI file to be released. Without this, then if bdist_msi
        # is run programmatically from within a larger script, subsequent
        # editting of the MSI is blocked.
        self.db = None


def _is_valid_guid(code) -> bool:
    pattern = re.compile(
        r"^\{[0-9A-F]{8}-([0-9A-F]{4}-){3}[0-9A-F]{12}\}$", re.IGNORECASE
    )
    return isinstance(code, str) and pattern.match(code) is not None
