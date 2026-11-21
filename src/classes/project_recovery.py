# Copyright (c) 2026 OpenShot Studios, LLC
# This file is part of OpenShot Video Editor (https://www.openshot.org).
# SPDX-License-Identifier: GPL-3.0-or-later
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Video Editor. If not, see <https://www.gnu.org/licenses/>.

"""Conservative project recovery. Never modify an input file or guess missing edits."""
import json
import math
import os
import re
import zipfile


def _json_decoder(repair_numbers=False):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(
                    "Duplicate JSON field: {}. Try a previous version; choosing a value could lose edits.".format(key))
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Invalid JSON number: " + value)

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Invalid JSON number: " + value)
        return number

    return json.JSONDecoder(object_pairs_hook=unique_object,
                            parse_constant=float if repair_numbers else invalid_constant,
                            parse_float=float if repair_numbers else finite_float)


def decode_json(text):
    return _json_decoder().decode(text)


def clip_problem(clip):
    if not isinstance(clip, dict):
        return "clip is not an object"
    for key in ("position", "start", "end", "layer"):
        value = clip.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return "missing or invalid " + key
    if clip["start"] < 0 or clip["end"] < clip["start"]:
        return "invalid source range"
    if (not isinstance(clip.get("reader"), dict)
            or not isinstance(clip["reader"].get("type"), str) or not clip["reader"]["type"]):
        return "missing media reader"
    if "path" in clip["reader"] and not isinstance(clip["reader"]["path"], str):
        return "invalid media reader path"
    if not isinstance(clip.get("effects", []), list) or any(
            not isinstance(effect, dict) for effect in clip.get("effects", [])):
        return "invalid effects collection"
    return None


def validate_project(data):
    if not isinstance(data, dict):
        raise ValueError("The project must be a JSON object.")
    for key in ("clips", "files", "layers"):
        if not isinstance(data.get(key), list):
            raise ValueError("Missing or invalid project collection: " + key)
    for key in ("files", "layers", "effects", "markers"):
        collection = data.get(key, [])
        if not isinstance(collection, list) or any(not isinstance(item, dict) for item in collection):
            raise ValueError("Invalid project collection: " + key)
    history = data.get("history")
    if history and (not isinstance(history, dict) or any(
            not isinstance(history.get(key, []), list) for key in ("undo", "redo"))):
        raise ValueError("Invalid undo/redo history. Try a previous version.")
    if isinstance(history, dict):
        for collection in ('undo', 'redo'):
            for index, action in enumerate(history.get(collection, [])):
                if _history_problem(action):
                    raise ValueError("Invalid {} history entry {}. Try a previous version.".format(
                        collection, index + 1))
    fps = data.get("fps", {"num": 30, "den": 1})
    if not isinstance(fps, dict):
        raise ValueError("Invalid project frame rate.")
    for key in ("num", "den"):
        value = fps.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError("Invalid project frame rate.")
    problems = []
    for index, clip in enumerate(data["clips"]):
        problem = clip_problem(clip)
        if problem:
            identity = clip.get("id", "unknown") if isinstance(clip, dict) else "unknown"
            problems.append("Clip {} ({}): {}".format(index + 1, identity, problem))
    if problems:
        raise ValueError("Incomplete project clips:\n" + "\n".join(problems))


def _quote_legacy_keys(text):
    """Repair the 2.6.0 lost-key-quotes bug without touching JSON strings."""
    tokens = re.compile(r'"(?:[^"\\]|\\.)*"|(?P<key>[A-Za-z_]\w*)\s*:')
    quoted = 0

    def replace(match):
        nonlocal quoted
        key = match.group('key')
        if key is None:
            return match.group(0)
        preceding = match.start() - 1
        while preceding >= 0 and text[preceding].isspace():
            preceding -= 1
        if preceding < 0 or text[preceding] not in '{,':
            return match.group(0)
        quoted += 1
        return json.dumps(key) + match.group(0)[len(key):]

    repaired = tokens.sub(replace, text)
    return repaired, quoted


def _clean_waveforms(value, changes, location="project"):
    """Only regenerable UI envelopes may contain nonfinite numbers in recovery."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "ui" and isinstance(child, dict):
                for cache in ("audio_data", "audio_data_rms"):
                    samples = child.get(cache)
                    if isinstance(samples, list) and any(
                            isinstance(v, float) and not math.isfinite(v) for v in samples):
                        child[cache] = []
                        changes.append("Discarded invalid waveform cache at {}/ui/{}; it can be regenerated.".format(
                            location, cache))
            _clean_waveforms(child, changes, location + "/" + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _clean_waveforms(child, changes, location + "/" + str(index))


def _history_problem(action):
    return (not isinstance(action, dict)
            or action.get("type") not in ("load", "insert", "update", "delete")
            or (action.get("type") != "load" and (
                not isinstance(action.get("key"), list) or not action["key"]))
            or ("transaction" in action and not isinstance(action["transaction"], str)))


def _repair_history(data, changes):
    history = data.get("history")
    if history is None:
        return
    if not isinstance(history, dict):
        data["history"] = {"undo": [], "redo": []}
        changes.append("Discarded invalid undo/redo history; current project edits were retained.")
        return
    for side in ("undo", "redo"):
        actions = history.get(side, [])
        if not isinstance(actions, list):
            history[side] = []
            changes.append("Discarded invalid {} history stack.".format(side))
            continue
        bad = [i for i, action in enumerate(actions) if _history_problem(action)]
        if not bad:
            continue
        # Both stacks pop from the end. Retain a reachable suffix, never jump
        # over a broken action or split an async/non-contiguous transaction.
        cutoff = max(bad) + 1
        while cutoff < len(actions):
            removed = {a.get("transaction") for a in actions[:cutoff]
                       if isinstance(a, dict) and isinstance(a.get("transaction"), str)}
            crossing = [i for i in range(cutoff, len(actions))
                        if actions[i].get("transaction") in removed]
            if not crossing:
                break
            cutoff = max(crossing) + 1
        history[side] = actions[cutoff:]
        changes.append("Truncated {} history: discarded {} of {} actions through the damaged transaction; retained {} recent actions.".format(
            side, cutoff, len(actions), len(actions) - cutoff))


def _recover_before_history(text, changes):
    """Read complete root fields only; never synthesize partial current edits."""
    decoder = _json_decoder(repair_numbers=True)
    pos = len(text) - len(text.lstrip())
    if text[pos:pos + 1] != "{":
        raise ValueError("No complete project before damaged history.")
    pos += 1
    data = {}
    while True:
        while pos < len(text) and text[pos].isspace():
            pos += 1
        key, pos = decoder.raw_decode(text, pos)
        if not isinstance(key, str) or key in data:
            raise ValueError("Invalid or duplicate project field before history.")
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if text[pos:pos + 1] != ":":
            raise ValueError("Invalid project field before history.")
        pos += 1
        while pos < len(text) and text[pos].isspace():
            pos += 1
        try:
            value, end = decoder.raw_decode(text, pos)
        except json.JSONDecodeError:
            if key != "history":
                raise
            # Validation below requires complete clips, files, layers and all
            # other current fields encountered before history.
            validate_project(data)
            data["history"] = {"undo": [], "redo": []}
            changes.append("Discarded unreadable undo/redo history and the unreadable remainder of the file (which may include version metadata); retained complete current project fields preceding history.")
            return data
        data[key] = value
        pos = end
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if text[pos:pos + 1] != ",":
            raise ValueError("Damage is outside undo/redo history.")
        pos += 1


def _repair_path_quotes(text, original_path, changes):
    """Correct only invalid, line-delimited path strings verified on disk."""
    def replace(match):
        line = match.group(0)
        try:
            decode_json("{" + line.strip().rstrip(",") + "}")
            return line
        except ValueError:
            pass
        if not original_path or str(original_path).startswith("content://"):
            raise ValueError("Filename quote repair requires a local project path to verify the media exists.")
        body = match.group(2)
        # Historical path normalization changed escaped opening quotes into
        # /". Also consider literal slashes so a real subdirectory is retained.
        candidates = {}
        for raw in (body, body.replace('/"', '\\"')):
            raw = raw.replace('\\\\"', '\\"')
            raw = re.sub(r'(?<!\\)"', r'\\"', raw)
            try:
                path = decode_json('"' + raw + '"')
            except ValueError:
                continue
            if "@assets" in path:
                from classes.assets import get_assets_path
                resolved = path.replace("@assets", get_assets_path(original_path, create_paths=False))
            elif path.startswith("@"):
                continue
            else:
                resolved = os.path.join(os.path.dirname(os.path.abspath(original_path)), path)
            if os.path.isfile(resolved):
                candidates[os.path.realpath(resolved)] = path
        if len(candidates) != 1:
            raise ValueError("Cannot safely repair filename quotes: expected one existing file, found {}.".format(len(candidates)))
        path = next(iter(candidates.values()))
        changes.append("Repaired filename quote escaping and verified existing file: " + path)
        return match.group(1) + json.dumps(path, ensure_ascii=False)[1:-1] + match.group(3)
    return re.sub(r'(^[ \t]*"path"[ \t]*:[ \t]*")(.*)(",?[ \t]*\r?$)', replace, text, flags=re.M)


def parse_project(text, repair=False, original_path=None):
    changes = []
    if repair:
        if re.search(r'"openshot-qt"\s*:\s*"2\.6\.0"', text):
            text, count = _quote_legacy_keys(text)
            if count:
                changes.append("Quoted {} project keys affected by the OpenShot 2.6.0 bug.".format(count))
        if text.startswith("\ufeff"):
            text = text[1:]
            changes.append("Removed the UTF-8 byte-order mark.")
        # Only commas followed by a closing delimiter outside JSON strings.
        result = []
        quoted = escaped = False
        removed = 0
        for index, char in enumerate(text):
            if not quoted and char == ",":
                following = index + 1
                while following < len(text) and text[following].isspace():
                    following += 1
                preceding = index - 1
                while preceding >= 0 and text[preceding].isspace():
                    preceding -= 1
                if (following < len(text) and text[following] in "]}"
                        and preceding >= 0 and text[preceding] not in "[{,:"):
                    removed += 1
                    continue
            result.append(char)
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
        text = "".join(result)
        if removed:
            changes.append("Removed {} trailing comma(s).".format(removed))
    try:
        data = _json_decoder(repair_numbers=repair).decode(text)
    except json.JSONDecodeError as error:
        if repair:
            try:
                text = _repair_path_quotes(text, original_path, changes)
                try:
                    data = _json_decoder(repair_numbers=True).decode(text)
                except json.JSONDecodeError:
                    data = _recover_before_history(text, changes)
            except ValueError as recovery_error:
                raise ValueError("Unable to repair project: " + str(recovery_error)) from recovery_error
        else:
            raise ValueError("Invalid JSON at line {}, column {}: {}. Try a previous version instead of guessing missing edits.".format(
                error.lineno, error.colno, error.msg)) from error
    if repair:
        _clean_waveforms(data, changes)
        # Nonfinite data outside a discarded waveform cache is never accepted.
        decode_json(json.dumps(data))
        if isinstance(data, dict):
            _repair_history(data, changes)
    if repair and isinstance(data, dict) and isinstance(data.get("clips"), list):
        kept = []
        for index, clip in enumerate(data["clips"]):
            problem = clip_problem(clip)
            if problem:
                identity = clip.get("id", "unknown") if isinstance(clip, dict) else "unknown"
                position = clip.get("position", "unknown") if isinstance(clip, dict) else "unknown"
                changes.append("Omit clip {} (ID {}, position {} seconds): {}.".format(
                    index + 1, identity, position, problem))
            else:
                kept.append(clip)
        data["clips"] = kept
    validate_project(data)
    return data, changes


def _archive_matches(archive, original_path):
    if not archive.comment:
        return True  # Older archives only identify the basename; the UI explains this.
    try:
        metadata = json.loads(archive.comment.decode("utf-8"))
        return metadata.get("project_path") == os.path.realpath(original_path)
    except (ValueError, UnicodeError, AttributeError):
        return False


def previous_versions(file_path, recovery_dir):
    """Match exact basenames and, for newer archives, the recorded original path."""
    stem = os.path.splitext(os.path.basename(file_path))[0]
    if not os.path.isdir(recovery_dir):
        return []
    matches = []
    for name in os.listdir(recovery_dir):
        timestamp, separator, remainder = name.partition("-")
        if separator and timestamp.isdigit() and remainder in (stem + ".zip", stem + ".osp"):
            path = os.path.join(recovery_dir, name)
            # Leave unreadable archives selectable so the user sees a useful
            # validation error rather than silently hiding a recovery candidate.
            try:
                if path.endswith(".zip"):
                    with zipfile.ZipFile(path) as archive:
                        if not _archive_matches(archive, file_path):
                            continue
            except (OSError, zipfile.BadZipFile):
                pass
            matches.append(path)
    return sorted(matches, reverse=True)


def read_version(path, original_path):
    if path.endswith(".zip"):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if names != [os.path.basename(original_path)] or not _archive_matches(archive, original_path):
                raise ValueError("This recovery archive does not contain exactly the expected project file.")
            return archive.read(names[0]).decode("utf-8")
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def save_recovered_copy(data, original_path, destination):
    """Copy assets and publish JSON without changing the damaged source."""
    import shutil
    from classes.assets import get_assets_path
    from classes.json_data import JsonDataStore
    from qt_api import is_content_uri
    if is_content_uri(original_path) or is_content_uri(destination):
        raise ValueError("Recovery currently requires local project files.")
    validate_project(data)
    store = JsonDataStore()
    contents = store.convert_paths_to_absolute(original_path, json.dumps(data, ensure_ascii=False))
    data = json.loads(contents)
    source_assets = get_assets_path(original_path, create_paths=False)
    target_assets = get_assets_path(destination, create_paths=False)
    if os.path.exists(destination) or os.path.exists(target_assets):
        raise ValueError("Choose a new filename with no existing project or assets folder.")
    copied = False
    reserved = False
    try:
        # Reserve the filename exclusively; write_to_file still publishes atomically.
        with open(destination, "x", encoding="utf-8"):
            reserved = True
        if os.path.isdir(source_assets):
            copied = True
            shutil.copytree(source_assets, target_assets)

            def relocate(value):
                if isinstance(value, dict):
                    for key, child in value.items():
                        if (key in ("path", "image", "resource", "protobuf_data_path", "lut_path")
                                and isinstance(child, str)):
                            if child.startswith(source_assets + os.sep):
                                value[key] = target_assets + child[len(source_assets):]
                        else:
                            relocate(child)
                elif isinstance(value, list):
                    for child in value:
                        relocate(child)
            relocate(data)
        store.write_to_file(destination, data, path_mode="relative", previous_path=destination, compact=True)
    except Exception:
        if reserved:
            os.unlink(destination)
        if copied and os.path.isdir(target_assets):
            shutil.rmtree(target_assets)
        raise


def archive_previous_version(file_path, recovery_dir, timestamp):
    """Publish a complete archive before allowing the project to be replaced."""
    import tempfile
    os.makedirs(recovery_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(file_path))[0]
    destination = os.path.join(recovery_dir, '{}-{}.zip'.format(timestamp, stem))
    while os.path.exists(destination):
        timestamp += 1
        destination = os.path.join(recovery_dir, '{}-{}.zip'.format(timestamp, stem))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=recovery_dir, prefix='.recovery-', suffix='.tmp', delete=False) as stream:
            temporary = stream.name
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.write(file_path, os.path.basename(file_path))
            archive.comment = json.dumps({'project_path': os.path.realpath(file_path)}).encode('utf-8')
        # Windows requires write access when flushing a file to disk.
        with open(temporary, 'r+b') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        return destination
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def save_recovery_automatically(data, original_path):
    """Choose an unused sibling filename; recovery never asks for a location."""
    from classes.assets import get_assets_path
    stem = os.path.splitext(original_path)[0]
    for number in range(1, 10000):
        suffix = '-recovered' if number == 1 else '-recovered-{}'.format(number)
        destination = stem + suffix + '.osp'
        if os.path.lexists(destination) or os.path.lexists(get_assets_path(destination, create_paths=False)):
            continue
        try:
            save_recovered_copy(data, original_path, destination)
        except FileExistsError:
            continue  # Another process reserved that name; try the next one.
        return destination
    raise OSError('Could not find an unused filename for the recovery copy.')
