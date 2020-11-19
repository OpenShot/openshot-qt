# OpenShot Video Editor is a program that creates, modifies, and edits video files.
#   Copyright (C) 2009  Jonathan Thomas
#
# This file is part of OpenShot Video Editor (http://launchpad.net/openshot/).
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Video Editor.  If not, see <http://www.gnu.org/licenses/>.


# Import Blender's python API.  This only works when the script is being
# run from the context of Blender.  Blender contains it's own version of Python
# with this library pre-installed.
import math
import bpy
import json


def load_font(font_path):
    """ Load a new TTF font into Blender, and return the font object """
    # get the original list of fonts (before we add a new one)
    original_fonts = bpy.data.fonts.keys()

    # load new font
    bpy.ops.font.open(filepath=font_path)

    # get the new list of fonts (after we added a new one)
    for font_name in bpy.data.fonts.keys():
        if font_name not in original_fonts:
            return bpy.data.fonts[font_name]

    # no new font was added
    return None

# Debug Info:
# ./blender -b test.blend -P demo.py
# -b = background mode
# -P = run a Python script within the context of the project file


# Init all of the variables needed by this script.  Because Blender executes
# this script, OpenShot will inject a dictionary of the required parameters
# before this script is executed.
params = {
    'extrude': 0.1,
    'bevel_depth': 0.02,
    'spacemode': 'CENTER',
    'text_size': 1.5,
    'width': 1.0,
    'fontname': 'Bfont',

    'color': [0.8, 0.8, 0.8],
    'alpha': 1.0,

    'output_path': '/tmp/',
    'fps': 24,
    'quality': 90,
    'file_format': 'PNG',
    'color_mode': 'RGBA',
    'horizon_color': [0.57, 0.57, 0.57],
    'resolution_x': 1920,
    'resolution_y': 1080,
    'resolution_percentage': 100,
    'start_frame': 1,
    'end_frame': 250,
    'length_multiplier': 1,

    'depart_title': 'Paris',
    'depart_lat_deg': 48,
    'depart_lat_min': 51,
    'depart_lat_sec': 24,
    'depart_lat_dir': "N",
    'depart_lon_deg': 2,
    'depart_lon_min': 21,
    'depart_lon_sec': 7,
    'depart_lon_dir': "E",

    'arrive_title': 'New York',
    'arrive_lat_deg': 40,
    'arrive_lat_min': 42,
    'arrive_lat_sec': 51,
    'arrive_lat_dir': "N",
    'arrive_lon_deg': 74,
    'arrive_lon_min': 0,
    'arrive_lon_sec': 23,
    'arrive_lon_dir': "E",
}


# INJECT_PARAMS_HERE

# The remainder of this script will modify the current Blender .blend project
# file, and adjust the settings.  The .blend file is specified in the XML file
# that defines this template in OpenShot.
# ----------------------------------------------------------------------------

# Process parameters supplied as JSON serialization
try:
    injected_params = json.loads(params_json)
    params.update(injected_params)
except NameError:
    pass


depart = {
    "lat_deg": params["depart_lat_deg"],
    "lat_min": params["depart_lat_min"],
    "lat_sec": params["depart_lat_sec"],
    "lat_dir": params["depart_lat_dir"],

    "lon_deg": params["depart_lon_deg"],
    "lon_min": params["depart_lon_min"],
    "lon_sec": params["depart_lon_sec"],
    "lon_dir": params["depart_lon_dir"],
}

arrive = {
    "lat_deg": params["arrive_lat_deg"],
    "lat_min": params["arrive_lat_min"],
    "lat_sec": params["arrive_lat_sec"],
    "lat_dir": params["arrive_lat_dir"],

    "lon_deg": params["arrive_lon_deg"],
    "lon_min": params["arrive_lon_min"],
    "lon_sec": params["arrive_lon_sec"],
    "lon_dir": params["arrive_lon_dir"],
}


def get_latitude(direction, degrees, minutes, seconds):
    lat = degrees + minutes / 60.0 + seconds / 3600.0
    if direction == "N":
        # North of the equator
        return -lat
    else:
        # South of the equator
        return lat


def get_longitude(direction, degrees, minutes, seconds):
    lon = degrees + minutes / 60.0 + seconds / 3600.0
    if direction == "E":
        # East of prime meridian
        return lon
    else:
        # West of prime meridian
        return -lon


def correct_longitude(depart_longitude, arrive_longitude):
    if -180 < (arrive_longitude - depart_longitude) < 180:
        return depart_longitude
    else:
        if depart_longitude < 0:
            return depart_longitude + 360
        else:
            return depart_longitude - 360


class Point:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z


class Coord(Point):
    def __init__(self, latitude, longitude, radius):
        self.lat = latitude
        self.lon = longitude
        self.radius = radius
        p_x = (
            radius
            * math.cos(math.radians(latitude))
            * math.sin(math.radians(longitude))
            )
        p_y = (
            radius
            * math.cos(math.radians(latitude))
            * math.cos(math.radians(longitude))
        )
        p_z = (radius * math.sin(math.radians(latitude)))
        super().__init__(p_x, p_y, p_z)


# Calculate latitude / longitude for depart and arrive points
sphere_radius = 10.0
point_a = Coord(
    get_latitude(
        depart["lat_dir"], depart["lat_deg"],
        depart["lat_min"], depart["lat_sec"]),
    get_longitude(
        depart["lon_dir"], depart["lon_deg"],
        depart["lon_min"], depart["lon_sec"]),
    sphere_radius
)
point_b = Coord(
    get_latitude(
        arrive["lat_dir"], arrive["lat_deg"],
        arrive["lat_min"], arrive["lat_sec"]),
    get_longitude(
        arrive["lon_dir"], arrive["lon_deg"],
        arrive["lon_min"], arrive["lon_sec"]),
    sphere_radius
)

# Correct longitude if necessary
orig_point_a_lon = point_a.lon
point_a.lon = correct_longitude(orig_point_a_lon, point_b.lon)

# Get angle between A & B points
ab_angle_radians = math.acos(
    (point_a.x * point_b.x + point_a.y * point_b.y + point_a.z * point_b.z)
    / (sphere_radius * sphere_radius)
)
ab_angle_degrees = ab_angle_radians * 180 / math.pi

# calculate points C & D
point_c = Coord(
    point_a.lat + 0.25 * (point_b.lat - point_a.lat),
    point_a.lon + 0.25 * (point_b.lon - point_a.lon),
    sphere_radius
)
point_d = Coord(
    point_a.lat + 0.75 * (point_b.lat - point_a.lat),
    point_a.lon + 0.75 * (point_b.lon - point_a.lon),
    sphere_radius
)

# radius of CD line segment
location_CD = (sphere_radius + 1.0) / math.cos(ab_angle_radians / 4.0)

print("EmptyPointA Transform Rotation: Y= %f Z= %f" % (point_a.lat, point_a.lon))
print("EmptyPointB Transform Rotation: Y= %f Z= %f" % (point_b.lat, point_b.lon))
print("EmptyPointC Transform Rotation: Y= %f Z= %f" % (point_c.lat, point_c.lon))
print("EmptyPointD Transform Rotation: Y= %f Z= %f" % (point_d.lat, point_d.lon))
print("EmptyPointC.001 Transform Location: X= %f" % location_CD)
print("EmptyPointD.001 Transform Location: X= %f" % location_CD)
print("EmptyCam Frame 20 ->Transform Rotation: Y= %f Z= %f" % (point_a.lat, point_a.lon))
print("EmptyCam Frame 80 ->Transform Rotation: Y= %f Z= %f" % (point_b.lat, point_b.lon))

# Set Blender properties
for pname, point in [
        ("EmptyPointA", point_a),
        ("EmptyPointB", point_b),
        ("EmptyPointC", point_c),
        ("EmptyPointD", point_d),
        ]:
    bpy.data.objects[pname].rotation_euler = (
        0.0, math.radians(point.lat), math.radians(point.lon)
    )
bpy.data.objects["EmptyPointC.001"].location.x = location_CD
bpy.data.objects["EmptyPointD.001"].location.x = location_CD


def update_curve(curve, start, end):
    coords = [
        (20.0, start),
        (80.0, end),
        ]
    for i, coord in enumerate(coords):
        p = curve.keyframe_points[i]
        p.co = coord
        p.handle_left.y = coord[1]
        p.handle_right.y = coord[1]


# set Y rotation on the camera
action = bpy.data.actions["EmptyCamAction"]
update_curve(
    action.fcurves[1], math.radians(point_a.lat), math.radians(point_b.lat))
update_curve(
    action.fcurves[2], math.radians(point_a.lon), math.radians(point_b.lon))

# set world texture (i.e. the globe texture)
if params["map_texture"]:
    bpy.data.textures["Texture.002"].image.filepath = params["map_texture"]

# Get font object
font = None
if params["fontname"] != "Bfont":
    # Add font so it's available to Blender
    font = load_font(params["fontname"])
else:
    # Get default font
    font = bpy.data.fonts["Bfont"]

# Modify Text for Departure
text_object = bpy.data.curves["Text"]
text_object.body = params["depart_title"]

# Modify Text for Arrival
text_object = bpy.data.curves["Text.001"]
text_object.body = params["arrive_title"]

# Set common text parameters
for ob in [bpy.data.curves["Text"], bpy.data.curves["Text.001"]]:
    ob.extrude = params["extrude"]
    ob.bevel_depth = params["bevel_depth"]
    ob.size = params["text_size"]
    ob.space_character = params["width"]
    ob.font = font

# Modify the Materials for Text, Lines, and Pins
for material in [
        "Material.001",
        "Material.002",
        "Material.003",
        "Material.004",
        "Material.005",
        ]:
    ob = bpy.data.materials[material]
    ob.diffuse_color = params["diffuse_color"]
    ob.specular_color = params["specular_color"]
    ob.specular_intensity = params["specular_intensity"]

# Set the render options.  It is important that these are set
# to the same values as the current OpenShot project.  These
# params are automatically set by OpenShot
render = bpy.context.scene.render
render.filepath = params["output_path"]
render.fps = params["fps"]
if "fps_base" in params:
    render.fps_base = params["fps_base"]
render.image_settings.file_format = params["file_format"]
render.image_settings.color_mode = params["color_mode"]
render.resolution_x = params["resolution_x"]
render.resolution_y = params["resolution_y"]
render.resolution_percentage = params["resolution_percentage"]

# Animation Speed (use Blender's time remapping to slow or speed up animation)
length_multiplier = int(params["length_multiplier"])  # time remapping multiplier
new_length = int(params["end_frame"]) * length_multiplier  # new length (in frames)
render.frame_map_old = 1
render.frame_map_new = length_multiplier

# Set render length/position
bpy.context.scene.frame_start = params["start_frame"]
bpy.context.scene.frame_end = new_length
