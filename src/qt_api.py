"""
Centralized Qt binding loader for OpenShot.

Selects an available binding (PyQt6/PySide6/PyQt5) using the
`OPENSHOT_QT_API` env var (`auto` default, otherwise one of
`pyqt6|pyside6|pyqt5`). Logs the selection attempts, failures,
and final choice to help diagnose environment issues.
"""

import logging
import os
import sys
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def _is_android_runtime() -> bool:
    return sys.platform == "android" or bool(
        os.environ.get("ANDROID_ARGUMENT")
        or os.environ.get("ANDROID_PRIVATE")
        or os.environ.get("ANDROID_DATA")
        or os.environ.get("ANDROID_APP_PATH")
    )


# Public exports filled in after binding selection
QtCore = QtGui = QtWidgets = QtSvg = None
Signal = Slot = Property = None
QRegularExpression = None
QByteArray = QDir = QLibraryInfo = None
QSignalTransition = None
QState = QStateMachine = None
uic = None
QT_API: Optional[str] = None
QT_VERSION_STR: Optional[str] = None
PYQT_VERSION_STR: Optional[str] = None
BINDING_VERSION_STR: Optional[str] = None
_MODULES = []
_FAILED_IMPORT: Optional[Exception] = None
_SELECTING = False

_shiboken_ext_load_error = None
_openshot_shiboken_ext = None
if _is_android_runtime():
    try:
        import openshot_shiboken_ext as _openshot_shiboken_ext  # type: ignore
    except Exception as exc:
        _shiboken_ext_load_error = exc
    if _openshot_shiboken_ext is not None:
        logger.debug("qt_api: openshot_shiboken_ext loaded successfully")
    else:
        logger.warning("qt_api: openshot_shiboken_ext failed to load: %r", _shiboken_ext_load_error)


def _load_sip_like():
    """Return ('sip'|'shiboken', module) for the active binding."""
    if QT_API is None:
        _select_binding()
    if QT_API == "pyqt6":
        try:
            from PyQt6 import sip as sip_mod  # type: ignore
        except Exception:
            sip_mod = None
        return ("sip", sip_mod)
    if QT_API == "pyqt5":
        try:
            from PyQt5 import sip as sip_mod  # type: ignore
        except Exception:
            try:
                import sip as sip_mod  # type: ignore  # standalone sip (older PyQt5 builds)
            except Exception:
                sip_mod = None
        return ("sip", sip_mod)
    if QT_API == "pyside6":
        try:
            import shiboken6 as shiboken_mod  # type: ignore
        except Exception:
            shiboken_mod = None
        return ("shiboken", shiboken_mod)
    return ("sip", None)


def unwrapinstance(obj):
    """Return the underlying C++ pointer for a Qt object."""
    backend, mod = _load_sip_like()
    if mod is None:
        raise RuntimeError("No SIP/shiboken module available for unwrapinstance()")
    if backend == "sip":
        return mod.unwrapinstance(obj)
    return mod.getCppPointer(obj)[0]


def wrapinstance(ptr, base_type):
    """Wrap a C++ pointer into a Qt object."""
    backend, mod = _load_sip_like()
    if mod is None:
        raise RuntimeError("No SIP/shiboken module available for wrapinstance()")
    if backend == "sip":
        return mod.wrapinstance(ptr, base_type)
    if _openshot_shiboken_ext is not None:
        return _openshot_shiboken_ext.wrap_instance_u64(ptr, base_type)
    if _shiboken_ext_load_error is not None:
        logger.warning("qt_api: openshot_shiboken_ext unavailable: %s", _shiboken_ext_load_error)
    ptr_in = int(ptr)
    # Shiboken expects a signed pointer-sized integer. If we got an unsigned
    # 64-bit value with the high bit set, convert it to signed.
    if ptr_in >= (1 << 63):
        ptr_in -= (1 << 64)
    return mod.wrapInstance(ptr_in, base_type)


def isdeleted(obj):
    """Return True if the Qt object has been deleted."""
    backend, mod = _load_sip_like()
    if mod is None:
        return False
    if backend == "sip":
        return mod.isdeleted(obj)
    return not mod.isValid(obj)


def modifiers_has(modifiers, flag):
    """Return True if a modifier flag is set on a modifiers bitmask."""
    try:
        return bool(modifiers & flag)
    except Exception:
        try:
            return bool(int(modifiers) & int(flag))
        except Exception:
            return False


def clear_override_cursor():
    """Clear any active QApplication override cursors."""
    try:
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
    except Exception as exc:
        logger.debug("qt_api: failed to clear override cursor: %s", exc, exc_info=True)


# Module-level references keep pickers alive until the callback fires.
_active_picker = None
_active_save_picker = None

# Lazily created on the main thread; used to post callbacks from background threads.
_callback_bridge = None


def _get_callback_bridge():
    """Return the shared callback bridge, creating it lazily (must be called on the main thread).

    The class is defined here rather than at module level because QtCore is None
    until the Qt binding is selected — defining it inline avoids that ordering issue.
    """
    global _callback_bridge
    if _callback_bridge is None:
        class _CallbackBridge(QtCore.QObject):
            """Delivers a callable to Qt's main thread via a queued signal connection."""
            _invoke = QtCore.Signal(object)

            def __init__(self):
                super().__init__()
                self._invoke.connect(self._run, QtCore.Qt.QueuedConnection)

            def call(self, fn):
                self._invoke.emit(fn)

            def _run(self, fn):
                fn()

        _callback_bridge = _CallbackBridge()
    return _callback_bridge


class _AndroidFilePicker:
    """Launches Android's document picker and resolves selected files to local paths.

    On API 30+, requests MANAGE_EXTERNAL_STORAGE first so files can be accessed
    directly without copying.  Falls back to stream-copying into app cache when
    the permission is absent or denied.

    Calls on_complete([QUrl, ...]) on the Qt main thread when done.
    """

    # Activity result request codes
    _RC_STORAGE_PERM = 10442
    _RC_FILE_PICKER  = 10443

    def __init__(self, on_complete, allow_multiple=True):
        self._on_complete = on_complete
        self._allow_multiple = allow_multiple
        self._listener = None
        self._perm_listener = None
        self._mActivity = None
        # jnius class refs stored here so open/launch/resolve all share them
        self._Activity = None
        self._Intent = None
        self._OpenableColumns = None
        self._File = None
        self._FileOutputStream = None
        self._PythonJavaClass = None
        self._java_method = None
        self._autoclass = None

    def open(self):
        try:
            from jnius import autoclass, PythonJavaClass, java_method  # type: ignore
        except Exception:
            self._on_complete([])
            return

        # Store all class refs on self so they survive across method calls
        self._autoclass = autoclass
        self._PythonJavaClass = PythonJavaClass
        self._java_method = java_method

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        self._mActivity = PythonActivity.mActivity
        self._Activity = autoclass("android.app.Activity")
        self._Intent = autoclass("android.content.Intent")
        self._OpenableColumns = autoclass("android.provider.OpenableColumns")
        self._File = autoclass("java.io.File")
        self._FileOutputStream = autoclass("java.io.FileOutputStream")

        # On API 30+ request All Files Access so we can read files directly.
        # On older API or if already granted, go straight to the picker.
        BuildVersion = autoclass("android.os.Build$VERSION")
        Environment = autoclass("android.os.Environment")
        needs_perm = (BuildVersion.SDK_INT >= 30
                      and not Environment.isExternalStorageManager())

        if needs_perm:
            self._request_storage_permission()
        else:
            self._launch_picker()

    def _request_storage_permission(self):
        """Send the user to the All Files Access settings page, then open the picker on return."""
        autoclass = self._autoclass
        Settings = autoclass("android.provider.Settings")
        Uri = autoclass("android.net.Uri")

        intent = self._Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
        intent.setData(Uri.parse("package:" + self._mActivity.getPackageName()))

        picker = self
        PythonJavaClass = self._PythonJavaClass
        java_method = self._java_method

        class _PermListener(PythonJavaClass):
            __javainterfaces__ = ["org/kivy/android/PythonActivity$ActivityResultListener"]
            __javacontext__ = "app"

            def __init__(self):
                super().__init__()

            @java_method("(IILandroid/content/Intent;)V")
            def onActivityResult(self, request_code, result_code, data):
                if request_code != picker._RC_STORAGE_PERM:
                    return
                try:
                    picker._mActivity.unregisterActivityResultListener(self)
                except Exception as exc:
                    logger.debug("qt_api: failed to unregister storage permission listener: %s", exc, exc_info=True)
                picker._perm_listener = None
                # Open the picker regardless — user may have granted or denied
                picker._launch_picker()

        try:
            self._perm_listener = _PermListener()
            self._mActivity.registerActivityResultListener(self._perm_listener)
            self._mActivity.startActivityForResult(intent, self._RC_STORAGE_PERM)
        except Exception:
            # Some ROMs may not handle this intent; skip straight to the picker
            self._perm_listener = None
            self._launch_picker()

    def _launch_picker(self):
        """Start the system document picker."""
        Intent = self._Intent
        Activity = self._Activity
        OpenableColumns = self._OpenableColumns
        File = self._File
        FileOutputStream = self._FileOutputStream
        PythonJavaClass = self._PythonJavaClass
        java_method = self._java_method

        intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType("*/*")
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        if self._allow_multiple:
            intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, True)

        picker = self

        class _Listener(PythonJavaClass):
            __javainterfaces__ = ["org/kivy/android/PythonActivity$ActivityResultListener"]
            __javacontext__ = "app"

            def __init__(self):
                super().__init__()
                self._Activity = Activity
                self._OpenableColumns = OpenableColumns
                self._File = File
                self._FileOutputStream = FileOutputStream

            @java_method("(IILandroid/content/Intent;)V")
            def onActivityResult(self, request_code, result_code, data):
                if request_code != picker._RC_FILE_PICKER:
                    return
                try:
                    picker._mActivity.unregisterActivityResultListener(self)
                except Exception as exc:
                    logger.debug("qt_api: failed to unregister file picker listener: %s", exc, exc_info=True)

                if result_code != self._Activity.RESULT_OK or data is None:
                    picker._on_complete([])
                    return

                resolver = picker._mActivity.getContentResolver()

                uris = []
                try:
                    clip = data.getClipData()
                    if clip is not None:
                        for i in range(clip.getItemCount()):
                            uri = clip.getItemAt(i).getUri()
                            if uri is not None:
                                uris.append(uri)
                    else:
                        uri = data.getData()
                        if uri is not None:
                            uris.append(uri)
                except Exception as exc:
                    logger.debug("qt_api: failed to read Android picker result URIs: %s", exc, exc_info=True)

                # Snapshot URI strings now — jnius objects may not survive thread boundaries.
                uri_strings = [u.toString() for u in uris]
                cache_dir = picker._mActivity.getCacheDir().getAbsolutePath()
                on_complete = picker._on_complete

                # Take persistable read+write permissions so content:// URIs remain
                # accessible across app restarts (needed for Recent Projects save/load).
                read_write = (Intent.FLAG_GRANT_READ_URI_PERMISSION
                              | Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
                for uri in uris:
                    try:
                        resolver.takePersistableUriPermission(uri, read_write)
                    except Exception as exc:
                        logger.debug("qt_api: failed to persist URI permission for %s: %s", uri, exc, exc_info=True)

                # The bridge was created on the Qt main thread (in show_open_file_dialog).
                # Do NOT call _get_callback_bridge() here — this runs on the Android main thread.
                bridge = _callback_bridge

                import threading
                def _resolve_and_complete():
                    urls = []
                    for uri_str in uri_strings:
                        path = picker._resolve_uri(resolver, uri_str, cache_dir,
                                                   self._OpenableColumns, self._File,
                                                   self._FileOutputStream)
                        if path:
                            if path.startswith("content://"):
                                urls.append(QtCore.QUrl(path))
                            else:
                                urls.append(QtCore.QUrl.fromLocalFile(path))
                    bridge.call(lambda: on_complete(urls))

                threading.Thread(target=_resolve_and_complete, daemon=True).start()

        try:
            self._listener = _Listener()
            self._mActivity.registerActivityResultListener(self._listener)
            self._mActivity.startActivityForResult(intent, self._RC_FILE_PICKER)
        except Exception:
            self._on_complete([])

    def _resolve_uri(self, resolver, uri_str, cache_dir, OpenableColumns, File, FileOutputStream):
        """Return a local file path (or content:// URI) for a content URI.

        Resolution is attempted in order, falling through on failure:

        1. MediaStore path for com.android.providers.media.documents URIs
           (requires MANAGE_EXTERNAL_STORAGE; fast, no copy).
        2. External-storage document ID decoding for
           com.android.externalstorage.documents URIs — the document ID
           encodes the path as "primary:relative/path".
        3. Downloads document ID decoding for
           com.android.providers.downloads.documents URIs — modern Android
           encodes the path as "raw:/absolute/path".
        4. _data column query via ContentResolver (works for local files
           when MANAGE_EXTERNAL_STORAGE is granted).
        5. For .osp project files with no resolvable local path: return the
           content:// URI directly so reads/writes use ContentResolver.
        6. Stream-copy into app cache (media files that must have a real path
           for libopenshot, or cloud files like Google Drive).
        """
        autoclass = self._autoclass

        def _accessible(path):
            """Return path if it is a readable local file, else None."""
            return path if (path and os.path.isfile(path) and os.access(path, os.R_OK)) else None

        # --- Attempt 1: MediaStore path via document ID ---
        if "com.android.providers.media.documents" in uri_str:
            try:
                Environment = autoclass("android.os.Environment")
                if Environment.isExternalStorageManager():
                    DocumentsContract = autoclass("android.provider.DocumentsContract")
                    ContentUris = autoclass("android.content.ContentUris")
                    Uri = autoclass("android.net.Uri")
                    uri_obj = Uri.parse(uri_str)
                    doc_id = DocumentsContract.getDocumentId(uri_obj)
                    parts = doc_id.split(":")
                    if len(parts) == 2:
                        media_type, media_id_str = parts[0], parts[1]
                        media_id = int(media_id_str)
                        media_uri = None
                        if media_type == "video":
                            media_uri = autoclass("android.provider.MediaStore$Video$Media")
                        elif media_type == "image":
                            media_uri = autoclass("android.provider.MediaStore$Images$Media")
                        elif media_type == "audio":
                            media_uri = autoclass("android.provider.MediaStore$Audio$Media")
                        if media_uri is not None:
                            row_uri = ContentUris.withAppendedId(
                                media_uri.EXTERNAL_CONTENT_URI, media_id)
                            cursor = resolver.query(row_uri, ["_data"], None, None, None)
                            if cursor is not None:
                                try:
                                    if cursor.moveToFirst():
                                        idx = cursor.getColumnIndex("_data")
                                        if idx >= 0:
                                            path = _accessible(cursor.getString(idx))
                                            if path:
                                                return path
                                finally:
                                    cursor.close()
            except Exception:
                pass

        # --- Attempt 2: External-storage document ID decoding ---
        # Document ID format: "primary:relative/path" or "<uuid>:relative/path"
        if "com.android.externalstorage.documents" in uri_str:
            try:
                DocumentsContract = autoclass("android.provider.DocumentsContract")
                Uri = autoclass("android.net.Uri")
                uri_obj = Uri.parse(uri_str)
                doc_id = DocumentsContract.getDocumentId(uri_obj)
                if ":" in doc_id:
                    volume, rel_path = doc_id.split(":", 1)
                    if volume.lower() == "primary":
                        Environment = autoclass("android.os.Environment")
                        base = Environment.getExternalStorageDirectory().getAbsolutePath()
                        path = _accessible(os.path.join(base, rel_path))
                        if path:
                            return path
            except Exception:
                pass

        # --- Attempt 3: Downloads document ID decoding ---
        # Modern Android encodes the path as "raw:/absolute/path".
        if "com.android.providers.downloads.documents" in uri_str:
            try:
                DocumentsContract = autoclass("android.provider.DocumentsContract")
                Uri = autoclass("android.net.Uri")
                uri_obj = Uri.parse(uri_str)
                doc_id = DocumentsContract.getDocumentId(uri_obj)
                if doc_id.startswith("raw:"):
                    path = _accessible(doc_id[4:])
                    if path:
                        return path
            except Exception:
                pass

        # --- Attempt 4: _data column query (any URI, requires MANAGE_EXTERNAL_STORAGE) ---
        try:
            Environment = autoclass("android.os.Environment")
            if Environment.isExternalStorageManager():
                Uri = autoclass("android.net.Uri")
                uri_obj = Uri.parse(uri_str)
                cursor = resolver.query(uri_obj, ["_data"], None, None, None)
                if cursor is not None:
                    try:
                        if cursor.moveToFirst():
                            idx = cursor.getColumnIndex("_data")
                            if idx >= 0:
                                path = _accessible(cursor.getString(idx))
                                if path:
                                    return path
                    finally:
                        cursor.close()
        except Exception:
            pass

        # --- Query display name to determine file type for fallback ---
        display_name = ""
        try:
            Uri = autoclass("android.net.Uri")
            uri_obj = Uri.parse(uri_str)
            cursor = resolver.query(uri_obj, None, None, None, None)
            if cursor is not None:
                try:
                    if cursor.moveToFirst():
                        idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                        if idx >= 0:
                            display_name = cursor.getString(idx) or ""
                finally:
                    cursor.close()
        except Exception:
            pass

        suffix = os.path.splitext(display_name)[1]

        # --- Attempt 5: For project files without a resolvable local path ---
        # Return the content:// URI directly; read_file_text/write_file_text handle it
        # so saves go back to the source file (e.g. Google Drive, restricted storage).
        if suffix.lower() == ".osp":
            return uri_str

        # --- Attempt 6: Stream-copy into app cache ---
        # Required for media files: libopenshot needs a real filesystem path.
        # Also used for cloud files (Google Drive) of any type.
        import hashlib
        uri_hash = hashlib.sha1(uri_str.encode()).hexdigest()[:16]
        dest_path = os.path.join(cache_dir, f"openshot_import_{uri_hash}{suffix}")

        try:
            Uri = autoclass("android.net.Uri")
            uri_obj = Uri.parse(uri_str)
            input_stream = resolver.openInputStream(uri_obj)
            if input_stream is None:
                return None
            output_stream = FileOutputStream(File(dest_path))
            try:
                buf = bytearray(64 * 1024)
                while True:
                    count = input_stream.read(buf)
                    if count == -1:
                        break
                    output_stream.write(buf, 0, count)
            finally:
                input_stream.close()
                output_stream.close()
            return dest_path
        except Exception:
            return None


class _AndroidSavePicker:
    """Launches Android's ACTION_CREATE_DOCUMENT intent so the user picks a save location.

    Calls on_complete(uri_string) on the Qt main thread when done.
    uri_string is a content:// URI on success or "" if the user cancelled.

    After the user confirms, the display name is queried and, if the required
    extension (self._extension) is missing, DocumentsContract.renameDocument is
    used to append it before delivering the URI to the callback.
    """

    _RC_SAVE_PICKER = 10444

    def __init__(self, on_complete, suggested_name="untitled", mime_type="*/*",
                 extension=".osp"):
        self._on_complete = on_complete
        self._suggested_name = suggested_name
        self._mime_type = mime_type
        self._extension = extension.lower()
        self._listener = None
        self._mActivity = None
        self._autoclass = None

    def open(self):
        try:
            from jnius import autoclass, PythonJavaClass, java_method  # type: ignore
        except Exception:
            self._on_complete("")
            return

        self._autoclass = autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        self._mActivity = PythonActivity.mActivity
        Intent = autoclass("android.content.Intent")
        Activity = autoclass("android.app.Activity")
        Bundle = autoclass("android.os.Bundle")

        intent = Intent(Intent.ACTION_CREATE_DOCUMENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType(self._mime_type)
        intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)

        # Use Bundle.putString to set EXTRA_TITLE — Intent.putExtra is heavily
        # overloaded and jnius may silently pick the wrong overload when both
        # arguments are strings (e.g. resolving to putExtra(String,Serializable)
        # instead of putExtra(String,String)), causing the prefill to be ignored.
        extras = Bundle()
        extras.putString("android.intent.extra.TITLE", self._suggested_name)
        intent.putExtras(extras)

        picker = self

        class _Listener(PythonJavaClass):
            __javainterfaces__ = ["org/kivy/android/PythonActivity$ActivityResultListener"]
            __javacontext__ = "app"

            def __init__(self):
                super().__init__()
                self._Activity = Activity

            @java_method("(IILandroid/content/Intent;)V")
            def onActivityResult(self, request_code, result_code, data):
                if request_code != picker._RC_SAVE_PICKER:
                    return
                try:
                    picker._mActivity.unregisterActivityResultListener(self)
                except Exception:
                    pass

                uri_str = ""
                if result_code == self._Activity.RESULT_OK and data is not None:
                    try:
                        uri = data.getData()
                        if uri is not None:
                            uri_str = uri.toString()
                            # Enforce the required file extension.
                            # Query the display name; rename via DocumentsContract if needed.
                            if picker._extension:
                                try:
                                    autoclass = picker._autoclass
                                    resolver = picker._mActivity.getContentResolver()
                                    OpenableColumns = autoclass("android.provider.OpenableColumns")
                                    cursor = resolver.query(uri, None, None, None, None)
                                    display_name = ""
                                    if cursor is not None:
                                        try:
                                            if cursor.moveToFirst():
                                                idx = cursor.getColumnIndex(
                                                    OpenableColumns.DISPLAY_NAME)
                                                if idx >= 0:
                                                    display_name = cursor.getString(idx) or ""
                                        finally:
                                            cursor.close()
                                    display_name = display_name.strip()
                                    if display_name and not display_name.lower().endswith(
                                            picker._extension):
                                        new_name = display_name + picker._extension
                                        DocumentsContract = autoclass(
                                            "android.provider.DocumentsContract")
                                        new_uri = DocumentsContract.renameDocument(
                                            resolver, uri, new_name)
                                        if new_uri is not None:
                                            uri_str = new_uri.toString()
                                except Exception:
                                    pass  # Keep original URI if rename fails
                    except Exception:
                        pass

                # Deliver result on the Qt main thread via the callback bridge.
                bridge = _callback_bridge
                on_complete = picker._on_complete
                bridge.call(lambda: on_complete(uri_str))

        try:
            self._listener = _Listener()
            self._mActivity.registerActivityResultListener(self._listener)
            self._mActivity.startActivityForResult(intent, self._RC_SAVE_PICKER)
        except Exception:
            self._on_complete("")


def read_from_content_uri(uri_str):
    """Read the UTF-8 text content of an Android content:// URI via ContentResolver.openInputStream.

    Returns the decoded string on success, raises IOError on failure.
    """
    try:
        from jnius import autoclass  # type: ignore
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        mActivity = PythonActivity.mActivity
        resolver = mActivity.getContentResolver()
        Uri = autoclass("android.net.Uri")
        uri_obj = Uri.parse(uri_str)
        input_stream = resolver.openInputStream(uri_obj)
        if input_stream is None:
            raise IOError("ContentResolver returned null InputStream for %s" % uri_str)
        chunks = []
        buf = bytearray(64 * 1024)
        try:
            while True:
                count = input_stream.read(buf)
                if count == -1:
                    break
                chunks.append(bytes(buf[:count]))
        finally:
            input_stream.close()
        return b"".join(chunks).decode("utf-8")
    except Exception as exc:
        raise IOError("Failed to read from content URI %s: %s" % (uri_str, exc)) from exc


def write_to_content_uri(uri_str, content):
    """Write a UTF-8 string to an Android content:// URI via ContentResolver.openOutputStream.

    Raises IOError on failure.  Should only be called from a background thread
    so the Qt main thread is never blocked by I/O.
    """
    try:
        from jnius import autoclass  # type: ignore
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        mActivity = PythonActivity.mActivity
        resolver = mActivity.getContentResolver()
        Uri = autoclass("android.net.Uri")
        uri_obj = Uri.parse(uri_str)
        # "wt" mode truncates the file before writing (Android default is append).
        output_stream = resolver.openOutputStream(uri_obj, "wt")
        if output_stream is None:
            raise IOError("ContentResolver returned null OutputStream for %s" % uri_str)
        try:
            data = bytearray(content.encode("utf-8"))
            output_stream.write(data)
            output_stream.flush()
        finally:
            output_stream.close()
    except Exception as exc:
        raise IOError("Failed to write to content URI %s: %s" % (uri_str, exc)) from exc


def is_content_uri(path) -> bool:
    """Return True when *path* is an Android content:// URI rather than a local filesystem path."""
    return str(path).startswith("content://")


def file_exists(path) -> bool:
    """Return True when *path* is accessible: a local file that exists, or a content:// URI."""
    return is_content_uri(path) or os.path.exists(path)


def read_file_text(path) -> str:
    """Read UTF-8 text from *path* — works transparently for local paths and content:// URIs."""
    if is_content_uri(path):
        return read_from_content_uri(path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file_text(path, content: str) -> None:
    """Write UTF-8 text to *path* — works transparently for local paths and content:// URIs."""
    if is_content_uri(path):
        write_to_content_uri(path, content)
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def ensure_extension(path: str, ext: str = ".osp") -> str:
    """Append *ext* to *path* if the path does not already end with it.

    Safe for content:// URIs — the extension is enforced at save time by
    _AndroidSavePicker, so the URI is returned unchanged.
    """
    if not path or is_content_uri(path):
        return path
    if not path.lower().endswith(ext.lower()):
        return path + ext
    return path


def path_basename(path: str) -> str:
    """Return the filename component of *path*.

    Returns an empty string for content:// URIs (which have no meaningful
    basename) so callers can fall back to a sensible default.
    """
    if not path or is_content_uri(path):
        return ""
    return os.path.basename(path)


def request_android_storage_permission_if_needed():
    """On Android API 30+, open the All Files Access settings page if not already granted.

    Safe to call at any time — does nothing on non-Android platforms or when the
    permission is already granted.  Uses startActivity (fire-and-forget) so no
    callback or result listener is required; the user grants the permission, presses
    Back, and returns to the app.  Intended to be called once at startup so the
    permission is in place before the user first taps Import Files.
    """
    if not _is_android_runtime():
        return
    try:
        from jnius import autoclass  # type: ignore
        BuildVersion = autoclass("android.os.Build$VERSION")
        if BuildVersion.SDK_INT < 30:
            return
        Environment = autoclass("android.os.Environment")
        if Environment.isExternalStorageManager():
            return
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Settings = autoclass("android.provider.Settings")
        Uri = autoclass("android.net.Uri")
        Intent = autoclass("android.content.Intent")
        mActivity = PythonActivity.mActivity
        intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
        intent.setData(Uri.parse("package:" + mActivity.getPackageName()))
        mActivity.startActivity(intent)
    except Exception:
        pass


def location_file_dialog_options():
    """Return options that preserve requested folders with the Linux portal theme.

    The Qt 5 xdgdesktopportal platform theme used by our AppImage ignores the
    initial directory passed to static native file dialogs. Use Qt's own dialog
    for location-aware operations so Recent Folder and Project Folder settings
    remain effective.
    """
    platform_theme = os.environ.get("QT_QPA_PLATFORMTHEME", "")
    if platform_theme.lower() != "xdgdesktopportal":
        return None

    QFileDialog = getattr(QtWidgets, "QFileDialog", None)
    return getattr(QFileDialog, "DontUseNativeDialog", None)


def show_open_file_dialog(parent, caption, directory, file_filter, on_complete, allow_multiple=True):
    """Show a file-open dialog and call on_complete([QUrl, ...]) with the result.

    On desktop this is synchronous (on_complete is called before returning).
    On Android the system document picker is used and on_complete is called
    asynchronously from the main thread when the user finishes selecting.
    """
    if _is_android_runtime():
        global _active_picker
        # Create (or confirm) the bridge HERE, on the Qt main thread, so its QObject
        # ownership belongs to the Qt event loop.  onActivityResult runs on the Android
        # main thread — a different thread — so creating the bridge there causes queued
        # signals to be posted to a thread with no Qt event loop (they are never delivered).
        _get_callback_bridge()
        _active_picker = _AndroidFilePicker(on_complete, allow_multiple=allow_multiple)
        _active_picker.open()
    else:
        QFileDialog = getattr(QtWidgets, "QFileDialog", None)
        dir_url = QtCore.QUrl.fromLocalFile(directory) if directory else QtCore.QUrl()
        options = location_file_dialog_options()
        if options is None:
            urls, _ = QFileDialog.getOpenFileUrls(parent, caption, dir_url, file_filter)
        else:
            urls, _ = QFileDialog.getOpenFileUrls(
                parent, caption, dir_url, file_filter, options=options)
        on_complete(urls)


def show_save_file_dialog(parent, caption, suggested_name, mime_type, on_complete, directory=""):
    """Show a file-save dialog and call on_complete(path_or_uri) with the result.

    on_complete receives a non-empty string on success:
      - On Android: a content:// URI string (write via write_to_content_uri).
      - On desktop: a local filesystem path.
    on_complete receives "" if the user cancels.

    ``directory`` is used on desktop only as the initial folder; Android ignores it
    (the suggested_name filename is passed via EXTRA_TITLE instead).

    On desktop this is synchronous (on_complete is called before returning).
    On Android ACTION_CREATE_DOCUMENT is launched and on_complete is called
    asynchronously on the Qt main thread when the user confirms the save location.
    """
    if _is_android_runtime():
        global _active_save_picker
        # Ensure the callback bridge is created on the Qt main thread.
        _get_callback_bridge()
        _active_save_picker = _AndroidSavePicker(on_complete, suggested_name=suggested_name,
                                                  mime_type=mime_type)
        _active_save_picker.open()
    else:
        QFileDialog = getattr(QtWidgets, "QFileDialog", None)
        initial_path = os.path.join(directory, suggested_name) if directory else suggested_name
        options = location_file_dialog_options()
        if options is None:
            path, _ = QFileDialog.getSaveFileName(parent, caption, initial_path)
        else:
            path, _ = QFileDialog.getSaveFileName(
                parent, caption, initial_path, options=options)
        on_complete(path or "")


def get_font_dialog_selection(initial_font=None, parent=None, title=""):
    """Return (font, accepted) from a font dialog across bindings."""
    font_dialog_class = getattr(QtWidgets, "QFontDialog", None)
    if font_dialog_class is None:
        raise RuntimeError("QFontDialog is unavailable")
    if not callable(font_dialog_class):
        raise RuntimeError("QFontDialog is not callable")

    # PySide6 has been unreliable with the static getFont() overloads here.
    # Use an instance dialog consistently across bindings.
    if initial_font is None:
        dialog = font_dialog_class(parent)
    else:
        dialog = font_dialog_class(initial_font, parent)
    if title:
        dialog.setWindowTitle(title)
    exec_fn = getattr(dialog, "exec", None) or getattr(dialog, "exec_", None)
    accepted = bool(exec_fn and exec_fn())
    selected_font = dialog.selectedFont() if accepted else initial_font
    return selected_font, accepted


def make_filter_regex(pattern: str, case_insensitive: bool = True):
    """Create a cross-binding regex for QSortFilterProxyModel filters."""
    if QT_API in ("pyqt6", "pyside6") and QRegularExpression is not None:
        regex = QRegularExpression(pattern)
        if case_insensitive:
            regex.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        return regex
    # PyQt5 path (QRegExp)
    QRegExp = getattr(QtCore, "QRegExp", None)
    if QRegExp is not None:
        cs = QtCore.Qt.CaseInsensitive if case_insensitive else QtCore.Qt.CaseSensitive
        return QRegExp(pattern, cs)
    # Fallback to QRegularExpression if available
    if QRegularExpression is not None:
        regex = QRegularExpression(pattern)
        if case_insensitive:
            regex.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        return regex
    return pattern


def set_proxy_filter(proxy, regex):
    """Set a filter regex on a QSortFilterProxyModel, across bindings."""
    if hasattr(proxy, "setFilterRegularExpression") and QRegularExpression is not None and isinstance(regex, QRegularExpression):
        return proxy.setFilterRegularExpression(regex)
    return proxy.setFilterRegExp(regex)


def get_proxy_filter_regex(proxy):
    """Get the current filter regex from a QSortFilterProxyModel."""
    if QT_API == "pyqt5":
        return proxy.filterRegExp()
    if hasattr(proxy, "filterRegularExpression") and QRegularExpression is not None:
        try:
            return proxy.filterRegularExpression()
        except Exception:
            pass
    # Fallback to legacy API if present or non-empty
    return proxy.filterRegExp()


def regex_is_empty(regex):
    """Return True if the regex has no pattern."""
    if regex is None:
        return True
    if QRegularExpression is not None and isinstance(regex, QRegularExpression):
        return not regex.pattern()
    if hasattr(regex, "isEmpty"):
        try:
            return regex.isEmpty()
        except Exception:
            return True
    return not bool(regex)


def regex_matches(regex, text):
    """Return True if regex matches text, across bindings."""
    if text is None:
        text = ""
    if QRegularExpression is not None and isinstance(regex, QRegularExpression):
        return regex.match(text).hasMatch()
    if hasattr(regex, "indexIn"):
        return regex.indexIn(text) >= 0
    return False


def _patch_enums_for_qt6():
    """Backfill Qt5-style enum attributes on Qt6 scoped enums."""
    if QT_API not in ("pyqt6", "pyside6"):
        return
    QDir = getattr(QtCore, "QDir", None)
    if QDir:
        # Filters
        filt = getattr(QDir, "Filter", None) or getattr(QDir, "Filters", None)
        if filt:
            for name, val in vars(filt).items():
                if name.startswith("_"):
                    continue
                if not hasattr(QDir, name):
                    try:
                        setattr(QDir, name, val)
                    except Exception:
                        pass

    QLibraryInfo = getattr(QtCore, "QLibraryInfo", None)
    if QLibraryInfo:
        # Backfill TranslationsPath constant and location() alias
        lib_path_enum = getattr(QLibraryInfo, "LibraryPath", None)
        if lib_path_enum and not hasattr(QLibraryInfo, "TranslationsPath"):
            try:
                setattr(QLibraryInfo, "TranslationsPath", lib_path_enum.TranslationsPath)
            except Exception:
                pass
        if hasattr(QLibraryInfo, "path") and not hasattr(QLibraryInfo, "location"):
            try:
                setattr(QLibraryInfo, "location", staticmethod(QLibraryInfo.path))
            except Exception:
                pass
        # Sort flags
        sort = getattr(QDir, "SortFlag", None) or getattr(QDir, "SortFlags", None)
        if sort:
            for name, val in vars(sort).items():
                if name.startswith("_"):
                    continue
                if not hasattr(QDir, name):
                    try:
                        setattr(QDir, name, val)
                    except Exception:
                        pass

    QMetaMethod = getattr(QtCore, "QMetaMethod", None)
    if QMetaMethod and not hasattr(QMetaMethod, "Signal"):
        method_type = getattr(QMetaMethod, "MethodType", None)
        if method_type and hasattr(method_type, "Signal"):
            try:
                setattr(QMetaMethod, "Signal", method_type.Signal)
            except Exception:
                pass

    QEvent = getattr(QtCore, "QEvent", None)
    if QEvent:
        event_type = getattr(QEvent, "Type", None)
        if event_type:
            for name in ("ShortcutOverride", "Resize", "Paint", "KeyPress", "MouseButtonPress", "MouseButtonRelease", "Close", "Hide", "Show"):
                if hasattr(event_type, name) and not hasattr(QEvent, name):
                    try:
                        setattr(QEvent, name, getattr(event_type, name))
                    except Exception:
                        pass
    QEventLoop = getattr(QtCore, "QEventLoop", None)
    if QEventLoop and not hasattr(QEventLoop, "ExcludeUserInputEvents"):
        process_flag = getattr(QEventLoop, "ProcessEventsFlag", None)
        if process_flag and hasattr(process_flag, "ExcludeUserInputEvents"):
            try:
                setattr(QEventLoop, "ExcludeUserInputEvents", process_flag.ExcludeUserInputEvents)
            except Exception:
                pass
        if process_flag and hasattr(process_flag, "ExcludeSocketNotifiers"):
            if not hasattr(QEventLoop, "ExcludeSocketNotifiers"):
                try:
                    setattr(QEventLoop, "ExcludeSocketNotifiers", process_flag.ExcludeSocketNotifiers)
                except Exception:
                    pass

    def _patch_point_event_methods(cls):
        if cls is None or hasattr(cls, "x") or not hasattr(cls, "position"):
            return

        def _x(self):
            return int(self.position().x())

        def _y(self):
            return int(self.position().y())

        def _pos(self):
            point = getattr(QtCore, "QPoint", None)
            if point is not None:
                return point(int(self.position().x()), int(self.position().y()))
            return self.position().toPoint()

        try:
            setattr(cls, "x", _x)
        except Exception:
            pass
        try:
            setattr(cls, "y", _y)
        except Exception:
            pass
        if not hasattr(cls, "pos"):
            try:
                setattr(cls, "pos", _pos)
            except Exception:
                pass

    for event_name in ("QMouseEvent", "QHoverEvent", "QEnterEvent", "QTabletEvent"):
        _patch_point_event_methods(getattr(QtGui, event_name, None))

    if QtCore and not hasattr(QtCore, "Qt"):
        return
    if not hasattr(QtCore.Qt, "WA_OpaquePaintEvent"):
        widget_attr = getattr(QtCore.Qt, "WidgetAttribute", None)
        if widget_attr and hasattr(widget_attr, "WA_OpaquePaintEvent"):
            try:
                setattr(QtCore.Qt, "WA_OpaquePaintEvent", widget_attr.WA_OpaquePaintEvent)
            except Exception:
                pass
    if not hasattr(QtCore.Qt, "WA_DeleteOnClose"):
        widget_attr = getattr(QtCore.Qt, "WidgetAttribute", None)
        if widget_attr and hasattr(widget_attr, "WA_DeleteOnClose"):
            try:
                setattr(QtCore.Qt, "WA_DeleteOnClose", widget_attr.WA_DeleteOnClose)
            except Exception:
                pass
    if not hasattr(QtCore.Qt, "WA_NoSystemBackground"):
        widget_attr = getattr(QtCore.Qt, "WidgetAttribute", None)
        if widget_attr and hasattr(widget_attr, "WA_NoSystemBackground"):
            try:
                setattr(QtCore.Qt, "WA_NoSystemBackground", widget_attr.WA_NoSystemBackground)
            except Exception:
                pass
    if not hasattr(QtCore.Qt, "WA_TranslucentBackground"):
        widget_attr = getattr(QtCore.Qt, "WidgetAttribute", None)
        if widget_attr and hasattr(widget_attr, "WA_TranslucentBackground"):
            try:
                setattr(QtCore.Qt, "WA_TranslucentBackground", widget_attr.WA_TranslucentBackground)
            except Exception:
                pass
    if not hasattr(QtCore.Qt, "WA_TransparentForMouseEvents"):
        widget_attr = getattr(QtCore.Qt, "WidgetAttribute", None)
        if widget_attr and hasattr(widget_attr, "WA_TransparentForMouseEvents"):
            try:
                setattr(QtCore.Qt, "WA_TransparentForMouseEvents", widget_attr.WA_TransparentForMouseEvents)
            except Exception:
                pass

    corner_enum = getattr(QtCore.Qt, "Corner", None)
    if corner_enum:
        for name in ("TopLeftCorner", "TopRightCorner", "BottomLeftCorner", "BottomRightCorner"):
            if hasattr(corner_enum, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(corner_enum, name))
                except Exception:
                    pass

    dock_enum = getattr(QtCore.Qt, "DockWidgetArea", None)
    if dock_enum:
        for name in (
            "LeftDockWidgetArea",
            "RightDockWidgetArea",
            "TopDockWidgetArea",
            "BottomDockWidgetArea",
            "AllDockWidgetAreas",
            "NoDockWidgetArea",
        ):
            if hasattr(dock_enum, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(dock_enum, name))
                except Exception:
                    pass

    context_menu_policy = getattr(QtCore.Qt, "ContextMenuPolicy", None)
    if context_menu_policy:
        for name in ("NoContextMenu", "DefaultContextMenu", "ActionsContextMenu", "CustomContextMenu", "PreventContextMenu"):
            if hasattr(context_menu_policy, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(context_menu_policy, name))
                except Exception:
                    pass

    case_enum = getattr(QtCore.Qt, "CaseSensitivity", None)
    if case_enum:
        for name in ("CaseSensitive", "CaseInsensitive"):
            if hasattr(case_enum, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(case_enum, name))
                except Exception:
                    pass

    elide_enum = getattr(QtCore.Qt, "TextElideMode", None)
    if elide_enum:
        for name in ("ElideLeft", "ElideRight", "ElideMiddle", "ElideNone"):
            if hasattr(elide_enum, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(elide_enum, name))
                except Exception:
                    pass

    sort_enum = getattr(QtCore.Qt, "SortOrder", None)
    if sort_enum:
        for name in ("AscendingOrder", "DescendingOrder"):
            if hasattr(sort_enum, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(sort_enum, name))
                except Exception:
                    pass

    item_flag = getattr(QtCore.Qt, "ItemFlag", None)
    if item_flag:
        for name in (
            "NoItemFlags",
            "ItemIsSelectable",
            "ItemIsEditable",
            "ItemIsDragEnabled",
            "ItemIsDropEnabled",
            "ItemIsUserCheckable",
            "ItemIsEnabled",
            "ItemIsAutoTristate",
            "ItemIsTristate",
            "ItemNeverHasChildren",
        ):
            if hasattr(item_flag, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(item_flag, name))
                except Exception:
                    pass

    check_state = getattr(QtCore.Qt, "CheckState", None)
    if check_state:
        for name in ("Unchecked", "PartiallyChecked", "Checked"):
            if hasattr(check_state, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(check_state, name))
                except Exception:
                    pass

    size_mode = getattr(QtCore.Qt, "SizeMode", None)
    if size_mode:
        for name in ("AbsoluteSize", "RelativeSize"):
            if hasattr(size_mode, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(size_mode, name))
                except Exception:
                    pass

    keyboard_modifier = getattr(QtCore.Qt, "KeyboardModifier", None)
    if keyboard_modifier:
        for name in ("NoModifier", "ShiftModifier", "ControlModifier", "AltModifier", "MetaModifier", "KeypadModifier", "GroupSwitchModifier"):
            if hasattr(keyboard_modifier, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(keyboard_modifier, name))
                except Exception:
                    pass

    mouse_button = getattr(QtCore.Qt, "MouseButton", None)
    if mouse_button:
        for name in ("NoButton", "LeftButton", "RightButton", "MiddleButton", "BackButton", "ForwardButton", "TaskButton"):
            if hasattr(mouse_button, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(mouse_button, name))
                except Exception:
                    pass

    clip_operation = getattr(QtCore.Qt, "ClipOperation", None)
    if clip_operation:
        for name in ("NoClip", "ReplaceClip", "IntersectClip"):
            if hasattr(clip_operation, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(clip_operation, name))
                except Exception:
                    pass

    item_data_role = getattr(QtCore.Qt, "ItemDataRole", None)
    if item_data_role:
        for name in (
            "DisplayRole",
            "DecorationRole",
            "EditRole",
            "ToolTipRole",
            "StatusTipRole",
            "WhatsThisRole",
            "FontRole",
            "TextAlignmentRole",
            "BackgroundRole",
            "ForegroundRole",
            "CheckStateRole",
            "InitialSortOrderRole",
            "AccessibleTextRole",
            "AccessibleDescriptionRole",
            "SizeHintRole",
            "UserRole",
        ):
            if hasattr(item_data_role, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(item_data_role, name))
                except Exception:
                    pass

    alignment_flag = getattr(QtCore.Qt, "AlignmentFlag", None)
    if alignment_flag:
        for name in (
            "AlignLeft",
            "AlignRight",
            "AlignHCenter",
            "AlignJustify",
            "AlignTop",
            "AlignBottom",
            "AlignVCenter",
            "AlignBaseline",
            "AlignCenter",
            "AlignLeading",
            "AlignTrailing",
            "AlignAbsolute",
        ):
            if hasattr(alignment_flag, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(alignment_flag, name))
                except Exception:
                    pass

    pen_style = getattr(QtCore.Qt, "PenStyle", None)
    if pen_style:
        for name in (
            "NoPen",
            "SolidLine",
            "DashLine",
            "DotLine",
            "DashDotLine",
            "DashDotDotLine",
            "CustomDashLine",
        ):
            if hasattr(pen_style, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(pen_style, name))
                except Exception:
                    pass

    pen_cap_style = getattr(QtCore.Qt, "PenCapStyle", None)
    if pen_cap_style:
        for name in ("FlatCap", "SquareCap", "RoundCap", "MPenCapStyle"):
            if hasattr(pen_cap_style, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(pen_cap_style, name))
                except Exception:
                    pass

    brush_style = getattr(QtCore.Qt, "BrushStyle", None)
    if brush_style:
        for name in (
            "NoBrush",
            "SolidPattern",
            "Dense1Pattern",
            "Dense2Pattern",
            "Dense3Pattern",
            "Dense4Pattern",
            "Dense5Pattern",
            "Dense6Pattern",
            "Dense7Pattern",
            "HorPattern",
            "VerPattern",
            "CrossPattern",
            "BDiagPattern",
            "FDiagPattern",
            "DiagCrossPattern",
        ):
            if hasattr(brush_style, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(brush_style, name))
                except Exception:
                    pass

    text_format = getattr(QtCore.Qt, "TextFormat", None)
    if text_format:
        for name in ("PlainText", "RichText", "AutoText", "MarkdownText"):
            if hasattr(text_format, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(text_format, name))
                except Exception:
                    pass

    cursor_shape = getattr(QtCore.Qt, "CursorShape", None)
    if cursor_shape:
        for name in (
            "ArrowCursor",
            "UpArrowCursor",
            "CrossCursor",
            "WaitCursor",
            "IBeamCursor",
            "SizeVerCursor",
            "SizeHorCursor",
            "SizeBDiagCursor",
            "SizeFDiagCursor",
            "SizeAllCursor",
            "BlankCursor",
            "SplitVCursor",
            "SplitHCursor",
            "PointingHandCursor",
            "ForbiddenCursor",
            "WhatsThisCursor",
            "BusyCursor",
            "OpenHandCursor",
            "ClosedHandCursor",
            "DragCopyCursor",
            "DragMoveCursor",
            "DragLinkCursor",
        ):
            if hasattr(cursor_shape, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(cursor_shape, name))
                except Exception:
                    pass

    connection_type = getattr(QtCore.Qt, "ConnectionType", None)
    if connection_type:
        for name in ("AutoConnection", "DirectConnection", "QueuedConnection", "BlockingQueuedConnection", "UniqueConnection"):
            if hasattr(connection_type, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(connection_type, name))
                except Exception:
                    pass

    window_type = getattr(QtCore.Qt, "WindowType", None)
    if window_type:
        for name in (
            "Widget",
            "Window",
            "Dialog",
            "Sheet",
            "Drawer",
            "Popup",
            "Tool",
            "ToolTip",
            "SplashScreen",
            "Desktop",
            "SubWindow",
            "ForeignWindow",
            "CoverWindow",
            "WindowTitleHint",
            "WindowSystemMenuHint",
            "WindowMinimizeButtonHint",
            "WindowMaximizeButtonHint",
            "WindowCloseButtonHint",
            "WindowContextHelpButtonHint",
            "MacWindowToolBarButtonHint",
            "WindowFullscreenButtonHint",
            "BypassWindowManagerHint",
            "CustomizeWindowHint",
            "WindowStaysOnTopHint",
            "WindowStaysOnBottomHint",
            "WindowTransparentForInput",
            "WindowOverridesSystemGestures",
            "WindowDoesNotAcceptFocus",
            "WindowType_Mask",
            "FramelessWindowHint",
        ):
            if hasattr(window_type, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(window_type, name))
                except Exception:
                    pass
        if not hasattr(QtCore.Qt, "WindowMinMaxButtonsHint"):
            min_hint = getattr(QtCore.Qt, "WindowMinimizeButtonHint", None)
            max_hint = getattr(QtCore.Qt, "WindowMaximizeButtonHint", None)
            if min_hint is not None and max_hint is not None:
                try:
                    setattr(QtCore.Qt, "WindowMinMaxButtonsHint", min_hint | max_hint)
                except Exception:
                    pass

    tool_button_style = getattr(QtCore.Qt, "ToolButtonStyle", None)
    if tool_button_style:
        for name in (
            "ToolButtonIconOnly",
            "ToolButtonTextOnly",
            "ToolButtonTextBesideIcon",
            "ToolButtonTextUnderIcon",
            "ToolButtonFollowStyle",
        ):
            if hasattr(tool_button_style, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(tool_button_style, name))
                except Exception:
                    pass

    shortcut_context = getattr(QtCore.Qt, "ShortcutContext", None)
    if shortcut_context:
        for name in ("WidgetShortcut", "WindowShortcut", "ApplicationShortcut", "WidgetWithChildrenShortcut"):
            if hasattr(shortcut_context, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(shortcut_context, name))
                except Exception:
                    pass

    focus_policy = getattr(QtCore.Qt, "FocusPolicy", None)
    if focus_policy:
        for name in ("NoFocus", "TabFocus", "ClickFocus", "StrongFocus", "WheelFocus"):
            if hasattr(focus_policy, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(focus_policy, name))
                except Exception:
                    pass

    focus_reason = getattr(QtCore.Qt, "FocusReason", None)
    if focus_reason:
        for name in ("MouseFocusReason", "TabFocusReason", "BacktabFocusReason", "ActiveWindowFocusReason", "ShortcutFocusReason", "OtherFocusReason"):
            if hasattr(focus_reason, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(focus_reason, name))
                except Exception:
                    pass

    orientation = getattr(QtCore.Qt, "Orientation", None)
    if orientation:
        for name in ("Horizontal", "Vertical"):
            if hasattr(orientation, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(orientation, name))
                except Exception:
                    pass

    drop_action = getattr(QtCore.Qt, "DropAction", None)
    if drop_action:
        for name in ("CopyAction", "MoveAction", "LinkAction", "ActionMask", "IgnoreAction"):
            if hasattr(drop_action, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(drop_action, name))
                except Exception:
                    pass

    text_interaction = getattr(QtCore.Qt, "TextInteractionFlag", None)
    if text_interaction:
        for name in (
            "NoTextInteraction",
            "TextSelectableByMouse",
            "TextSelectableByKeyboard",
            "LinksAccessibleByMouse",
            "LinksAccessibleByKeyboard",
            "TextEditable",
            "TextEditorInteraction",
            "TextBrowserInteraction",
        ):
            if hasattr(text_interaction, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(text_interaction, name))
                except Exception:
                    pass

    window_modality = getattr(QtCore.Qt, "WindowModality", None)
    if window_modality:
        for name in ("NonModal", "WindowModal", "ApplicationModal"):
            if hasattr(window_modality, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(window_modality, name))
                except Exception:
                    pass

    window_state = getattr(QtCore.Qt, "WindowState", None)
    if window_state:
        for name in ("WindowNoState", "WindowMinimized", "WindowMaximized", "WindowFullScreen", "WindowActive"):
            if hasattr(window_state, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(window_state, name))
                except Exception:
                    pass

    app_attr = getattr(QtCore.Qt, "ApplicationAttribute", None)
    if app_attr:
        for name in ("AA_EnableHighDpiScaling", "AA_ShareOpenGLContexts", "AA_UseHighDpiPixmaps"):
            if hasattr(app_attr, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(app_attr, name))
                except Exception:
                    pass

    key_enum = getattr(QtCore.Qt, "Key", None)
    if key_enum:
        for name, val in vars(key_enum).items():
            if name.startswith("_"):
                continue
            if not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, val)
                except Exception:
                    pass

    aspect_ratio_mode = getattr(QtCore.Qt, "AspectRatioMode", None)
    if aspect_ratio_mode:
        for name in ("IgnoreAspectRatio", "KeepAspectRatio", "KeepAspectRatioByExpanding"):
            if hasattr(aspect_ratio_mode, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(aspect_ratio_mode, name))
                except Exception:
                    pass

    scroll_bar_policy = getattr(QtCore.Qt, "ScrollBarPolicy", None)
    if scroll_bar_policy:
        for name in ("ScrollBarAsNeeded", "ScrollBarAlwaysOff", "ScrollBarAlwaysOn"):
            if hasattr(scroll_bar_policy, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(scroll_bar_policy, name))
                except Exception:
                    pass

    transformation_mode = getattr(QtCore.Qt, "TransformationMode", None)
    if transformation_mode:
        for name in ("FastTransformation", "SmoothTransformation"):
            if hasattr(transformation_mode, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(transformation_mode, name))
                except Exception:
                    pass

    fill_rule = getattr(QtCore.Qt, "FillRule", None)
    if fill_rule:
        for name in ("OddEvenFill", "WindingFill"):
            if hasattr(fill_rule, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(fill_rule, name))
                except Exception:
                    pass

    QPainter = getattr(QtGui, "QPainter", None)
    if QPainter and not hasattr(QPainter, "Antialiasing"):
        render_hint = getattr(QPainter, "RenderHint", None)
        if render_hint:
            for name in (
                "Antialiasing",
                "TextAntialiasing",
                "SmoothPixmapTransform",
                "HighQualityAntialiasing",
                "NonCosmeticDefaultPen",
                "LosslessImageRendering",
            ):
                if hasattr(render_hint, name) and not hasattr(QPainter, name):
                    try:
                        setattr(QPainter, name, getattr(render_hint, name))
                    except Exception:
                        pass
    if QPainter and not hasattr(QPainter, "CompositionMode_SourceOver"):
        composition_mode = getattr(QPainter, "CompositionMode", None)
        if composition_mode:
            for name in (
                "CompositionMode_SourceOver",
                "CompositionMode_DestinationOver",
                "CompositionMode_Clear",
                "CompositionMode_Source",
                "CompositionMode_Destination",
                "CompositionMode_SourceIn",
                "CompositionMode_DestinationIn",
                "CompositionMode_SourceOut",
                "CompositionMode_DestinationOut",
                "CompositionMode_SourceAtop",
                "CompositionMode_DestinationAtop",
                "CompositionMode_Xor",
                "CompositionMode_Plus",
                "CompositionMode_Multiply",
                "CompositionMode_Screen",
                "CompositionMode_Overlay",
                "CompositionMode_Darken",
                "CompositionMode_Lighten",
                "CompositionMode_ColorDodge",
                "CompositionMode_ColorBurn",
                "CompositionMode_HardLight",
                "CompositionMode_SoftLight",
                "CompositionMode_Difference",
                "CompositionMode_Exclusion",
            ):
                if hasattr(composition_mode, name) and not hasattr(QPainter, name):
                    try:
                        setattr(QPainter, name, getattr(composition_mode, name))
                    except Exception:
                        pass

    global_color = getattr(QtCore.Qt, "GlobalColor", None)
    if global_color:
        for name in (
            "transparent",
            "black",
            "white",
            "red",
            "darkRed",
            "green",
            "darkGreen",
            "blue",
            "darkBlue",
            "cyan",
            "darkCyan",
            "magenta",
            "darkMagenta",
            "yellow",
            "darkYellow",
            "gray",
            "darkGray",
            "lightGray",
            "color0",
            "color1",
        ):
            if hasattr(global_color, name) and not hasattr(QtCore.Qt, name):
                try:
                    setattr(QtCore.Qt, name, getattr(global_color, name))
                except Exception:
                    pass

    QSizePolicy = getattr(QtWidgets, "QSizePolicy", None)
    if QSizePolicy and not hasattr(QSizePolicy, "Expanding"):
        policy = getattr(QSizePolicy, "Policy", None)
        if policy:
            for name in ("Fixed", "Minimum", "Maximum", "Preferred", "Expanding", "MinimumExpanding", "Ignored"):
                if hasattr(policy, name) and not hasattr(QSizePolicy, name):
                    try:
                        setattr(QSizePolicy, name, getattr(policy, name))
                    except Exception:
                        pass

    QAbstractItemView = getattr(QtWidgets, "QAbstractItemView", None)
    if QAbstractItemView and not hasattr(QAbstractItemView, "ExtendedSelection"):
        selection_mode = getattr(QAbstractItemView, "SelectionMode", None)
        if selection_mode:
            for name in (
                "NoSelection",
                "SingleSelection",
                "MultiSelection",
                "ExtendedSelection",
                "ContiguousSelection",
            ):
                if hasattr(selection_mode, name) and not hasattr(QAbstractItemView, name):
                    try:
                        setattr(QAbstractItemView, name, getattr(selection_mode, name))
                    except Exception:
                        pass
        selection_behavior = getattr(QAbstractItemView, "SelectionBehavior", None)
        if selection_behavior:
            for name in ("SelectItems", "SelectRows", "SelectColumns"):
                if hasattr(selection_behavior, name) and not hasattr(QAbstractItemView, name):
                    try:
                        setattr(QAbstractItemView, name, getattr(selection_behavior, name))
                    except Exception:
                        pass
        scroll_hint = getattr(QAbstractItemView, "ScrollHint", None)
        if scroll_hint:
            for name in ("EnsureVisible", "PositionAtTop", "PositionAtBottom", "PositionAtCenter"):
                if hasattr(scroll_hint, name) and not hasattr(QAbstractItemView, name):
                    try:
                        setattr(QAbstractItemView, name, getattr(scroll_hint, name))
                    except Exception:
                        pass

    QSortFilterProxyModel = getattr(QtCore, "QSortFilterProxyModel", None)
    if QSortFilterProxyModel:
        if not hasattr(QSortFilterProxyModel, "setFilterRegExp") and hasattr(QSortFilterProxyModel, "setFilterRegularExpression"):
            def _setFilterRegExp(self, exp):
                return self.setFilterRegularExpression(exp)
            try:
                setattr(QSortFilterProxyModel, "setFilterRegExp", _setFilterRegExp)
            except Exception:
                pass
        if not hasattr(QSortFilterProxyModel, "filterRegExp") and hasattr(QSortFilterProxyModel, "filterRegularExpression"):
            def _filterRegExp(self):
                return self.filterRegularExpression()
            try:
                setattr(QSortFilterProxyModel, "filterRegExp", _filterRegExp)
            except Exception:
                pass

    QListView = getattr(QtWidgets, "QListView", None)
    if QListView and not hasattr(QListView, "IconMode"):
        view_mode = getattr(QListView, "ViewMode", None)
        if view_mode:
            for name in ("ListMode", "IconMode"):
                if hasattr(view_mode, name) and not hasattr(QListView, name):
                    try:
                        setattr(QListView, name, getattr(view_mode, name))
                    except Exception:
                        pass
        flow = getattr(QListView, "Flow", None)
        if flow:
            for name in ("LeftToRight", "TopToBottom"):
                if hasattr(flow, name) and not hasattr(QListView, name):
                    try:
                        setattr(QListView, name, getattr(flow, name))
                    except Exception:
                        pass
        layout_mode = getattr(QListView, "LayoutMode", None)
        if layout_mode:
            for name in ("SinglePass", "Batched"):
                if hasattr(layout_mode, name) and not hasattr(QListView, name):
                    try:
                        setattr(QListView, name, getattr(layout_mode, name))
                    except Exception:
                        pass
        resize_mode = getattr(QListView, "ResizeMode", None)
        if resize_mode:
            for name in ("Fixed", "Adjust"):
                if hasattr(resize_mode, name) and not hasattr(QListView, name):
                    try:
                        setattr(QListView, name, getattr(resize_mode, name))
                    except Exception:
                        pass
        selection_behavior = getattr(QListView, "SelectionBehavior", None)
        if selection_behavior:
            for name in ("SelectItems", "SelectRows", "SelectColumns"):
                if hasattr(selection_behavior, name) and not hasattr(QListView, name):
                    try:
                        setattr(QListView, name, getattr(selection_behavior, name))
                    except Exception:
                        pass
        selection_mode = getattr(QListView, "SelectionMode", None)
        if selection_mode:
            for name in ("NoSelection", "SingleSelection", "MultiSelection", "ExtendedSelection", "ContiguousSelection"):
                if hasattr(selection_mode, name) and not hasattr(QListView, name):
                    try:
                        setattr(QListView, name, getattr(selection_mode, name))
                    except Exception:
                        pass

    QFrame = getattr(QtWidgets, "QFrame", None)
    if QFrame and not hasattr(QFrame, "NoFrame"):
        frame_shape = getattr(QFrame, "Shape", None)
        if frame_shape:
            for name in ("NoFrame", "Box", "Panel", "StyledPanel", "HLine", "VLine", "WinPanel"):
                if hasattr(frame_shape, name) and not hasattr(QFrame, name):
                    try:
                        setattr(QFrame, name, getattr(frame_shape, name))
                    except Exception:
                        pass
        frame_shadow = getattr(QFrame, "Shadow", None)
        if frame_shadow:
            for name in ("Plain", "Raised", "Sunken"):
                if hasattr(frame_shadow, name) and not hasattr(QFrame, name):
                    try:
                        setattr(QFrame, name, getattr(frame_shadow, name))
                    except Exception:
                        pass

    QTreeView = getattr(QtWidgets, "QTreeView", None)
    if QTreeView and not hasattr(QTreeView, "SelectRows"):
        selection_behavior = getattr(QTreeView, "SelectionBehavior", None)
        if selection_behavior:
            for name in ("SelectItems", "SelectRows", "SelectColumns"):
                if hasattr(selection_behavior, name) and not hasattr(QTreeView, name):
                    try:
                        setattr(QTreeView, name, getattr(selection_behavior, name))
                    except Exception:
                        pass

    QHeaderView = getattr(QtWidgets, "QHeaderView", None)
    if QHeaderView and not hasattr(QHeaderView, "Stretch"):
        resize_mode = getattr(QHeaderView, "ResizeMode", None)
        if resize_mode:
            for name in ("Interactive", "Stretch", "Fixed", "ResizeToContents", "Custom"):
                if hasattr(resize_mode, name) and not hasattr(QHeaderView, name):
                    try:
                        setattr(QHeaderView, name, getattr(resize_mode, name))
                    except Exception:
                        pass

    QDockWidget = getattr(QtWidgets, "QDockWidget", None)
    if QDockWidget and not hasattr(QDockWidget, "DockWidgetClosable"):
        dock_feature = getattr(QDockWidget, "DockWidgetFeature", None)
        if dock_feature:
            for name in (
                "DockWidgetClosable",
                "DockWidgetMovable",
                "DockWidgetFloatable",
                "DockWidgetVerticalTitleBar",
                "DockWidgetFeatureMask",
                "NoDockWidgetFeatures",
            ):
                if hasattr(dock_feature, name) and not hasattr(QDockWidget, name):
                    try:
                        setattr(QDockWidget, name, getattr(dock_feature, name))
                    except Exception:
                        pass

    QTabWidget = getattr(QtWidgets, "QTabWidget", None)
    if QTabWidget and not hasattr(QTabWidget, "South"):
        tab_position = getattr(QTabWidget, "TabPosition", None)
        if tab_position:
            for name in ("North", "South", "West", "East"):
                if hasattr(tab_position, name) and not hasattr(QTabWidget, name):
                    try:
                        setattr(QTabWidget, name, getattr(tab_position, name))
                    except Exception:
                        pass

    QPalette = getattr(QtGui, "QPalette", None)
    if QPalette and not hasattr(QPalette, "Window"):
        color_role = getattr(QPalette, "ColorRole", None)
        if color_role:
            for name in (
                "WindowText",
                "Button",
                "Light",
                "Midlight",
                "Dark",
                "Mid",
                "Text",
                "BrightText",
                "ButtonText",
                "Base",
                "Window",
                "Shadow",
                "Highlight",
                "HighlightedText",
                "Link",
                "LinkVisited",
                "AlternateBase",
                "NoRole",
                "ToolTipBase",
                "ToolTipText",
                "PlaceholderText",
            ):
                if hasattr(color_role, name) and not hasattr(QPalette, name):
                    try:
                        setattr(QPalette, name, getattr(color_role, name))
                    except Exception:
                        pass

    QDialogButtonBox = getattr(QtWidgets, "QDialogButtonBox", None)
    if QDialogButtonBox:
        if not hasattr(QDialogButtonBox, "RejectRole"):
            button_role = getattr(QDialogButtonBox, "ButtonRole", None)
            if button_role:
                for name in (
                    "InvalidRole",
                    "AcceptRole",
                    "RejectRole",
                    "DestructiveRole",
                    "ActionRole",
                    "HelpRole",
                    "YesRole",
                    "NoRole",
                    "ResetRole",
                    "ApplyRole",
                    "NRoles",
                ):
                    if hasattr(button_role, name) and not hasattr(QDialogButtonBox, name):
                        try:
                            setattr(QDialogButtonBox, name, getattr(button_role, name))
                        except Exception:
                            pass
        if not hasattr(QDialogButtonBox, "Ok"):
            std_button = getattr(QDialogButtonBox, "StandardButton", None)
            if std_button:
                for name in (
                    "NoButton",
                    "Ok",
                    "Save",
                    "SaveAll",
                    "Open",
                    "Yes",
                    "YesToAll",
                    "No",
                    "NoToAll",
                    "Abort",
                    "Retry",
                    "Ignore",
                    "Close",
                    "Cancel",
                    "Discard",
                    "Help",
                    "Apply",
                    "Reset",
                    "RestoreDefaults",
                ):
                    if hasattr(std_button, name) and not hasattr(QDialogButtonBox, name):
                        try:
                            setattr(QDialogButtonBox, name, getattr(std_button, name))
                        except Exception:
                            pass

    QDialog = getattr(QtWidgets, "QDialog", None)
    if QDialog and not hasattr(QDialog, "Accepted"):
        dialog_code = getattr(QDialog, "DialogCode", None)
        if dialog_code:
            for name in ("Rejected", "Accepted"):
                if hasattr(dialog_code, name) and not hasattr(QDialog, name):
                    try:
                        setattr(QDialog, name, getattr(dialog_code, name))
                    except Exception:
                        pass

    QImage = getattr(QtGui, "QImage", None)
    if QImage and not hasattr(QImage, "Format_ARGB32_Premultiplied"):
        image_format = getattr(QImage, "Format", None)
        if image_format:
            for name in (
                "Format_Invalid",
                "Format_Mono",
                "Format_MonoLSB",
                "Format_Indexed8",
                "Format_RGB32",
                "Format_ARGB32",
                "Format_ARGB32_Premultiplied",
                "Format_RGB16",
                "Format_ARGB8565_Premultiplied",
                "Format_RGB666",
                "Format_ARGB6666_Premultiplied",
                "Format_RGB555",
                "Format_ARGB8555_Premultiplied",
                "Format_RGB888",
                "Format_RGB444",
                "Format_ARGB4444_Premultiplied",
                "Format_RGBX8888",
                "Format_RGBA8888",
                "Format_RGBA8888_Premultiplied",
                "Format_BGR30",
                "Format_A2BGR30_Premultiplied",
                "Format_RGB30",
                "Format_A2RGB30_Premultiplied",
                "Format_Alpha8",
                "Format_Grayscale8",
            ):
                if hasattr(image_format, name) and not hasattr(QImage, name):
                    try:
                        setattr(QImage, name, getattr(image_format, name))
                    except Exception:
                        pass

    QRegion = getattr(QtGui, "QRegion", None)
    if QRegion and not hasattr(QRegion, "Rectangle"):
        region_type = getattr(QRegion, "RegionType", None)
        if region_type:
            for name in ("Rectangle", "Ellipse"):
                if hasattr(region_type, name) and not hasattr(QRegion, name):
                    try:
                        setattr(QRegion, name, getattr(region_type, name))
                    except Exception:
                        pass

    QStyle = getattr(QtWidgets, "QStyle", None)
    if QStyle and not hasattr(QStyle, "State_Selected"):
        state_flag = getattr(QStyle, "StateFlag", None)
        if state_flag:
            for name in (
                "State_None",
                "State_Enabled",
                "State_Raised",
                "State_Sunken",
                "State_Off",
                "State_NoChange",
                "State_On",
                "State_DownArrow",
                "State_Horizontal",
                "State_HasFocus",
                "State_Top",
                "State_Bottom",
                "State_FocusAtBorder",
                "State_AutoRaise",
                "State_MouseOver",
                "State_UpArrow",
                "State_Selected",
                "State_Active",
                "State_Window",
                "State_Open",
                "State_Children",
                "State_Item",
                "State_Sibling",
                "State_Editing",
                "State_KeyboardFocusChange",
                "State_ReadOnly",
                "State_Small",
                "State_Mini",
            ):
                if hasattr(state_flag, name) and not hasattr(QStyle, name):
                    try:
                        setattr(QStyle, name, getattr(state_flag, name))
                    except Exception:
                        pass
    if QStyle and not hasattr(QStyle, "SP_DialogApplyButton"):
        standard_pixmap = getattr(QStyle, "StandardPixmap", None)
        if standard_pixmap:
            for name, value in vars(standard_pixmap).items():
                if not name.startswith("SP_") or hasattr(QStyle, name):
                    continue
                try:
                    setattr(QStyle, name, value)
                except Exception:
                    pass

    QComboBox = getattr(QtWidgets, "QComboBox", None)
    if QComboBox and not hasattr(QComboBox, "AdjustToMinimumContentsLengthWithIcon"):
        size_adjust = getattr(QComboBox, "SizeAdjustPolicy", None)
        if size_adjust:
            for name in (
                "AdjustToContents",
                "AdjustToContentsOnFirstShow",
                "AdjustToMinimumContentsLength",
                "AdjustToMinimumContentsLengthWithIcon",
            ):
                if hasattr(size_adjust, name) and not hasattr(QComboBox, name):
                    try:
                        setattr(QComboBox, name, getattr(size_adjust, name))
                    except Exception:
                        pass

    QColorDialog = getattr(QtWidgets, "QColorDialog", None)
    if QColorDialog and not hasattr(QColorDialog, "DontUseNativeDialog"):
        option = getattr(QColorDialog, "ColorDialogOption", None)
        if option:
            for name in (
                "ShowAlphaChannel",
                "NoButtons",
                "DontUseNativeDialog",
            ):
                if hasattr(option, name) and not hasattr(QColorDialog, name):
                    try:
                        setattr(QColorDialog, name, getattr(option, name))
                    except Exception:
                        pass

    QFileDialog = getattr(QtWidgets, "QFileDialog", None)
    if QFileDialog and not hasattr(QFileDialog, "ShowDirsOnly"):
        option = getattr(QFileDialog, "Option", None)
        if option:
            for name in ("ShowDirsOnly", "DontResolveSymlinks", "DontConfirmOverwrite", "DontUseNativeDialog", "ReadOnly", "HideNameFilterDetails"):
                if hasattr(option, name) and not hasattr(QFileDialog, name):
                    try:
                        setattr(QFileDialog, name, getattr(option, name))
                    except Exception:
                        pass

    QItemSelectionModel = getattr(QtCore, "QItemSelectionModel", None)
    if QItemSelectionModel and not hasattr(QItemSelectionModel, "Select"):
        selection_flag = getattr(QItemSelectionModel, "SelectionFlag", None)
        if selection_flag:
            for name in (
                "NoUpdate",
                "Clear",
                "Select",
                "Deselect",
                "Toggle",
                "Current",
                "Rows",
                "Columns",
                "SelectCurrent",
                "ToggleCurrent",
                "ClearAndSelect",
            ):
                if hasattr(selection_flag, name) and not hasattr(QItemSelectionModel, name):
                    try:
                        setattr(QItemSelectionModel, name, getattr(selection_flag, name))
                    except Exception:
                        pass

    QMessageBox = getattr(QtWidgets, "QMessageBox", None)
    if QMessageBox and not hasattr(QMessageBox, "Cancel"):
        std_button = getattr(QMessageBox, "StandardButton", None)
        if std_button:
            for name in (
                "NoButton",
                "Ok",
                "Save",
                "SaveAll",
                "Open",
                "Yes",
                "YesToAll",
                "No",
                "NoToAll",
                "Abort",
                "Retry",
                "Ignore",
                "Close",
                "Cancel",
                "Discard",
                "Help",
                "Apply",
                "Reset",
                "RestoreDefaults",
            ):
                if hasattr(std_button, name) and not hasattr(QMessageBox, name):
                    try:
                        setattr(QMessageBox, name, getattr(std_button, name))
                    except Exception:
                        pass
        icon = getattr(QMessageBox, "Icon", None)
        if icon:
            for name in ("NoIcon", "Information", "Warning", "Critical", "Question"):
                if hasattr(icon, name) and not hasattr(QMessageBox, name):
                    try:
                        setattr(QMessageBox, name, getattr(icon, name))
                    except Exception:
                        pass
        color_group = getattr(QPalette, "ColorGroup", None)
        if color_group:
            for name in ("Disabled", "Active", "Inactive", "Normal", "All"):
                if hasattr(color_group, name) and not hasattr(QPalette, name):
                    try:
                        setattr(QPalette, name, getattr(color_group, name))
                    except Exception:
                        pass

    if QRegularExpression and not hasattr(QRegularExpression, "CaseInsensitiveOption"):
        pattern_option = getattr(QRegularExpression, "PatternOption", None)
        if pattern_option:
            for name in ("NoPatternOption", "CaseInsensitiveOption", "DotMatchesEverythingOption", "MultilineOption"):
                if hasattr(pattern_option, name) and not hasattr(QRegularExpression, name):
                    try:
                        setattr(QRegularExpression, name, getattr(pattern_option, name))
                    except Exception:
                        pass
    if QRegularExpression and not hasattr(QRegularExpression, "indexIn"):
        def _index_in(self, text):
            if text is None:
                text = ""
            return 0 if self.match(text).hasMatch() else -1
        try:
            setattr(QRegularExpression, "indexIn", _index_in)
        except Exception:
            pass

    QStyle = getattr(QtWidgets, "QStyle", None)
    if QStyle:
        sub_element = getattr(QStyle, "SubElement", None)
        if sub_element:
            for name, val in vars(sub_element).items():
                if name.startswith("_"):
                    continue
                if not hasattr(QStyle, name):
                    try:
                        setattr(QStyle, name, val)
                    except Exception:
                        pass

    QFont = getattr(QtGui, "QFont", None)
    if QFont:
        weight_enum = getattr(QFont, "Weight", None)
        if weight_enum:
            for name, val in vars(weight_enum).items():
                if name.startswith("_"):
                    continue
                if not hasattr(QFont, name):
                    try:
                        setattr(QFont, name, val)
                    except Exception:
                        pass

    QColor = getattr(QtGui, "QColor", None)
    if QColor and not hasattr(QColor, "HexArgb"):
        name_format = getattr(QColor, "NameFormat", None)
        if name_format:
            for name in ("HexRgb", "HexArgb"):
                if hasattr(name_format, name) and not hasattr(QColor, name):
                    try:
                        setattr(QColor, name, getattr(name_format, name))
                    except Exception:
                        pass

    QTextCursor = getattr(QtGui, "QTextCursor", None)
    if QTextCursor and not hasattr(QTextCursor, "StartOfLine"):
        move_operation = getattr(QTextCursor, "MoveOperation", None)
        if move_operation:
            for name in ("Up", "Down", "StartOfLine", "EndOfLine", "Start", "End"):
                if hasattr(move_operation, name) and not hasattr(QTextCursor, name):
                    try:
                        setattr(QTextCursor, name, getattr(move_operation, name))
                    except Exception:
                        pass

    QStyle = getattr(QtWidgets, "QStyle", None)
    if QStyle:
        complex_control = getattr(QStyle, "ComplexControl", None)
        if complex_control:
            for name, val in vars(complex_control).items():
                if name.startswith("_"):
                    continue
                if not hasattr(QStyle, name):
                    try:
                        setattr(QStyle, name, val)
                    except Exception:
                        pass
        sub_control = getattr(QStyle, "SubControl", None)
        if sub_control:
            for name, val in vars(sub_control).items():
                if name.startswith("_"):
                    continue
                if not hasattr(QStyle, name):
                    try:
                        setattr(QStyle, name, val)
                    except Exception:
                        pass

    # Qt6 renamed exec_() -> exec(); backfill exec_ on common classes.
    def _exec_wrapper(self, *args, **kwargs):
        return self.exec(*args, **kwargs)

    if QtWidgets:
        for name in (
            "QDialog",
            "QMessageBox",
            "QMenu",
            "QInputDialog",
            "QFileDialog",
            "QColorDialog",
            "QFontDialog",
            "QProgressDialog",
        ):
            cls = getattr(QtWidgets, name, None)
            if cls and hasattr(cls, "exec") and not hasattr(cls, "exec_"):
                try:
                    setattr(cls, "exec_", _exec_wrapper)
                except Exception:
                    pass
    if QtGui:
        cls = getattr(QtGui, "QDrag", None)
        if cls and hasattr(cls, "exec") and not hasattr(cls, "exec_"):
            try:
                setattr(cls, "exec_", _exec_wrapper)
            except Exception:
                pass

    if not hasattr(QtCore, "QSignalTransition"):
        try:
            if QT_API == "pyqt6":
                import PyQt6.QtStateMachine as QtStateMachineMod  # type: ignore
            else:
                import PySide6.QtStateMachine as QtStateMachineMod  # type: ignore
            q_signal_transition = getattr(QtStateMachineMod, "QSignalTransition", None)
            if q_signal_transition is not None:
                setattr(QtCore, "QSignalTransition", q_signal_transition)
        except Exception:
            pass


def _binding_order(env_value: str) -> List[str]:
    """Compute binding preference order based on env."""
    value = (env_value or "auto").strip().lower()
    if value in ("pyqt6", "pyside6", "pyqt5"):
        return [value]
    return ["pyqt6", "pyside6", "pyqt5"]


def _import_binding(name: str) -> Tuple:
    """Import a specific binding and return modules and helpers."""
    if name == "pyqt6":
        import PyQt6.QtCore as QtCoreMod
        import PyQt6.QtGui as QtGuiMod
        import PyQt6.QtWidgets as QtWidgetsMod
        try:
            import PyQt6.uic as uicMod
        except Exception:
            uicMod = None
        try:
            import PyQt6.QtStateMachine as QtStateMachineMod  # type: ignore
            q_state = getattr(QtStateMachineMod, "QState", None)
            q_state_machine = getattr(QtStateMachineMod, "QStateMachine", None)
        except Exception:
            QtStateMachineMod = None
            q_state = getattr(QtCoreMod, "QState", None)
            q_state_machine = getattr(QtCoreMod, "QStateMachine", None)

        if q_state is None or q_state_machine is None:
            raise ImportError("PyQt6 QtStateMachine module not available (QState/QStateMachine missing)")
        QtSvgMod = None
        try:
            import PyQt6.QtSvg as QtSvgMod  # type: ignore
        except Exception:
            pass
        return (
            "pyqt6",
            QtCoreMod,
            QtGuiMod,
            QtWidgetsMod,
            QtSvgMod,
            QtCoreMod.pyqtSignal,
            QtCoreMod.pyqtSlot,
            QtCoreMod.pyqtProperty,
            QtCoreMod.QRegularExpression,
            q_state,
            q_state_machine,
            uicMod,
            QtCoreMod.QT_VERSION_STR,
            QtCoreMod.PYQT_VERSION_STR,
            QtCoreMod.PYQT_VERSION_STR,
        )

    if name == "pyside6":
        import PySide6.QtCore as QtCoreMod
        import PySide6.QtGui as QtGuiMod
        import PySide6.QtWidgets as QtWidgetsMod
        QtUiToolsMod = None
        try:
            import PySide6.QtStateMachine as QtStateMachineMod  # type: ignore
            q_state = getattr(QtStateMachineMod, "QState", None)
            q_state_machine = getattr(QtStateMachineMod, "QStateMachine", None)
        except Exception:
            QtStateMachineMod = None
            q_state = getattr(QtCoreMod, "QState", None)
            q_state_machine = getattr(QtCoreMod, "QStateMachine", None)

        if q_state is None or q_state_machine is None:
            raise ImportError("PySide6 QtStateMachine module not available (QState/QStateMachine missing)")
        QtSvgMod = None
        try:
            import PySide6.QtSvg as QtSvgMod  # type: ignore
        except Exception:
            pass
        return (
            "pyside6",
            QtCoreMod,
            QtGuiMod,
            QtWidgetsMod,
            QtSvgMod,
            QtCoreMod.Signal,
            QtCoreMod.Slot,
            QtCoreMod.Property,
            QtCoreMod.QRegularExpression,
            q_state,
            q_state_machine,
            QtUiToolsMod,
            QtCoreMod.__version__,  # PySide binds Qt version here
            QtCoreMod.__version__,
            QtCoreMod.__version__,
        )

    if name == "pyqt5":
        import PyQt5.QtCore as QtCoreMod
        import PyQt5.QtGui as QtGuiMod
        import PyQt5.QtWidgets as QtWidgetsMod
        import PyQt5.uic as uicMod
        q_state = getattr(QtCoreMod, "QState", None)
        q_state_machine = getattr(QtCoreMod, "QStateMachine", None)
        if q_state is None or q_state_machine is None:
            raise ImportError("PyQt5 missing QState/QStateMachine in QtCore")

        QtSvgMod = None
        try:
            import PyQt5.QtSvg as QtSvgMod  # type: ignore
        except Exception:
            pass
        return (
            "pyqt5",
            QtCoreMod,
            QtGuiMod,
            QtWidgetsMod,
            QtSvgMod,
            QtCoreMod.pyqtSignal,
            QtCoreMod.pyqtSlot,
            QtCoreMod.pyqtProperty,
            QtCoreMod.QRegularExpression,
            q_state,
            q_state_machine,
            uicMod,
            QtCoreMod.QT_VERSION_STR,
            QtCoreMod.PYQT_VERSION_STR,
            QtCoreMod.PYQT_VERSION_STR,
        )

    raise ImportError(f"Unknown binding '{name}'")


def _select_binding() -> str:
    """Select and load the first available binding."""
    global QtCore, QtGui, QtWidgets, QtSvg
    global Signal, Slot, Property, QRegularExpression, QByteArray, QDir, QLibraryInfo, QSignalTransition
    global QState, QStateMachine, uic, QT_API, QT_VERSION_STR, PYQT_VERSION_STR, BINDING_VERSION_STR, _MODULES
    global _FAILED_IMPORT, _SELECTING

    if _FAILED_IMPORT:
        raise _FAILED_IMPORT
    if _SELECTING:
        # Prevent recursion if an import path triggers __getattr__ again
        raise ImportError("qt_api: binding selection already in progress")
    _SELECTING = True

    requested = os.environ.get("OPENSHOT_QT_API", "auto")
    attempts = _binding_order(requested)
    errors = []
    logger.info("qt_api: requested=%s, attempts=%s", requested, attempts)

    for candidate in attempts:
        try:
            (
                QT_API,
                QtCore,
                QtGui,
                QtWidgets,
                QtSvg,
                Signal,
                Slot,
                Property,
                QRegularExpression,
                QState,
                QStateMachine,
                uic,
                QT_VERSION_STR,
                PYQT_VERSION_STR,
                BINDING_VERSION_STR,
            ) = _import_binding(candidate)
            logger.info(
                "qt_api: selected %s (Qt %s, binding %s)",
                QT_API,
                QT_VERSION_STR,
                BINDING_VERSION_STR,
            )
            _MODULES = [
                m
                for m in (
                    QtCore,
                    QtGui,
                    QtWidgets,
                    QtSvg,
                )
                if m is not None
            ]
            _patch_enums_for_qt6()
            QByteArray = getattr(QtCore, "QByteArray", None)
            QDir = getattr(QtCore, "QDir", None)
            QLibraryInfo = getattr(QtCore, "QLibraryInfo", None)
            QSignalTransition = getattr(QtCore, "QSignalTransition", None)
            _FAILED_IMPORT = None
            _SELECTING = False
            return QT_API
        except Exception as ex:  # noqa: BLE001
            if requested == "auto":
                logger.info("qt_api: skipping %s during auto-detect: %s", candidate, ex)
            else:
                logger.warning("qt_api: failed to load %s: %s", candidate, ex)
            errors.append(f"{candidate}: {ex}")

    _SELECTING = False
    _FAILED_IMPORT = ImportError(
        "No suitable Qt binding found. Tried: "
        + ", ".join(errors)
        + ". Set OPENSHOT_QT_API to force a specific binding."
    )
    raise _FAILED_IMPORT


def load_ui(path: str, baseinstance=None):
    """Load a Qt Designer .ui file using the active binding."""
    if QT_API is None:
        _select_binding()

    if QT_API in ("pyqt6", "pyqt5"):
        from importlib import import_module

        uic = import_module(f"{'PyQt6' if QT_API == 'pyqt6' else 'PyQt5'}.uic")
        return uic.loadUi(path, baseinstance)

    # PySide
    from importlib import import_module

    if QT_API != "pyside6":
        raise RuntimeError(f"Unsupported Qt binding for load_ui(): {QT_API}")
    QtUiTools = import_module("PySide6.QtUiTools")  # type: ignore
    if baseinstance is not None:
        class UiLoader(QtUiTools.QUiLoader):
            def __init__(self, base):
                super().__init__(base)
                self.base = base

            def createWidget(self, class_name, parent=None, name=""):
                if parent is None and self.base is not None:
                    return self.base
                widget = super().createWidget(class_name, parent, name)
                if self.base is not None and name:
                    setattr(self.base, name, widget)
                return widget

            def createAction(self, parent=None, name=""):
                if parent is None and self.base is not None:
                    parent = self.base
                action = super().createAction(parent, name)
                if self.base is not None and name:
                    setattr(self.base, name, action)
                return action

        loader = UiLoader(baseinstance)
        setattr(baseinstance, "_qt_ui_loader", loader)
    else:
        loader = QtUiTools.QUiLoader()
    ui_file = QtCore.QFile(path)
    if not ui_file.open(QtCore.QFile.ReadOnly):
        raise IOError(f"Cannot open UI file: {path}")
    try:
        widget = loader.load(ui_file)
        if baseinstance is not None:
            if widget is not None and widget is not baseinstance:
                setattr(baseinstance, "_qt_loaded_ui", widget)
                main_window_type = getattr(QtWidgets, "QMainWindow", None)
                if main_window_type and isinstance(baseinstance, main_window_type) and isinstance(widget, main_window_type):
                    central = widget.centralWidget()
                    if central is not None:
                        baseinstance.setCentralWidget(central)
                    menubar = widget.menuBar()
                    if menubar is not None:
                        baseinstance.setMenuBar(menubar)
                    statusbar = widget.statusBar()
                    if statusbar is not None:
                        baseinstance.setStatusBar(statusbar)
                    tool_bar_type = getattr(QtWidgets, "QToolBar", None)
                    if tool_bar_type:
                        for toolbar in widget.findChildren(tool_bar_type):
                            baseinstance.addToolBar(toolbar)
                    dock_type = getattr(QtWidgets, "QDockWidget", None)
                    if dock_type:
                        for dock in widget.findChildren(dock_type):
                            try:
                                area = widget.dockWidgetArea(dock)
                            except Exception:
                                area = None
                            if area is None or area == QtCore.Qt.NoDockWidgetArea:
                                baseinstance.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
                            else:
                                baseinstance.addDockWidget(area, dock)
            if widget is not None:
                main_window_type = getattr(QtWidgets, "QMainWindow", None)
                if main_window_type and isinstance(baseinstance, main_window_type):
                    root = baseinstance
                else:
                    root = widget
            else:
                root = baseinstance
            qaction_type = getattr(QtGui, "QAction", None)
            actions = []
            seen = set()
            if qaction_type is not None:
                for holder in (root, baseinstance, loader):
                    if holder is None:
                        continue
                    for act in holder.findChildren(qaction_type):
                        ident = id(act)
                        if ident in seen:
                            continue
                        seen.add(ident)
                        actions.append(act)
                for act in actions:
                    try:
                        act.setParent(baseinstance)
                    except Exception:
                        pass
            for obj in root.findChildren(QtCore.QObject):
                obj_name = obj.objectName()
                if obj_name and not hasattr(baseinstance, obj_name):
                    setattr(baseinstance, obj_name, obj)
            if widget is not None and widget is not baseinstance:
                widget_type = getattr(QtWidgets, "QWidget", None)
                if widget_type and isinstance(baseinstance, widget_type) and isinstance(widget, widget_type):
                    try:
                        if baseinstance.layout() is None and widget.layout() is not None:
                            baseinstance.setLayout(widget.layout())
                    except Exception:
                        pass
            return baseinstance
        return widget
    finally:
        ui_file.close()


def ensure_binding():
    """Force binding selection (useful for early importers)."""
    if QT_API is None:
        _select_binding()
    return QT_API


def __getattr__(name):
    """Lazy attribute forwarding so `from qt_api import QIcon` works."""
    global QSignalTransition, QState, QStateMachine
    if QT_API is None:
        _select_binding()
    # Expose common QtCore symbols directly
    if name in ("pyqtSignal", "Signal"):
        return Signal
    if name in ("pyqtSlot", "Slot"):
        return Slot
    if name in ("pyqtProperty", "Property"):
        return Property
    if name in ("QByteArray", "QLibraryInfo", "QDir"):
        value = getattr(QtCore, name)
        globals()[name] = value
        return value
    if name in ("QSignalTransition", "QState", "QStateMachine"):
        if QState is None or QStateMachine is None:
            try:
                if QT_API == "pyqt6":
                    import PyQt6.QtStateMachine as QtStateMachine  # type: ignore
                elif QT_API == "pyside6":
                    import PySide6.QtStateMachine as QtStateMachine  # type: ignore
                elif QT_API == "pyqt5":
                    QtStateMachine = QtCore
                else:
                    QtStateMachine = QtCore
                QState = getattr(QtStateMachine, "QState", None)
                QStateMachine = getattr(QtStateMachine, "QStateMachine", None)
                QSignalTransition = getattr(QtStateMachine, "QSignalTransition", None)
            except Exception:
                pass
        if name == "QSignalTransition":
            return QSignalTransition
        return QState if name == "QState" else QStateMachine
    if name == "QAbstractItemModelTester":
        try:
            if QT_API == "pyqt6":
                import PyQt6.QtTest as QtTest  # type: ignore
            elif QT_API == "pyside6":
                import PySide6.QtTest as QtTest  # type: ignore
            elif QT_API == "pyqt5":
                import PyQt5.QtTest as QtTest  # type: ignore
            else:
                QtTest = None
            if QtTest is not None and hasattr(QtTest, "QAbstractItemModelTester"):
                return QtTest.QAbstractItemModelTester
        except Exception:
            pass
    for module in _MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(name)


# Select binding immediately on import for visibility
ensure_binding()

__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QtSvg",
    "Signal",
    "Slot",
    "Property",
    "QRegularExpression",
    "QState",
    "QStateMachine",
    # Commonly used Qt types
    "QSignalTransition",
    "QState",
    "QStateMachine",
    "QByteArray",
    "QDir",
    "QLibraryInfo",
    "QT_API",
    "QT_VERSION_STR",
    "PYQT_VERSION_STR",
    "BINDING_VERSION_STR",
    "ensure_binding",
    "load_ui",
    "unwrapinstance",
    "wrapinstance",
    "isdeleted",
    "modifiers_has",
    "clear_override_cursor",
]
