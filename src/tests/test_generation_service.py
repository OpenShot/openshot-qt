import copy
import os
import sys
import types
import unittest
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

TEST_MEDIA_ROOT = os.path.join(os.sep, "mock-media")

generate_module = types.ModuleType("windows.generate")
generate_module.GenerateMediaDialog = type("GenerateMediaDialog", (), {})
sys.modules.setdefault("windows.generate", generate_module)

from classes.generation_service import GenerationService


class _StatusBarRecorder:
    def __init__(self):
        self.calls = []

    def showMessage(self, text, timeout):
        self.calls.append((text, timeout))


class _QueueStub:
    def __init__(self):
        self.jobs = {}


class GenerationServiceTests(unittest.TestCase):
    def test_split_generation_suffix_handles_legacy_and_current_formats(self):
        service = GenerationService.__new__(GenerationService)

        self.assertEqual(service._split_generation_suffix("alpha_gen"), ("alpha", 1))
        self.assertEqual(service._split_generation_suffix("alpha_gen1"), ("alpha", 1))
        self.assertEqual(service._split_generation_suffix("alpha_gen_001"), ("alpha", 1))
        self.assertEqual(service._split_generation_suffix("alpha_gen#2"), ("alpha", 2))
        self.assertEqual(service._split_generation_suffix("alpha"), ("alpha", None))

    def test_default_generation_name_uses_gen_suffix_and_increments_from_legacy_names(self):
        service = GenerationService.__new__(GenerationService)

        existing_files = [
            types.SimpleNamespace(data={"name": "p232_229_gen1", "path": os.path.join(TEST_MEDIA_ROOT, "p232_229_gen1.flac")}),
            types.SimpleNamespace(data={"name": "p232_229_gen#2 [Noise: Remove]", "path": os.path.join(TEST_MEDIA_ROOT, "p232_229_gen#2.flac")}),
        ]
        with patch("classes.generation_service.File.filter", return_value=existing_files):
            file_obj = types.SimpleNamespace(data={"path": os.path.join(TEST_MEDIA_ROOT, "p232_229_gen_001.flac")})
            self.assertEqual(service._default_generation_name(file_obj), "p232_229_gen3")

            file_obj = types.SimpleNamespace(data={"path": os.path.join(TEST_MEDIA_ROOT, "afdr001_30s.wav")})
            self.assertEqual(service._default_generation_name(file_obj), "afdr001_30s_gen1")

    def test_default_generation_name_prefers_display_name_over_collision_adjusted_path(self):
        service = GenerationService.__new__(GenerationService)

        existing_files = [
            types.SimpleNamespace(
                data={
                    "name": "generation_gen1 [Noise: Remove]",
                    "path": os.path.join(TEST_MEDIA_ROOT, "generation_gen1_2.png"),
                }
            ),
        ]
        with patch("classes.generation_service.File.filter", return_value=existing_files):
            file_obj = types.SimpleNamespace(
                data={
                    "name": "generation_gen1 [Noise: Remove]",
                    "path": os.path.join(TEST_MEDIA_ROOT, "generation_gen1_2.png"),
                }
            )
            self.assertEqual(service._default_generation_name(file_obj), "generation_gen2")

    def test_next_generation_name_preserves_custom_names_and_normalizes_generation_names(self):
        service = GenerationService.__new__(GenerationService)

        existing_files = [
            types.SimpleNamespace(data={"name": "alpha_gen1", "path": os.path.join(TEST_MEDIA_ROOT, "alpha_gen1.flac")}),
            types.SimpleNamespace(data={"name": "alpha_gen2 [Noise: Remove]", "path": os.path.join(TEST_MEDIA_ROOT, "alpha_gen2.flac")}),
            types.SimpleNamespace(data={"name": "custom_name", "path": os.path.join(TEST_MEDIA_ROOT, "custom_name.flac")}),
        ]
        with patch("classes.generation_service.File.filter", return_value=existing_files):
            self.assertEqual(service._next_generation_name("alpha_gen#2"), "alpha_gen3")
            self.assertEqual(service._next_generation_name("alpha_gen"), "alpha_gen3")
            self.assertEqual(service._next_generation_name("fresh_custom"), "fresh_custom")
            self.assertEqual(service._next_generation_name("custom_name"), "custom_name_gen1")

    def test_next_generation_name_considers_already_queued_jobs(self):
        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace(generation_queue=_QueueStub())
        service.win.generation_queue.jobs = {
            "J1": {"name": "generation_gen1"},
            "J2": {"name": "generation_gen2"},
        }
        with patch("classes.generation_service.File.filter", return_value=[]):
            self.assertEqual(service._next_generation_name("generation_gen1"), "generation_gen3")
            self.assertEqual(service._next_generation_name("generation"), "generation_gen3")

    def test_workflow_display_label_uses_tight_variant(self):
        service = GenerationService.__new__(GenerationService)
        self.assertEqual(
            service._workflow_display_label({"menu_parent": "noise", "display_name": "Remove"}),
            "Noise: Remove",
        )
        self.assertEqual(
            service._workflow_display_label({"menu_parent": "track_object", "display_name": "Highlight..."}),
            "Track: Highlight",
        )
        self.assertEqual(
            service._workflow_display_label({"display_name": "Increase Resolution (4x)"}),
            "Increase Resolution (4x)",
        )

    def test_source_display_root_name_strips_workflow_suffix(self):
        service = GenerationService.__new__(GenerationService)

        file_obj = types.SimpleNamespace(data={"name": "alpha_gen2 [Noise: Remove]", "path": os.path.join(TEST_MEDIA_ROOT, "alpha_gen2.flac")})
        self.assertEqual(service._source_display_root_name(file_obj), "alpha")

        file_obj = types.SimpleNamespace(data={"name": "Bravo Custom [Clarity: Speech]", "path": os.path.join(TEST_MEDIA_ROOT, "bravo.wav")})
        self.assertEqual(service._source_display_root_name(file_obj), "Bravo Custom")

    def test_output_local_name_omits_index_for_single_output(self):
        service = GenerationService.__new__(GenerationService)

        self.assertEqual(service._output_local_name("alpha_gen", 1, 1, ".flac"), "alpha_gen.flac")
        self.assertEqual(service._output_local_name("alpha_gen", 1, 2, ".flac"), "alpha_gen_001.flac")
        self.assertEqual(service._output_local_name("alpha_gen", 2, 2, ".flac"), "alpha_gen_002.flac")

    def test_action_generate_trigger_queues_all_selected_files_for_quick_actions(self):
        files = [
            types.SimpleNamespace(id="F1", data={"path": os.path.join(TEST_MEDIA_ROOT, "alpha.wav")}),
            types.SimpleNamespace(id="F2", data={"path": os.path.join(TEST_MEDIA_ROOT, "bravo.wav")}),
            types.SimpleNamespace(id="F3", data={"path": os.path.join(TEST_MEDIA_ROOT, "charlie.wav")}),
        ]
        status_bar = _StatusBarRecorder()
        queued_targets = []

        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace(
            selected_files=lambda: list(files),
            statusBar=status_bar,
        )
        service.template_registry = types.SimpleNamespace()
        service.is_comfy_available = lambda force=False: True
        service.templates_for_context = lambda source_file=None: [{"id": "audio-noise-remove"}]
        service._selected_generation_targets = lambda source_file=None: list(files)
        service._enqueue_generation_for_file = (
            lambda source_file, payload: queued_targets.append((source_file.id if source_file else None, dict(payload))) or (True, "")
        )
        with patch("classes.generation_service.File.filter", return_value=[]):
            service.action_generate_trigger(
                source_file=files[0],
                template_id="audio-noise-remove",
                open_dialog=False,
            )

        self.assertEqual([target_id for target_id, _ in queued_targets], ["F1", "F2", "F3"])
        self.assertEqual(status_bar.calls, [("Queued 3 generation jobs", 3000)])
        self.assertTrue(all(payload["template_id"] == "audio-noise-remove" for _, payload in queued_targets))
        self.assertEqual(
            [payload["name"] for _, payload in queued_targets],
            ["alpha_gen1", "bravo_gen1", "charlie_gen1"],
        )

    def test_action_generate_trigger_create_workflow_reserves_names_across_queued_jobs(self):
        status_bar = _StatusBarRecorder()
        queued_payload_names = []
        queue = _QueueStub()

        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace(
            selected_files=lambda: [],
            statusBar=status_bar,
            generation_queue=queue,
        )
        service.template_registry = types.SimpleNamespace()
        service.is_comfy_available = lambda force=False: True
        service.templates_for_context = lambda source_file=None: [{"id": "txt2img-basic"}]
        service._selected_generation_targets = lambda source_file=None: []

        def enqueue_generation_for_file(_source_file, payload):
            queued_payload_names.append(payload["name"])
            queue.jobs[f"J{len(queue.jobs) + 1}"] = {"name": payload["name"]}
            return True, ""

        service._enqueue_generation_for_file = enqueue_generation_for_file

        with patch("classes.generation_service.File.filter", return_value=[]):
            service.action_generate_trigger(template_id="txt2img-basic", open_dialog=False)
            service.action_generate_trigger(template_id="txt2img-basic", open_dialog=False)
            service.action_generate_trigger(template_id="txt2img-basic", open_dialog=False)

        self.assertEqual(
            queued_payload_names,
            ["generation_gen1", "generation_gen2", "generation_gen3"],
        )

    def test_prepare_template_workflow_resolves_named_extra_input_placeholders(self):
        workflow_fixture = {
            "1": {"class_type": "LoadVideo", "inputs": {"video": "__openshot_input__"}},
            "2": {"class_type": "SomeCustomLoader", "inputs": {"video_path": "__openshot_input:end_clip__"}},
            "3": {"class_type": "AnotherLoader", "inputs": {"src": "{{openshot_input:end_clip}}"}},
            "4": {"class_type": "ThirdLoader", "inputs": {"path": "$openshot_input:end_clip"}},
        }
        service = GenerationService.__new__(GenerationService)
        service.template_registry = types.SimpleNamespace(
            get_workflow_copy=lambda template_id: copy.deepcopy(workflow_fixture),
        )

        workflow, bindings = service._prepare_template_workflow(
            template={"id": "t1", "path": ""},
            payload_name="test_gen",
            prompt_text="",
            source_file=None,
            source_path="/media/source.mp4",
            extra_input_paths={"end_clip": "/media/end_clip.mp4"},
        )

        self.assertEqual(workflow["1"]["inputs"]["video"], "/media/source.mp4")
        self.assertEqual(workflow["2"]["inputs"]["video_path"], "/media/end_clip.mp4")
        self.assertEqual(workflow["3"]["inputs"]["src"], "/media/end_clip.mp4")
        self.assertEqual(workflow["4"]["inputs"]["path"], "/media/end_clip.mp4")

        binding_paths = {(node_id, key): path for node_id, key, path in bindings}
        self.assertEqual(binding_paths.get(("1", "video")), "/media/source.mp4")
        self.assertEqual(binding_paths.get(("2", "video_path")), "/media/end_clip.mp4")
        self.assertEqual(binding_paths.get(("3", "src")), "/media/end_clip.mp4")
        self.assertEqual(binding_paths.get(("4", "path")), "/media/end_clip.mp4")

    def test_prepare_template_workflow_keeps_primary_and_overlay_images_distinct(self):
        workflow_fixture = {
            "1": {"class_type": "LoadImage", "inputs": {"image": "__openshot_input__", "upload": "image"}},
            "2": {"class_type": "LoadImage", "inputs": {"image": "__openshot_input:overlay_image__", "upload": "image"}},
        }
        service = GenerationService.__new__(GenerationService)
        service.template_registry = types.SimpleNamespace(
            get_workflow_copy=lambda template_id: copy.deepcopy(workflow_fixture),
        )

        workflow, _bindings = service._prepare_template_workflow(
            template={"id": "image-blend-multi-input-demo", "path": ""},
            payload_name="test_gen",
            prompt_text="",
            source_file=None,
            source_path="/media/primary.png",
            extra_input_paths={"overlay_image": "/media/overlay.png"},
        )

        self.assertEqual(workflow["1"]["inputs"]["image"], "/media/primary.png")
        self.assertEqual(workflow["2"]["inputs"]["image"], "/media/overlay.png")

    def test_prepare_template_workflow_keeps_legacy_reference_image_placeholder_working(self):
        workflow_fixture = {
            "1": {"class_type": "LegacyRef", "inputs": {"image": "__openshot_reference_image__"}},
        }
        service = GenerationService.__new__(GenerationService)
        service.template_registry = types.SimpleNamespace(
            get_workflow_copy=lambda template_id: copy.deepcopy(workflow_fixture),
        )

        workflow, bindings = service._prepare_template_workflow(
            template={"id": "t1", "path": ""},
            payload_name="test_gen",
            prompt_text="",
            source_file=None,
            source_path="",
            reference_image_path="/media/ref.png",
        )

        self.assertEqual(workflow["1"]["inputs"]["image"], "/media/ref.png")
        self.assertIn(("1", "image", "/media/ref.png"), bindings)

    def test_prepare_template_workflow_text_substitution_is_never_a_binding_even_on_shared_node(self):
        # Same node receiving both a media-backed and a text-backed extra input --
        # only the media one should appear in bindings.
        workflow_fixture = {
            "1": {
                "class_type": "MultiInputNode",
                "inputs": {
                    "video_path": "__openshot_input:end_clip__",
                    "note": "__openshot_input:scene_note__",
                },
            },
        }
        service = GenerationService.__new__(GenerationService)
        service.template_registry = types.SimpleNamespace(
            get_workflow_copy=lambda template_id: copy.deepcopy(workflow_fixture),
        )

        workflow, bindings = service._prepare_template_workflow(
            template={"id": "t1", "path": ""},
            payload_name="test_gen",
            prompt_text="",
            source_file=None,
            source_path="",
            extra_input_paths={"end_clip": "/media/end_clip.mp4"},
            extra_input_texts={"scene_note": "a quiet transition"},
        )

        self.assertEqual(workflow["1"]["inputs"]["video_path"], "/media/end_clip.mp4")
        self.assertEqual(workflow["1"]["inputs"]["note"], "a quiet transition")
        binding_keys = {(node_id, key) for node_id, key, _path in bindings}
        self.assertIn(("1", "video_path"), binding_keys)
        self.assertNotIn(("1", "note"), binding_keys)

    def test_prepare_template_workflow_named_prompt_is_not_overwritten_by_generic_prompt(self):
        workflow_fixture = {
            "1": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["2", 1],
                    "text": "__openshot_input:style_prompt__",
                },
            },
        }
        service = GenerationService.__new__(GenerationService)
        service.template_registry = types.SimpleNamespace(
            get_workflow_copy=lambda template_id: copy.deepcopy(workflow_fixture),
        )

        workflow, _bindings = service._prepare_template_workflow(
            template={"id": "image-blend-multi-input-demo", "path": ""},
            payload_name="test_gen",
            prompt_text="generic prompt that must not replace the style prompt",
            source_file=None,
            source_path="",
            extra_input_texts={"style_prompt": "keep this named blend prompt"},
        )

        self.assertEqual(workflow["1"]["inputs"]["text"], "keep this named blend prompt")

    def test_prepare_template_workflow_unknown_extra_input_key_is_left_untouched_and_logged(self):
        workflow_fixture = {
            "1": {"class_type": "Mystery", "inputs": {"thing": "__openshot_input:nonexistent_key__"}},
        }
        service = GenerationService.__new__(GenerationService)
        service.template_registry = types.SimpleNamespace(
            get_workflow_copy=lambda template_id: copy.deepcopy(workflow_fixture),
        )

        with patch("classes.generation_service.log.warning") as mock_warning:
            workflow, bindings = service._prepare_template_workflow(
                template={"id": "t1", "path": ""},
                payload_name="test_gen",
                prompt_text="",
                source_file=None,
                source_path="",
            )

        self.assertEqual(workflow["1"]["inputs"]["thing"], "__openshot_input:nonexistent_key__")
        self.assertEqual(bindings, [])
        mock_warning.assert_called_once()
        self.assertIn("nonexistent_key", mock_warning.call_args.args[1])

    def test_prepare_template_workflow_resolves_embedded_named_text_placeholder(self):
        workflow_fixture = {
            "1": {
                "class_type": "StringConstantMultiline",
                "inputs": {"string": "subject is __openshot_input:subject_description__, in frame."},
            },
        }
        service = GenerationService.__new__(GenerationService)
        service.template_registry = types.SimpleNamespace(
            get_workflow_copy=lambda template_id: copy.deepcopy(workflow_fixture),
        )

        workflow, bindings = service._prepare_template_workflow(
            template={"id": "t1", "path": ""},
            payload_name="test_gen",
            prompt_text="",
            source_file=None,
            source_path="",
            extra_input_texts={"subject_description": "a man in a blue jacket"},
        )

        self.assertEqual(
            workflow["1"]["inputs"]["string"],
            "subject is a man in a blue jacket, in frame.",
        )
        self.assertEqual(bindings, [])

    def test_prepare_template_workflow_embedded_file_type_key_is_left_unresolved_and_logged(self):
        workflow_fixture = {
            "1": {
                "class_type": "StringConstantMultiline",
                "inputs": {"string": "uses __openshot_input:end_clip__ embedded."},
            },
        }
        service = GenerationService.__new__(GenerationService)
        service.template_registry = types.SimpleNamespace(
            get_workflow_copy=lambda template_id: copy.deepcopy(workflow_fixture),
        )

        with patch("classes.generation_service.log.warning") as mock_warning:
            workflow, bindings = service._prepare_template_workflow(
                template={"id": "t1", "path": ""},
                payload_name="test_gen",
                prompt_text="",
                source_file=None,
                source_path="",
                extra_input_paths={"end_clip": "/media/end_clip.mp4"},
            )

        self.assertEqual(workflow["1"]["inputs"]["string"], "uses __openshot_input:end_clip__ embedded.")
        self.assertEqual(bindings, [])
        mock_warning.assert_called_once()
        self.assertIn("end_clip", mock_warning.call_args.args[1])

    def test_prepare_template_workflow_embedded_unknown_key_is_left_unresolved_and_logged(self):
        workflow_fixture = {
            "1": {
                "class_type": "StringConstantMultiline",
                "inputs": {"string": "uses __openshot_input:nonexistent_key__ embedded."},
            },
        }
        service = GenerationService.__new__(GenerationService)
        service.template_registry = types.SimpleNamespace(
            get_workflow_copy=lambda template_id: copy.deepcopy(workflow_fixture),
        )

        with patch("classes.generation_service.log.warning") as mock_warning:
            workflow, bindings = service._prepare_template_workflow(
                template={"id": "t1", "path": ""},
                payload_name="test_gen",
                prompt_text="",
                source_file=None,
                source_path="",
            )

        self.assertEqual(
            workflow["1"]["inputs"]["string"], "uses __openshot_input:nonexistent_key__ embedded.",
        )
        self.assertEqual(bindings, [])
        mock_warning.assert_called_once()
        self.assertIn("nonexistent_key", mock_warning.call_args.args[1])

    def test_prepare_template_workflow_replaces_openshot_prompt_placeholder_in_string_field(self):
        # Regression test: StringConstantMultiline (and similar nodes) use a
        # "string" input key, not "text"/"prompt"/"tags" -- the placeholder
        # substitution must check that key too, or a user's typed prompt
        # never reaches the workflow sent to ComfyUI.
        workflow_fixture = {
            "1": {
                "class_type": "StringConstantMultiline",
                "inputs": {"string": "__openshot_prompt__", "strip_newlines": False},
            },
        }
        service = GenerationService.__new__(GenerationService)
        service.template_registry = types.SimpleNamespace(
            get_workflow_copy=lambda template_id: copy.deepcopy(workflow_fixture),
        )

        workflow, bindings = service._prepare_template_workflow(
            template={"id": "t1", "path": ""},
            payload_name="test_gen",
            prompt_text="S1 is the hero, V1 continues the action.",
            source_file=None,
            source_path="",
        )

        self.assertEqual(
            workflow["1"]["inputs"]["string"],
            "S1 is the hero, V1 continues the action.",
        )
        self.assertEqual(bindings, [])

    def test_prepare_template_workflow_leaves_unrelated_string_field_untouched(self):
        # A "string" field that never contains the placeholder literal (e.g. a
        # template's own fixed default prompt) must not be altered just
        # because prompt_text was also supplied elsewhere in the workflow.
        workflow_fixture = {
            "1": {
                "class_type": "StringConstantMultiline",
                "inputs": {"string": "a fixed template prompt with no placeholder"},
            },
        }
        service = GenerationService.__new__(GenerationService)
        service.template_registry = types.SimpleNamespace(
            get_workflow_copy=lambda template_id: copy.deepcopy(workflow_fixture),
        )

        workflow, bindings = service._prepare_template_workflow(
            template={"id": "t1", "path": ""},
            payload_name="test_gen",
            prompt_text="the user's custom prompt",
            source_file=None,
            source_path="",
        )

        self.assertEqual(
            workflow["1"]["inputs"]["string"],
            "a fixed template prompt with no placeholder",
        )

    def test_enqueue_generation_for_file_missing_required_media_input_returns_clear_error(self):
        service = GenerationService.__new__(GenerationService)
        service.template_registry = types.SimpleNamespace(
            get_template=lambda template_id: {
                "id": "bridge-clips",
                "path": "",
                "extra_inputs": [
                    {"key": "end_clip", "type": "video", "label": "End clip", "required": True},
                ],
            },
        )
        service._next_generation_name = lambda name: "test_gen"

        ok, error = service._enqueue_generation_for_file(
            None,
            {"name": "test", "template_id": "bridge-clips", "input_file_ids": {}, "input_text_values": {}},
        )

        self.assertFalse(ok)
        self.assertIn("End clip", error)

    def test_enqueue_generation_for_file_missing_required_text_input_returns_clear_error(self):
        service = GenerationService.__new__(GenerationService)
        service.template_registry = types.SimpleNamespace(
            get_template=lambda template_id: {
                "id": "bridge-clips",
                "path": "",
                "extra_inputs": [
                    {"key": "scene_note", "type": "text", "label": "Scene detail", "required": True},
                ],
            },
        )
        service._next_generation_name = lambda name: "test_gen"

        ok, error = service._enqueue_generation_for_file(
            None,
            {"name": "test", "template_id": "bridge-clips", "input_file_ids": {}, "input_text_values": {}},
        )

        self.assertFalse(ok)
        self.assertIn("Scene detail", error)


if __name__ == "__main__":
    unittest.main()
