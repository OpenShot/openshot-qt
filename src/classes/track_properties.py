"""Static track settings exposed through the existing Properties table."""
import json
import openshot
from classes.app import get_app
from classes.query import Track


class TrackProperties:
    def __init__(self, track_id):
        self.track_id = track_id

    def Id(self):
        return self.track_id

    @property
    def data(self):
        track = Track.get(id=self.track_id)
        return track.data if track else {}

    def Json(self):
        return json.dumps(self.data)

    def PropertiesJSON(self, frame):
        data = self.data
        tracks = sorted(get_app().project.get("layers"), key=lambda t: t["number"])
        number = next((i + 1 for i, track in enumerate(tracks) if track["id"] == self.track_id), 0)
        definitions = (("display_number", "Track Number", "int", number, True),
                       ("label", "Name", "string", data.get("label") or get_app()._tr("Track %s") % number, bool(data.get("lock"))),
                       ("muted", "Mute Audio", "bool", bool(data.get("muted")), False),
                       ("hidden", "Hide Video", "bool", bool(data.get("hidden")), False),
                       ("lock", "Lock", "bool", bool(data.get("lock")), False))
        properties = {}
        for key, name, kind, value, readonly in definitions:
            properties["track." + key] = dict(
                name=name, type=kind, value=value, memo=str(value) if kind == "string" else "",
                readonly=readonly, min=0, max=1000000, keyframe=False, points=0,
                interpolation=openshot.CONSTANT, closest_point_x=1, previous_point_x=1,
                object_id="", choices=[dict(name=label, value=choice, selected=value == choice)
                    for choice, label in ((False, "False"), (True, "True"))] if kind == "bool" else [])
        return json.dumps(properties)
