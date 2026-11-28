"""Project-wide canvas settings, using the regular color/keyframe editor."""
import json
from copy import deepcopy
import openshot
from classes.app import get_app


class TimelineProperties:
    def __init__(self):
        app = get_app()
        self.data = {key: deepcopy(app.project.get(key)) for key in ("color", "width", "height", "fps", "display_ratio", "pixel_ratio", "profile", "profile_settings")}
        if not self.data["color"].get("alpha", {}).get("Points"):
            self.data["color"]["alpha"] = json.loads(openshot.Keyframe(255).Json())
        self._color_properties = openshot.Clip()

    def Id(self):
        return "__timeline__"

    def Json(self):
        return json.dumps(self.data)

    def save(self):
        get_app().updates.update(["color"], self.data["color"])

    def PropertiesJSON(self, frame):
        # Reuse the native color metadata, including all four channel curves,
        # so the existing picker, insertion, interpolation and removal work alike.
        self._color_properties.wave_color.SetJson(json.dumps(self.data["color"]))
        color = json.loads(self._color_properties.PropertiesJSON(frame))["wave_color"]
        color["name"] = "Background Color"
        props = {"color": color}
        fps = self.data["fps"]
        profile = self.data["profile_settings"] or {}
        ratio = lambda key: "%s:%s" % (self.data[key]["num"], self.data[key]["den"])
        definitions = [
            ("profile", "Profile", "string", self.data["profile"]),
            ("width", "Width", "int", self.data["width"]),
            ("height", "Height", "int", self.data["height"]),
            ("fps", "Frame Rate", "float", fps["num"] / fps["den"]),
            ("display_ratio", "Display Aspect Ratio", "string", ratio("display_ratio")),
            ("pixel_ratio", "Pixel Aspect Ratio", "string", ratio("pixel_ratio")),
        ]
        # Profile JSON contains the remaining video format settings.
        for key, name, kind in (("progressive", "Progressive", "bool"),
                                ("spherical", "Spherical", "bool"),
                                ("pixel_format", "Pixel Format", "int")):
            if key in profile:
                definitions.append((key, name, kind, profile[key]))
        for key, name, kind, value in definitions:
            props[key] = dict(name=name, type=kind, value=value,
                memo=str(value) if kind == "string" else "", readonly=True,
                profile_property=True, min=0, max=1000000, keyframe=False, points=0,
                interpolation=openshot.CONSTANT, closest_point_x=1, previous_point_x=1,
                choices=[], object_id="")
        return json.dumps(props)
