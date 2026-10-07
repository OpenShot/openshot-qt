"""Qt-free protocol helpers shared by the CLI and session host."""
import json
import os
import struct
import sys
from pathlib import Path

VERSION = 1
MAX_MESSAGE = 8 * 1024 * 1024
MAX_DIMENSION = 4096
MAX_PIXELS = 8 * 1024 * 1024
MAX_SAMPLES = 64


class CommandError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.details = code, details


def session_dir():
    return Path(os.environ.get('OPENSHOT_SESSION_DIR', str(Path.home() / '.openshot_qt' / 'sessions')))


def parse_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise CommandError('invalid_json', "Duplicate JSON field '{}'. Each field must occur once.".format(key))
            result[key] = value
        return result
    def constant(value):
        raise CommandError('invalid_json', value + ' is not a finite JSON number. Use a numeric value.')
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except json.JSONDecodeError as exc:
        raise CommandError('invalid_json', 'JSON syntax error at line {}, column {}: {}. Use double-quoted keys/strings and no trailing commas.'.format(exc.lineno, exc.colno, exc.msg),
                           {'line': exc.lineno, 'column': exc.colno})


def encode(value):
    payload = json.dumps(value, allow_nan=False).encode('utf-8')
    if len(payload) > MAX_MESSAGE:
        raise CommandError('message_too_large', 'Message exceeds 8 MiB; use smaller batches or queries.')
    return struct.pack('!I', len(payload)) + payload


def decode(buffer):
    """Consume one framed message, retaining incomplete or subsequent messages."""
    if len(buffer) < 4:
        return None
    size = struct.unpack('!I', buffer[:4])[0]
    if size > MAX_MESSAGE:
        raise CommandError('message_too_large', 'Message exceeds 8 MiB.')
    if len(buffer) < size + 4:
        return None
    value = parse_json(bytes(buffer[4:4 + size]).decode('utf-8'))
    del buffer[:4 + size]
    return value


def dimensions(width, height):
    if not (1 <= width <= MAX_DIMENSION and 1 <= height <= MAX_DIMENSION
            and width * height <= MAX_PIXELS):
        raise CommandError('image_limit', 'Images require dimensions 1..4096 and at most 8,388,608 pixels.')


def records():
    result = []
    for path in sorted(session_dir().glob('*.json')):
        try:
            item = json.loads(path.read_text())
            if item.get('protocol') == VERSION:
                result.append(item)
        except (OSError, ValueError):
            continue
    return result


def network():
    # Import only for connections: --help and agent guidance require no Qt/native engine.
    from importlib import import_module
    from qt_api import QT_API
    binding = {'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API]
    return import_module(binding + '.QtNetwork')


def cli_command(*arguments):
    """Launch the console entry point in source, installed, and frozen builds."""
    if getattr(sys, 'frozen', False):
        executable = Path(sys.executable).with_name('openshot-cli.exe' if os.name == 'nt' else 'openshot-cli')
        if not executable.is_file():
            raise CommandError('missing_cli', 'Packaged openshot-cli executable is missing: ' + str(executable))
        return [str(executable), *arguments]
    return [sys.executable, str(Path(__file__).resolve().parents[2] / 'cli.py'), *arguments]
