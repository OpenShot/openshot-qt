"""
 @file
 @brief Check export settings against the FFmpeg build OpenShot is running with.

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import json
import locale
import os
import re

ERROR = "error"
WARNING = "warning"

# Export modes (matching configure_writer)
VIDEO_AUDIO = "video_audio"
VIDEO_ONLY = "video"
AUDIO_ONLY = "audio"
IMAGE_SEQUENCE = "image_sequence"

# Channel layout masks (matching openshot.LAYOUT_*)
LAYOUT_MONO = 0x4
LAYOUT_STEREO = 0x3

# Quality units accepted after a number, and their writer limits
QUALITY_LIMITS = {"crf": 63, "cqp": 63, "qp": 255}

COMMON_SAMPLE_RATES = [8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000, 88200, 96000]
COMMON_AUDIO_BITRATES = ["64 kb/s", "96 kb/s", "128 kb/s", "160 kb/s", "192 kb/s", "256 kb/s", "320 kb/s"]
COMMON_VIDEO_BITRATES = ["1 Mb/s", "2.5 Mb/s", "5 Mb/s", "8 Mb/s", "12 Mb/s", "20 Mb/s", "40 Mb/s"]
COMMON_QUALITY_VALUES = {"crf": ["18 crf", "23 crf", "28 crf"], "qp": ["20 qp", "25 qp", "30 qp"]}

# Formats offered in the format dropdown (when this FFmpeg build has them)
COMMON_FORMATS = ["mp4", "mkv", "mov", "webm", "avi", "mpeg", "ogg", "gif",
                  "mp3", "m4a", "flac", "wav", "opus"]

IMAGE_SEQUENCE_PATTERN = re.compile(r"%0?\d*d")

# Audio formats whose only "video" is a cover image (i.e. mp3, flac): FFmpeg accepts any video
# codec there and quietly treats its first frame as the picture.
COVER_IMAGE_CODECS = ("png", "mjpeg")

# The setting an engine check blames, by the stage that failed (see export_settings.test_writer)
ENGINE_STAGE_FIELDS = {"video": "vcodec", "audio": "acodec", "format": "vformat", "header": "vformat"}


class Issue:
    """One problem with one export setting."""

    def __init__(self, field, severity, message, fix=None, fix_label=None):
        self.field = field
        self.severity = severity
        self.message = message
        self.fix = fix
        self.fix_label = fix_label

    @property
    def is_error(self):
        return self.severity == ERROR

    def __repr__(self):
        return "Issue(%r, %r, %r, fix=%r)" % (self.field, self.severity, self.message, self.fix)


def parse_rate(text):
    """Split a bit rate or quality string (i.e. '128 kb/s', '23 crf') into (number, unit).

    Returns None when the text can't be understood. The rules match Export.convert_to_bytes."""
    parts = (text or "").strip().lower().split()
    if len(parts) < 2:
        return None
    try:
        number = locale.atof(parts[0])
    except ValueError:
        try:
            number = float(parts[0])
        except ValueError:
            return None
    measurement = parts[1]
    for unit in ("kb", "mb", "crf", "cqp", "qp"):
        if unit in measurement:
            return number, unit
    return None


def rate_to_value(number, unit):
    """Convert a parsed rate into the integer the writer expects (bits per second, or quality)."""
    if unit == "kb":
        return int(number * 1000.0)
    if unit == "mb":
        return int(number * 1000.0 * 1000.0)
    return int(min(max(number, 0), QUALITY_LIMITS[unit]))


class Capabilities:
    """Cached questions about the FFmpeg build, asked through libopenshot."""

    def __init__(self, writer=None):
        if writer is None:
            import openshot
            writer = openshot.FFmpegWriter
        self.writer = writer
        self._cache = {}

    def _cached(self, key, compute):
        if key not in self._cache:
            try:
                self._cache[key] = compute()
            except (RuntimeError, ValueError, TypeError):
                self._cache[key] = None
        return self._cache[key]

    def encoder(self, name):
        """Encoder details (or {'found': False}). Lists are None when anything is accepted."""
        name = (name or "").strip()
        return self._cached(("encoder", name), lambda: json.loads(self.writer.GetEncoderInfo(name))) or {}

    def format(self, name):
        """Format details, or {'found': False}."""
        name = (name or "").strip()
        return self._cached(("format", name), lambda: json.loads(self.writer.GetFormatInfo(name))) or {}

    def supports(self, format_name, codec_name):
        """1 if the format can hold the codec, 0 if not, -1 when unknown."""
        result = self._cached(("supports", format_name, codec_name),
                              lambda: int(self.writer.IsCodecSupportedByFormat(format_name, codec_name)))
        return -1 if result is None else result

    def encoders(self, media_type, format_name=""):
        """Available encoders of a media type, optionally limited to those a format can hold."""
        return self._cached(("encoders", media_type, format_name),
                            lambda: json.loads(self.writer.GetEncoders(media_type, format_name))) or []

    def formats(self, candidates=COMMON_FORMATS):
        """The candidate formats this FFmpeg build can write."""
        return [name for name in candidates if self.format(name).get("found")]

    def all_formats(self):
        """Every file extension the writer can export to (FFmpegWriter.GetFormats)."""
        return self._cached(("all_formats",), lambda: json.loads(self.writer.GetFormats())) or []


# Menus longer than FLAT_LIMIT are grouped into categories. Groups longer than MENU_LIMIT (about
# a screen) split again, alphabetically, as a last resort.
FLAT_LIMIT = 10
MENU_LIMIT = 30

# Formats for single images, which Image Sequence exports use instead (see its Image Format field)
SINGLE_IMAGE_FORMATS = ("image2", "image2pipe", "ico", "fits")
ANIMATION_FORMATS = ("gif", "apng", "webp")


def encoder_menu(encoders, media_type, tr=lambda text: text):
    """Group encoders into a menu that's quick to skim (see grouped_menu).

    encoders: dicts like Capabilities.encoder() returns. Categories are i.e. Hardware Accelerated,
    and families are encoders of the same codec (i.e. h264) or name prefix (i.e. pcm_).
    """
    _ = tr
    if media_type == "video":
        categories = [
            (_("Hardware Accelerated"), lambda e: e.get("hardware")),
            (_("Sharing & Playback"), lambda e: e.get("lossy") and not e.get("intra_only")),
            (_("Editing & Mastering"), lambda e: e.get("lossy") and not e.get("image")),
            (_("Images"), lambda e: e.get("image")),
            (_("Lossless"), lambda e: e.get("lossless")),
        ]
    else:
        categories = [(_("Lossy"), lambda e: e.get("lossy")),
                      (_("Lossless & Uncompressed"), lambda e: e.get("lossless"))]
    categories.append((_("Other"), lambda e: True))
    return grouped_menu(encoders, categories, lambda e: e.get("name", ""), _encoder_families)


def format_menu(formats, tr=lambda text: text, encoder=lambda name: {}):
    """Group formats (FFmpegWriter.GetFormats rows) into a menu that's quick to skim.

    Formats that can't hold video or audio (i.e. subtitles), and single images, are left out.
    encoder(name) describes a codec (Capabilities.encoder), to split lossless audio formats out.
    """
    _ = tr

    def video(row):
        return row.get("default_video_codec") and row.get("default_video_codec") not in COVER_IMAGE_CODECS

    formats = [row for row in formats if (row.get("default_video_codec") or row.get("default_audio_codec"))
               and row.get("name") not in SINGLE_IMAGE_FORMATS]
    categories = [
        (_("Video"), lambda row: video(row) and row.get("default_audio_codec")),
        (_("Audio"), lambda row: row.get("default_audio_codec")
         and not encoder(row["default_audio_codec"]).get("lossless")),
        (_("Lossless & PCM Audio"), lambda row: row.get("default_audio_codec")),
        (_("Animation"), lambda row: row.get("name") in ANIMATION_FORMATS),
        (_("Raw Video Streams"), lambda row: True),
    ]

    def families(rows):
        # Extensions of the same format (i.e. ts, m2ts, mts)
        counts = {}
        for row in rows:
            counts[row.get("name")] = counts.get(row.get("name"), 0) + 1
        return [row.get("name") if counts[row.get("name")] >= 3 else None for row in rows]

    return grouped_menu(formats, categories, lambda row: row.get("extension", ""), families)


def grouped_menu(items, categories, name, families=None):
    """Split a long list into a menu that's quick to skim.

    Returns a list of nodes, where each node is an item or a (title, [nodes]) group: categories
    first (the first matching (title, test) wins), then families of related items
    (families(items) gives each item's family, or None), then alphabetical ranges as a last resort.
    Short lists stay flat.
    """
    items = sorted(items, key=lambda item: name(item).lower())
    if len(items) <= FLAT_LIMIT:
        return items
    groups = []
    remaining = items
    for title, belongs in categories:
        members = [item for item in remaining if belongs(item)]
        remaining = [item for item in remaining if not belongs(item)]
        if members:
            nodes = _menu_families(members, name, families) if families else members
            groups.append(("%s (%d)" % (title, len(members)), _menu_ranges(nodes, name)))
    return groups[0][1] if len(groups) == 1 else groups


def _menu_label(node, name):
    return node[0] if isinstance(node, tuple) else name(node)


def _menu_families(items, name, families):
    """Collapse families of 3 or more items into one group each."""
    keys = families(items)
    by_family = {}
    for item, key in zip(items, keys):
        by_family.setdefault(key, []).append(item)
    nodes = []
    for key, members in by_family.items():
        if key and len(members) >= 3:
            nodes.append(("%s (%d)" % (key.upper(), len(members)), members))
        else:
            nodes.extend(members)
    return sorted(nodes, key=lambda node: _menu_label(node, name).lower())


def _encoder_families(encoders):
    """Each encoder's family: its codec when 3+ share it (i.e. h264), or its name prefix (i.e. pcm)."""
    codecs = {}
    for encoder in encoders:
        codecs[encoder.get("codec")] = codecs.get(encoder.get("codec"), 0) + 1
    families = []
    for encoder in encoders:
        name, codec = encoder.get("name", ""), encoder.get("codec")
        families.append(codec if codec and codecs[codec] >= 3 else (name.split("_")[0] if "_" in name else None))
    return families


def _menu_ranges(nodes, name):
    """Split a long menu into alphabetical ranges (i.e. "A – F")."""
    if len(nodes) <= MENU_LIMIT:
        return nodes
    count = -(-len(nodes) // MENU_LIMIT)
    size = -(-len(nodes) // count)
    ranges = []
    for start in range(0, len(nodes), size):
        part = nodes[start:start + size]
        first, last = _menu_label(part[0], name), _menu_label(part[-1], name)
        if first[:1].upper() != last[:1].upper():
            title = "%s – %s" % (first[:1].upper(), last[:1].upper())
        else:
            # Many names share a first letter (i.e. lib*), so show them whole
            title = "%s – %s" % (first, last)
        ranges.append((title, part))
    return ranges


def _closest(value, choices):
    return min(choices, key=lambda choice: (abs(choice - value), -choice))


def _pixel_format_constraint(pixel_format):
    """Return (width_even, height_even) required by a pixel format's chroma subsampling."""
    name = (pixel_format or "").lower()
    if "420" in name or name.startswith(("nv12", "nv21", "p010", "p016")):
        return True, True
    if "422" in name or name in ("yuyv422", "uyvy422", "nv16") or "411" in name:
        return True, False
    return False, False


class ExportValidator:
    """Check a dictionary of export settings, and return a list of Issues.

    Settings keys: mode, vformat, vcodec, video_bitrate, width, height, fps_num, fps_den,
    image_format, acodec, sample_rate, channel_layout, audio_bitrate, start_frame, end_frame, folder."""

    def __init__(self, capabilities=None, tr=None):
        self.caps = capabilities or Capabilities()
        self._ = tr or (lambda text: text)

    def validate(self, settings):
        issues = []
        mode = settings.get("mode", VIDEO_AUDIO)
        if mode == IMAGE_SEQUENCE:
            self._check_image_sequence(settings, issues)
        else:
            self._check_format(settings, issues)
            if mode in (VIDEO_AUDIO, VIDEO_ONLY):
                self._check_video(settings, issues)
            if mode in (VIDEO_AUDIO, AUDIO_ONLY):
                self._check_audio(settings, issues)
        self._check_range_and_folder(settings, issues)
        return issues

    # ----- Format -----

    def _format_name(self, settings):
        return (settings.get("vformat") or "").strip().lstrip(".")

    def _check_format(self, settings, issues):
        _ = self._
        vformat = self._format_name(settings)
        if not vformat:
            issues.append(Issue("vformat", ERROR, _("Choose a file format (such as mp4)."), "mp4", "mp4"))
            return
        if "/" in vformat or "\\" in vformat or " " in vformat:
            issues.append(Issue("vformat", ERROR, _("The format should be a file extension, such as mp4.")))
            return
        info = self.caps.format(vformat)
        if info.get("found") is False:
            issues.append(Issue("vformat", ERROR,
                                _("%(format)s isn't a file format this version of FFmpeg can write.") % {
                                    "format": vformat}, "mp4", "mp4"))

    def effective_codec(self, settings, key, default_key):
        """The codec the writer will use: the chosen one, or the format's default."""
        codec = (settings.get(key) or "").strip()
        if codec:
            return codec, False
        return (self.caps.format(self._format_name(settings)).get(default_key) or ""), True

    def is_cover_image_format(self, vformat):
        """True for audio formats whose only picture is a cover image (i.e. mp3, flac)."""
        info = self.caps.format(vformat)
        return bool(info.get("found") and info.get("default_audio_codec")
                    and info.get("default_video_codec") in COVER_IMAGE_CODECS)

    def engine_issue(self, settings, result):
        """Turn a failed engine check (export_settings.test_writer) into an Issue, or None."""
        if result.get("ok"):
            return None
        _ = self._
        field = ENGINE_STAGE_FIELDS.get(result.get("stage"), "vformat")
        fix = None
        if field == "vcodec":
            fix = self._suggest_encoder(settings, "video", "default_video_codec")
        elif field == "acodec":
            fix = self._suggest_encoder(settings, "audio", "default_audio_codec")
        current, _is_default = self.effective_codec(
            settings, field, "default_video_codec" if field == "vcodec" else "default_audio_codec") \
            if field != "vformat" else (None, False)
        if fix == current:
            fix = None
        message = _("FFmpeg can't export these settings: %(reason)s") % {
            "reason": result.get("message") or _("unknown error")}
        return Issue(field, ERROR, message, fix, fix)

    def _suggest_encoder(self, settings, media_type, default_key):
        """A good replacement encoder for this format, or None."""
        vformat = self._format_name(settings)
        default = self.caps.format(vformat).get(default_key)
        if default and self.caps.encoder(default).get("found"):
            return default
        encoders = self.caps.encoders(media_type, vformat)
        return encoders[0]["name"] if encoders else None

    def _codec_messages(self, media_type):
        _ = self._
        if media_type == "video":
            return {"missing": _("%(codec)s isn't a video encoder in this version of FFmpeg."),
                    "type": _("%(codec)s is not a video codec."),
                    "format": _("%(format)s files can't hold %(codec)s video.")}
        return {"missing": _("%(codec)s isn't an audio encoder in this version of FFmpeg."),
                "type": _("%(codec)s is not an audio codec."),
                "format": _("%(format)s files can't hold %(codec)s audio.")}

    def _check_codec(self, settings, issues, field, media_type, default_key):
        """Check a codec exists, is the right type, and fits the format. Returns its info or None."""
        codec, is_default = self.effective_codec(settings, field, default_key)
        if not codec:
            return None
        vformat = self._format_name(settings)
        info = self.caps.encoder(codec)
        messages = self._codec_messages(media_type)
        values = {"codec": codec, "format": vformat}
        problem = None
        if not info.get("found"):
            if is_default:
                return None
            problem = "missing"
        elif info.get("type") and info.get("type") != media_type:
            problem = "type"
        elif self.caps.format(vformat).get("found") and self.caps.supports(vformat, codec) == 0:
            problem = "format"
        if problem:
            fix = self._suggest_encoder(settings, media_type, default_key)
            issues.append(Issue(field, ERROR, messages[problem] % values, fix, fix))
            return None
        return info

    # ----- Video -----

    def _check_video(self, settings, issues):
        _ = self._
        vformat = self._format_name(settings)
        format_info = self.caps.format(vformat)
        if format_info.get("found") and not format_info.get("default_video_codec") \
                and not (settings.get("vcodec") or "").strip():
            if settings.get("mode") == VIDEO_ONLY:
                issues.append(Issue("vformat", ERROR, _("%(format)s files can't hold video.") % {
                    "format": vformat}))
            else:
                issues.append(Issue("vformat", WARNING, _("%(format)s files can't hold video, so only audio "
                                                          "will be exported.") % {"format": vformat}))
            return

        if self.is_cover_image_format(vformat):
            codec, _is_default = self.effective_codec(settings, "vcodec", "default_video_codec")
            if settings.get("mode") == VIDEO_ONLY:
                issues.append(Issue("vformat", ERROR, _("%(format)s files hold audio and a cover image, "
                                                        "not video.") % {"format": vformat}, "mp4", "mp4"))
                return
            if codec not in COVER_IMAGE_CODECS:
                fix = format_info.get("default_video_codec")
                issues.append(Issue("vcodec", ERROR, _("%(format)s files can only hold a cover image, so "
                                                       "%(codec)s video can't be used.") % {
                                        "format": vformat, "codec": codec}, fix, fix))
            # A single picture: bit rate and quality settings don't apply
            return

        info = self._check_codec(settings, issues, "vcodec", "video", "default_video_codec")
        self._check_dimensions(settings, issues, info)
        self._check_video_rate(settings, issues, info)

    def _check_dimensions(self, settings, issues, info):
        _ = self._
        if not info or info.get("hardware") or not info.get("pixel_formats"):
            return
        need_even_width, need_even_height = _pixel_format_constraint(info["pixel_formats"][0])
        width, height = int(settings.get("width") or 0), int(settings.get("height") or 0)
        if need_even_width and width % 2:
            issues.append(Issue("width", ERROR, _("%(codec)s needs an even width.") % {
                "codec": info.get("name")}, width - 1, str(width - 1)))
        if need_even_height and height % 2:
            issues.append(Issue("height", ERROR, _("%(codec)s needs an even height.") % {
                "codec": info.get("name")}, height - 1, str(height - 1)))

    def _check_video_rate(self, settings, issues, info):
        _ = self._
        text = settings.get("video_bitrate") or ""
        parsed = parse_rate(text)
        if parsed is None:
            fix = self._unitless_fix(text, "kb/s") or "8 Mb/s"
            issues.append(Issue("video_bitrate", ERROR,
                                _("Use a bit rate (like 8 Mb/s) or a quality (like 23 crf)."), fix, fix))
            return
        number, unit = parsed
        if unit in QUALITY_LIMITS:
            if number < 0 or number > QUALITY_LIMITS[unit]:
                fix = "%d %s" % (min(max(number, 0), QUALITY_LIMITS[unit]), unit)
                issues.append(Issue("video_bitrate", ERROR, _("%(unit)s must be between 0 and %(max)d.") % {
                    "unit": unit, "max": QUALITY_LIMITS[unit]}, fix, fix))
            elif info and not info.get("hardware") and info.get("quality_options") == []:
                issues.append(Issue("video_bitrate", WARNING,
                                    _("%(codec)s doesn't support %(unit)s, so OpenShot will estimate a "
                                      "bit rate instead.") % {"codec": info.get("name"), "unit": unit}))
            return
        if rate_to_value(number, unit) < 1000:
            issues.append(Issue("video_bitrate", ERROR, _("The bit rate is too low to use."),
                                "8 Mb/s", "8 Mb/s"))

    # ----- Audio -----

    def _check_audio(self, settings, issues):
        _ = self._
        codec, _is_default = self.effective_codec(settings, "acodec", "default_audio_codec")
        if not codec:
            vformat = self._format_name(settings)
            if settings.get("mode") == AUDIO_ONLY and self.caps.format(vformat).get("found"):
                issues.append(Issue("vformat", ERROR, _("%(format)s files can't hold audio.") % {
                    "format": vformat}))
            return
        info = self._check_codec(settings, issues, "acodec", "audio", "default_audio_codec")

        sample_rate = int(settings.get("sample_rate") or 0)
        rates = (info or {}).get("sample_rates")
        if sample_rate < 8000:
            fix = _closest(48000, rates) if rates else 48000
            issues.append(Issue("sample_rate", ERROR, _("Choose a sample rate of at least 8000 Hz."),
                                fix, "%d Hz" % fix))
        elif rates and sample_rate not in rates:
            fix = _closest(sample_rate, rates)
            issues.append(Issue("sample_rate", ERROR, _("%(codec)s doesn't support %(rate)d Hz.") % {
                "codec": info.get("name"), "rate": sample_rate}, fix, "%d Hz" % fix))

        layout = settings.get("channel_layout")
        layouts = (info or {}).get("channel_layouts")
        if layouts and layout is not None and int(layout) not in layouts:
            known = [value for value in (LAYOUT_STEREO, LAYOUT_MONO) if value in layouts]
            fix = known[0] if known else None
            issues.append(Issue("channel_layout", ERROR, _("%(codec)s doesn't support this channel layout.") % {
                "codec": info.get("name")}, fix, fix and (_("Stereo") if fix == LAYOUT_STEREO else _("Mono"))))

        self._check_audio_rate(settings, issues, info)

    def _check_audio_rate(self, settings, issues, info):
        _ = self._
        if info and info.get("lossless") and not info.get("lossy"):
            # Lossless codecs ignore the bit rate, so anything goes
            return
        text = settings.get("audio_bitrate") or ""
        parsed = parse_rate(text)
        if parsed is None or parsed[1] in QUALITY_LIMITS:
            fix = self._unitless_fix(text, "kb/s") or "192 kb/s"
            issues.append(Issue("audio_bitrate", ERROR, _("Use an audio bit rate, like 192 kb/s."), fix, fix))
            return
        value = rate_to_value(*parsed)
        if value < 1000:
            issues.append(Issue("audio_bitrate", ERROR, _("The audio bit rate is too low to use."),
                                "192 kb/s", "192 kb/s"))
        elif value < 32000:
            issues.append(Issue("audio_bitrate", WARNING, _("Audio below 32 kb/s will sound poor.")))

    @staticmethod
    def _unitless_fix(text, unit):
        """Suggest a unit for a bare number (i.e. '128' -> '128 kb/s')."""
        text = (text or "").strip()
        match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(kbps|kbit/s|k|kb|kb/s|mbps|m|mb|mb/s)?", text.lower())
        if not match:
            return None
        number, suffix = match.groups()
        if suffix and suffix.startswith("m"):
            return "%s Mb/s" % number
        return "%s %s" % (number, unit)

    # ----- Image sequences -----

    def _check_image_sequence(self, settings, issues):
        _ = self._
        pattern = (settings.get("image_format") or "").strip()
        extension = os.path.splitext(pattern)[1].lstrip(".").lower()
        if not IMAGE_SEQUENCE_PATTERN.search(pattern):
            fix = "-%05d." + (extension or "png")
            issues.append(Issue("image_format", ERROR,
                                _("Include a frame number like %05d in the image name."), fix, fix))
            return
        if not extension:
            issues.append(Issue("image_format", ERROR, _("End the image name with a type, like .png."),
                                pattern + ".png", pattern + ".png"))
            return
        codec = "mjpeg" if extension in ("jpg", "jpeg") else extension
        if self.caps.format(extension).get("found") is False or not self.caps.encoder(codec).get("found"):
            fix = IMAGE_SEQUENCE_PATTERN.search(pattern).group(0)
            fix = pattern[:pattern.index(fix) + len(fix)] + ".png"
            issues.append(Issue("image_format", ERROR, _("%(type)s images aren't supported.") % {
                "type": extension}, fix, fix))

    # ----- Range and folder -----

    def _check_range_and_folder(self, settings, issues):
        _ = self._
        start, end = settings.get("start_frame"), settings.get("end_frame")
        if start is not None and end is not None and int(start) >= int(end):
            issues.append(Issue("end_frame", ERROR, _("The end frame must come after the start frame.")))
        folder = (settings.get("folder") or "").lstrip()
        if folder and not os.path.isdir(folder) and not os.path.isdir(folder.rstrip()):
            issues.append(Issue("folder", ERROR, _("This folder doesn't exist.")))
