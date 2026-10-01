"""
 @file
 @brief Unit tests for ComfyTemplateRegistry's extra_inputs template-schema parsing.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from classes.comfy_templates import ComfyTemplateRegistry


class ParseExtraInputsTests(unittest.TestCase):
    def setUp(self):
        self.registry = ComfyTemplateRegistry()

    def test_valid_entries_across_all_four_types_are_kept(self):
        payload = {
            "extra_inputs": [
                {"key": "end_clip", "type": "video", "label": "End clip", "required": True},
                {"key": "ref_photo", "type": "image", "label": "Reference photo", "required": False},
                {"key": "voice_sample", "type": "audio", "label": "Voice sample"},
                {"key": "scene_note", "type": "text", "label": "Scene detail", "required": False},
            ],
        }
        result = self.registry._parse_extra_inputs(payload, "some_template.json", needs_reference_image=False)
        self.assertEqual(
            result,
            [
                {"key": "end_clip", "type": "video", "label": "End clip", "required": True},
                {"key": "ref_photo", "type": "image", "label": "Reference photo", "required": False},
                {"key": "voice_sample", "type": "audio", "label": "Voice sample", "required": True},
                {"key": "scene_note", "type": "text", "label": "Scene detail", "required": False},
            ],
        )

    def test_text_entry_with_string_default_keeps_it(self):
        payload = {
            "extra_inputs": [
                {"key": "subject", "type": "text", "label": "Subject", "default": "the central subject"},
            ],
        }
        result = self.registry._parse_extra_inputs(payload, "t.json", needs_reference_image=False)
        self.assertEqual(
            result,
            [{"key": "subject", "type": "text", "label": "Subject", "required": True,
              "default": "the central subject"}],
        )

    def test_text_entry_with_empty_or_non_string_default_omits_it(self):
        payload = {
            "extra_inputs": [
                {"key": "a", "type": "text", "label": "A", "default": ""},
                {"key": "b", "type": "text", "label": "B", "default": 123},
            ],
        }
        result = self.registry._parse_extra_inputs(payload, "t.json", needs_reference_image=False)
        self.assertNotIn("default", result[0])
        self.assertNotIn("default", result[1])

    def test_non_text_entry_ignores_default(self):
        payload = {
            "extra_inputs": [
                {"key": "photo", "type": "image", "label": "Photo", "default": "ignored"},
            ],
        }
        result = self.registry._parse_extra_inputs(payload, "t.json", needs_reference_image=False)
        self.assertNotIn("default", result[0])

    def test_choice_entry_with_valid_choices_and_default_is_kept(self):
        payload = {
            "extra_inputs": [
                {"key": "n", "type": "choice", "label": "N", "choices": ["5", "22", "39"], "default": "22"},
            ],
        }
        result = self.registry._parse_extra_inputs(payload, "t.json", needs_reference_image=False)
        self.assertEqual(
            result,
            [{"key": "n", "type": "choice", "label": "N", "required": True,
              "choices": ["5", "22", "39"], "default": "22"}],
        )

    def test_choice_entry_missing_choices_is_rejected(self):
        payload = {"extra_inputs": [{"key": "n", "type": "choice", "label": "N"}]}
        result = self.registry._parse_extra_inputs(payload, "t.json", needs_reference_image=False)
        self.assertEqual(result, [])

    def test_choice_entry_empty_choices_list_is_rejected(self):
        payload = {"extra_inputs": [{"key": "n", "type": "choice", "label": "N", "choices": []}]}
        result = self.registry._parse_extra_inputs(payload, "t.json", needs_reference_image=False)
        self.assertEqual(result, [])

    def test_choice_entry_default_not_in_choices_is_dropped(self):
        payload = {
            "extra_inputs": [
                {"key": "n", "type": "choice", "label": "N", "choices": ["5", "22"], "default": "999"},
            ],
        }
        result = self.registry._parse_extra_inputs(payload, "t.json", needs_reference_image=False)
        self.assertNotIn("default", result[0])

    def test_missing_extra_inputs_key_returns_empty_list(self):
        self.assertEqual(self.registry._parse_extra_inputs({}, "t.json", needs_reference_image=False), [])

    def test_non_list_extra_inputs_is_skipped_with_warning(self):
        with patch("classes.comfy_templates.log.warning") as mock_warning:
            result = self.registry._parse_extra_inputs(
                {"extra_inputs": "not-a-list"}, "t.json", needs_reference_image=False,
            )
        self.assertEqual(result, [])
        mock_warning.assert_called_once()

    def test_non_dict_entry_is_skipped_with_warning(self):
        with patch("classes.comfy_templates.log.warning") as mock_warning:
            result = self.registry._parse_extra_inputs(
                {"extra_inputs": ["not-a-dict"]}, "t.json", needs_reference_image=False,
            )
        self.assertEqual(result, [])
        mock_warning.assert_called_once()

    def test_invalid_key_is_rejected(self):
        with patch("classes.comfy_templates.log.warning") as mock_warning:
            result = self.registry._parse_extra_inputs(
                {"extra_inputs": [{"key": "Bad Key!", "type": "video"}]}, "t.json", needs_reference_image=False,
            )
        self.assertEqual(result, [])
        mock_warning.assert_called_once()

    def test_duplicate_key_second_occurrence_is_rejected(self):
        with patch("classes.comfy_templates.log.warning") as mock_warning:
            result = self.registry._parse_extra_inputs(
                {
                    "extra_inputs": [
                        {"key": "end_clip", "type": "video"},
                        {"key": "end_clip", "type": "audio"},
                    ],
                },
                "t.json",
                needs_reference_image=False,
            )
        self.assertEqual([e["key"] for e in result], ["end_clip"])
        self.assertEqual(result[0]["type"], "video")
        mock_warning.assert_called_once()

    def test_invalid_type_is_rejected(self):
        with patch("classes.comfy_templates.log.warning") as mock_warning:
            result = self.registry._parse_extra_inputs(
                {"extra_inputs": [{"key": "thing", "type": "nonsense"}]}, "t.json", needs_reference_image=False,
            )
        self.assertEqual(result, [])
        mock_warning.assert_called_once()

    def test_missing_label_is_auto_derived_from_key(self):
        result = self.registry._parse_extra_inputs(
            {"extra_inputs": [{"key": "scene_note", "type": "text"}]}, "t.json", needs_reference_image=False,
        )
        self.assertEqual(result[0]["label"], "Scene note")

    def test_required_defaults_true_and_non_bool_is_coerced_true(self):
        result = self.registry._parse_extra_inputs(
            {
                "extra_inputs": [
                    {"key": "a", "type": "text"},
                    {"key": "b", "type": "text", "required": "yes"},
                    {"key": "c", "type": "text", "required": False},
                ],
            },
            "t.json",
            needs_reference_image=False,
        )
        self.assertEqual([e["required"] for e in result], [True, True, False])

    def test_needs_reference_image_synthesizes_entry_when_absent(self):
        result = self.registry._parse_extra_inputs({}, "video2video-basic.json", needs_reference_image=True)
        self.assertEqual(
            result,
            [{"key": "reference_image", "type": "image", "label": "Reference image", "required": True}],
        )

    def test_needs_reference_image_does_not_duplicate_explicit_entry(self):
        result = self.registry._parse_extra_inputs(
            {"extra_inputs": [{"key": "reference_image", "type": "image", "label": "Custom label"}]},
            "t.json",
            needs_reference_image=True,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["label"], "Custom label")

    def test_needs_reference_image_false_does_not_synthesize(self):
        result = self.registry._parse_extra_inputs({}, "t.json", needs_reference_image=False)
        self.assertEqual(result, [])


class LoadTemplateDefaultPromptTests(unittest.TestCase):
    def setUp(self):
        self.registry = ComfyTemplateRegistry()

    def _write_template(self, tmp_dir, payload):
        path = os.path.join(tmp_dir, "t.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return path

    def test_default_prompt_is_parsed_and_stripped(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._write_template(tmp_dir, {
                "name": "Test",
                "default_prompt": "  S1 is here.  ",
                "workflow": {"1": {"class_type": "SaveImage", "inputs": {}}},
            })
            result = self.registry._load_template(path, is_user=False, existing_ids=set())
            self.assertEqual(result["default_prompt"], "S1 is here.")

    def test_missing_default_prompt_defaults_to_empty_string(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._write_template(tmp_dir, {
                "name": "Test",
                "workflow": {"1": {"class_type": "SaveImage", "inputs": {}}},
            })
            result = self.registry._load_template(path, is_user=False, existing_ids=set())
            self.assertEqual(result["default_prompt"], "")


if __name__ == "__main__":
    unittest.main()
