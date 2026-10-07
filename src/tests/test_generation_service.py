import copy
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

TEST_MEDIA_ROOT = os.path.join(os.sep, "mock-media")

generate_module = types.ModuleType("windows.generate")
generate_module.GenerateMediaDialog = type("GenerateMediaDialog", (), {})
sys.modules.setdefault("windows.generate", generate_module)

from qt_api import QDialog
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

    def test_insert_generated_clip_on_timeline_opens_gap_and_saves_new_clip(self):
        service = GenerationService.__new__(GenerationService)
        saved_clips = []

        class FakeProjectClip:
            def __init__(self):
                self.data = None

            def save(self):
                saved_clips.append(self.data)

        ripple_calls = []
        service.win = types.SimpleNamespace(
            ripple_insert_gap=lambda position, layer, gap: ripple_calls.append((position, layer, gap)),
            timeline=None,
        )
        file_obj = types.SimpleNamespace(
            id="F1",
            data={"path": "/media/result.mp4", "duration": 5.0, "name": "result"},
        )
        fake_reader = types.SimpleNamespace(Json=lambda: '{"id": "c1"}')
        updates = types.SimpleNamespace(transaction_id=None)

        with patch("classes.generation_service.openshot.Clip", return_value=fake_reader), \
             patch("classes.generation_service.Clip", FakeProjectClip), \
             patch("classes.generation_service.get_app", return_value=types.SimpleNamespace(updates=updates)):
            result = service._insert_generated_clip_on_timeline(file_obj, 12.0, 2)

        self.assertTrue(result)
        self.assertEqual(ripple_calls, [(12.0, 2, 5.0)])
        self.assertEqual(len(saved_clips), 1)
        new_clip = saved_clips[0]
        self.assertEqual(new_clip["position"], 12.0)
        self.assertEqual(new_clip["layer"], 2)
        self.assertEqual(new_clip["file_id"], "F1")
        self.assertEqual(new_clip["duration"], 5.0)
        self.assertEqual(new_clip["start"], 0.0)
        self.assertEqual(new_clip["end"], 5.0)
        self.assertIsNone(updates.transaction_id)

    def test_insert_generated_clip_on_timeline_false_when_no_layer(self):
        service = GenerationService.__new__(GenerationService)
        file_obj = types.SimpleNamespace(data={"path": "/media/result.mp4", "duration": 5.0})
        self.assertFalse(service._insert_generated_clip_on_timeline(file_obj, 12.0, None))

    def test_insert_generated_clip_on_timeline_false_when_no_duration(self):
        service = GenerationService.__new__(GenerationService)
        file_obj = types.SimpleNamespace(data={"path": "/media/result.mp4", "duration": 0.0})
        self.assertFalse(service._insert_generated_clip_on_timeline(file_obj, 12.0, 1))

    def test_insert_generated_clip_on_timeline_false_when_no_path(self):
        service = GenerationService.__new__(GenerationService)
        file_obj = types.SimpleNamespace(data={"path": "", "duration": 5.0})
        self.assertFalse(service._insert_generated_clip_on_timeline(file_obj, 12.0, 1))

    def test_import_generation_outputs_inserts_on_timeline_when_requested(self):
        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace(
            files_model=types.SimpleNamespace(add_files=lambda *a, **k: None),
            FileUpdated=types.SimpleNamespace(emit=lambda *a, **k: None),
        )
        service._next_available_path = lambda path: path
        service._output_local_name = staticmethod(lambda base, index, total, ext: "result.mp4")
        service.comfy_ui_url = lambda: "http://localhost:8188"

        result_file = types.SimpleNamespace(
            id="F2", data={"path": "/out/result.mp4", "duration": 5.0, "name": "result"},
            save=lambda: None,
        )
        insert_calls = []
        service._insert_generated_clip_on_timeline = lambda file_obj, position, layer: (
            insert_calls.append((file_obj, position, layer)) or True
        )

        job = {
            "outputs": [{"filename": "result.mp4"}],
            "request": {"insert_on_timeline": {"position": 10.0, "layer": 3}},
            "name": "bridge_result",
        }

        fake_client = types.SimpleNamespace(download_output_file=lambda ref, path: None)

        with patch("classes.generation_service.ComfyClient", return_value=fake_client), \
             patch("classes.generation_service.File.get", return_value=result_file), \
             patch("classes.generation_service.info.COMFYUI_OUTPUT_PATH", "/out"), \
             patch("classes.generation_service.os.makedirs", lambda *a, **k: None):
            result = service._import_generation_outputs(job)

        self.assertTrue(result["inserted_on_timeline"])
        self.assertEqual(insert_calls, [(result_file, 10.0, 3)])

    def test_import_generation_outputs_skips_insertion_when_not_requested(self):
        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace(
            files_model=types.SimpleNamespace(add_files=lambda *a, **k: None),
            FileUpdated=types.SimpleNamespace(emit=lambda *a, **k: None),
        )
        service._next_available_path = lambda path: path
        service._output_local_name = staticmethod(lambda base, index, total, ext: "result.mp4")
        service.comfy_ui_url = lambda: "http://localhost:8188"

        result_file = types.SimpleNamespace(
            id="F2", data={"path": "/out/result.mp4", "duration": 5.0, "name": "result"},
            save=lambda: None,
        )
        service._insert_generated_clip_on_timeline = lambda *a, **k: self.fail(
            "should not be called when insert_on_timeline is absent"
        )

        job = {
            "outputs": [{"filename": "result.mp4"}],
            "request": {},
            "name": "bridge_result",
        }

        fake_client = types.SimpleNamespace(download_output_file=lambda ref, path: None)

        with patch("classes.generation_service.ComfyClient", return_value=fake_client), \
             patch("classes.generation_service.File.get", return_value=result_file), \
             patch("classes.generation_service.info.COMFYUI_OUTPUT_PATH", "/out"), \
             patch("classes.generation_service.os.makedirs", lambda *a, **k: None):
            result = service._import_generation_outputs(job)

        self.assertFalse(result["inserted_on_timeline"])

    # ---- two-clip AI bridge ----

    def test_video_extra_input_keys_returns_ordered_video_keys(self):
        entry = {
            "template": {
                "extra_inputs": [
                    {"key": "scene_note", "type": "text"},
                    {"key": "clip_b", "type": "video"},
                    {"key": "ref_image", "type": "image"},
                    {"key": "clip_c", "type": "video"},
                ],
            },
        }
        self.assertEqual(
            GenerationService._video_extra_input_keys(entry),
            ["clip_b", "clip_c"],
        )

    def test_video_extra_input_keys_empty_when_no_extra_inputs(self):
        self.assertEqual(GenerationService._video_extra_input_keys({"template": {}}), [])

    def test_qualifies_as_bridge_template_true_with_one_video_input(self):
        entry = {"template": {"extra_inputs": [{"key": "clip_b", "type": "video"}]}}
        self.assertTrue(GenerationService._qualifies_as_bridge_template(entry))

    def test_qualifies_as_bridge_template_false_with_no_video_input(self):
        entry = {"template": {"extra_inputs": [{"key": "note", "type": "text"}]}}
        self.assertFalse(GenerationService._qualifies_as_bridge_template(entry))

    def test_preselect_bridge_second_video_input_sets_combo(self):
        service = GenerationService.__new__(GenerationService)
        combo = MagicMock()
        combo.findData.return_value = 2
        dialog = types.SimpleNamespace(
            _current_template=lambda: {"extra_inputs": [{"key": "clip_b", "type": "video"}]},
            _extra_input_widgets={"clip_b": (combo, {"type": "video"})},
        )
        service._preselect_bridge_second_video_input(dialog, "F-clip-b")
        combo.findData.assert_called_once_with("F-clip-b")
        combo.setCurrentIndex.assert_called_once_with(2)

    def test_preselect_bridge_second_video_input_noop_when_template_has_no_video_input(self):
        service = GenerationService.__new__(GenerationService)
        dialog = types.SimpleNamespace(
            _current_template=lambda: {"extra_inputs": []},
            _extra_input_widgets={},
        )
        # Should not raise even with nothing to preselect.
        service._preselect_bridge_second_video_input(dialog, "F-clip-b")

    def test_bridge_clips_with_ai_shows_message_when_no_qualifying_template(self):
        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace()
        service.templates_for_context = lambda source_file=None: [{"id": "txt2img-basic", "template": {}}]

        with patch("classes.generation_service.QMessageBox") as mock_box:
            service.bridge_clips_with_ai(
                types.SimpleNamespace(data={}), types.SimpleNamespace(data={}),
            )
        mock_box.information.assert_called_once()

    def test_bridge_clips_with_ai_queries_templates_with_video_context(self):
        # Regression test: templates_for_context(source_file=None) only returns
        # "create"-category templates, which silently excludes "enhance"-category
        # bridge templates regardless of their extra_inputs. A video-media-type
        # stand-in must be passed so "enhance" templates are considered too.
        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace()
        calls = []

        def fake_templates_for_context(source_file=None):
            calls.append(source_file)
            return []

        service.templates_for_context = fake_templates_for_context

        with patch("classes.generation_service.QMessageBox"):
            service.bridge_clips_with_ai(
                types.SimpleNamespace(data={}), types.SimpleNamespace(data={}),
            )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].data.get("media_type"), "video")

    def test_bridge_clips_with_ai_warns_when_render_fails(self):
        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace()
        bridge_template = {"id": "video-bridge", "template": {"extra_inputs": [{"key": "clip_b", "type": "video"}]}}
        service.templates_for_context = lambda source_file=None: [bridge_template]

        with patch("classes.generation_service.render_clip_to_file", return_value=False), \
             patch("classes.generation_service.tempfile.mkdtemp", return_value="/tmp/bridge"), \
             patch("classes.generation_service.QMessageBox") as mock_box:
            service.bridge_clips_with_ai(
                types.SimpleNamespace(data={}), types.SimpleNamespace(data={}),
            )
        mock_box.warning.assert_called_once()

    def test_bridge_clips_with_ai_warns_when_files_do_not_import(self):
        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace(
            files_model=types.SimpleNamespace(add_files=lambda *a, **k: None),
        )
        bridge_template = {"id": "video-bridge", "template": {"extra_inputs": [{"key": "clip_b", "type": "video"}]}}
        service.templates_for_context = lambda source_file=None: [bridge_template]

        with patch("classes.generation_service.render_clip_to_file", return_value=True), \
             patch("classes.generation_service.tempfile.mkdtemp", return_value="/tmp/bridge"), \
             patch("classes.generation_service.File.get", return_value=None), \
             patch("classes.generation_service.QMessageBox") as mock_box:
            service.bridge_clips_with_ai(
                types.SimpleNamespace(data={}), types.SimpleNamespace(data={}),
            )
        mock_box.warning.assert_called_once()

    def test_bridge_clips_with_ai_happy_path_enqueues_with_insert_metadata(self):
        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace(
            files_model=types.SimpleNamespace(add_files=lambda *a, **k: None),
        )
        bridge_template = {"id": "video-bridge", "template": {"extra_inputs": [{"key": "clip_b", "type": "video"}]}}
        service.templates_for_context = lambda source_file=None: [bridge_template]
        service._default_generation_name = lambda file_obj: "bridge_gen1"

        file_a = types.SimpleNamespace(id="FA", data={"path": "/tmp/bridge/clip_a.mp4"})
        file_b = types.SimpleNamespace(id="FB", data={"path": "/tmp/bridge/clip_b.mp4"})
        files_by_path = {file_a.data["path"]: file_a, file_b.data["path"]: file_b}

        dialog_instance = MagicMock()
        dialog_instance.exec_.return_value = QDialog.Accepted
        dialog_instance.get_payload.return_value = {"name": "bridge_gen1", "template_id": "video-bridge"}
        dialog_cls = MagicMock(return_value=dialog_instance)

        enqueue_calls = []
        service._enqueue_generation_for_file = lambda source_file, payload: (
            enqueue_calls.append((source_file, payload)) or (True, "")
        )

        clip_a = types.SimpleNamespace(data={"position": 0.0, "layer": 1})
        clip_b = types.SimpleNamespace(data={"position": 5.0, "layer": 1})

        with patch("classes.generation_service.render_clip_to_file", return_value=True), \
             patch("classes.generation_service.tempfile.mkdtemp", return_value="/tmp/bridge"), \
             patch("classes.generation_service.File.get", side_effect=lambda path: files_by_path.get(path)), \
             patch("classes.generation_service.GenerateMediaDialog", dialog_cls), \
             patch.object(service, "_preselect_bridge_second_video_input") as preselect_mock:
            service.bridge_clips_with_ai(clip_a, clip_b)

        dialog_cls.assert_called_once()
        _args, kwargs = dialog_cls.call_args
        self.assertEqual(kwargs["source_file"], file_a)
        self.assertEqual(kwargs["templates"], [bridge_template])
        self.assertEqual(kwargs["preselected_template_id"], "video-bridge")

        preselect_mock.assert_called_once_with(dialog_instance, "FB")
        self.assertEqual(len(enqueue_calls), 1)
        enqueued_source, enqueued_payload = enqueue_calls[0]
        self.assertEqual(enqueued_source, file_a)
        self.assertEqual(
            enqueued_payload["insert_on_timeline"],
            {"position": 5.0, "layer": 1},
        )

    def test_bridge_clips_with_ai_does_not_enqueue_when_dialog_canceled(self):
        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace(
            files_model=types.SimpleNamespace(add_files=lambda *a, **k: None),
        )
        bridge_template = {"id": "video-bridge", "template": {"extra_inputs": [{"key": "clip_b", "type": "video"}]}}
        service.templates_for_context = lambda source_file=None: [bridge_template]
        service._default_generation_name = lambda file_obj: "bridge_gen1"

        file_a = types.SimpleNamespace(id="FA", data={"path": "/tmp/bridge/clip_a.mp4"})
        file_b = types.SimpleNamespace(id="FB", data={"path": "/tmp/bridge/clip_b.mp4"})
        files_by_path = {file_a.data["path"]: file_a, file_b.data["path"]: file_b}

        dialog_instance = MagicMock()
        dialog_instance.exec_.return_value = QDialog.Rejected
        dialog_cls = MagicMock(return_value=dialog_instance)

        service._enqueue_generation_for_file = lambda *a, **k: self.fail("should not enqueue when canceled")

        clip_a = types.SimpleNamespace(data={"position": 0.0, "layer": 1})
        clip_b = types.SimpleNamespace(data={"position": 5.0, "layer": 1})

        with patch("classes.generation_service.render_clip_to_file", return_value=True), \
             patch("classes.generation_service.tempfile.mkdtemp", return_value="/tmp/bridge"), \
             patch("classes.generation_service.File.get", side_effect=lambda path: files_by_path.get(path)), \
             patch("classes.generation_service.GenerateMediaDialog", dialog_cls), \
             patch.object(service, "_preselect_bridge_second_video_input"):
            service.bridge_clips_with_ai(clip_a, clip_b)

        dialog_instance.get_payload.assert_not_called()

    def test_bridge_clips_with_ai_template_combo_change_rewires_preselect(self):
        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace(
            files_model=types.SimpleNamespace(add_files=lambda *a, **k: None),
        )
        bridge_template = {"id": "video-bridge", "template": {"extra_inputs": [{"key": "clip_b", "type": "video"}]}}
        service.templates_for_context = lambda source_file=None: [bridge_template]
        service._default_generation_name = lambda file_obj: "bridge_gen1"

        file_a = types.SimpleNamespace(id="FA", data={"path": "/tmp/bridge/clip_a.mp4"})
        file_b = types.SimpleNamespace(id="FB", data={"path": "/tmp/bridge/clip_b.mp4"})
        files_by_path = {file_a.data["path"]: file_a, file_b.data["path"]: file_b}

        dialog_instance = MagicMock()
        dialog_instance.exec_.return_value = QDialog.Rejected
        dialog_cls = MagicMock(return_value=dialog_instance)
        service._enqueue_generation_for_file = lambda *a, **k: (True, "")

        clip_a = types.SimpleNamespace(data={"position": 0.0, "layer": 1})
        clip_b = types.SimpleNamespace(data={"position": 5.0, "layer": 1})

        with patch("classes.generation_service.render_clip_to_file", return_value=True), \
             patch("classes.generation_service.tempfile.mkdtemp", return_value="/tmp/bridge"), \
             patch("classes.generation_service.File.get", side_effect=lambda path: files_by_path.get(path)), \
             patch("classes.generation_service.GenerateMediaDialog", dialog_cls):
            service.bridge_clips_with_ai(clip_a, clip_b)

        # The template combo's change signal must be wired to re-run the
        # preselect, so picking a different qualifying template still fills
        # Clip B in rather than leaving it to the user to notice and redo.
        dialog_instance.template_combo.currentIndexChanged.connect.assert_called_once()

    # ---- two-clip AI bridge: temporary render cleanup and naming ----

    def _bridge_cleanup_fixture(self):
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix="openshot_bridge_test_")
        self.addCleanup(lambda: __import__("shutil").rmtree(temp_dir, ignore_errors=True))
        path_a = os.path.join(temp_dir, "clip_a.mp4")
        path_b = os.path.join(temp_dir, "clip_b.mp4")
        for path in (path_a, path_b):
            open(path, "w").close()
        files = {
            path_a: MagicMock(id="FA", data={"path": path_a}),
            path_b: MagicMock(id="FB", data={"path": path_b}),
        }
        return temp_dir, path_a, path_b, files

    def test_remove_bridge_temp_files_removes_project_entries_and_disk_files(self):
        service = GenerationService.__new__(GenerationService)
        temp_dir, path_a, path_b, files = self._bridge_cleanup_fixture()

        with patch("classes.generation_service.File.get", side_effect=lambda path: files.get(path)), \
             patch("classes.generation_service.Clip.filter", return_value=[]):
            service._remove_bridge_temp_files({"dir": temp_dir, "paths": [path_a, path_b]})

        files[path_a].delete.assert_called_once()
        files[path_b].delete.assert_called_once()
        self.assertFalse(os.path.exists(path_a))
        self.assertFalse(os.path.exists(path_b))
        self.assertFalse(os.path.exists(temp_dir))

    def test_remove_bridge_temp_files_keeps_a_render_a_timeline_clip_uses(self):
        service = GenerationService.__new__(GenerationService)
        temp_dir, path_a, path_b, files = self._bridge_cleanup_fixture()

        with patch("classes.generation_service.File.get", side_effect=lambda path: files.get(path)), \
             patch("classes.generation_service.Clip.filter",
                   side_effect=lambda file_id: [object()] if file_id == "FA" else []):
            service._remove_bridge_temp_files({"dir": temp_dir, "paths": [path_a, path_b]})

        files[path_a].delete.assert_not_called()
        self.assertTrue(os.path.exists(path_a))
        files[path_b].delete.assert_called_once()
        self.assertFalse(os.path.exists(path_b))
        self.assertTrue(os.path.isdir(temp_dir))

    def test_remove_bridge_temp_files_ignores_paths_outside_the_bridge_dir(self):
        import tempfile
        service = GenerationService.__new__(GenerationService)
        temp_dir, path_a, _path_b, files = self._bridge_cleanup_fixture()
        other_dir = tempfile.mkdtemp(prefix="openshot_bridge_other_")
        self.addCleanup(lambda: __import__("shutil").rmtree(other_dir, ignore_errors=True))
        outside = os.path.join(other_dir, "precious.mp4")
        open(outside, "w").close()
        files[outside] = MagicMock(id="FX", data={"path": outside})

        with patch("classes.generation_service.File.get", side_effect=lambda path: files.get(path)), \
             patch("classes.generation_service.Clip.filter", return_value=[]):
            service._remove_bridge_temp_files({"dir": temp_dir, "paths": [outside, path_a]})

        files[outside].delete.assert_not_called()
        self.assertTrue(os.path.exists(outside))
        self.assertFalse(os.path.exists(path_a))

    def test_remove_bridge_temp_files_is_a_noop_without_cleanup_info(self):
        service = GenerationService.__new__(GenerationService)
        service._remove_bridge_temp_files(None)
        service._remove_bridge_temp_files({})
        service._remove_bridge_temp_files({"paths": ["/etc/hosts"]})

    def test_job_finished_removes_bridge_temp_files_for_every_outcome(self):
        for status in ("completed", "failed", "canceled"):
            with self.subTest(status=status):
                service = GenerationService.__new__(GenerationService)
                cleanup = {"dir": "/tmp/x", "paths": ["/tmp/x/clip_a.mp4"]}
                job = {"request": {"bridge_cleanup": cleanup}}
                service.win = types.SimpleNamespace(
                    generation_queue=types.SimpleNamespace(get_job=lambda job_id, job=job: job),
                )
                service._handle_generation_job_finished = MagicMock()
                service._remove_bridge_temp_files = MagicMock()

                service.on_generation_job_finished("J1", status)

                service._handle_generation_job_finished.assert_called_once_with("J1", status)
                service._remove_bridge_temp_files.assert_called_once_with(cleanup)

    def test_job_finished_removes_bridge_temp_files_even_if_handling_raises(self):
        service = GenerationService.__new__(GenerationService)
        cleanup = {"dir": "/tmp/x", "paths": []}
        job = {"request": {"bridge_cleanup": cleanup}}
        service.win = types.SimpleNamespace(
            generation_queue=types.SimpleNamespace(get_job=lambda job_id: job),
        )
        service._handle_generation_job_finished = MagicMock(side_effect=RuntimeError("boom"))
        service._remove_bridge_temp_files = MagicMock()

        with self.assertRaises(RuntimeError):
            service.on_generation_job_finished("J1", "completed")

        service._remove_bridge_temp_files.assert_called_once_with(cleanup)

    def test_bridge_default_name_uses_both_source_clip_names(self):
        service = GenerationService.__new__(GenerationService)
        service._next_generation_name = lambda name: name
        clip_a = types.SimpleNamespace(data={"reader": {"path": "/media/Beach Walk_gen2.mp4"}})
        clip_b = types.SimpleNamespace(data={"reader": {"path": "/media/sunset.mov"}})
        self.assertEqual(
            service._bridge_default_name(clip_a, clip_b, None), "Beach Walk_to_sunset_bridge",
        )

    def test_bridge_default_name_collapses_two_copies_of_the_same_clip(self):
        service = GenerationService.__new__(GenerationService)
        service._next_generation_name = lambda name: name
        clip = types.SimpleNamespace(data={"reader": {"path": "/media/loop.mp4"}})
        self.assertEqual(service._bridge_default_name(clip, clip, None), "loop_bridge")

    def test_bridge_default_name_falls_back_when_clip_names_are_unknown(self):
        service = GenerationService.__new__(GenerationService)
        service._default_generation_name = lambda file_obj: "fallback_gen1"
        clip = types.SimpleNamespace(data={})
        self.assertEqual(service._bridge_default_name(clip, clip, object()), "fallback_gen1")

    def test_bridge_clips_with_ai_passes_cleanup_and_name_flag_with_the_payload(self):
        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace(
            files_model=types.SimpleNamespace(add_files=lambda *a, **k: None),
        )
        bridge_template = {"id": "video-bridge", "template": {"extra_inputs": [{"key": "clip_b", "type": "video"}]}}
        service.templates_for_context = lambda source_file=None: [bridge_template]
        service._default_generation_name = lambda file_obj: "bridge_gen1"
        file_a = types.SimpleNamespace(id="FA", data={"path": "/tmp/bridge/clip_a.mp4"})
        file_b = types.SimpleNamespace(id="FB", data={"path": "/tmp/bridge/clip_b.mp4"})
        files_by_path = {file_a.data["path"]: file_a, file_b.data["path"]: file_b}
        dialog_instance = MagicMock()
        dialog_instance.exec_.return_value = QDialog.Accepted
        dialog_instance.get_payload.return_value = {"name": "my_bridge", "template_id": "video-bridge"}
        enqueue_calls = []
        service._enqueue_generation_for_file = lambda source_file, payload: (
            enqueue_calls.append(payload) or (True, "")
        )
        service._remove_bridge_temp_files = MagicMock()

        with patch("classes.generation_service.render_clip_to_file", return_value=True), \
             patch("classes.generation_service.tempfile.mkdtemp", return_value="/tmp/bridge"), \
             patch("classes.generation_service.File.get", side_effect=lambda path: files_by_path.get(path)), \
             patch("classes.generation_service.GenerateMediaDialog", MagicMock(return_value=dialog_instance)), \
             patch.object(service, "_preselect_bridge_second_video_input"):
            service.bridge_clips_with_ai(
                types.SimpleNamespace(data={"position": 0.0, "layer": 1}),
                types.SimpleNamespace(data={"position": 5.0, "layer": 1}),
            )

        self.assertTrue(enqueue_calls[0]["display_name_from_payload"])
        self.assertEqual(
            enqueue_calls[0]["bridge_cleanup"],
            {"dir": "/tmp/bridge", "paths": ["/tmp/bridge/clip_a.mp4", "/tmp/bridge/clip_b.mp4"]},
        )
        service._remove_bridge_temp_files.assert_not_called()

    def test_bridge_clips_with_ai_removes_renders_when_dialog_canceled(self):
        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace(
            files_model=types.SimpleNamespace(add_files=lambda *a, **k: None),
        )
        bridge_template = {"id": "video-bridge", "template": {"extra_inputs": [{"key": "clip_b", "type": "video"}]}}
        service.templates_for_context = lambda source_file=None: [bridge_template]
        service._default_generation_name = lambda file_obj: "bridge_gen1"
        file_a = types.SimpleNamespace(id="FA", data={"path": "/tmp/bridge/clip_a.mp4"})
        file_b = types.SimpleNamespace(id="FB", data={"path": "/tmp/bridge/clip_b.mp4"})
        files_by_path = {file_a.data["path"]: file_a, file_b.data["path"]: file_b}
        dialog_instance = MagicMock()
        dialog_instance.exec_.return_value = QDialog.Rejected
        service._remove_bridge_temp_files = MagicMock()

        with patch("classes.generation_service.render_clip_to_file", return_value=True), \
             patch("classes.generation_service.tempfile.mkdtemp", return_value="/tmp/bridge"), \
             patch("classes.generation_service.File.get", side_effect=lambda path: files_by_path.get(path)), \
             patch("classes.generation_service.GenerateMediaDialog", MagicMock(return_value=dialog_instance)), \
             patch.object(service, "_preselect_bridge_second_video_input"):
            service.bridge_clips_with_ai(
                types.SimpleNamespace(data={}), types.SimpleNamespace(data={}),
            )

        service._remove_bridge_temp_files.assert_called_once()

    def test_bridge_clips_with_ai_removes_renders_when_enqueue_fails(self):
        service = GenerationService.__new__(GenerationService)
        service.win = types.SimpleNamespace(
            files_model=types.SimpleNamespace(add_files=lambda *a, **k: None),
        )
        bridge_template = {"id": "video-bridge", "template": {"extra_inputs": [{"key": "clip_b", "type": "video"}]}}
        service.templates_for_context = lambda source_file=None: [bridge_template]
        service._default_generation_name = lambda file_obj: "bridge_gen1"
        file_a = types.SimpleNamespace(id="FA", data={"path": "/tmp/bridge/clip_a.mp4"})
        file_b = types.SimpleNamespace(id="FB", data={"path": "/tmp/bridge/clip_b.mp4"})
        files_by_path = {file_a.data["path"]: file_a, file_b.data["path"]: file_b}
        dialog_instance = MagicMock()
        dialog_instance.exec_.return_value = QDialog.Accepted
        dialog_instance.get_payload.return_value = {"name": "x", "template_id": "video-bridge"}
        service._enqueue_generation_for_file = lambda *a, **k: (False, "nope")
        service._remove_bridge_temp_files = MagicMock()

        with patch("classes.generation_service.render_clip_to_file", return_value=True), \
             patch("classes.generation_service.tempfile.mkdtemp", return_value="/tmp/bridge"), \
             patch("classes.generation_service.File.get", side_effect=lambda path: files_by_path.get(path)), \
             patch("classes.generation_service.GenerateMediaDialog", MagicMock(return_value=dialog_instance)), \
             patch("classes.generation_service.QMessageBox"), \
             patch.object(service, "_preselect_bridge_second_video_input"):
            service.bridge_clips_with_ai(
                types.SimpleNamespace(data={}), types.SimpleNamespace(data={}),
            )

        service._remove_bridge_temp_files.assert_called_once()


if __name__ == "__main__":
    unittest.main()
