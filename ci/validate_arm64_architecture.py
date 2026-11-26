#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 OpenShot Studios, LLC
# SPDX-License-Identifier: LGPL-3.0-or-later

"""
@file
@brief Reusable Windows Arm64 architecture validator (design-spec.md
       G2/G3/G8/G11) implementing design-amendment-A1 native-process
       semantics.

This script is shared, byte-for-byte, across libopenshot-audio (PR A),
libopenshot (PR B), and openshot-qt (PR C). It performs two independent
checks, exactly as required by design-amendment-A1:

1. Native-process oracle (host evidence): calls IsWow64Process2 via ctypes on
   the *currently running* Python process and asserts
     - pNativeMachine == IMAGE_FILE_MACHINE_ARM64 (0xAA64)
     - pProcessMachine == IMAGE_FILE_MACHINE_UNKNOWN (0x0)
   Any nonzero pProcessMachine is WOW/emulated execution and fails this
   check. This check only passes evidence when actually run under a native
   Arm64 Python interpreter; on any other host it reports the real, honest
   values it observed and does not fabricate a pass.

2. Recursive static PE architecture scan (payload evidence): recursively
   scans a given root directory for every .exe, .dll, and .pyd, reads the
   COFF file header "Machine" field directly (no external tool dependency),
   and asserts every one of them is IMAGE_FILE_MACHINE_ARM64 (0xAA64). This
   check is independent of the host architecture and can run on any Python
   3 interpreter, including this AMD64 documentation/implementation
   workspace, against whatever candidate payload directory is supplied.

The two checks are deliberately independent, per design-amendment-A1: a
native process oracle failure does not imply a payload architecture
failure, and vice versa. Callers (CI jobs) should run both and fail closed
if either reports a problem, unless the repository/job intentionally only
has one kind of evidence available (e.g. no payload directory yet).
"""

import argparse
import ctypes
import json
import os
import re
import subprocess
import struct
import sys

IMAGE_FILE_MACHINE_UNKNOWN = 0x0
IMAGE_FILE_MACHINE_ARM64 = 0xAA64
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_FILE_MACHINE_I386 = 0x14C

MACHINE_NAMES = {
    IMAGE_FILE_MACHINE_UNKNOWN: "UNKNOWN (native, non-WOW64)",
    IMAGE_FILE_MACHINE_ARM64: "ARM64",
    IMAGE_FILE_MACHINE_AMD64: "AMD64",
    IMAGE_FILE_MACHINE_I386: "I386",
}


def machine_name(value):
    return MACHINE_NAMES.get(value, "0x%04X" % value)


def read_native_process_oracle():
    """
    Query IsWow64Process2 for the current process. Returns a dict with the
    exact observed pProcessMachine / pNativeMachine values, the derived
    WOW/emulation state, and a pass/fail verdict against
    design-amendment-A1's native-execution requirement.
    """
    result = {
        "checked": False,
        "process_machine": None,
        "native_machine": None,
        "is_wow_or_emulated": None,
        "native_arm64_ok": False,
        "reason": None,
    }

    if not sys.platform.startswith("win"):
        result["reason"] = "IsWow64Process2 is a Windows-only API; not running on Windows."
        return result

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        is_wow64_process2 = getattr(kernel32, "IsWow64Process2", None)
        if is_wow64_process2 is None:
            result["reason"] = "IsWow64Process2 is unavailable on this Windows system."
            return result
        is_wow64_process2.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ushort),
            ctypes.POINTER(ctypes.c_ushort),
        ]
        is_wow64_process2.restype = ctypes.c_int
        process_machine = ctypes.c_ushort(0)
        native_machine = ctypes.c_ushort(0)
        handle = kernel32.GetCurrentProcess()
        ok = is_wow64_process2(
            handle,
            ctypes.byref(process_machine),
            ctypes.byref(native_machine),
        )
        if not ok:
            result["reason"] = (
                "IsWow64Process2 returned failure (GetLastError=%s)."
                % ctypes.get_last_error()
            )
            return result

        result["checked"] = True
        result["process_machine"] = process_machine.value
        result["native_machine"] = native_machine.value
        result["is_wow_or_emulated"] = process_machine.value != IMAGE_FILE_MACHINE_UNKNOWN
        result["native_arm64_ok"] = (
            native_machine.value == IMAGE_FILE_MACHINE_ARM64
            and process_machine.value == IMAGE_FILE_MACHINE_UNKNOWN
        )
        return result
    except Exception as exc:  # noqa: BLE001 - report, don't hide
        result["reason"] = "IsWow64Process2 call failed: %r" % exc
        return result


def read_pe_machine(path):
    """
    Read the COFF "Machine" field directly from a PE file's file header,
    without requiring llvm-readobj/dumpbin/objdump. Returns an int machine
    value, or None if the file is not a valid PE (e.g. a script stub).
    """
    with open(path, "rb") as f:
        dos_header = f.read(64)
        if len(dos_header) < 64 or dos_header[0:2] != b"MZ":
            return None
        pe_offset = struct.unpack_from("<I", dos_header, 0x3C)[0]
        f.seek(pe_offset)
        pe_sig = f.read(4)
        if pe_sig != b"PE\x00\x00":
            return None
        coff_header = f.read(20)
        if len(coff_header) < 20:
            return None
        machine = struct.unpack_from("<H", coff_header, 0)[0]
        return machine


def scan_payload_architecture(root):
    """
    Recursively scan `root` for .exe/.dll/.pyd files and read each PE
    Machine field. Returns (results, failures) where results is a list of
    {"path", "machine", "machine_name"} and failures is a list of
    human-readable problem strings (missing PE header, wrong architecture).
    """
    results = []
    failures = []
    if not os.path.isdir(root):
        failures.append("Payload root does not exist: %s" % root)
        return results, failures

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for filename in sorted(filenames):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in (".exe", ".dll", ".pyd"):
                continue
            full_path = os.path.join(dirpath, filename)
            try:
                machine = read_pe_machine(full_path)
            except OSError as exc:
                failures.append("Could not read %s: %s" % (full_path, exc))
                continue

            if machine is None:
                failures.append("Not a valid PE file (no MZ/PE header): %s" % full_path)
                continue

            results.append({
                "path": full_path,
                "machine": machine,
                "machine_name": machine_name(machine),
            })
            if machine != IMAGE_FILE_MACHINE_ARM64:
                failures.append(
                    "Wrong architecture %s (expected ARM64/0xAA64): %s"
                    % (machine_name(machine), full_path)
                )

    return results, failures


def verify_package_lock(path):
    failures = []
    verified = []
    try:
        with open(path, encoding="utf-8") as stream:
            entries = [
                line.strip()
                for line in stream
                if line.strip() and not line.lstrip().startswith("#")
            ]
    except OSError as exc:
        return verified, ["Unable to read package lock %s: %s" % (path, exc)]
    for entry in entries:
        if "=" not in entry or "," not in entry.split("=", 1)[1]:
            failures.append("Malformed package lock entry: %s" % entry)
            continue
        package, remainder = entry.split("=", 1)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9@._+:-]*", package):
            failures.append("Invalid package name in lock: %r" % package)
            continue
        expected_version, expected_sha256 = (
            value.strip() for value in remainder.split(",", 1)
        )
        if expected_sha256 != "UNVERIFIED-NO-SIGNED-SNAPSHOT":
            failures.append(
                "Package archive hash verification is not implemented for %s: %s"
                % (package, expected_sha256)
            )
        try:
            completed = subprocess.run(
                ["pacman", "-Q", "--", package],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            failures.append("Unable to run pacman for %s: %s" % (package, exc))
            continue
        if completed.returncode != 0:
            failures.append("Package not installed: %s" % package)
            continue
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        fields = lines[0].split() if lines else []
        if len(fields) != 2 or fields[0] != package:
            failures.append(
                "Unexpected pacman output for %s: %r" % (package, completed.stdout)
            )
            continue
        actual_version = fields[1]
        verified.append({
            "package": package,
            "version": actual_version,
            "expected_version": expected_version,
            "expected_sha256": expected_sha256,
        })
        if actual_version != expected_version:
            failures.append(
                "Wrong package version for %s: %s (expected %s)"
                % (package, actual_version, expected_version)
            )
    return verified, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--payload-root",
        default=None,
        help="Directory to recursively scan for .exe/.dll/.pyd PE architecture. "
             "If omitted, only the native-process oracle check runs.",
    )
    parser.add_argument(
        "--require-payload",
        action="store_true",
        help="Fail if --payload-root is omitted or contains no valid PE candidate files.",
    )
    parser.add_argument(
        "--require-native-arm64",
        action="store_true",
        help="Fail unless the current process is running natively on Windows Arm64.",
    )
    parser.add_argument(
        "--json-report",
        default=None,
        help="Optional path to write the full machine-readable report.",
    )
    parser.add_argument(
        "--package-lock",
        default=None,
        help="Verify installed pacman package versions against this lock file.",
    )
    args = parser.parse_args()

    oracle = read_native_process_oracle()

    payload_results = []
    payload_failures = []
    if args.payload_root:
        payload_results, payload_failures = scan_payload_architecture(args.payload_root)
        if args.require_payload and not payload_results:
            payload_failures.append(
                "No valid PE .exe/.dll/.pyd files were scanned under: %s" % args.payload_root
            )
    elif args.require_payload:
        payload_failures.append("--require-payload was set but --payload-root was not provided.")

    package_results = []
    package_failures = []
    if args.package_lock:
        package_results, package_failures = verify_package_lock(args.package_lock)

    report = {
        "contract": "windows-arm64-clangarm64-v1",
        "amendment": "A1",
        "native_process_oracle": oracle,
        "native_process_required": args.require_native_arm64,
        "payload_root": args.payload_root,
        "payload_files_scanned": len(payload_results),
        "payload_failures": payload_failures,
        "payload_results": payload_results,
        "package_lock": args.package_lock,
        "package_results": package_results,
        "package_failures": package_failures,
    }

    print("== Native Arm64 process oracle (design-amendment-A1) ==")
    if oracle["checked"]:
        print("  process_machine = %s" % machine_name(oracle["process_machine"]))
        print("  native_machine  = %s" % machine_name(oracle["native_machine"]))
        print("  wow/emulated    = %s" % oracle["is_wow_or_emulated"])
        print("  native ARM64 ok = %s" % oracle["native_arm64_ok"])
    else:
        print("  NOT AVAILABLE: %s" % oracle["reason"])

    print("== Recursive payload PE architecture scan ==")
    if args.payload_root:
        print("  root = %s" % args.payload_root)
        print("  files scanned = %d" % len(payload_results))
        for failure in payload_failures:
            print("  FAIL: %s" % failure)
    else:
        print("  SKIPPED: no --payload-root supplied")

    print("== MSYS2 package lock ==")
    if args.package_lock:
        print("  lock = %s" % args.package_lock)
        print("  packages verified = %d" % len(package_results))
        for failure in package_failures:
            print("  FAIL: %s" % failure)
    else:
        print("  SKIPPED: no --package-lock supplied")

    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    if args.require_native_arm64 and not oracle["native_arm64_ok"]:
        reason = oracle["reason"] or (
            "observed process_machine=%s, native_machine=%s"
            % (
                machine_name(oracle["process_machine"]),
                machine_name(oracle["native_machine"]),
            )
        )
        print("RESULT: FAIL (native Windows Arm64 process required: %s)" % reason)
        return 1

    if payload_failures:
        print("RESULT: FAIL (%d payload architecture problem(s))" % len(payload_failures))
        return 1
    if package_failures:
        print("RESULT: FAIL (%d package lock problem(s))" % len(package_failures))
        return 1

    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
