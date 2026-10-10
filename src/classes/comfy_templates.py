"""
 @file
 @brief ComfyUI workflow template discovery and classification helpers.
"""

import copy
import json
import os
import re

from classes import info
from classes.logger import log


IMAGE_INPUT_TYPES = {
    "loadimage",
    "load image",
}
VIDEO_INPUT_TYPES = {
    "loadvideo",
    "load video",
    "vhs_loadvideo",
}
AUDIO_INPUT_TYPES = {
    "loadaudio",
    "load audio",
}

IMAGE_OUTPUT_TYPES = {
    "saveimage",
    "save image",
}
VIDEO_OUTPUT_TYPES = {
    "savevideo",
    "save video",
}
AUDIO_OUTPUT_TYPES = {
    "saveaudio",
    "save audio",
}

KNOWN_NODE_TYPES = {
    # Input
    "checkpointloadersimple",
    "unetloader",
    "cliptextencode",
    "cliploader",
    "vaeloader",
    "loadimage",
    "loadvideo",
    "vhs_loadvideo",
    "loadaudio",
    # Core built-in/OpenShot workflows
    "vaeencode",
    "vaedecode",
    "ksampler",
    "upscalemodelloader",
    "imageupscalewithmodel",
    "videoslice",
    "video slice",
    "getvideocomponents",
    "createvideo",
    "saveimage",
    "savevideo",
    "saveaudio",
    "getimagesize",
    "vhs_getimagecount",
    "save srt",
    "emptylatentimage",
    "emptyhunyuanlatentvideo",
    "wan22imagetovideolatent",
    "wanimagetoimageapi",
    "wantexttoimageapi",
    "imageonlycheckpointloader",
    "modelsamplingsd3",
    "svd_img2vid_conditioning",
    "videolinearcfgguidance",
    "emptylatentaudio",
    "vaedecodeaudio",
    "previewany",
    "apply whisper",
    "riff vfi",
    "rife vfi",
    "downloadandloadtransnetmodel",
    "transnetv2_run",
    "selectvideo",
    "stableaudioprojectionmodel",
    "stableaudiomodelloader",
    "stableaudioemptylatentaudio",
    "stableaudioembedding",
    "kdiffusionsampler",
    "stableaudiovaedecode",
    # ComfyUI_FL-ClearVoice
    "fl_clearvoice_modelloader",
    "fl_clearvoice_process",
    "videocombine",
    "imagescaleby",
    "imagetosimage",
    "imagetoimage",
    "imagescaleto",
    "imageblur",
    "imagecompositemasked",
    "imageblend",
    "controlnetloader",
    "controlnetapply",
    "controlnetapplyadvanced",
    "canny",
    "depthanythingpreprocessor",
    "depthanythingv2preprocessor",
    "midas-depthmappreprocessor",
    "zoe-depthmappreprocessor",
    "zoe_depthanythingpreprocessor",
    # Video Helper Suite
    "vhs_batchmanager",
    "vhs_loadaudio",
    "vhs_loadvideo",
    "vhs_loadaudioupload",
    "vhs_loadvideopath",
    "vhs_loadvideoffmpegpath",
    "vhs_videocombine",
    "vhs_videoinfo",
    "vhs_videoinfoloaded",
    "vhs_videoinfosource",
    # ComfyUI-segment-anything-2
    "downloadandloadsam2model",
    "sam2segmentation",
    "sam2autosegmentation",
    "sam2videosegmentationaddpoints",
    "sam2videosegmentation",
    # OpenShot-ComfyUI (custom SAM2)
    "openshotdownloadandloadsam2model",
    "openshotsam2segmentation",
    "openshotsam2videosegmentationaddpoints",
    "openshotsam2videosegmentationchunked",
    "openshotimageblurmasked",
    "openshotimagehighlightmasked",
    "openshotdeepfilternetdenoiseaudio",
    "openshotlavasrspeechclarity",
}


EXTRA_INPUT_TYPES = {"image", "video", "audio", "text", "choice"}
EXTRA_INPUT_KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")


class ComfyTemplateRegistry:
    """Discovers ComfyUI templates from built-in + user folders."""

    def __init__(self):
        self._cache = None
        self._cache_signature = None

    @staticmethod
    def _is_ignored_filename(name):
        return str(name or "").strip().lower() in ("debug.json", "debug_error.json", "debug_sent.json")

    def _template_roots(self):
        return [
            (os.path.join(info.PATH, "comfyui"), False),
            (info.COMFYUI_PATH, True),
        ]

    def _current_signature(self):
        signature = []
        for folder, _is_user in self._template_roots():
            if not os.path.isdir(folder):
                continue
            for name in sorted(os.listdir(folder)):
                if not name.lower().endswith(".json"):
                    continue
                if self._is_ignored_filename(name):
                    continue
                path = os.path.join(folder, name)
                try:
                    stat = os.stat(path)
                    signature.append((path, stat.st_mtime_ns, stat.st_size))
                except OSError:
                    continue
        return tuple(signature)

    def discover(self, force=False):
        signature = self._current_signature()
        if not force and self._cache is not None and signature == self._cache_signature:
            return self._cache

        templates = []
        existing_ids = set()
        for folder, is_user in self._template_roots():
            if not os.path.isdir(folder):
                continue
            for name in sorted(os.listdir(folder)):
                if not name.lower().endswith(".json"):
                    continue
                if self._is_ignored_filename(name):
                    continue
                path = os.path.join(folder, name)
                template = self._load_template(path, is_user=is_user, existing_ids=existing_ids)
                if template is None:
                    continue
                templates.append(template)

        templates.sort(key=lambda t: (int(t.get("sort_order", 99999)), str(t.get("display_name", "")).lower()))
        self._cache = templates
        self._cache_signature = signature
        return templates

    def _load_template(self, path, is_user, existing_ids):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as ex:
            log.warning("Skipping invalid ComfyUI template JSON %s: %s", path, ex)
            return None
        if not isinstance(payload, dict):
            log.warning("Skipping invalid ComfyUI template JSON %s: root must be an object", path)
            return None

        workflow = self._extract_workflow(payload)
        if workflow is None:
            log.warning("Skipping invalid ComfyUI template JSON %s: no valid workflow graph found", path)
            return None

        node_types = []
        input_types = set()
        output_types = set()
        unknown_node_types = set()
        needs_prompt = False
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            class_type = str(node.get("class_type", "")).strip()
            if not class_type:
                continue
            inputs = node.get("inputs", {})
            if not isinstance(inputs, dict):
                inputs = {}
            class_key = class_type.lower().replace("_", "")
            class_flat = class_type.lower().strip()
            node_types.append(class_type)

            text_value = inputs.get("text", None)
            if isinstance(text_value, str):
                meta = node.get("_meta", {})
                meta_title = ""
                if isinstance(meta, dict):
                    meta_title = str(meta.get("title", "")).strip().lower()
                if "textencode" in class_key or "prompt" in meta_title:
                    needs_prompt = True

            if class_flat in IMAGE_INPUT_TYPES or class_key in IMAGE_INPUT_TYPES:
                input_types.add("image")
            if class_flat in VIDEO_INPUT_TYPES or class_key in VIDEO_INPUT_TYPES:
                input_types.add("video")
            if class_flat in AUDIO_INPUT_TYPES or class_key in AUDIO_INPUT_TYPES:
                input_types.add("audio")

            if class_flat in IMAGE_OUTPUT_TYPES or class_key in IMAGE_OUTPUT_TYPES:
                output_types.add("image")
            if class_flat in VIDEO_OUTPUT_TYPES or class_key in VIDEO_OUTPUT_TYPES:
                output_types.add("video")
            if class_flat in AUDIO_OUTPUT_TYPES or class_key in AUDIO_OUTPUT_TYPES:
                output_types.add("audio")

            if class_flat not in KNOWN_NODE_TYPES and class_key not in KNOWN_NODE_TYPES:
                unknown_node_types.add(class_type)

        if unknown_node_types:
            log.warning(
                "ComfyUI template has unknown node types (%s): %s",
                os.path.basename(path),
                ", ".join(sorted(unknown_node_types)),
            )

        override_category = str(payload.get("menu_category") or payload.get("category") or "").strip().lower()
        override_menu_parent = str(payload.get("menu_parent") or "").strip()
        override_input_type = str(payload.get("input_type") or payload.get("source_type") or "").strip().lower()
        override_output_type = str(payload.get("output_type") or payload.get("media_output") or "").strip().lower()
        override_icon = str(payload.get("action_icon") or payload.get("icon") or "").strip()
        override_open_dialog = payload.get("open_dialog", None)
        needs_reference_image = bool(payload.get("needs_reference_image", False))
        extra_inputs = self._parse_extra_inputs(payload, path, needs_reference_image)

        inferred_category = "unknown"
        requires_source = bool(input_types)
        if output_types:
            inferred_category = "enhance" if requires_source else "create"
        else:
            if override_category not in ("create", "enhance", "unknown"):
                log.warning(
                    "ComfyUI template category unknown (%s): no output nodes detected",
                    os.path.basename(path),
                )
        if override_category in ("create", "enhance", "unknown"):
            inferred_category = override_category
        if override_input_type in ("image", "video", "audio"):
            input_types = {override_input_type}

        template_id = str(payload.get("template_id") or payload.get("id") or "").strip()
        if not template_id:
            template_id = os.path.splitext(os.path.basename(path))[0]

        unique_id = template_id
        suffix = 2
        while unique_id in existing_ids:
            unique_id = "{}__{}".format(template_id, suffix)
            suffix += 1
        existing_ids.add(unique_id)

        display_name = self._extract_name(payload, path)
        if is_user:
            display_name = "(User) {}".format(display_name)

        try:
            sort_order = int(payload.get("menu_order", 99999))
        except (TypeError, ValueError):
            sort_order = 99999
        primary_output = self._primary_output_type(output_types)
        if override_output_type in ("image", "video", "audio", "unknown"):
            primary_output = override_output_type

        open_dialog = None
        if isinstance(override_open_dialog, bool):
            open_dialog = override_open_dialog

        return {
            "id": unique_id,
            "template_id": template_id,
            "display_name": display_name,
            "path": path,
            "is_user": is_user,
            "category": inferred_category,
            "input_types": sorted(input_types),
            "output_types": sorted(output_types),
            "primary_output": primary_output,
            "sort_order": sort_order,
            "workflow": workflow,
            "node_types": node_types,
            "needs_prompt": needs_prompt,
            "action_icon": override_icon,
            "open_dialog": open_dialog,
            "menu_parent": override_menu_parent,
            "needs_reference_image": needs_reference_image,
            "extra_inputs": extra_inputs,
            "default_prompt": str(payload.get("default_prompt") or "").strip(),
        }

    def _parse_extra_inputs(self, payload, path, needs_reference_image):
        """Parse and normalize the optional "extra_inputs" template key.

        Each entry declares one additional input the Generate dialog should collect:
        an "image"/"video"/"audio" file (picked from Project Files, same as the existing
        reference-image combo) or free-form "text". Invalid entries are skipped with a
        warning rather than failing the whole template.

        Backward compatible with the older, single-purpose "needs_reference_image" flag:
        if set and no entry already declares key "reference_image", one is synthesized
        so existing templates (e.g. video2video-basic.json) keep working unchanged.
        """
        raw_entries = payload.get("extra_inputs")
        if raw_entries is None:
            raw_entries = []
        elif not isinstance(raw_entries, list):
            log.warning(
                "ComfyUI template has invalid extra_inputs (%s): must be a list, got %s",
                os.path.basename(path), type(raw_entries).__name__,
            )
            raw_entries = []

        parsed = []
        seen_keys = set()
        for entry in raw_entries:
            if not isinstance(entry, dict):
                log.warning(
                    "ComfyUI template has invalid extra_inputs entry (%s): not an object: %r",
                    os.path.basename(path), entry,
                )
                continue

            key = str(entry.get("key", "")).strip()
            if not key or not EXTRA_INPUT_KEY_PATTERN.match(key):
                log.warning(
                    "ComfyUI template has invalid extra_inputs entry (%s): "
                    "key must match [a-z0-9_]+, got %r",
                    os.path.basename(path), key,
                )
                continue
            if key in seen_keys:
                log.warning(
                    "ComfyUI template has duplicate extra_inputs key (%s): %r",
                    os.path.basename(path), key,
                )
                continue

            entry_type = str(entry.get("type", "")).strip().lower()
            if entry_type not in EXTRA_INPUT_TYPES:
                log.warning(
                    "ComfyUI template has invalid extra_inputs entry (%s): "
                    "type must be one of %s, got %r",
                    os.path.basename(path), sorted(EXTRA_INPUT_TYPES), entry_type,
                )
                continue

            label = str(entry.get("label", "")).strip()
            if not label:
                label = key.replace("_", " ").strip().capitalize()

            required = entry.get("required", True)
            if not isinstance(required, bool):
                required = True

            if entry_type == "choice":
                raw_choices = entry.get("choices")
                choices = [
                    str(c).strip() for c in raw_choices
                ] if isinstance(raw_choices, list) else []
                choices = [c for c in choices if c]
                if not choices:
                    log.warning(
                        "ComfyUI template has invalid extra_inputs entry (%s): "
                        "type 'choice' requires a non-empty 'choices' list, got %r",
                        os.path.basename(path), raw_choices,
                    )
                    continue

            seen_keys.add(key)
            parsed_entry = {"key": key, "type": entry_type, "label": label, "required": required}
            if entry_type == "text":
                default_value = entry.get("default")
                if isinstance(default_value, str) and default_value:
                    parsed_entry["default"] = default_value
            elif entry_type == "choice":
                parsed_entry["choices"] = choices
                default_value = entry.get("default")
                if isinstance(default_value, str) and default_value in choices:
                    parsed_entry["default"] = default_value
            parsed.append(parsed_entry)

        if needs_reference_image and "reference_image" not in seen_keys:
            parsed.insert(0, {
                "key": "reference_image",
                "type": "image",
                "label": "Reference image",
                "required": True,
            })

        return parsed

    def _primary_output_type(self, output_types):
        if "video" in output_types:
            return "video"
        if "image" in output_types:
            return "image"
        if "audio" in output_types:
            return "audio"
        return "unknown"

    def _extract_name(self, payload, path):
        fields = [
            payload.get("name"),
            payload.get("title"),
            payload.get("workflow_name"),
        ]
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            fields.extend([metadata.get("name"), metadata.get("title")])

        for value in fields:
            text = str(value or "").strip()
            if text:
                return text

        return os.path.splitext(os.path.basename(path))[0]

    def _extract_workflow(self, payload):
        if self._looks_like_workflow(payload):
            return payload
        if isinstance(payload, dict):
            workflow = payload.get("workflow")
            if self._looks_like_workflow(workflow):
                return workflow
        return None

    def _looks_like_workflow(self, value):
        if not isinstance(value, dict) or not value:
            return False
        for node in value.values():
            if isinstance(node, dict) and str(node.get("class_type", "")).strip():
                return True
        return False

    def templates_for_context(self, source_file=None):
        templates = self.discover()
        media_type = ""
        if source_file:
            media_type = str(source_file.data.get("media_type", "")).strip().lower()

        filtered = []
        for template in templates:
            category = str(template.get("category", "unknown"))
            input_types = set(template.get("input_types", []))
            if source_file:
                if category not in ("enhance", "unknown"):
                    continue
                if input_types and media_type not in input_types:
                    continue
            else:
                if category not in ("create", "unknown"):
                    continue
                if category == "unknown" and input_types:
                    continue
            filtered.append(template)
        return filtered

    def get_template(self, template_id):
        template_id = str(template_id or "").strip()
        if not template_id:
            return None
        for template in self.discover():
            if str(template.get("id")) == template_id:
                return template
        return None

    def get_workflow_copy(self, template_id):
        template = self.get_template(template_id)
        if not template:
            return None
        return copy.deepcopy(template.get("workflow") or {})

    def output_icon_name(self, template):
        explicit_icon = str((template or {}).get("action_icon") or "").strip()
        if explicit_icon:
            return explicit_icon
        kind = str((template or {}).get("primary_output") or "unknown")
        if kind == "video":
            return "ai-action-create-video.svg"
        if kind == "audio":
            return "ai-action-create-audio.svg"
        if kind == "image":
            return "ai-action-create-image.svg"
        return "tool-generate-sparkle.svg"
