"""Logging options shared by startup and Preferences; independent of Qt."""
# Copyright (c) 2026 OpenShot Studios, LLC
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import os
import sys

LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50, "OFF": 100}
_cli = {}
_environment = None


def level(value):
    value = value.upper()
    if value not in LEVELS:
        raise argparse.ArgumentTypeError("expected DEBUG, INFO, WARNING, ERROR, CRITICAL, or OFF")
    return value


class LevelAction(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        if self.nargs == 0:
            value = self.const
        previous = getattr(namespace, self.dest, None)
        if previous is not None and previous != value:
            parser.error("conflicting logging levels for " + option_string)
        setattr(namespace, self.dest, value)


def add_arguments(parser):
    for suffix, help_text in (("", "File and console logging level"),
                              ("-file", "File logging level"),
                              ("-console", "Console logging level")):
        parser.add_argument("--log" + suffix + "-level", type=level, action=LevelAction,
                            metavar="LEVEL", help=help_text)
    parser.add_argument("-d", "--debug", "--debug-ui", dest="debug", action="store_true",
                        help="Enable User Interface Debug Logging to file and console")
    parser.add_argument("--debug-engine", action="store_true",
                        help="Enable Video & Audio Engine Debug Logging to file and console")
    parser.add_argument("--debug-file", dest="debug_file", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--debug-console", dest="debug_console", action="store_true", help=argparse.SUPPRESS)


def configure_arguments(parser, args):
    global _cli
    _cli = {}
    for flag, enabled in (("--debug-ui/--debug", args.debug), ("--debug-engine", args.debug_engine)):
        if enabled and args.log_level not in (None, "DEBUG"):
            parser.error(flag + " conflicts with --log-level")
    for destination in ("file", "console"):
        explicit = getattr(args, "log_" + destination + "_level")
        alias = getattr(args, "debug_" + destination)
        if alias and explicit not in (None, "DEBUG"):
            parser.error("--debug-" + destination + " conflicts with --log-" + destination + "-level")
        # Explicit destination levels override the component-wide debug flags.
        native = explicit or args.log_level or ("DEBUG" if args.debug_engine else None)
        python = explicit or ("DEBUG" if alias else None) or args.log_level or ("DEBUG" if args.debug else None)
        for component, effective in (("native", native), ("python", python)):
            if effective:
                _cli[component, destination] = (effective, "command line")


def environment():
    global _environment
    if _environment is None:
        _environment = {}
        for prefix in ("OPENSHOT", "LIBOPENSHOT"):
            for suffix in ("LEVEL", "FILE_LEVEL", "CONSOLE_LEVEL"):
                key = prefix + "_LOG_" + suffix
                if key in os.environ:
                    try:
                        _environment[key] = level(os.environ[key])
                    except argparse.ArgumentTypeError:
                        print("OpenShot: ignoring invalid {}={!r}".format(key, os.environ[key]), file=sys.stderr)
        if "LIBOPENSHOT_DEBUG" in os.environ:
            _environment["LIBOPENSHOT_DEBUG"] = "DEBUG"
    return _environment


def resolve(component, destination, debug=False):
    """Return (level name, source), without modifying saved preferences."""
    if (component, destination) in _cli:
        return _cli[component, destination]
    env = environment()
    prefixes = ("LIBOPENSHOT", "OPENSHOT") if component == "native" else ("OPENSHOT",)
    for prefix in prefixes:
        for suffix in (destination.upper() + "_LEVEL", "LEVEL"):
            key = prefix + "_LOG_" + suffix
            if key in env:
                return env[key], key
    if component == "native" and destination == "console" and "LIBOPENSHOT_DEBUG" in env:
        return "DEBUG", "LIBOPENSHOT_DEBUG"
    if destination == "file":
        return ("DEBUG" if debug else "INFO"), "Preferences"
    return "INFO", "default"


def preference_description(debug=False, component="native"):
    value, source = resolve(component, "file", debug)
    if source != "Preferences":
        return "Override for this session: {} ({})".format(value, source)
    return ""
