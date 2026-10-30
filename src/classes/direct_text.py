"""Generated text assets: project JSON is authoritative; images are disposable caches."""
import copy
import hashlib
import json
import os
import tempfile
from functools import lru_cache

import openshot
from qt_api import QColor, QFont, QImage, QPainter, QTextDocument, QTextOption, Qt


# Preferred default faces, in order. A generic name like "Sans Serif" becomes
# the legacy "MS Shell Dlg 2" on Windows, so default to a real installed font.
DEFAULT_FONTS = ("Segoe UI", "Helvetica Neue", "Noto Sans", "DejaVu Sans", "Liberation Sans", "Arial")
_default_font = None
# Style that remembers the last text made; the words and box size are per text.
REMEMBERED_STYLE = ("font_family", "font_bold", "font_italic", "font_size", "letter_spacing", "line_spacing",
                    "color", "background", "alignment", "background_padding", "background_corner",
                    "stroke_width", "stroke", "border_width", "border")


def default_font_family():
    global _default_font
    if _default_font is None:
        from qt_api import QFontDatabase, QFontInfo
        families = set(QFontDatabase().families())
        _default_font = next((name for name in DEFAULT_FONTS if name in families), None) \
            or QFontInfo(QFont()).family()
    return _default_font


def default_text(width, height):
    return dict(version=1, text="Text", font_family=default_font_family(), font_bold=False, font_italic=False,
                font_size=max(12, round(height / 15)), letter_spacing=0, line_spacing=1.0,
                color="#ffffff", background="#00000000", alignment="center", background_padding=12,
                background_corner=0,
                stroke_width=0, stroke="#000000", border_width=0, border="#ffffff",
                width=max(64, round(width / 2)), height=max(64, round(height / 8)))


def new_text_style(width, height):
    """Defaults for a new text, with the style of the last text made."""
    from classes.app import get_app
    style = default_text(width, height)
    style["text"] = get_app()._tr("Text")
    remembered = get_app().get_settings().get("text-last-style")
    if isinstance(remembered, dict):
        style.update({key: remembered[key] for key in REMEMBERED_STYLE if key in remembered})
    return style


def remember_style(style, keys=REMEMBERED_STYLE):
    """Remember these style keys for the next new text."""
    from classes.app import get_app
    settings = get_app().get_settings()
    remembered = settings.get("text-last-style")
    remembered = remembered if isinstance(remembered, dict) else {}
    remembered.update({key: style[key] for key in keys if key in REMEMBERED_STYLE and key in style})
    settings.set("text-last-style", remembered)


def reset_style(style, width, height):
    """Factory style, keeping the words."""
    reset = default_text(width, height)
    reset["text"] = style.get("text", reset["text"])
    return fit_height(reset)


def text_font(style):
    font = QFont(style["font_family"])
    font.setPixelSize(int(style["font_size"]))
    font.setBold(bool(style.get("font_bold", False)))
    font.setItalic(bool(style.get("font_italic", False)))
    if style.get("letter_spacing"):
        font.setLetterSpacing(QFont.AbsoluteSpacing, float(style["letter_spacing"]))
    return font


def fit_height(style):
    """The box is as tall as its text, so it shrinks again when the text does."""
    style["height"] = int(text_document(style).size().height() + 1)
    return style


def text_document(style, document=None, outline=False):
    """Use the same document layout for the in-preview editor and raster.

    The reader draws the outline as its own pass behind the letters, so a
    wide outline grows outward instead of covering them: outline=True
    builds that pass, and the default builds the fill on top of it."""
    document = document or QTextDocument()
    document.setDefaultFont(text_font(style))
    document.setDocumentMargin(style.get("background_padding", 12))
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
    option.setAlignment({"left": Qt.AlignLeft, "center": Qt.AlignHCenter, "right": Qt.AlignRight}[style["alignment"]])
    document.setDefaultTextOption(option)
    document.setDefaultStyleSheet("body { color: %s; }" % style["color"])
    document.setPlainText(style["text"])
    document.setTextWidth(style["width"])
    from qt_api import QTextCursor, QTextCharFormat, QPen
    cursor = QTextCursor(document)
    cursor.select(QTextCursor.Document)
    apply_line_spacing(document, style)
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(Qt.transparent if outline else style["color"]))
    if style.get("stroke_width", 0):
        # The fill is drawn as a path too (invisible pen), matching the reader.
        pen = QPen(QColor(style.get("stroke", "#000000")), float(style["stroke_width"])) if outline else QPen(Qt.transparent, 0)
        fmt.setTextOutline(pen)
    cursor.mergeCharFormat(fmt)
    return document


def corner_radius(style):
    """Background corner radius as drawn: never more than half the box."""
    corner = max(0.0, float(style.get("background_corner", 0) or 0))
    return min(corner, min(style["width"], style["height"]) / 2.0)


def apply_line_spacing(document, style):
    """Space every paragraph's lines like the reader; True when anything changed.

    The in-preview editor calls this as it types, since new lines it starts
    do not always copy the spacing."""
    from qt_api import QTextBlockFormat, QTextCursor
    # Line height types are plain ints in Qt 5 and 6: 0 single, 1 proportional.
    spacing = float(style.get("line_spacing", 1.0))
    height, kind = (spacing * 100, 1) if spacing != 1.0 else (0, 0)
    block, changed = document.begin(), False
    while block.isValid():
        if (block.blockFormat().lineHeight(), block.blockFormat().lineHeightType()) != (height, kind):
            fmt = QTextBlockFormat()
            fmt.setLineHeight(height, kind)
            QTextCursor(block).mergeBlockFormat(fmt)
            changed = True
        block = block.next()
    return changed


def project_fps():
    """The open project's frame rate, or 30 fps without a project."""
    try:
        from classes.app import get_app
        fps = get_app().project.get("fps")
    except Exception:
        fps = None
    if isinstance(fps, dict) and fps.get("num", 0) > 0 and fps.get("den", 0) > 0:
        return {"num": int(fps["num"]), "den": int(fps["den"])}
    return {"num": 30, "den": 1}


def stamp_reader_fps(reader, fps):
    """Key a text reader's style curves to project frames.

    Curves use project frame numbers. A reader at the project frame rate passes
    through the timeline's FrameMapper unchanged, so curves evaluate on time.
    """
    reader["fps"] = {"num": int(fps["num"]), "den": int(fps["den"])}
    reader["video_timebase"] = {"num": int(fps["den"]), "den": int(fps["num"])}
    reader["video_length"] = round(float(reader.get("duration") or 3600.0) * fps["num"] / fps["den"])
    return reader


def sync_text_fps(project_data):
    """Stamp every text source and clip reader in raw project data with its fps."""
    fps = project_data.get("fps")
    if not (isinstance(fps, dict) and fps.get("num", 0) > 0 and fps.get("den", 0) > 0):
        return
    for file in project_data.get("files", []):
        if file.get("type") == "QtTextReader":
            stamp_reader_fps(file, fps)
    for clip in project_data.get("clips", []):
        if clip.get("direct_text") and isinstance(clip.get("reader"), dict):
            stamp_reader_fps(clip["reader"], fps)


def reader_data(style, fps=None):
    """Native text reader JSON, including normal media metadata for Project Files."""
    font = text_font(dict(style, letter_spacing=0))
    reader = openshot.QtTextReader()
    data = dict(type="QtTextReader", width=int(style["width"]), height=int(style["height"]),
                text=style["text"], font=font.toString(), text_color=style["color"],
                background_color=style["background"], document_layout=True,
                gravity={"left": openshot.GRAVITY_TOP_LEFT, "center": openshot.GRAVITY_TOP,
                         "right": openshot.GRAVITY_TOP_RIGHT}[style["alignment"]])
    for key in ("background_padding", "background_corner", "stroke_width", "stroke", "border_width", "border",
                "letter_spacing", "line_spacing"):
        data[key] = style.get(key, default_text(1920, 1080)[key])
    data["fps"] = dict(fps or project_fps())
    # Reader info is complete after SetJson; opening would render needlessly.
    reader.SetJson(json.dumps(data))
    result = json.loads(reader.Json())
    result.update(data)
    # Empty path is deliberate: this generated source has no backing file.
    result.update(path="", media_type="image", direct_text=copy.deepcopy(style))
    return result


def text_thumbnail_scale():
    """Device scale for text thumbnails; reads the window, so GUI thread only."""
    from classes.thumbnail import GetThumbDeviceScale
    return GetThumbDeviceScale()


def text_image_path(style, root, black_background=False, device_scale=1.0):
    """Content-addressed path of a text image, without rendering it."""
    key = [style, black_background, float(device_scale) if black_background else 1.0, "thumbnail-v3"]
    digest = hashlib.sha256(json.dumps(key, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return os.path.join(root, "text-%s.png" % digest)


def render_text(style, root, black_background=False, device_scale=None):
    """Generate a content-addressed, disposable image using the native renderer.

    Safe on a worker thread when device_scale is passed in (see text_thumbnail_scale).
    """
    cache_style = copy.deepcopy(style)
    if black_background and device_scale is None:
        device_scale = text_thumbnail_scale()
    path = text_image_path(cache_style, root, black_background, device_scale or 1.0)
    os.makedirs(root, exist_ok=True)
    if not os.path.exists(path):
        reader = openshot.QtTextReader()
        # Only frame 1 is drawn, so the frame rate is irrelevant (and avoids
        # reading the project from a worker thread).
        reader.SetJson(json.dumps(reader_data(cache_style, {"num": 30, "den": 1})))
        reader.Open()
        try:
            frame = reader.GetFrame(1)
            image = QImage(frame.GetPixelsBytes(), frame.GetWidth(), frame.GetHeight(),
                           frame.GetWidth() * 4, QImage.Format_RGBA8888_Premultiplied).copy()
        finally:
            reader.Close()
        if black_background:
            canvas = QImage(image.size(), QImage.Format_ARGB32_Premultiplied)
            canvas.fill(QColor("#000000"))
            painter = QPainter(canvas)
            painter.drawImage(0, 0, image)
            painter.end()
            # Keep icon aspect/size consistent with ordinary media thumbnails.
            # QListView's uniform item sizing otherwise uses the short text icon
            # to reduce the decoration height of every Project Files entry.
            from classes import info
            from qt_api import QSize
            scale = device_scale
            size = QSize(round(info.LIST_ICON_SIZE.width() * scale),
                         round(info.LIST_ICON_SIZE.height() * scale))
            thumbnail = QImage(size, QImage.Format_ARGB32_Premultiplied)
            thumbnail.fill(QColor("#000000"))
            fitted = canvas.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter = QPainter(thumbnail)
            painter.drawImage((size.width() - fitted.width()) // 2,
                              (size.height() - fitted.height()) // 2, fitted)
            painter.end()
            # Round corners with the same mask the thumbnail server passes to
            # Frame::Thumbnail: mask intensity becomes thumbnail alpha.
            mask = QImage(os.path.join(info.IMAGES_PATH, "mask.png"))
            if not mask.isNull():
                gray = mask.scaled(size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_Grayscale8)
                alpha = QImage(gray.constBits(), gray.width(), gray.height(),
                               gray.bytesPerLine(), QImage.Format_Alpha8).copy()
                painter = QPainter(thumbnail)
                painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
                painter.drawImage(0, 0, alpha)
                painter.end()
            image = thumbnail
        fd, temporary = tempfile.mkstemp(suffix=".png", dir=root)
        os.close(fd)
        try:
            if not image.save(temporary, "PNG"):
                raise OSError("Unable to render text thumbnail")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)
    return path


def apply_text(clip_data, style, root=None):
    """Return detached reader/style data while retaining clip timing and transforms."""
    data = copy.deepcopy(clip_data)
    style = copy.deepcopy(style)
    fit_height(style)
    data.update(direct_text=style, reader=reader_data(style),
                title=style["text"].split("\n", 1)[0] or "Text")
    data.pop("image", None)
    return initialize_text_curves(data)


def new_text_clip(style, root, position, layer, duration):
    data = apply_text(json.loads(openshot.Clip().Json()), style)
    # A pathless Clip has no reader orientation metadata to initialize rotation.
    data["rotation"] = json.loads(openshot.Keyframe(0.0).Json())
    data.update(position=position, layer=layer, start=0.0, end=duration, duration=duration,
                scale=openshot.SCALE_NONE)
    return data


def save_text_asset(style, file_id=None):
    """Save a shared source and update all its instances in the caller's transaction."""
    from classes.query import File, Clip
    style = copy.deepcopy(style)
    fit_height(style)
    asset = File.get(id=file_id) if file_id else None
    asset = asset or File()
    data = copy.deepcopy(asset.data or {})
    data.update(reader_data(style))
    data["name"] = style["text"].split("\n", 1)[0] or "Text"
    asset.data = data
    asset.save()
    # Clip.filter(file_id=...) also matches clips without a file_id.
    for clip in [c for c in Clip.filter() if c.data.get("file_id") == asset.id]:
        updated = apply_text(clip.data, style)
        updated["reader"] = copy.deepcopy(asset.data)
        sync_text_reader(updated)
        updated["_text_asset_update"] = True
        save_clip_data(updated)
    return asset


def save_clip_data(data):
    """Save a whole clip record through the timeline, or directly without an editor window."""
    from classes.query import Clip
    from classes.app import get_app
    window = getattr(get_app(), "window", None)
    if window:
        window.timeline.update_clip_data(data, only_basic_props=False, ignore_reader=False)
        return
    clip = Clip.get(id=data.get("id")) or Clip()
    clip.data = data
    clip.save()


def editable_text_clips(clip_ids):
    """Text clips among these IDs, skipping clips on locked tracks."""
    from classes.query import Clip, Track
    locked = {track.data["number"] for track in Track.filter() if track.data.get("lock", False)}
    clips = (Clip.get(id=clip_id) for clip_id in clip_ids)
    return [clip for clip in clips if clip and clip.data.get("direct_text") and clip.data["layer"] not in locked]


def reset_text_clips(clip_ids, width, height):
    """Factory style for these clips' texts; each clip drops its own text keyframes. Caller owns the transaction."""
    from classes.query import Clip, File
    clips = editable_text_clips(clip_ids)
    assets = []
    for clip in clips:
        asset = File.get(id=clip.data.get("file_id"))
        if asset and asset.id not in assets:
            assets.append(asset.id)
            save_text_asset(reset_style(asset.data["direct_text"], width, height), asset.id)
    for clip in clips:
        data = copy.deepcopy(Clip.get(id=clip.id).data)
        data["text_style_overrides"] = []
        for key in TEXT_ANIMATED:
            data.pop("text_" + key, None)
        # The fresh default curves are not this clip's own edits.
        data["_text_asset_update"] = True
        save_clip_data(initialize_text_curves(data))
    return [clip.id for clip in clips]


def copied_text_keyframes(data):
    """This clip's own text color and outline/border curves, for Copy > Keyframes."""
    return {"text_" + key: copy.deepcopy(data["text_" + key])
            for key in data.get("text_style_overrides", []) if key in TEXT_ANIMATED and "text_" + key in data}


def copied_text_style(data):
    """The look of a text clip, without its words or box width, for Copy > Text Style."""
    style = data["direct_text"]
    return {"style": {key: copy.deepcopy(style[key]) for key in REMEMBERED_STYLE if key in style},
            "keyframes": copied_text_keyframes(data)}


def paste_text_style(clip_ids, copied):
    """Give these text clips a copied look. Their texts take the shared style; each clip
    then animates exactly what the source clip animated. Caller owns the transaction."""
    from classes.query import Clip, File
    clips = editable_text_clips(clip_ids)
    assets = []
    for clip in clips:
        asset = File.get(id=clip.data.get("file_id"))
        if asset and asset.id not in assets:
            assets.append(asset.id)
            style = copy.deepcopy(asset.data["direct_text"])
            style.update(copy.deepcopy(copied.get("style", {})))
            save_text_asset(style, asset.id)
    keyframes = {name: value for name, value in copied.get("keyframes", {}).items()
                 if name.startswith("text_") and name[5:] in TEXT_ANIMATED}
    for clip in clips:
        data = copy.deepcopy(Clip.get(id=clip.id).data)
        for key in TEXT_ANIMATED:
            data.pop("text_" + key, None)
        data.update(copy.deepcopy(keyframes))
        data["text_style_overrides"] = sorted(name[5:] for name in keyframes)
        data["_text_asset_update"] = True
        save_clip_data(initialize_text_curves(data))
    return [clip.id for clip in clips]


# Style names match the Caption effect where they mean the same thing.
# Names saved by early test builds, upgraded when a project opens.
RENAMED_STYLE = {"stroke_color": "stroke", "border_color": "border", "padding": "background_padding"}

# Asset defaults are shared. These properties can be overridden/animated per clip.
# Only styles that keep the box size animate; font size, padding, width, letter
# spacing and line spacing set the size of the text image.
TEXT_ANIMATED = {
    "color": ("Text Color", "color", 0, 255),
    "background": ("Text Background Color", "color", 0, 255),
    "stroke": ("Text Outline Color", "color", 0, 255),
    "border": ("Text Border Color", "color", 0, 255),
    "stroke_width": ("Text Outline Width", "float", 0, 30),
    "border_width": ("Text Border Width", "float", 0, 30),
    "background_corner": ("Text Corner Radius", "float", 0, 200),
}


def upgrade_style_names(data):
    """Rename old style keys in a text clip or asset; True when anything changed."""
    changed = False
    style = data.get("direct_text")
    for old, new in RENAMED_STYLE.items():
        if isinstance(style, dict) and old in style:
            style.setdefault(new, style.pop(old))
            changed = True
        if "text_" + old in data:
            data.setdefault("text_" + new, data.pop("text_" + old))
            changed = True
    overrides = data.get("text_style_overrides")
    if overrides and any(key in RENAMED_STYLE for key in overrides):
        data["text_style_overrides"] = sorted(RENAMED_STYLE.get(key, key) for key in overrides)
        changed = True
    return changed


def initialize_text_curves(data):
    style = data["direct_text"]
    defaults = default_text(1920, 1080)
    overrides = data.get("text_style_overrides", [])
    for key, (_, kind, _, _) in TEXT_ANIMATED.items():
        prop = "text_" + key
        if prop not in data or key not in overrides:
            value = style.get(key, defaults[key])
            native = openshot.Color(value) if kind == "color" else openshot.Keyframe(float(value))
            data[prop] = json.loads(native.Json())
    return sync_text_reader(data)


def sync_text_reader(data):
    reader = copy.deepcopy(data["reader"])
    reader["text_animation"] = {key: copy.deepcopy(data["text_" + key])
                                for key in data.get("text_style_overrides", [])
                                if key in TEXT_ANIMATED and "text_" + key in data}
    reader["has_single_image"] = not bool(reader["text_animation"])
    stamp_reader_fps(reader, project_fps())
    data["reader"] = reader
    return data


def evaluated_text_style(data, frame):
    style = copy.deepcopy(data["direct_text"])
    for key in data.get("text_style_overrides", []):
        if key not in TEXT_ANIMATED:
            continue
        if TEXT_ANIMATED[key][1] == "color":
            color = openshot.Color("#ffffff")
            color.SetJson(json.dumps(data["text_" + key]))
            style[key] = QColor(*color.GetColorRGBA(frame)).name(QColor.HexArgb)
        else:
            curve = openshot.Keyframe()
            curve.SetJson(json.dumps(data["text_" + key]))
            style[key] = curve.GetValue(frame)
    return style


def text_animation_properties(data, frame):
    """Use libopenshot's normal keyframe metadata for Properties and curve editing."""
    # Position/scale edits do not change typography. Do not rebuild every text
    # curve (or copy the whole clip) for each axis of a preview drag.
    source = {"direct_text": data["direct_text"],
              "text_style_overrides": data.get("text_style_overrides", []), "reader": {}}
    for key in TEXT_ANIMATED:
        if key in source["text_style_overrides"] and "text_" + key in data:
            source["text_" + key] = data["text_" + key]
    # Return fresh objects: the Properties dock adds readonly/draft values.
    return json.loads(_text_animation_properties_json(json.dumps(source, sort_keys=True), frame))


@lru_cache(maxsize=128)
def _text_animation_properties_json(source_json, frame):
    """Cache immutable metadata by text style, overrides, and clip frame."""
    result = {}
    native = openshot.Clip()
    def property_for(curve):
        native.alpha.SetJson(json.dumps(curve))
        return json.loads(native.PropertiesJSON(frame))["alpha"]
    source = initialize_text_curves(json.loads(source_json))
    for key, (name, kind, minimum, maximum) in TEXT_ANIMATED.items():
        curve = source["text_" + key]
        if kind == "color":
            prop = property_for(curve["red"])
            for channel in ("red", "green", "blue", "alpha"):
                prop[channel] = property_for(curve[channel])
                prop[channel].update(min=0, max=255)
            prop["value"] = 0
        else:
            prop = property_for(curve)
        prop.update(name=name, type=kind, min=minimum, max=maximum)
        result["text_" + key] = prop
    return json.dumps(result)


def set_text_keyframe(data, key, value, frame, auto_keyframes):
    from classes.keyframe_editing import edit_frame
    data = initialize_text_curves(copy.deepcopy(data))
    prop = data["text_" + key]
    if TEXT_ANIMATED[key][1] == "color":
        color = QColor(value)
        changes = [(prop[channel], getattr(color, channel)()) for channel in ("red", "green", "blue", "alpha")]
    else:
        changes = [(prop, float(value))]
    for curve, new_value in changes:
        target = edit_frame(curve.get("Points", []), frame, auto_keyframes)
        native = openshot.Keyframe()
        native.SetJson(json.dumps(curve))
        native.AddPoint(target, new_value, openshot.LINEAR)
        curve.update(json.loads(native.Json()))
    overrides = set(data.get("text_style_overrides", []))
    overrides.add(key)
    data["text_style_overrides"] = sorted(overrides)
    return sync_text_reader(data)
