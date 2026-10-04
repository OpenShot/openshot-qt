"""Semantic text clips backed by immutable, portable Qt-rendered images.

The application JSON is authoritative (as it is for clip titles/file IDs).
The native Clip ignores direct_text; its QtImageReader consumes the raster.
Never replace a raster in place: history and duplicated clips can share it.
"""
import copy
import hashlib
import json
import os
import tempfile

import openshot
from qt_api import QColor, QFont, QImage, QPainter, QTextDocument, QTextOption, Qt


def default_text(width, height):
    return dict(version=1, text="Text", font_family="Sans Serif", font_bold=False, font_italic=False, font_size=max(12, round(height / 15)),
                color="#ffffff", background="#00000000", alignment="center",
                width=max(64, round(width / 2)), height=max(64, round(height / 8)))


def text_document(style, document=None):
    """Use the same document layout for the in-preview editor and raster."""
    document = document or QTextDocument()
    font = QFont(style["font_family"])
    font.setPixelSize(int(style["font_size"]))
    font.setBold(bool(style.get("font_bold", False)))
    font.setItalic(bool(style.get("font_italic", False)))
    document.setDefaultFont(font)
    document.setDocumentMargin(12)
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
    option.setAlignment({"left": Qt.AlignLeft, "center": Qt.AlignHCenter, "right": Qt.AlignRight}[style["alignment"]])
    document.setDefaultTextOption(option)
    document.setDefaultStyleSheet("body { color: %s; }" % style["color"])
    document.setPlainText(style["text"])
    document.setTextWidth(style["width"])
    return document


def render_text(style, root):
    """Render only on a semantic edit; assets live in the managed title folder."""
    digest = hashlib.sha256(json.dumps(style, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, "text-%s.png" % digest)
    if not os.path.exists(path):
        image = QImage(int(style["width"]), int(style["height"]), QImage.Format_ARGB32_Premultiplied)
        image.fill(QColor(style["background"]))
        painter = QPainter(image)
        painter.setPen(QColor(style["color"]))
        # drawContents uses the document palette's text color.
        from qt_api import QAbstractTextDocumentLayout, QPalette
        context = QAbstractTextDocumentLayout.PaintContext()
        context.palette.setColor(QPalette.Text, QColor(style["color"]))
        document = text_document(style)
        document.documentLayout().draw(painter, context)
        painter.end()
        fd, temporary = tempfile.mkstemp(suffix=".png", dir=root)
        os.close(fd)
        try:
            if not image.save(temporary, "PNG"):
                raise OSError("Unable to render text image")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)
    return path


def apply_text(clip_data, style, root):
    """Return a detached edit, preserving timing, effects and transforms."""
    data = copy.deepcopy(clip_data)
    style = copy.deepcopy(style)
    style["height"] = max(style["height"], int(text_document(style).size().height() + 1))
    path = render_text(style, root)
    native = openshot.Clip(path)
    reader = json.loads(native.Json())["reader"]
    data.update(direct_text=copy.deepcopy(style), reader=reader,
                title=style["text"].split("\n", 1)[0] or "Text", image=path)
    return data


def new_text_clip(style, root, position, layer, duration):
    native = openshot.Clip(render_text(style, root))
    data = json.loads(native.Json())
    data = apply_text(data, style, root)
    data.update(position=position, layer=layer, start=0.0, end=duration, duration=duration,
                scale=openshot.SCALE_NONE)
    return data
