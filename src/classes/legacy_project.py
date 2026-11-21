"""Read OpenShot 1.x pickle data without importing or constructing its classes.

Only inert records and the narrowly checked Python 2 reconstruction helper are
available to the pickle VM. Application objects, builtins with capabilities,
persistent objects, and extension-registry globals are never resolved.
"""

import io
import math
import ntpath
import os
# Only the restricted Unpickler below executes pickle opcodes.
import pickle  # nosec B403
# Disassembles the stream without executing it.
import pickletools  # nosec B403


class _Record:
    def __new__(cls, *args, **kwargs):
        if cls not in _RECORD_TYPES or args or kwargs:
            raise pickle.UnpicklingError("Invalid legacy object construction")
        return object.__new__(cls)

    def __setstate__(self, state):
        if not isinstance(state, dict) or any(
                not isinstance(key, str) or key.startswith('__') for key in state):
            raise pickle.UnpicklingError("Invalid legacy object state")
        self.__dict__.update(state)


# These are data holders, not the operational classes named in the input.
_NAMES = {
    'project': ('project',),
    'sequences': ('sequence',),
    'track': ('track',),
    'clip': ('clip',),
    'keyframe': ('keyframe',),
    'files': ('OpenShotFile', 'OpenShotFolder'),
    'transition': ('transition',),
    'effect': ('effect',),
    'marker': ('marker',),
}
_RECORDS = {name: type(name, (_Record,), {})
            for names in _NAMES.values() for name in names}
_RECORD_TYPES = frozenset(_RECORDS.values())
_GLOBALS = {(prefix + module, name): _RECORDS[name]
            for prefix in ('classes.', 'openshot.classes.', 'classes.legacy.openshot.classes.')
            for module, names in _NAMES.items() for name in names}


def _reconstruct(cls, base, state):
    """Python 2/early protocol compatibility, without calling supplied objects."""
    if cls not in _RECORD_TYPES or base is not object or state is not None:
        raise pickle.UnpicklingError("Invalid legacy reconstruction")
    return object.__new__(cls)


class LegacyProjectUnpickler(pickle.Unpickler):
    def __init__(self, stream):
        contents = stream.read()
        # EXT can use CPython's global cache without calling find_class. Inspect
        # this same immutable byte stream before initializing the pickle VM.
        try:
            end = -1
            for opcode, _argument, position in pickletools.genops(contents):
                if opcode.name in ('EXT1', 'EXT2', 'EXT4', 'PERSID', 'BINPERSID'):
                    raise pickle.UnpicklingError("Unsupported legacy opcode: " + opcode.name)
                end = position
            if end + 1 != len(contents):
                raise pickle.UnpicklingError("Trailing legacy project data")
        except (ValueError, IndexError) as ex:
            raise pickle.UnpicklingError("Malformed legacy pickle") from ex
        super().__init__(io.BytesIO(contents), fix_imports=True, encoding='UTF-8')

    def find_class(self, module, name):
        record = _GLOBALS.get((module, name))
        if record is not None:
            return record
        if (module, name) in (('copy_reg', '_reconstructor'), ('copyreg', '_reconstructor')):
            return _reconstruct
        if (module, name) in (('__builtin__', 'object'), ('builtins', 'object')):
            return object
        raise pickle.UnpicklingError("Forbidden legacy global: %s.%s" % (module, name))

    def persistent_load(self, pid):
        raise pickle.UnpicklingError("Persistent legacy objects are not supported")

    def load(self):
        result = super().load()
        _validate_graph(result)
        _validate_project(result)
        return result


def read_legacy_project(file_path):
    with open(file_path, 'rb') as stream:
        return LegacyProjectUnpickler(stream).load()


def _validate_graph(root):
    """Reject capability objects and malformed state; preserve shared/cyclic data."""
    pending = [root]
    visited = set()
    while pending:
        value = pending.pop()
        if id(value) in visited:
            continue
        visited.add(id(value))
        kind = type(value)
        if kind in (str, bytes, int, bool, type(None)):
            continue
        if kind is float and math.isfinite(value):
            continue
        if kind in (list, tuple):
            pending.extend(value)
        elif kind is dict:
            pending.extend(value.keys())
            pending.extend(value.values())
        elif kind in _RECORD_TYPES:
            pending.extend(vars(value).values())
        else:
            raise pickle.UnpicklingError("Invalid legacy value type")


def _validate_project(project):
    """Validate the fields the existing converter consumes before it mutates UI data."""
    def record(value, name):
        # _validate_graph already requires exact registered record types; none
        # of those types derive from another registered record type.
        if not isinstance(value, _RECORDS[name]):
            raise pickle.UnpicklingError("Invalid legacy " + name)

    def sequence(value):
        if type(value) not in (list, tuple):
            raise pickle.UnpicklingError("Invalid legacy collection")
        return value

    def field(value, key, kinds):
        item = getattr(value, key, None)
        if type(item) not in kinds:
            raise pickle.UnpicklingError("Invalid legacy field: " + key)
        return item

    record(project, 'project')
    record(getattr(project, 'project_folder', None), 'OpenShotFolder')
    for item in sequence(getattr(project.project_folder, 'items', None)):
        if isinstance(item, _RECORDS['OpenShotFolder']):
            continue  # The existing importer skips subfolders.
        record(item, 'OpenShotFile')
        field(item, 'name', (str,))
        field(item, 'unique_id', (str,))
    sequences = sequence(getattr(project, 'sequences', None))
    if not sequences:
        raise pickle.UnpicklingError("Legacy project has no sequences")
    for seq in sequences:
        record(seq, 'sequence')
        for track in sequence(getattr(seq, 'tracks', None)):
            record(track, 'track')
            field(track, 'name', (str,))
            for clip in sequence(getattr(track, 'clips', None)):
                record(clip, 'clip')
                record(getattr(clip, 'file_object', None), 'OpenShotFile')
                field(clip.file_object, 'unique_id', (str,))
                for key in ('start_time', 'end_time', 'position_on_track', 'volume'):
                    field(clip, key, (int, float))
                for stream in ('video', 'audio'):
                    for direction in ('in', 'out'):
                        enabled = field(clip, stream + '_fade_' + direction, (bool, int))
                        if not enabled:
                            continue  # The converter never reads an inactive fade amount.
                        amount = stream + '_fade_' + direction + '_amount'
                        if amount not in vars(clip) and stream + '_fade_amount' in vars(clip):
                            # Early 1.x files shared one duration for both fade
                            # directions. Preserve it; do not invent a duration.
                            setattr(clip, amount, field(clip, stream + '_fade_amount', (int, float)))
                        field(clip, amount, (int, float))
            for transition in sequence(getattr(track, 'transitions', None)):
                record(transition, 'transition')
                field(transition, 'resource', (str, type(None)))
                field(transition, 'reverse', (bool, int))
                for key in ('length', 'position_on_track', 'softness'):
                    field(transition, key, (int, float))


def legacy_media_path(project_path, media_path):
    """Resolve portable relative media beside the project, retaining absolute paths."""
    if (not media_path or media_path.startswith(("/", "\\"))
            or ntpath.splitdrive(media_path)[0]):
        return media_path
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(project_path)), media_path))
