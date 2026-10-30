"""Session GPU evidence shared by logs, About, and copied version information.

Capability probes do not prove acceleration was used. Only successful native
preview draws count as observed GPU presentation. Readbacks include thumbnails
and CPU effects, and are not an export or decode acceleration measurement.
"""
import copy
import json
import os
import sys
import threading


class GpuDiagnostics:
    def __init__(self, native, logger, environ=None):
        self.native = native
        self.log = logger
        self.environ = dict(os.environ if environ is None else environ)
        self.lock = threading.RLock()
        self.previews = {}
        self.started = False
        self.probe_state = "not checked"
        self.devices = []
        self.selected = ""
        self.encoders = []
        self.errors = []
        self.last_summary = None
        self.apis = {name: callable(getattr(native, name, None)) for name in
                     ("VulkanOpenGLPresenter", "ListGpuDevices", "ActiveGpuDevice", "GpuEncoders")}

    def event(self, name, **details):
        self.log.info("GPU diagnostics [%s]: %s", name,
                      json.dumps(details, sort_keys=True, ensure_ascii=False))

    def log_startup(self):
        self.event("startup", apis=self.apis,
                   backend=self.environ.get("OPENSHOT_RENDER_BACKEND", "vulkan (default)"),
                   device_override=self.environ.get("OPENSHOT_VULKAN_DEVICE", "automatic"),
                   bindings=getattr(self.native, "__file__", "unknown"),
                   extension=getattr(sys.modules.get("_openshot"), "__file__", "unknown"))

    def start_probe(self):
        """Probe once off the GUI thread; About only reads the cached result."""
        with self.lock:
            if self.started:
                return
            self.started = True
            self.probe_state = "checking"
        threading.Thread(target=self.probe, name="GPU diagnostics", daemon=True).start()

    def probe(self):
        devices, selected, encoders, errors = [], "", [], []
        for name in ("ListGpuDevices", "ActiveGpuDevice", "GpuEncoders"):
            if not self.apis[name]:
                continue
            # Encoder probes are tied to the active Vulkan device. An explicit
            # CPU backend must not be described as having no hardware encoders.
            if name == "GpuEncoders" and (
                    self.environ.get("OPENSHOT_RENDER_BACKEND") == "cpu" or not selected):
                continue
            try:
                value = getattr(self.native, name)()
                if name == "ListGpuDevices":
                    devices = [{key: getattr(item, key, "not reported") for key in
                                ("name", "vendor", "type", "driver", "uuid", "vulkan_api", "video_decode", "video_encode")}
                               for item in value]
                elif name == "ActiveGpuDevice":
                    selected = value.name
                else:
                    encoders = list(value)
            except Exception as error:
                errors.append("%s: %s" % (name, error))
        with self.lock:
            self.devices, self.selected, self.encoders, self.errors = devices, selected, encoders, errors
            self.probe_state = "complete"
        self.event("capabilities", devices=devices, selected_vulkan_device=selected,
                   hardware_encoders_that_open=encoders, errors=errors,
                   encoders_checked=bool(selected) and self.apis["GpuEncoders"] and
                   self.environ.get("OPENSHOT_RENDER_BACKEND") != "cpu",
                   note="Capabilities are not proof of active decoding, presentation, or encoding")

    def register_preview(self, name, enabled, reason):
        with self.lock:
            key = len(self.previews) + 1
            self.previews[key] = dict(name=name, enabled=enabled, selection_reason=reason,
                                      native_draws=0, cpu_draws=0, fallback_reasons=[])
        self.event("preview selection", preview=name, native_presenter=enabled, reason=reason)
        return key

    def observe_preview(self, key, native_draw, reason=""):
        with self.lock:
            preview = self.previews[key]
            counter = "native_draws" if native_draw else "cpu_draws"
            first = preview[counter] == 0
            preview[counter] += 1
            new_reason = (reason and reason not in preview["fallback_reasons"]
                          and len(preview["fallback_reasons"]) < 8)
            if new_reason:
                preview["fallback_reasons"].append(reason)
            name = preview["name"]
        if first or new_reason:
            self.event("native preview confirmed" if native_draw else "CPU preview fallback",
                       preview=name, reason=reason or None)

    def snapshot(self):
        with self.lock:
            result = copy.deepcopy(dict(probe=self.probe_state, apis=self.apis, devices=self.devices,
                                        selected=self.selected, encoders=self.encoders, errors=self.errors,
                                        previews=list(self.previews.values()),
                                        backend=self.environ.get("OPENSHOT_RENDER_BACKEND", "vulkan")))
        try:
            result["readbacks"] = self.native.VulkanFrameReadbackCount()
        except (AttributeError, RuntimeError):
            result["readbacks"] = None
        return result

    def log_summary(self):
        current = self.snapshot()
        if current != self.last_summary:
            self.event("session summary", **current)
            self.last_summary = current

    def brief(self, translate=lambda value: value):
        _ = translate
        state = self.snapshot()
        device = state["selected"] or next((d["name"] for d in state["devices"]
                                            if d["type"] != "software"), "")
        if not state["apis"]["ListGpuDevices"]:
            return _("GPU information unavailable · Vulkan API unavailable")
        if state["probe"] != "complete":
            return _("GPU: checking capabilities…")
        prefix = (_("GPU: %s") % device) if device else _("GPU: not available through Vulkan")
        previews = state["previews"]
        native = sum(p["native_draws"] for p in previews)
        cpu = sum(p["cpu_draws"] for p in previews)
        if state["backend"] == "cpu":
            status = _("CPU rendering requested")
        elif native and cpu:
            status = _("GPU preview with CPU fallback")
        elif native:
            status = _("Vulkan preview active")
        elif cpu:
            status = _("CPU preview fallback")
        elif previews and not any(p["enabled"] for p in previews):
            status = _("CPU preview selected")
        elif state["selected"]:
            status = _("Vulkan available · not yet observed")
        else:
            status = _("Vulkan unavailable")
        return prefix + " · " + status

    def copy_lines(self):
        """Compact support summary; detailed evidence stays in logs/tooltip."""
        state = self.snapshot()
        device = next((d for d in state["devices"] if d["name"] == state["selected"]), None)
        if device is None:
            device = next((d for d in state["devices"] if d["type"] != "software"), None)
        lines = ["GPU: " + (device["name"] if device else "not identified")]
        previews = state["previews"]
        native = sum(p["native_draws"] for p in previews)
        cpu = sum(p["cpu_draws"] for p in previews)
        if not state["apis"]["ListGpuDevices"]:
            status = "GPU acceleration unavailable in this build"
        elif state["backend"] == "cpu":
            status = "CPU rendering was explicitly requested"
        elif native and cpu:
            status = "GPU acceleration worked, but CPU fallback also occurred"
        elif native:
            status = "GPU acceleration used for preview"
        elif cpu:
            status = "CPU preview used; GPU presentation did not succeed"
        elif previews and not any(p["enabled"] for p in previews):
            status = "CPU preview selected"
        elif state["probe"] != "complete":
            status = "Checking whether GPU acceleration is available"
        elif state["selected"]:
            status = "GPU acceleration available; not yet used for preview"
        else:
            status = "No usable Vulkan device"
        lines.append("Preview: " + status)
        driver_line = None
        if device:
            driver_line = "Driver: %s | Vulkan: %s" % (device["driver"] or "not reported", device["vulkan_api"])
        if state["backend"] != "cpu":
            # Prefer the timeline's explanation; keep additional previews and
            # earlier reasons in the detailed report rather than the clipboard.
            reasons = []
            for preview in sorted(state["previews"], key=lambda p: p["name"] != "timeline"):
                if preview["fallback_reasons"]:
                    reasons.append(preview["fallback_reasons"][-1])
                elif not preview["enabled"]:
                    reasons.append(preview["selection_reason"])
            if reasons or state["errors"]:
                reason = (reasons or state["errors"])[0].splitlines()[0]
                if "selected different GPUs" in reason:
                    reason = "Display and video processing selected different GPUs"
                elif reason.startswith("Frame is CPU-backed"):
                    reason = "This preview needed CPU image data"
                elif reason == "Qt could not create a usable OpenGL context":
                    reason = "Display initialization could not enable GPU preview"
                elif reason == "libopenshot has no Vulkan presenter binding":
                    reason = "This build does not provide GPU preview support"
                lines.append("Fallback reason: " + (reason[:237] + "…" if len(reason) > 240 else reason))
        if driver_line:
            lines.append(driver_line)
        return lines

    def report_lines(self):
        state = self.snapshot()
        lines = [self.brief(), "GPU backend requested: " + state["backend"],
                 "GPU device override: " + self.environ.get("OPENSHOT_VULKAN_DEVICE", "automatic"),
                 "GPU capability probe: " + state["probe"],
                 "Selected Vulkan rendering device: " +
                 (state["selected"] or ("none" if state["probe"] == "complete" else "not checked")),
                 "Vulkan APIs: " + ", ".join("%s=%s" % pair for pair in state["apis"].items())]
        for device in state["devices"]:
            lines.append("GPU device: {name} | {vendor} | {type} | driver: {driver} | "
                         "Vulkan API: {vulkan_api} | Vulkan Video queues: decode={video_decode}, encode={video_encode}".format(**device))
        if state["probe"] == "complete":
            checked = self.apis["GpuEncoders"] and state["backend"] != "cpu" and bool(state["selected"])
            lines.append("Hardware encoders that opened: " +
                         (", ".join(state["encoders"]) or ("none" if checked else "not checked")))
        for preview in state["previews"]:
            lines.append("GPU preview (%s): selected=%s; native draws=%s; CPU fallback draws=%s; %s" %
                         (preview["name"], preview["enabled"], preview["native_draws"], preview["cpu_draws"],
                          "; ".join(preview["fallback_reasons"]) or preview["selection_reason"]))
        lines.extend("GPU probe error: " + error for error in state["errors"])
        lines.append("GPU → CPU materializations (session): %s (includes thumbnails and CPU effects)" %
                     (state["readbacks"] if state["readbacks"] is not None else "unavailable"))
        lines.append("GPU capabilities and preview counts do not establish hardware decoding or encoding; "
                     "see libopenshot.log for per-reader and export paths.")
        return lines
