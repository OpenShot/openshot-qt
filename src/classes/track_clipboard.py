"""Copy complete tracks without sharing editable clip, effect, or asset identities."""
from copy import deepcopy
from classes.app import get_app
from classes.query import Track, Clip, Transition, File
from classes.clipboard import ClipboardManager
from classes.keyframe_scaler import KeyframeScaler
from classes.path_utils import absolute_media_path


def _absolute_paths(value):
    if isinstance(value, dict):
        return {key: absolute_media_path(child) if key == "path" and isinstance(child, str) and child
                else _absolute_paths(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_absolute_paths(child) for child in value]
    return value


def copy_track(track_id, cut=False):
    app = get_app()
    track = Track.get(id=track_id)
    if not track or (cut and (track.data.get("lock") or len(app.project.get("layers")) <= 1)):
        return False
    clips = [clip.data for clip in Clip.filter(layer=track.data["number"])]
    file_ids = {clip.get("file_id") for clip in clips if clip.get("file_id")}
    files = [file.data for file_id in file_ids if (file := File.get(id=file_id))]
    snapshot = Track()
    snapshot.id = track.id
    snapshot.data = _absolute_paths(deepcopy({
        "track": track.data, "clips": clips,
        "transitions": [t.data for t in Transition.filter(layer=track.data["number"])],
        "files": files, "fps": app.project.get("fps")}))
    mime = ClipboardManager.to_mime(snapshot)
    if not mime.hasText():
        return False
    app.clipboard().setMimeData(mime)
    if cut:
        app.window.selected_tracks = [track_id]
        app.window.actionRemoveTrack_trigger()
    return True


def _collect_ids(value, mapping, generate):
    if isinstance(value, dict):
        ident = value.get("id")
        if isinstance(ident, str) and ident not in mapping:
            mapping[ident] = generate()
        for child in value.values():
            _collect_ids(child, mapping, generate)
    elif isinstance(value, list):
        for child in value:
            _collect_ids(child, mapping, generate)


def _remap(value, mapping):
    if isinstance(value, dict):
        return {key: mapping.get(child, child) if (key == "id" or key.endswith("_id")) and isinstance(child, str)
                else _remap(child, mapping) for key, child in value.items()}
    if isinstance(value, list):
        return [_remap(child, mapping) for child in value]
    return value


def paste_track(target_id=None):
    app = get_app()
    snapshot = ClipboardManager.from_mime(app.clipboard().mimeData())
    if not isinstance(snapshot, Track):
        return None
    payload = deepcopy(snapshot.data)
    layers = sorted(app.project.get("layers"), key=lambda layer: layer["number"])
    target = Track.get(id=target_id) if target_id else None
    if target:
        index = next(i for i, layer in enumerate(layers) if layer["id"] == target.id)
        above = layers[index + 1]["number"] if index + 1 < len(layers) else target.data["number"] + 2000000
        if above - target.data["number"] <= 1:
            app.window.renumber_all_layers()
            return paste_track(target_id)
        number = (target.data["number"] + above) // 2
    else:
        number = layers[-1]["number"] + 1000000 if layers else 1000000
    timeline = app.window.timeline
    transaction = app.updates.transaction_id
    app.updates.transaction_id = timeline.get_uuid()
    app.window.IgnoreUpdates.emit(True, True)
    mapping = {}
    try:
        for file_data in payload["files"]:
            existing = File.get(id=file_data["id"])
            if existing and existing.data.get("path") == file_data.get("path") and file_data.get("type") != "QtTextReader":
                mapping[file_data["id"]] = existing.id
            else:
                new_id = app.project.generate_id()
                mapping[file_data["id"]] = new_id
                app.updates.insert(["files"], dict(file_data, id=new_id))
        _collect_ids(payload, mapping, app.project.generate_id)
        payload = _remap(payload, mapping)
        source_fps = snapshot.data["fps"]
        target_fps = app.project.get("fps")
        factor = (target_fps["num"] * source_fps["den"]) / (target_fps["den"] * source_fps["num"])
        if factor != 1:
            scaler = KeyframeScaler(factor)
            scaler({"clips": payload["clips"], "effects": payload["transitions"]})
            # Track effect coordinates, like clip curves, use project frames.
            for effect in payload["track"].get("effects", []):
                scaler({"effects": [effect]})
        new_track = dict(payload["track"], number=number)
        app.updates.insert(["layers"], new_track)
        for collection, key in (("clips", "clips"), ("transitions", "effects")):
            for item in payload[collection]:
                item["layer"] = number
                item.pop("selected", None)
                app.updates.insert([key], item)
        app.window.selected_tracks = [new_track["id"]]
        timeline._extend_timeline_to_fit_items()
    finally:
        app.updates.transaction_id = transaction
        app.window.IgnoreUpdates.emit(False, True)
    app.window.refreshFrameSignal.emit()
    return new_track["id"]
