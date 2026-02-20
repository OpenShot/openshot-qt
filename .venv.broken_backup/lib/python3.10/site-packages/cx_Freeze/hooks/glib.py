"""A collection of functions which are triggered automatically by finder when
glib package is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.module import Module


def load_glib(_, module: Module) -> None:
    """Ignore globals that are imported."""
    module.global_names.update(
        [
            "GError",
            "IOChannel",
            "IO_ERR",
            "IO_FLAG_APPEND",
            "IO_FLAG_GET_MASK",
            "IO_FLAG_IS_READABLE",
            "IO_FLAG_IS_SEEKABLE",
            "IO_FLAG_IS_WRITEABLE",
            "IO_FLAG_MASK",
            "IO_FLAG_NONBLOCK",
            "IO_FLAG_SET_MASK",
            "IO_HUP",
            "IO_IN",
            "IO_NVAL",
            "IO_OUT",
            "IO_PRI",
            "IO_STATUS_AGAIN",
            "IO_STATUS_EOF",
            "IO_STATUS_ERROR",
            "IO_STATUS_NORMAL",
            "Idle",
            "MainContext",
            "MainLoop",
            "OPTION_ERROR",
            "OPTION_ERROR_BAD_VALUE",
            "OPTION_ERROR_FAILED",
            "OPTION_ERROR_UNKNOWN_OPTION",
            "OPTION_FLAG_FILENAME",
            "OPTION_FLAG_HIDDEN",
            "OPTION_FLAG_IN_MAIN",
            "OPTION_FLAG_NOALIAS",
            "OPTION_FLAG_NO_ARG",
            "OPTION_FLAG_OPTIONAL_ARG",
            "OPTION_FLAG_REVERSE",
            "OPTION_REMAINING",
            "OptionContext",
            "OptionGroup",
            "PRIORITY_DEFAULT",
            "PRIORITY_DEFAULT_IDLE",
            "PRIORITY_HIGH",
            "PRIORITY_HIGH_IDLE",
            "PRIORITY_LOW",
            "Pid",
            "PollFD",
            "SPAWN_CHILD_INHERITS_STDIN",
            "SPAWN_DO_NOT_REAP_CHILD",
            "SPAWN_FILE_AND_ARGV_ZERO",
            "SPAWN_LEAVE_DESCRIPTORS_OPEN",
            "SPAWN_SEARCH_PATH",
            "SPAWN_STDERR_TO_DEV_NULL",
            "SPAWN_STDOUT_TO_DEV_NULL",
            "Source",
            "Timeout",
            "child_watch_add",
            "filename_display_basename",
            "filename_display_name",
            "filename_from_utf8",
            "get_application_name",
            "get_current_time",
            "get_prgname",
            "glib_version",
            "idle_add",
            "io_add_watch",
            "main_context_default",
            "main_depth",
            "markup_escape_text",
            "set_application_name",
            "set_prgname",
            "source_remove",
            "spawn_async",
            "timeout_add",
            "timeout_add_seconds",
        ]
    )
