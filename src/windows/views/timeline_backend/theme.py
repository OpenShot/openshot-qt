"""Utilities for parsing and applying timeline CSS themes."""

import os
import re
from typing import Callable, Optional, Sequence, Tuple, Union

from PyQt5.QtCore import QFile, QByteArray
from PyQt5.QtGui import QColor, QPixmap
from classes.logger import log
from classes.info import PATH


def _apply_overrides(obj, overrides: dict, *, allow_unknown: bool = False) -> None:
    """Apply keyword overrides to a theme object, optionally ignoring unknown keys."""
    if not overrides:
        return
    allowed = set(obj.__dict__.keys())
    for key, value in overrides.items():
        if key not in allowed:
            if allow_unknown:
                continue
            raise TypeError("Unexpected theme option '%s'" % key)
        setattr(obj, key, value)


class BasicTheme:
    """Common style options for timeline elements."""

    def __init__(self, **kwargs):
        self.background: QColor = QColor()
        self.background2: QColor = QColor()
        self.border_color: QColor = QColor()
        self.border_radius: int = 0
        self.border_width: float = 0
        self.font_color: QColor = QColor()
        self.font_size: int = 0
        self.height: int = 0
        self.background_image: Optional[QPixmap] = None
        self.shadow_color: QColor = QColor()
        self.shadow_blur: int = 0
        self.thumb_width: int = 0
        self.thumb_height: int = 0
        _apply_overrides(self, kwargs)


class TrackTheme(BasicTheme):
    """Theme for tracks."""

    def __init__(self, **kwargs):
        super().__init__()
        self.name_background: QColor = QColor()
        self.name_width: int = 0
        self.gap: int = 0
        self.margin_top: int = -1
        self.name_border_color: QColor = QColor()
        self.name_border_width: int = 0
        self.name_border_top_color: QColor = QColor()
        self.name_border_top_width: int = 0
        self.name_border_bottom_color: QColor = QColor()
        self.name_border_bottom_width: int = 0
        self.name_radius_tl: int = 0
        self.name_radius_bl: int = 0
        _apply_overrides(self, kwargs)


class TimelineTheme:
    """Container for all timeline related themes."""

    def __init__(self, **kwargs):
        self.background: QColor = QColor("#000")
        self.background2: QColor = QColor()
        self.playhead_color: QColor = QColor("#FFF")
        self.playhead_width: float = 0.0
        self.clip_selected: QColor = QColor("#FFF")
        self.selection: QColor = QColor(255, 255, 255, 80)
        self.selection_border: QColor = QColor()
        self.selection_border_width: float = 0.0
        self.playback_cache_color: QColor = QColor("#4B92AD")
        self.playback_cache_height: float = 5.0

        self.clip: BasicTheme = BasicTheme()
        self.transition: BasicTheme = BasicTheme()
        self.track: TrackTheme = TrackTheme()
        self.ruler: BasicTheme = BasicTheme()
        self.ruler_name_background: QColor = QColor()
        self.ruler_name_background2: QColor = QColor()
        self.ruler_time_font_size: int = 0
        self.menu_icon: Optional[QPixmap] = None
        self.menu_size: int = 0
        self.menu_margin: int = 0
        self.keyframe_toggle_off_icon: Optional[QPixmap] = None
        self.keyframe_toggle_on_icon: Optional[QPixmap] = None
        self.track_keyframe_panel_disabled_icon: Optional[QPixmap] = None
        self.track_keyframe_panel_enabled_icon: Optional[QPixmap] = None
        self.track_add_above_disabled_icon: Optional[QPixmap] = None
        self.track_add_above_enabled_icon: Optional[QPixmap] = None
        self.track_add_below_disabled_icon: Optional[QPixmap] = None
        self.track_add_below_enabled_icon: Optional[QPixmap] = None
        self.track_delete_disabled_icon: Optional[QPixmap] = None
        self.track_delete_enabled_icon: Optional[QPixmap] = None
        self.track_locked_disabled_icon: Optional[QPixmap] = None
        self.track_locked_enabled_icon: Optional[QPixmap] = None
        self.track_unlocked_disabled_icon: Optional[QPixmap] = None
        self.track_unlocked_enabled_icon: Optional[QPixmap] = None
        self.keyframe_panel_add_icon: Optional[QPixmap] = None
        self.keyframe_panel_property_bg: QColor = QColor()
        self.playhead_icon: Optional[QPixmap] = None
        self.playhead_icon_width: int = 0
        self.playhead_icon_height: int = 0
        self.playhead_icon_offset_x: int = 0
        self.playhead_icon_offset_y: int = 0
        self.marker_icon: Optional[QPixmap] = None
        self.marker_icon_width: int = 0
        self.marker_icon_height: int = 0
        self.marker_icon_offset_x: Optional[int] = None
        self.marker_icon_offset_y: Optional[int] = None
        self.marker_hit_padding: float = 4.0
        self.ruler_time_pad_left: int = 0
        self.ruler_time_pad_top: int = 0
        self.ruler_label_top: int = 0
        self.scrollbar_handle: QColor = QColor()
        self.scrollbar_track: QColor = QColor()
        self.scrollbar_width: int = 0
        self.waveform_color: QColor = QColor(42, 130, 218)
        self.waveform_peak_color: QColor = QColor(42, 130, 218, 128)
        self.keyframe_fill: QColor = QColor("#4d7bff")
        self.keyframe_border: QColor = QColor("#ffffff")
        self.keyframe_inactive_opacity: float = 0.5
        self.keyframe_size: int = 10
        _apply_overrides(self, kwargs)


DEFAULT_THEME = TimelineTheme()

# Load the main timeline CSS used by the web backends. Many timeline style
# values are defined here and are reused by the QWidget backend.
_CSS_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    "../../..",
    "timeline/media/css/main.css",
))
try:
    with open(_CSS_PATH, "r", encoding="utf-8") as _f:
        MAIN_CSS = _f.read()
except OSError:
    MAIN_CSS = ""


def _annotate_svg_metadata(pix: Optional[QPixmap], source: Optional[str]) -> Optional[QPixmap]:
    """Attach SVG metadata (path + bytes) to *pix* when available."""
    if not pix or pix.isNull() or not source or not source.lower().endswith(".svg"):
        return pix
    try:
        pix.svg_path = source
        data: Optional[bytes] = None
        if source.startswith(":"):
            file_obj = QFile(source)
            if file_obj.open(QFile.ReadOnly):
                try:
                    data = bytes(file_obj.readAll())
                finally:
                    file_obj.close()
        else:
            with open(source, "rb") as fh:
                data = fh.read()
        if data:
            pix.svg_bytes = data
            try:
                pix.svg_qbytearray = QByteArray(data)
            except Exception:
                pass
    except Exception:
        pass
    return pix


def _load_pixmap_with_meta(path: str) -> Optional[QPixmap]:
    pix = QPixmap(path)
    if pix.isNull():
        return None
    return _annotate_svg_metadata(pix, path)


def _css_prop(
    css: str,
    selector: str,
    prop: str,
    source: str,
    *,
    log_selector: bool = True,
    log_property: bool = True,
) -> Optional[str]:
    """Return property *prop* from the CSS *selector* block.

    Logging can be disabled for selector or property misses using the optional
    flags. This is useful when calling code plans to fall back to alternate
    property names and does not want intermediate MISS messages.
    """
    block_pat = rf"{re.escape(selector)}\s*\{{([^}}]*)\}}"
    m = re.search(block_pat, css, re.MULTILINE)
    if not m:
        if log_selector:
            log.info("Theme MISS [%s] selector '%s'", source, selector)
        return None
    block = m.group(1)
    m2 = re.search(rf"(?:^|;)\s*{re.escape(prop)}\s*:\s*([^;]+)", block)
    if not m2:
        if log_property:
            log.info(
                "Theme MISS [%s] selector '%s' property '%s'",
                source,
                selector,
                prop,
            )
        return None
    return m2.group(1).strip()


def _color_from_str(val: str) -> Optional[QColor]:
    """Parse a CSS color value into a ``QColor``.

    Supports hex colors and ``rgb/rgba`` declarations with either integer or
    float components. Returns ``None`` if the string cannot be parsed.
    """
    val = val.strip()
    if not val:
        return None
    if val.startswith("#"):
        col = QColor(val)
        return col if col.isValid() else None
    m = re.match(r"rgba?\(([^)]+)\)", val)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        if len(parts) >= 3:
            try:
                r = int(float(parts[0]))
                g = int(float(parts[1]))
                b = int(float(parts[2]))
                a = 255
                if len(parts) >= 4:
                    a_part = parts[3]
                    if a_part.endswith("%"):
                        a = int(float(a_part[:-1]) * 2.55)
                    else:
                        fa = float(a_part)
                        a = int(fa * 255) if fa <= 1 else int(fa)
                return QColor(r, g, b, a)
            except ValueError:
                return None
    col = QColor(val)
    return col if col.isValid() else None


def _parse_color(
    css: str,
    selector: str,
    prop: Union[str, Sequence[str]],
    source: str,
    *,
    log_miss: bool = True,
    log_selector: bool = True,
) -> Optional[QColor]:
    props = (prop,) if isinstance(prop, str) else tuple(prop)
    val = None
    for i, p in enumerate(props):
        val = _css_prop(
            css,
            selector,
            p,
            source,
            log_selector=i == 0 and log_selector,
            log_property=False,
        )
        if val is not None:
            break
    if val is None:
        if log_miss:
            log.info(
                "Theme MISS [%s] selector '%s' property '%s'",
                source,
                selector,
                props[0],
            )
        return None
    m = re.search(r"#([0-9a-fA-F]{3,8})", val)
    if m:
        col = _color_from_str("#" + m.group(1))
        if col:
            return col
    m = re.search(r"rgba?\([^\)]+\)", val)
    if m:
        col = _color_from_str(m.group(0))
        if col:
            return col
    # Handle shorthand declarations like "1px solid red !important" by
    # scanning tokens from right to left and returning the first valid color.
    parts = re.split(r"\s+", val.strip())
    for token in reversed(parts):
        if token.lower() == "!important":
            continue
        col = _color_from_str(token)
        if col and col.isValid():
            return col
    if log_miss:
        log.info(
            "Theme MISS [%s] selector '%s' property '%s' invalid color '%s'",
            source,
            selector,
            prop,
            val,
        )
    return None


def _parse_gradient(
    css: str, selector: str, prop: str, source: str, *, log_miss: bool = True
):
    """Return up to two colors from a CSS gradient.

    The returned colors are ordered for a top-to-bottom gradient. If the CSS
    gradient specifies the opposite direction (bottom to top), the order of the
    colors is swapped so callers can simply paint from top to bottom.
    """
    val = _css_prop(css, selector, prop, source)
    if not val:
        if log_miss:
            log.info("Theme MISS [%s] selector '%s' property '%s'", source, selector, prop)
        return None, None
    cols = re.findall(r"#(?:[0-9a-fA-F]{3,8})|rgba?\([^\)]+\)", val)
    qcols = [_color_from_str(c) for c in cols]
    qcols = [c for c in qcols if c and c.isValid()]
    if not qcols:
        if log_miss:
            log.info(
                "Theme MISS [%s] selector '%s' property '%s' invalid gradient '%s'",
                source,
                selector,
                prop,
                val,
            )
        return None, None

    first = qcols[0]
    second = qcols[1] if len(qcols) > 1 else None

    # Detect bottom-to-top gradients and reverse the color order so callers can
    # always assume the first color is at the top.
    val_lower = val.lower()
    idx_bottom = val_lower.find("bottom")
    idx_top = val_lower.find("top")
    reverse = False
    if idx_bottom != -1 and idx_top != -1:
        reverse = idx_bottom < idx_top
    else:
        m = re.search(r"linear-gradient\((?:to\s+)?(top|bottom)", val_lower)
        if m:
            reverse = m.group(1) == "bottom"
        else:
            m = re.search(r"-webkit-linear-gradient\((top|bottom)", val_lower)
            if m:
                reverse = m.group(1) == "bottom"
    if reverse and second is not None:
        first, second = second, first

    return first, second


def _parse_float(
    css: str,
    selector: str,
    prop: Union[str, Sequence[str]],
    source: str,
    *,
    log_miss: bool = True,
    log_selector: bool = True,
) -> Optional[float]:
    props = (prop,) if isinstance(prop, str) else tuple(prop)
    val = None
    for i, p in enumerate(props):
        val = _css_prop(
            css,
            selector,
            p,
            source,
            log_selector=i == 0 and log_selector,
            log_property=False,
        )
        if val is not None:
            break
    if val is None:
        if log_miss:
            log.info(
                "Theme MISS [%s] selector '%s' property '%s'",
                source,
                selector,
                props[0],
            )
        return None
    m = re.search(r"(-?[0-9.]+)", val)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    if log_miss:
        log.info(
            "Theme MISS [%s] selector '%s' property '%s' invalid number '%s'",
            source,
            selector,
            props[0],
            val,
        )
    return None


def _parse_pixmap(
    css: str,
    selector: str,
    prop: str,
    source: str,
    *,
    log_miss: bool = True,
) -> Optional[QPixmap]:
    val = _css_prop(css, selector, prop, source)
    if not val:
        if log_miss:
            log.info("Theme MISS [%s] selector '%s' property '%s'", source, selector, prop)
        return None
    m = re.search(r"url\(([^)]+)\)", val)
    if m:
        path = m.group(1).strip('"\'')
        if path.startswith(":"):
            img = QPixmap(path)
            if not img.isNull():
                return _annotate_svg_metadata(img, path)
        if not os.path.isabs(path):
            base = os.path.dirname(_CSS_PATH)
            found = None
            for i in range(3):
                candidate = os.path.normpath(
                    os.path.join(base, *([".."] * i), path)
                )
                if os.path.exists(candidate):
                    found = candidate
                    break
            path = found or os.path.normpath(os.path.join(base, path))
        if os.path.exists(path):
            img = _load_pixmap_with_meta(path)
            if img:
                if selector in {".playhead-top", ".marker_icon"} and prop == "background-image":
                    log.info(
                        "Theme [%s] %s %s loaded '%s'",
                        source,
                        selector,
                        prop,
                        path,
                    )
                return img
    if log_miss:
        log.info(
            "Theme MISS [%s] selector '%s' property '%s' invalid pixmap '%s'",
            source,
            selector,
            prop,
            val,
        )
    return None


def _parse_box_shadow(
    css: str, selector: str, source: str, *, log_miss: bool = True
):
    """Return (color, blur) from a box-shadow property."""
    val = _css_prop(css, selector, "box-shadow", source)
    if not val:
        if log_miss:
            log.info(
                "Theme MISS [%s] selector '%s' property '%s'",
                source,
                selector,
                "box-shadow",
            )
        return None, None
    col = None
    m = re.search(r"#([0-9a-fA-F]{3,8})", val)
    if m:
        col = QColor("#" + m.group(1))
    else:
        m = re.search(r"rgba?\([^\)]+\)", val)
        if m:
            col = QColor(m.group(0))
    nums = re.findall(r"(-?[0-9.]+)", val)
    blur = int(float(nums[2])) if len(nums) >= 3 else None
    if col is None and blur is None and log_miss:
        log.info(
            "Theme MISS [%s] selector '%s' property '%s' invalid value '%s'",
            source,
            selector,
            "box-shadow",
            val,
        )
    return col, blur


def _theme_pixmap(
    qt_theme, selector: str, prop: str, *, log_miss: bool = True
) -> Optional[QPixmap]:
    if not qt_theme or not hasattr(qt_theme, "style_sheet"):
        return None
    val = _css_prop(qt_theme.style_sheet, selector, prop, "theme", log_selector=log_miss, log_property=log_miss)
    if not val:
        return None
    m = re.search(r"url\(([^)]+)\)", val)
    if m:
        path = m.group(1).strip('"\'')
        if path.startswith(":"):
            img = QPixmap(path)
            if not img.isNull():
                return _annotate_svg_metadata(img, path)
        module_path = os.path.dirname(__import__(qt_theme.__module__).__file__)
        if not os.path.isabs(path):
            module_parent = os.path.dirname(module_path)
            trimmed = path.lstrip("./")
            rel_path = path
            while rel_path.startswith("../"):
                rel_path = rel_path[3:]
            candidates = []
            bases = [module_path, module_parent, PATH, os.path.dirname(PATH)]
            for base in bases:
                if not base:
                    continue
                candidates.append(os.path.normpath(os.path.join(base, path)))
                if trimmed and trimmed != path:
                    candidates.append(os.path.normpath(os.path.join(base, trimmed)))
                if rel_path and rel_path != path:
                    candidates.append(os.path.normpath(os.path.join(base, rel_path)))
            seen = set()
            resolved = None
            for candidate in candidates:
                if candidate in seen:
                    continue
                seen.add(candidate)
                if os.path.exists(candidate):
                    resolved = candidate
                    break
            if resolved:
                path = resolved
            else:
                path = os.path.normpath(os.path.join(module_path, path))
        if os.path.exists(path):
            img = _load_pixmap_with_meta(path)
            if img:
                if selector in {".playhead-top", ".marker_icon"} and prop == "background-image":
                    log.info(
                        "Theme [theme] %s %s loaded '%s'",
                        selector,
                        prop,
                        path,
                    )
                return img
    if log_miss:
        log.info("Theme MISS [theme] %s %s invalid pixmap '%s'", selector, prop, val)
    return None


def _theme_get_color(
    qt_theme,
    selector: str,
    prop: Union[str, Sequence[str]],
    *,
    log_miss: bool = True,
):
    if not qt_theme:
        return None
    props = (prop,) if isinstance(prop, str) else tuple(prop)
    if hasattr(qt_theme, "get_color"):
        for p in props:
            col = qt_theme.get_color(selector, p)
            if col:
                return col
    if hasattr(qt_theme, "style_sheet"):
        return _parse_color(
            qt_theme.style_sheet,
            selector,
            props,
            "theme",
            log_miss=log_miss,
            log_selector=log_miss,
        )
    return None


def _theme_get_int(
    qt_theme,
    selector: str,
    prop: Union[str, Sequence[str]],
    *,
    log_miss: bool = True,
):
    if not qt_theme:
        return None
    props = (prop,) if isinstance(prop, str) else tuple(prop)
    if hasattr(qt_theme, "get_int"):
        for p in props:
            val = qt_theme.get_int(selector, p)
            if val is not None:
                return val
    if hasattr(qt_theme, "style_sheet"):
        val = _parse_float(
            qt_theme.style_sheet,
            selector,
            props,
            "theme",
            log_miss=log_miss,
            log_selector=log_miss,
        )
        if val is not None:
            return int(val)
    return None


def _assign_color(target, attr: str, color: Optional[QColor]) -> None:
    if color:
        setattr(target, attr, color)


def _assign_value(
    target,
    attr: str,
    value: Optional[Union[int, float]],
    *,
    transform: Optional[Callable[[Union[int, float]], Union[int, float]]] = None,
) -> None:
    if value is not None:
        if transform:
            value = transform(value)
        setattr(target, attr, value)


def _apply_gradient_with_fallback(
    target,
    attr_primary: str,
    attr_secondary: str,
    gradient_func: Callable[[], Tuple[Optional[QColor], Optional[QColor]]],
    fallback_func: Callable[[], Optional[QColor]],
    *,
    miss_log: Optional[Callable[[], None]] = None,
) -> None:
    col1, col2 = gradient_func()
    if col1:
        setattr(target, attr_primary, col1)
    if col2:
        setattr(target, attr_secondary, col2)
    elif col1:
        setattr(target, attr_secondary, QColor())
    if col1 is None and col2 is None:
        fallback = fallback_func()
        if fallback:
            setattr(target, attr_primary, fallback)
            setattr(target, attr_secondary, QColor())
        elif miss_log:
            miss_log()


def _theme_apply_color(
    target,
    attr: str,
    qt_theme,
    selector: str,
    prop: Union[str, Sequence[str]],
    *,
    log_miss: bool = True,
) -> None:
    col = _theme_get_color(qt_theme, selector, prop, log_miss=log_miss)
    _assign_color(target, attr, col)


def _theme_apply_int(
    target,
    attr: str,
    qt_theme,
    selector: str,
    prop: Union[str, Sequence[str]],
    *,
    transform: Optional[Callable[[Union[int, float]], Union[int, float]]] = None,
    log_miss: bool = True,
) -> None:
    val = _theme_get_int(qt_theme, selector, prop, log_miss=log_miss)
    _assign_value(target, attr, val, transform=transform)


def _theme_get_first_color(
    qt_theme,
    queries: Sequence[Sequence],
) -> Optional[QColor]:
    for query in queries:
        selector, prop = query[0], query[1]
        extra = query[2] if len(query) > 2 else {}
        col = _theme_get_color(qt_theme, selector, prop, **extra)
        if col:
            return col
    return None


def _set_default_if_missing(target, attrs: Sequence[str], value: int) -> None:
    for attr in attrs:
        if not getattr(target, attr):
            setattr(target, attr, value)


def _apply_css_color_value(
    target,
    attr: str,
    css: str,
    selector: str,
    prop: Union[str, Sequence[str]],
    source: str,
    *,
    log_miss: bool = True,
    log_selector: bool = True,
) -> None:
    col = _parse_color(
        css,
        selector,
        prop,
        source,
        log_miss=log_miss,
        log_selector=log_selector,
    )
    _assign_color(target, attr, col)


def _apply_css_float_value(
    target,
    attr: str,
    css: str,
    selector: str,
    prop: Union[str, Sequence[str]],
    source: str,
    *,
    log_miss: bool = True,
    log_selector: bool = True,
    transform: Optional[Callable[[float], Union[int, float]]] = None,
) -> None:
    val = _parse_float(
        css,
        selector,
        prop,
        source,
        log_miss=log_miss,
        log_selector=log_selector,
    )
    _assign_value(target, attr, val, transform=transform)


def _apply_clip_box_shadow(
    theme: TimelineTheme,
    css: str,
    source: str,
    *,
    log_miss: bool,
) -> None:
    val = _css_prop(css, ".clip", "box-shadow", source, log_selector=False, log_property=False)
    if not val:
        return
    col, blur = _parse_box_shadow(css, ".clip", source, log_miss=log_miss)
    if col:
        theme.clip.shadow_color = col
    if blur is not None:
        theme.clip.shadow_blur = blur


def _ruler_gradient(css: str, source: str) -> Tuple[Optional[QColor], Optional[QColor]]:
    col1, col2 = _parse_gradient(css, "#scrolling_ruler", "background", source, log_miss=False)
    if not col1 and not col2:
        col1, col2 = _parse_gradient(css, "#ruler", "background", source, log_miss=False)
    return col1, col2


def _ruler_theme_background(qt_theme) -> Optional[QColor]:
    col = _theme_get_color(
        qt_theme,
        "#scrolling_ruler",
        ("background", "background-color"),
        log_miss=False,
    )
    if not col:
        col = _theme_get_color(
            qt_theme,
            "#ruler",
            ("background", "background-color"),
            log_miss=False,
        )
    return col


def _ruler_css_background(css: str, source: str) -> Optional[QColor]:
    col = _parse_color(
        css,
        "#scrolling_ruler",
        ("background", "background-color"),
        source,
        log_miss=False,
    )
    if not col:
        col = _parse_color(
            css,
            "#ruler",
            ("background", "background-color"),
            source,
            log_miss=False,
        )
    return col


def _css_get_first_color(
    css: str,
    source: str,
    log_miss: bool,
    queries: Sequence[Sequence],
) -> Optional[QColor]:
    for query in queries:
        selector, prop = query[0], query[1]
        col = _parse_color(css, selector, prop, source, log_miss=log_miss)
        if col:
            return col
    return None

def _theme_apply_background(theme: TimelineTheme, qt_theme, css_sheet: str) -> None:
    col1, col2 = _parse_gradient(css_sheet, "body", "background", "theme", log_miss=False)
    if col1:
        theme.background = col1
    if col2:
        theme.background2 = col2
    elif col1:
        theme.background2 = QColor()
    if col1 is None and col2 is None:
        col = _theme_get_color(qt_theme, "body", ("background", "background-color"))
        if col:
            theme.background = col
            theme.background2 = QColor()


def _theme_apply_clip(theme: TimelineTheme, qt_theme, css_sheet: str) -> None:
    _apply_gradient_with_fallback(
        theme.clip,
        "background",
        "background2",
        lambda: _parse_gradient(css_sheet, ".clip", "background", "theme", log_miss=False),
        lambda: _theme_get_color(qt_theme, ".clip", ("background", "background-color")),
    )
    _theme_apply_color(theme.clip, "border_color", qt_theme, ".clip", ("border-top", "border"))
    _theme_apply_int(
        theme.clip,
        "border_width",
        qt_theme,
        ".clip",
        ("border-top", "border"),
        transform=float,
    )
    _theme_apply_int(theme.clip, "border_radius", qt_theme, ".clip", "border-radius")
    _theme_apply_int(theme.clip, "font_size", qt_theme, ".clip", "font-size")
    _theme_apply_color(theme.clip, "font_color", qt_theme, ".clip_label", "color")
    _theme_apply_int(theme.clip, "height", qt_theme, ".clip", "height")
    _apply_clip_box_shadow(theme, css_sheet, "theme", log_miss=False)
    _theme_apply_int(theme.clip, "thumb_width", qt_theme, ".thumb", "width")
    _theme_apply_int(theme.clip, "thumb_height", qt_theme, ".thumb", "height")


def _theme_apply_selection(theme: TimelineTheme, qt_theme, css_sheet: str) -> None:
    col = _theme_get_color(qt_theme, ".ui-selected", ("border-top", "border"))
    if col:
        theme.clip_selected = col
    op = None
    if css_sheet:
        op = _parse_float(
            css_sheet,
            ".ui-selectable-helper",
            "opacity",
            "theme",
            log_miss=False,
            log_selector=False,
        )
    col = _theme_get_color(qt_theme, ".ui-selectable-helper", ("background", "background-color"))
    if col:
        if op is not None and col.alpha() == 255:
            col.setAlpha(int(255 * op))
        theme.selection = col
    col = _theme_get_color(qt_theme, ".ui-selectable-helper", ("border", "border-color"))
    if col:
        if op is not None and col.alpha() == 255:
            col.setAlpha(int(255 * op))
        theme.selection_border = col
    val = _theme_get_int(qt_theme, ".ui-selectable-helper", ("border", "border-width"))
    if val is not None:
        theme.selection_border_width = float(val)


def _theme_apply_transition(theme: TimelineTheme, qt_theme, css_sheet: str) -> None:
    col1, col2 = _parse_gradient(css_sheet, ".transition", "background", "theme", log_miss=False)
    if col1:
        theme.transition.background = col1
    if col2:
        theme.transition.background2 = col2
    elif col1:
        theme.transition.background2 = QColor()
    if col1 is None and col2 is None:
        col = _theme_get_color(qt_theme, ".transition", ("background", "background-color"))
        if col:
            theme.transition.background = col
            theme.transition.background2 = QColor()
    col = _theme_get_color(qt_theme, ".transition", ("border-top", "border"))
    if col:
        theme.transition.border_color = col
    val = _theme_get_int(qt_theme, ".transition", "border-radius")
    if val is not None:
        theme.transition.border_radius = val
    img = _theme_pixmap(qt_theme, ".transition", "background-image")
    if img:
        theme.transition.background_image = img
    col = _theme_get_color(qt_theme, ".transition_label", "color")
    if col:
        theme.transition.font_color = col
    val = _theme_get_int(qt_theme, ".transition", "font-size")
    if val is not None:
        theme.transition.font_size = val
    val = _theme_get_int(qt_theme, ".transition", "height")
    if val is not None:
        theme.transition.height = val


def _theme_apply_track(theme: TimelineTheme, qt_theme, css_sheet: str) -> None:
    _apply_gradient_with_fallback(
        theme.track,
        "background",
        "background2",
        lambda: _parse_gradient(css_sheet, ".track", "background", "theme", log_miss=False),
        lambda: _theme_get_color(qt_theme, ".track", ("background", "background-color")),
    )
    _theme_apply_color(theme.track, "border_color", qt_theme, ".track", ("border-top", "border"))
    _theme_apply_int(theme.track, "border_radius", qt_theme, ".track", "border-radius")
    col = _theme_get_first_color(
        qt_theme,
        [
            (".track_name", "color"),
            (".track_label", "color"),
        ],
    )
    _assign_color(theme.track, "font_color", col)
    _theme_apply_int(theme.track, "height", qt_theme, ".track", "height")
    _theme_apply_int(theme.track, "font_size", qt_theme, ".track_name", "font-size")
    _theme_apply_color(
        theme.track,
        "name_background",
        qt_theme,
        ".track_name",
        ("background", "background-color"),
    )
    _theme_apply_int(theme.track, "name_width", qt_theme, ".track_name", "width")
    _theme_apply_int(theme.track, "gap", qt_theme, ".track", "margin-bottom")
    _theme_apply_int(theme.track, "margin_top", qt_theme, ".track", "margin-top")
    for attr, prop in (
        ("name_border_color", "border-left"),
        ("name_border_top_color", ("border-top", "border")),
        ("name_border_bottom_color", ("border-bottom", "border")),
    ):
        _theme_apply_color(theme.track, attr, qt_theme, ".track_name", prop)
    for attr, prop in (
        ("name_border_width", "border-left"),
        ("name_border_top_width", ("border-top", "border")),
        ("name_border_bottom_width", ("border-bottom", "border")),
    ):
        _theme_apply_int(theme.track, attr, qt_theme, ".track_name", prop)
    _theme_apply_int(theme.track, "name_radius_tl", qt_theme, ".track_name", "border-top-left-radius")
    _theme_apply_int(
        theme.track,
        "name_radius_bl",
        qt_theme,
        ".track_name",
        "border-bottom-left-radius",
    )
    val = _theme_get_int(qt_theme, ".track_name", "border-radius")
    if val is not None:
        _set_default_if_missing(theme.track, ("name_radius_tl", "name_radius_bl"), val)


def _theme_apply_ruler(theme: TimelineTheme, qt_theme, css_sheet: str) -> None:
    _apply_gradient_with_fallback(
        theme.ruler,
        "background",
        "background2",
        lambda: _ruler_gradient(css_sheet, "theme"),
        lambda: _ruler_theme_background(qt_theme),
        miss_log=lambda: log.info(
            "Theme MISS [theme] selector '#scrolling_ruler' property 'background'"
        ),
    )
    _apply_gradient_with_fallback(
        theme,
        "ruler_name_background",
        "ruler_name_background2",
        lambda: _parse_gradient(css_sheet, "#ruler_label", "background", "theme", log_miss=False),
        lambda: _theme_get_color(qt_theme, "#ruler_label", ("background", "background-color")),
    )
    _theme_apply_color(theme.ruler, "border_color", qt_theme, ".tick_mark", "background-color")
    _theme_apply_color(theme.ruler, "font_color", qt_theme, "#ruler_time", "color")
    _theme_apply_int(theme, "ruler_time_font_size", qt_theme, "#ruler_time", "font-size")
    fs = _parse_float(css_sheet, ".ruler_time", "font-size", "theme", log_miss=False)
    if fs is not None:
        base = theme.ruler_time_font_size or 12
        theme.ruler.font_size = int(fs * base) if fs < 5 else int(fs)
    _theme_apply_int(theme, "ruler_label_top", qt_theme, ".ruler_time", "top")
    _theme_apply_int(theme.ruler, "height", qt_theme, "#ruler", "height")
    _theme_apply_int(theme, "ruler_time_pad_left", qt_theme, "#ruler_time", "padding-left")
    _theme_apply_int(theme, "ruler_time_pad_top", qt_theme, "#ruler_time", "padding-top")


def _theme_apply_playhead(theme: TimelineTheme, qt_theme) -> None:
    col = _theme_get_color(qt_theme, ".playhead-line", "background-color")
    if col:
        theme.playhead_color = col
    val = _theme_get_int(qt_theme, ".playhead-line", "width")
    if val is not None:
        theme.playhead_width = float(val)
    img = _theme_pixmap(qt_theme, ".playhead-top", "background-image")
    if img:
        theme.playhead_icon = img
    val = _theme_get_int(qt_theme, ".playhead-top", "width")
    if val is not None:
        theme.playhead_icon_width = val
    val = _theme_get_int(qt_theme, ".playhead-top", "height")
    if val is not None:
        theme.playhead_icon_height = val
    val = _theme_get_int(qt_theme, ".playhead-top", "margin-left")
    if val is not None:
        theme.playhead_icon_offset_x = val
    val = _theme_get_int(qt_theme, ".playhead-top", "margin-top")
    if val is not None:
        theme.playhead_icon_offset_y = val


def _theme_apply_markers(theme: TimelineTheme, qt_theme) -> None:
    img = _theme_pixmap(qt_theme, ".marker_icon", "background-image")
    if img:
        theme.marker_icon = img
    val = _theme_get_int(qt_theme, ".marker_icon", "width")
    if val is not None:
        theme.marker_icon_width = val
    val = _theme_get_int(qt_theme, ".marker_icon", "height")
    if val is not None:
        theme.marker_icon_height = val
    val = _theme_get_int(qt_theme, ".marker_icon", "margin-left")
    if val is not None:
        theme.marker_icon_offset_x = val
    val = _theme_get_int(qt_theme, ".marker_icon", "bottom")
    if val is not None:
        theme.marker_icon_offset_y = val


def _theme_apply_menu(theme: TimelineTheme, qt_theme) -> None:
    img = _theme_pixmap(qt_theme, ".menu", "background-image")
    if img:
        theme.menu_icon = img
    val = _theme_get_int(qt_theme, ".menu", "width")
    if val is not None:
        theme.menu_size = val
    val = _theme_get_int(qt_theme, ".menu", "margin")
    if val is not None:
        theme.menu_margin = val


def _theme_apply_keyframe_panel(theme: TimelineTheme, qt_theme) -> None:
    off_img = (
        _theme_pixmap(qt_theme, ".track-keyframe-panel-disabled", "background-image")
        or _theme_pixmap(qt_theme, ".keyframe-toggle-off", "background-image")
    )
    if off_img:
        theme.track_keyframe_panel_disabled_icon = off_img
        theme.keyframe_toggle_off_icon = off_img
    on_img = (
        _theme_pixmap(qt_theme, ".track-keyframe-panel-enabled", "background-image")
        or _theme_pixmap(qt_theme, ".keyframe-toggle-on", "background-image")
    )
    if on_img:
        theme.track_keyframe_panel_enabled_icon = on_img
        theme.keyframe_toggle_on_icon = on_img
    add_img = _theme_pixmap(qt_theme, ".keyframe-panel-add", "background-image")
    if add_img:
        theme.keyframe_panel_add_icon = add_img
    panel_bg = _theme_get_color(qt_theme, "QMenuBar", ("background", "background-color"))
    if panel_bg:
        theme.keyframe_panel_property_bg = panel_bg


def _theme_apply_track_toolbar(theme: TimelineTheme, qt_theme) -> None:
    if not qt_theme:
        return

    def _set_icon(attr, selector):
        pix = _theme_pixmap(qt_theme, selector, "background-image")
        if pix:
            setattr(theme, attr, pix)

    _set_icon("track_add_above_disabled_icon", ".track-add-above-disabled")
    _set_icon("track_add_above_enabled_icon", ".track-add-above-enabled")
    _set_icon("track_add_below_disabled_icon", ".track-add-below-disabled")
    _set_icon("track_add_below_enabled_icon", ".track-add-below-enabled")
    _set_icon("track_delete_disabled_icon", ".track-delete-disabled")
    _set_icon("track_delete_enabled_icon", ".track-delete-enabled")
    _set_icon("track_locked_disabled_icon", ".track-locked-disabled")
    _set_icon("track_locked_enabled_icon", ".track-locked-enabled")
    _set_icon("track_unlocked_disabled_icon", ".track-unlocked-disabled")
    _set_icon("track_unlocked_enabled_icon", ".track-unlocked-enabled")


def _apply_theme_obj(theme: TimelineTheme, qt_theme) -> TimelineTheme:
    """Update *theme* from a Qt theme instance using BaseTheme helpers."""

    if not qt_theme:
        return theme

    css_sheet = getattr(qt_theme, "style_sheet", "")
    _theme_apply_background(theme, qt_theme, css_sheet)
    _theme_apply_clip(theme, qt_theme, css_sheet)
    _theme_apply_selection(theme, qt_theme, css_sheet)
    _theme_apply_transition(theme, qt_theme, css_sheet)
    _theme_apply_track(theme, qt_theme, css_sheet)
    _theme_apply_ruler(theme, qt_theme, css_sheet)
    _theme_apply_playhead(theme, qt_theme)
    _theme_apply_markers(theme, qt_theme)
    _theme_apply_menu(theme, qt_theme)
    _theme_apply_keyframe_panel(theme, qt_theme)
    _theme_apply_track_toolbar(theme, qt_theme)

    return theme


def _css_apply_background(theme: TimelineTheme, css: str, source: str, log_miss: bool) -> None:
    col1, col2 = _parse_gradient(css, "body", "background", source, log_miss=False)
    if col1:
        theme.background = col1
    if col2:
        theme.background2 = col2
    elif col1:
        theme.background2 = QColor()
    if col1 is None and col2 is None:
        col = _parse_color(css, "body", ("background", "background-color"), source, log_miss=log_miss)
        if col:
            theme.background = col
            theme.background2 = QColor()


def _css_apply_clip(theme: TimelineTheme, css: str, source: str, log_miss: bool) -> None:
    _apply_gradient_with_fallback(
        theme.clip,
        "background",
        "background2",
        lambda: _parse_gradient(css, ".clip", "background", source, log_miss=False),
        lambda: _parse_color(
            css,
            ".clip",
            ("background", "background-color"),
            source,
            log_miss=log_miss,
        ),
    )
    _apply_css_color_value(
        theme.clip,
        "border_color",
        css,
        ".clip",
        ("border-top", "border"),
        source,
        log_miss=False,
    )
    _apply_css_float_value(
        theme.clip,
        "border_width",
        css,
        ".clip",
        ("border-top", "border"),
        source,
        log_miss=False,
        transform=float,
    )
    _apply_css_float_value(
        theme.clip,
        "border_radius",
        css,
        ".clip",
        "border-radius",
        source,
        log_miss=False,
        transform=int,
    )
    _apply_css_color_value(theme.clip, "font_color", css, ".clip_label", "color", source, log_miss=log_miss)
    _apply_css_float_value(
        theme.clip,
        "height",
        css,
        ".clip",
        "height",
        source,
        log_miss=log_miss,
        transform=int,
    )
    _apply_clip_box_shadow(theme, css, source, log_miss=log_miss)
    _apply_css_float_value(
        theme.clip,
        "thumb_width",
        css,
        ".thumb",
        "width",
        source,
        log_miss=log_miss,
        transform=int,
    )
    _apply_css_float_value(
        theme.clip,
        "thumb_height",
        css,
        ".thumb",
        "height",
        source,
        log_miss=log_miss,
        transform=int,
    )
    _apply_css_float_value(
        theme.clip,
        "font_size",
        css,
        ".clip",
        "font-size",
        source,
        log_miss=log_miss,
        transform=int,
    )


def _css_apply_selection(theme: TimelineTheme, css: str, source: str, log_miss: bool) -> None:
    col = _parse_color(css, ".ui-selected", ("border-top", "border"), source, log_miss=log_miss)
    if col:
        theme.clip_selected = col
    op = _parse_float(css, ".ui-selectable-helper", "opacity", source, log_miss=log_miss)
    col = _parse_color(css, ".ui-selectable-helper", ("background", "background-color"), source, log_miss=log_miss)
    if col:
        if op is not None and col.alpha() == 255:
            col.setAlpha(int(255 * op))
        theme.selection = col
    col = _parse_color(css, ".ui-selectable-helper", ("border", "border-color"), source, log_miss=log_miss)
    if col:
        if op is not None and col.alpha() == 255:
            col.setAlpha(int(255 * op))
        theme.selection_border = col
    val = _parse_float(css, ".ui-selectable-helper", ("border", "border-width"), source, log_miss=log_miss)
    if val is not None:
        theme.selection_border_width = float(val)


def _css_apply_transition(theme: TimelineTheme, css: str, source: str, log_miss: bool) -> None:
    col1, col2 = _parse_gradient(css, ".transition", "background", source, log_miss=False)
    if col1:
        theme.transition.background = col1
    if col2:
        theme.transition.background2 = col2
    elif col1:
        theme.transition.background2 = QColor()
    if col1 is None and col2 is None:
        col = _parse_color(css, ".transition", ("background", "background-color"), source, log_miss=log_miss)
        if col:
            theme.transition.background = col
            theme.transition.background2 = QColor()
    col = _parse_color(css, ".transition", ("border-top", "border"), source, log_miss=False)
    if col:
        theme.transition.border_color = col
    val = _parse_float(css, ".transition", "border-radius", source, log_miss=False)
    if val is not None:
        theme.transition.border_radius = int(val)
    img = _parse_pixmap(css, ".transition", "background-image", source, log_miss=log_miss)
    if img:
        theme.transition.background_image = img
    col = _parse_color(css, ".transition_label", "color", source, log_miss=log_miss)
    if col:
        theme.transition.font_color = col
    val = _parse_float(css, ".transition", "font-size", source, log_miss=log_miss)
    if val is not None:
        theme.transition.font_size = int(val)
    val = _parse_float(css, ".transition", "height", source, log_miss=log_miss)
    if val is not None:
        theme.transition.height = int(val)


def _css_apply_track(theme: TimelineTheme, css: str, source: str, log_miss: bool) -> None:
    _apply_gradient_with_fallback(
        theme.track,
        "background",
        "background2",
        lambda: _parse_gradient(css, ".track", "background", source, log_miss=False),
        lambda: _parse_color(
            css,
            ".track",
            ("background", "background-color"),
            source,
            log_miss=log_miss,
        ),
    )
    _apply_css_color_value(
        theme.track,
        "border_color",
        css,
        ".track",
        ("border-top", "border"),
        source,
        log_miss=False,
    )
    _apply_css_float_value(
        theme.track,
        "border_radius",
        css,
        ".track",
        "border-radius",
        source,
        log_miss=False,
        transform=int,
    )
    col = _css_get_first_color(
        css,
        source,
        log_miss,
        [
            (".track_name", "color"),
            (".track_label", "color"),
        ],
    )
    _assign_color(theme.track, "font_color", col)
    _apply_css_float_value(
        theme.track,
        "height",
        css,
        ".track",
        "height",
        source,
        log_miss=log_miss,
        transform=int,
    )
    _apply_css_color_value(
        theme.track,
        "name_background",
        css,
        ".track_name",
        ("background", "background-color"),
        source,
        log_miss=log_miss,
    )
    _apply_css_float_value(
        theme.track,
        "name_width",
        css,
        ".track_name",
        "width",
        source,
        log_miss=log_miss,
        transform=int,
    )
    _apply_css_float_value(
        theme.track,
        "gap",
        css,
        ".track",
        "margin-bottom",
        source,
        log_miss=log_miss,
        transform=int,
    )
    for attr, prop in (
        ("name_border_color", "border-left"),
        ("name_border_top_color", ("border-top", "border")),
        ("name_border_bottom_color", ("border-bottom", "border")),
    ):
        _apply_css_color_value(theme.track, attr, css, ".track_name", prop, source, log_miss=log_miss)
    for attr, prop in (
        ("name_border_width", "border-left"),
        ("name_border_top_width", ("border-top", "border")),
        ("name_border_bottom_width", ("border-bottom", "border")),
    ):
        _apply_css_float_value(
            theme.track,
            attr,
            css,
            ".track_name",
            prop,
            source,
            log_miss=log_miss,
            transform=int,
        )
    _apply_css_float_value(
        theme.track,
        "name_radius_tl",
        css,
        ".track_name",
        ("border-top-left-radius", "border-radius"),
        source,
        log_miss=log_miss,
        transform=int,
    )
    _apply_css_float_value(
        theme.track,
        "name_radius_bl",
        css,
        ".track_name",
        ("border-bottom-left-radius", "border-radius"),
        source,
        log_miss=log_miss,
        transform=int,
    )
    _apply_css_float_value(
        theme.track,
        "font_size",
        css,
        ".track_name",
        "font-size",
        source,
        log_miss=log_miss,
        transform=int,
    )


def _css_apply_ruler(theme: TimelineTheme, css: str, source: str, log_miss: bool) -> None:
    _apply_gradient_with_fallback(
        theme.ruler,
        "background",
        "background2",
        lambda: _ruler_gradient(css, source),
        lambda: _ruler_css_background(css, source),
        miss_log=lambda: log.info(
            "Theme MISS [%s] selector '#scrolling_ruler' property 'background'",
            source,
        ),
    )
    _apply_gradient_with_fallback(
        theme,
        "ruler_name_background",
        "ruler_name_background2",
        lambda: _parse_gradient(css, "#ruler_label", "background", source, log_miss=log_miss),
        lambda: _parse_color(
            css,
            "#ruler_label",
            ("background", "background-color"),
            source,
            log_miss=log_miss,
        ),
    )
    _apply_css_color_value(
        theme.ruler,
        "border_color",
        css,
        ".tick_mark",
        "background-color",
        source,
        log_miss=log_miss,
    )
    _apply_css_color_value(
        theme.ruler,
        "font_color",
        css,
        "#ruler_time",
        "color",
        source,
        log_miss=log_miss,
    )
    _apply_css_float_value(
        theme,
        "ruler_time_font_size",
        css,
        "#ruler_time",
        "font-size",
        source,
        log_miss=log_miss,
        transform=int,
    )
    fs = _parse_float(css, ".ruler_time", "font-size", source, log_miss=log_miss)
    if fs is not None:
        base = theme.ruler_time_font_size or 12
        theme.ruler.font_size = int(fs * base) if fs < 5 else int(fs)
    _apply_css_float_value(
        theme,
        "ruler_label_top",
        css,
        ".ruler_time",
        "top",
        source,
        log_miss=log_miss,
        transform=int,
    )
    _apply_css_float_value(
        theme.ruler,
        "height",
        css,
        "#ruler",
        "height",
        source,
        log_miss=log_miss,
        transform=int,
    )
    _apply_css_float_value(
        theme,
        "ruler_time_pad_left",
        css,
        "#ruler_time",
        "padding-left",
        source,
        log_miss=log_miss,
        transform=int,
    )
    _apply_css_float_value(
        theme,
        "ruler_time_pad_top",
        css,
        "#ruler_time",
        "padding-top",
        source,
        log_miss=log_miss,
        transform=int,
    )


def _css_apply_playhead(theme: TimelineTheme, css: str, source: str, log_miss: bool) -> None:
    col = _parse_color(css, ".playhead-line", "background-color", source, log_miss=log_miss)
    if col:
        theme.playhead_color = col
    val = _parse_float(css, ".playhead-line", "width", source, log_miss=log_miss)
    if val is not None:
        theme.playhead_width = val
    img = _parse_pixmap(css, ".playhead-top", "background-image", source, log_miss=log_miss)
    if img:
        theme.playhead_icon = img
    val = _parse_float(css, ".playhead-top", "width", source, log_miss=log_miss)
    if val is not None:
        theme.playhead_icon_width = int(val)
    val = _parse_float(css, ".playhead-top", "height", source, log_miss=log_miss)
    if val is not None:
        theme.playhead_icon_height = int(val)
    val = _parse_float(css, ".playhead-top", "margin-left", source, log_miss=log_miss)
    if val is not None:
        theme.playhead_icon_offset_x = int(val)
    val = _parse_float(css, ".playhead-top", "margin-top", source, log_miss=log_miss)
    if val is not None:
        theme.playhead_icon_offset_y = int(val)


def _css_apply_markers(theme: TimelineTheme, css: str, source: str, log_miss: bool) -> None:
    img = _parse_pixmap(css, ".marker_icon", "background-image", source, log_miss=log_miss)
    if img:
        theme.marker_icon = img
    val = _parse_float(css, ".marker_icon", "width", source, log_miss=log_miss)
    if val is not None:
        theme.marker_icon_width = int(val)
    val = _parse_float(css, ".marker_icon", "height", source, log_miss=log_miss)
    if val is not None:
        theme.marker_icon_height = int(val)
    val = _parse_float(css, ".marker_icon", "margin-left", source, log_miss=log_miss)
    if val is not None:
        theme.marker_icon_offset_x = int(val)
    val = _parse_float(css, ".marker_icon", "bottom", source, log_miss=log_miss)
    if val is not None:
        theme.marker_icon_offset_y = int(val)


def _css_apply_menu(theme: TimelineTheme, css: str, source: str, log_miss: bool) -> None:
    img = _parse_pixmap(css, ".menu", "background-image", source, log_miss=log_miss)
    if img:
        theme.menu_icon = img
    val = _parse_float(css, ".menu", "width", source, log_miss=log_miss)
    if val is not None:
        theme.menu_size = int(val)
    margin = _css_prop(css, ".menu", "margin", source, log_selector=log_miss, log_property=log_miss)
    if margin:
        match = re.search(r"(-?[0-9.]+)", margin)
        if match:
            theme.menu_margin = int(float(match.group(1)))


def _css_apply_keyframe_panel(theme: TimelineTheme, css: str, source: str, log_miss: bool) -> None:
    off_img = _parse_pixmap(
        css,
        ".track-keyframe-panel-disabled",
        "background-image",
        source,
        log_miss=log_miss,
    ) or _parse_pixmap(css, ".keyframe-toggle-off", "background-image", source, log_miss=log_miss)
    if off_img:
        theme.track_keyframe_panel_disabled_icon = off_img
        theme.keyframe_toggle_off_icon = off_img
    on_img = _parse_pixmap(
        css,
        ".track-keyframe-panel-enabled",
        "background-image",
        source,
        log_miss=log_miss,
    ) or _parse_pixmap(css, ".keyframe-toggle-on", "background-image", source, log_miss=log_miss)
    if on_img:
        theme.track_keyframe_panel_enabled_icon = on_img
        theme.keyframe_toggle_on_icon = on_img
    add_img = _parse_pixmap(css, ".keyframe-panel-add", "background-image", source, log_miss=log_miss)
    if add_img:
        theme.keyframe_panel_add_icon = add_img


def _css_apply_track_toolbar(theme: TimelineTheme, css: str, source: str, log_miss: bool) -> None:
    def _set_icon(attr, selector):
        pix = _parse_pixmap(css, selector, "background-image", source, log_miss=log_miss)
        if pix:
            setattr(theme, attr, pix)

    _set_icon("track_add_above_disabled_icon", ".track-add-above-disabled")
    _set_icon("track_add_above_enabled_icon", ".track-add-above-enabled")
    _set_icon("track_add_below_disabled_icon", ".track-add-below-disabled")
    _set_icon("track_add_below_enabled_icon", ".track-add-below-enabled")
    _set_icon("track_delete_disabled_icon", ".track-delete-disabled")
    _set_icon("track_delete_enabled_icon", ".track-delete-enabled")
    _set_icon("track_locked_disabled_icon", ".track-locked-disabled")
    _set_icon("track_locked_enabled_icon", ".track-locked-enabled")
    _set_icon("track_unlocked_disabled_icon", ".track-unlocked-disabled")
    _set_icon("track_unlocked_enabled_icon", ".track-unlocked-enabled")


def _css_apply_scrollbars(theme: TimelineTheme, css: str, source: str) -> None:
    col = _parse_color(css, "::-webkit-scrollbar-thumb", "background-color", source, log_miss=False)
    if col:
        theme.scrollbar_handle = col
    col = _parse_color(
        css,
        "::-webkit-scrollbar-track",
        ("background", "background-color"),
        source,
        log_miss=False,
    )
    if col:
        theme.scrollbar_track = col
    val = _parse_float(css, "::-webkit-scrollbar", ("width", "height"), source, log_miss=False)
    if val is not None:
        theme.scrollbar_width = int(val)


def _apply_css(theme: TimelineTheme, css: str, source: str = "css") -> TimelineTheme:
    """Update *theme* with values parsed from *css*."""

    if not css:
        return theme

    log_miss = True

    _css_apply_background(theme, css, source, log_miss)
    _css_apply_clip(theme, css, source, log_miss)
    _css_apply_selection(theme, css, source, log_miss)
    _css_apply_transition(theme, css, source, log_miss)
    _css_apply_track(theme, css, source, log_miss)
    _css_apply_ruler(theme, css, source, log_miss)
    _css_apply_playhead(theme, css, source, log_miss)
    _css_apply_markers(theme, css, source, log_miss)
    _css_apply_menu(theme, css, source, log_miss)
    _css_apply_keyframe_panel(theme, css, source, log_miss)
    _css_apply_track_toolbar(theme, css, source, log_miss)
    _css_apply_scrollbars(theme, css, source)

    return theme

def apply_theme(widget, css: str = "") -> bool:
    """Load theme values for *widget* and return True if geometry changed."""

    from classes.app import get_app

    app_theme = get_app().theme_manager.get_current_theme() if get_app() else None

    t = TimelineTheme()

    # Start with defaults from the main CSS file
    t = _apply_css(t, MAIN_CSS, source="main.css")

    # Override with values from the active Qt theme instance
    if app_theme:
        t = _apply_theme_obj(t, app_theme)

    # Optional additional CSS overrides
    if isinstance(css, str) and css.strip():
        t = _apply_css(t, css, source="override")

    if not t.playhead_icon:
        base = os.path.dirname(_CSS_PATH)
        default_path = os.path.normpath(os.path.join(base, "../images/playhead.svg"))
        if os.path.exists(default_path):
            t.playhead_icon = QPixmap(default_path)
            log.info(
                "Theme [default] .playhead-top background-image loaded '%s'",
                default_path,
            )

    def _load_fallback_icon(*parts):
        path = os.path.normpath(os.path.join(PATH, *parts))
        if not os.path.exists(path):
            return None
        pix = _load_pixmap_with_meta(path)
        if not pix:
            return None
        log.info("Theme [default] fallback icon loaded '%s'", path)
        return pix

    def _ensure_icon(attr, parts):
        pix = getattr(t, attr, None)
        if pix and not pix.isNull():
            return
        fallback = _load_fallback_icon(*parts)
        if fallback:
            setattr(t, attr, fallback)

    _fallback_map = {
        "track_keyframe_panel_disabled_icon": ("themes", "humanity", "images", "track-keyframe-panel-show-disabled.svg"),
        "track_keyframe_panel_enabled_icon": ("themes", "humanity", "images", "track-keyframe-panel-show-enabled.svg"),
        "track_add_above_disabled_icon": ("themes", "humanity", "images", "track-add-above-disabled.svg"),
        "track_add_above_enabled_icon": ("themes", "humanity", "images", "track-add-above-enabled.svg"),
        "track_add_below_disabled_icon": ("themes", "humanity", "images", "track-add-below-disabled.svg"),
        "track_add_below_enabled_icon": ("themes", "humanity", "images", "track-add-below-enabled.svg"),
        "track_delete_disabled_icon": ("themes", "humanity", "images", "track-delete-disabled.svg"),
        "track_delete_enabled_icon": ("themes", "humanity", "images", "track-delete-enabled.svg"),
        "track_locked_disabled_icon": ("themes", "humanity", "images", "track-locked-disabled.svg"),
        "track_locked_enabled_icon": ("themes", "humanity", "images", "track-locked-enabled.svg"),
        "track_unlocked_disabled_icon": ("themes", "humanity", "images", "track-unlocked-disabled.svg"),
        "track_unlocked_enabled_icon": ("themes", "humanity", "images", "track-unlocked-enabled.svg"),
        "marker_icon": ("timeline", "media", "images", "markers", "marker.svg"),
    }

    for attr, parts in _fallback_map.items():
        _ensure_icon(attr, parts)

    if t.marker_icon and not t.marker_icon.isNull():
        if not t.marker_icon_width:
            t.marker_icon_width = t.marker_icon.width()
        if not t.marker_icon_height:
            t.marker_icon_height = t.marker_icon.height()

    if (not t.keyframe_toggle_off_icon or t.keyframe_toggle_off_icon.isNull()) and t.track_keyframe_panel_disabled_icon:
        t.keyframe_toggle_off_icon = t.track_keyframe_panel_disabled_icon
    if (not t.keyframe_toggle_on_icon or t.keyframe_toggle_on_icon.isNull()) and t.track_keyframe_panel_enabled_icon:
        t.keyframe_toggle_on_icon = t.track_keyframe_panel_enabled_icon

    if not t.keyframe_panel_add_icon or t.keyframe_panel_add_icon.isNull():
        fallback = _load_fallback_icon("themes", "humanity", "images", "keyframe-panel-add.svg")
        if fallback:
            t.keyframe_panel_add_icon = fallback

    if not t.menu_icon or t.menu_icon.isNull():
        fallback = _load_fallback_icon("timeline", "media", "images", "menu.svg")
        if fallback:
            t.menu_icon = fallback
            if not t.menu_size:
                t.menu_size = fallback.width()


    old_track_h = widget.track_height
    old_name_w = widget.track_name_width
    old_ruler_h = widget.ruler_height
    old_gap = getattr(widget, 'track_gap', 0)
    old_margin_top = getattr(widget, 'track_margin_top', 0)

    widget.theme = t

    if t.track.height:
        widget.track_height = t.track.height
    if t.track.name_width:
        widget.track_name_width = t.track.name_width
    if t.track.gap:
        widget.track_gap = t.track.gap
    if t.track.margin_top >= 0:
        widget.track_margin_top = t.track.margin_top
    else:
        current_gap = getattr(widget, 'track_gap', 0)
        if current_gap:
            widget.track_margin_top = current_gap
    if t.ruler.height:
        widget.ruler_height = t.ruler.height
    if t.scrollbar_width:
        widget.scroll_bar_thickness = t.scrollbar_width

    return (
        old_track_h != widget.track_height
        or old_name_w != widget.track_name_width
        or old_ruler_h != widget.ruler_height
        or old_gap != widget.track_gap
        or old_margin_top != getattr(widget, 'track_margin_top', 0)
    )
