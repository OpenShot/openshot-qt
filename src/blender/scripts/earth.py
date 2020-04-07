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
    'title': 'Oh Yeah! OpenShot!',
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
    'start_frame': 20,
    'end_frame': 25,
    'animation': True,
}

# INJECT_PARAMS_HERE

# The remainder of this script will modify the current Blender .blend project
# file, and adjust the settings.  The .blend file is specified in the XML file
# that defines this template in OpenShot.
# ----------------------------------------------------------------------------


# depart = {"title":"Paris",
#    "lat_deg": 48, "lat_min": 51, "lat_sec": 24, "lat_dir": "N",
#    "lon_deg": 2, "lon_min": 21, "lon_sec": 7, "lon_dir": "E",
# }
#
# arrive = {"title":"New York",
#    "lat_deg": 40, "lat_min": 42, "lat_sec": 51, "lat_dir": "N",
#    "lon_deg": 74, "lon_min": 0, "lon_sec": 23, "lon_dir": "O",
# }

depart = {
    "lat_deg": params["depart_lat_deg"], "lat_min": params["depart_lat_min"], "lat_sec": params["depart_lat_sec"], "lat_dir": params["depart_lat_dir"],
    "lon_deg": params["depart_lon_deg"], "lon_min": params["depart_lon_min"], "lon_sec": params["depart_lon_sec"], "lon_dir": params["depart_lon_dir"],
}

arrive = {
    "lat_deg": params["arrive_lat_deg"], "lat_min": params["arrive_lat_min"], "lat_sec": params["arrive_lat_sec"], "lat_dir": params["arrive_lat_dir"],
    "lon_deg": params["arrive_lon_deg"], "lon_min": params["arrive_lon_min"], "lon_sec": params["arrive_lon_sec"], "lon_dir": params["arrive_lon_dir"],
}

point_a = {}
point_b = {}
point_c = {}
point_d = {}


def get_latitude(direction, degrees, minutes, seconds):

    latitude = 0.0
    if direction == "N":
        # North of the equator
        latitude = -(degrees + minutes / 60.0 + seconds / 3600.0)
    else:
        # South of the equator
        latitude = degrees + minutes / 60.0 + seconds / 3600.0

    return latitude


def get_longitude(direction, degrees, minutes, seconds):

    longitude = 0.0
    if direction == "E":
        # North of the equator
        longitude = degrees + minutes / 60.0 + seconds / 3600.0
    else:
        # South of the equator
        longitude = - (degrees + minutes / 60.0 + seconds / 3600.0)

    return longitude


def check_longitude(depart_longitude, arrive_longitude):

    if -180 < (arrive_longitude - depart_longitude) and (arrive_longitude - depart_longitude) < 180:
        return depart_longitude
    else:
        if depart_longitude < 0:
            return depart_longitude + 360
        else:
            return depart_longitude - 360


# Calculate latitude / longitude for depart and arrive points
sphere_radius = 10.0
point_a["lat"] = get_latitude(depart["lat_dir"], depart["lat_deg"], depart["lat_min"], depart["lat_sec"])
point_a["lon"] = get_longitude(depart["lon_dir"], depart["lon_deg"], depart["lon_min"], depart["lon_sec"])
point_b["lat"] = get_latitude(arrive["lat_dir"], arrive["lat_deg"], arrive["lat_min"], arrive["lat_sec"])
point_b["lon"] = get_longitude(arrive["lon_dir"], arrive["lon_deg"], arrive["lon_min"], arrive["lon_sec"])
point_a["lon_Z"] = check_longitude(point_a["lon"], point_b["lon"])
point_b["lon_Z"] = point_b["lon"]

point_a["x"] = sphere_radius * math.cos(math.radians(point_a["lat"])) * math.sin(math.radians(point_a["lon"]))
point_b["x"] = sphere_radius * math.cos(math.radians(point_b["lat"])) * math.sin(math.radians(point_b["lon"]))
point_a["y"] = sphere_radius * math.cos(math.radians(point_a["lat"])) * math.cos(math.radians(point_a["lon"]))
point_b["y"] = sphere_radius * math.cos(math.radians(point_b["lat"])) * math.cos(math.radians(point_b["lon"]))
point_a["z"] = sphere_radius * math.sin(math.radians(point_a["lat"]))
point_b["z"] = sphere_radius * math.sin(math.radians(point_b["lat"]))

# Get angle between A & B points
ab_angle_radians = math.acos((point_a["x"] * point_b["x"] + point_a["y"] * point_b["y"]
                              + point_a["z"] * point_b["z"]) / (sphere_radius * sphere_radius))
ab_angle_degrees = ab_angle_radians * 180 / math.pi

# calculate points C & D
point_c["lat"] = point_a["lat"] + 0.25 * (point_b["lat"] - point_a["lat"])
point_c["lon"] = point_a["lon_Z"] + 0.25 * (point_b["lon_Z"] - point_a["lon_Z"])
point_d["lat"] = point_a["lat"] + 0.75 * (point_b["lat"] - point_a["lat"])
point_d["lon"] = point_a["lon_Z"] + 0.75 * (point_b["lon_Z"] - point_a["lon_Z"])

# radius of CD line segment
location_CD = (sphere_radius + 1.0) / math.cos(ab_angle_radians / 4.0)

print("EmptyPointA Transform Rotation: Y= %f Z= %f" % (point_a["lat"], point_a["lon_Z"]))
print("EmptyPointB Transform Rotation: Y= %f Z= %f" % (point_b["lat"], point_b["lon_Z"]))
print("EmptyPointC Transform Rotation: Y= %f Z= %f" % (point_c["lat"], point_c["lon"]))
print("EmptyPointD Transform Rotation: Y= %f Z= %f" % (point_d["lat"], point_d["lon"]))
print("EmptyPointC.001 Transform Location: X= %f" % location_CD)
print("EmptyPointD.001 Transform Location: X= %f" % location_CD)
print("EmptyCam Frame 20 ->Transform Rotation: Y= %f Z= %f  And press I key" % (point_a["lat"], point_a["lon_Z"]))
print("EmptyCam Frame 80 ->Transform Rotation: Y= %f Z= %f  And press I key" % (point_b["lat"], point_b["lon_Z"]))

# Set Blender properties
bpy.data.objects["EmptyPointA"].rotation_euler = (0.0, math.radians(point_a["lat"]), math.radians(point_a["lon_Z"]))
bpy.data.objects["EmptyPointB"].rotation_euler = (0.0, math.radians(point_b["lat"]), math.radians(point_b["lon_Z"]))
bpy.data.objects["EmptyPointC"].rotation_euler = (0.0, math.radians(point_c["lat"]), math.radians(point_c["lon"]))
bpy.data.objects["EmptyPointD"].rotation_euler = (0.0, math.radians(point_d["lat"]), math.radians(point_d["lon"]))
bpy.data.objects["EmptyPointC.001"].location.x = location_CD
bpy.data.objects["EmptyPointD.001"].location.x = location_CD

# set Y rotation on the camera
bpy.data.actions["EmptyCamAction"].fcurves[1].keyframe_points[0].co = (20.0, math.radians(point_a["lat"]))
bpy.data.actions["EmptyCamAction"].fcurves[1].keyframe_points[0].handle_left.y = math.radians(point_a["lat"])
bpy.data.actions["EmptyCamAction"].fcurves[1].keyframe_points[0].handle_right.y = math.radians(point_a["lat"])

bpy.data.actions["EmptyCamAction"].fcurves[1].keyframe_points[1].co = (80.0, math.radians(point_b["lat"]))
bpy.data.actions["EmptyCamAction"].fcurves[1].keyframe_points[1].handle_left.y = math.radians(point_b["lat"])
bpy.data.actions["EmptyCamAction"].fcurves[1].keyframe_points[1].handle_right.y = math.radians(point_b["lat"])

# set Z rotation on the camera
bpy.data.actions["EmptyCamAction"].fcurves[2].keyframe_points[0].co = (20.0, math.radians(point_a["lon_Z"]))
bpy.data.actions["EmptyCamAction"].fcurves[2].keyframe_points[0].handle_left.y = math.radians(point_a["lon_Z"])
bpy.data.actions["EmptyCamAction"].fcurves[2].keyframe_points[0].handle_right.y = math.radians(point_a["lon_Z"])

bpy.data.actions["EmptyCamAction"].fcurves[2].keyframe_points[1].co = (80.0, math.radians(point_b["lon_Z"]))
bpy.data.actions["EmptyCamAction"].fcurves[2].keyframe_points[1].handle_left.y = math.radians(point_b["lon_Z"])
bpy.data.actions["EmptyCamAction"].fcurves[2].keyframe_points[1].handle_right.y = math.radians(point_b["lon_Z"])

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
text_object.extrude = params["extrude"]
text_object.bevel_depth = params["bevel_depth"]
text_object.size = params["text_size"]
text_object.space_character = params["width"]
text_object.font = font
material_object = bpy.data.materials["Material.001"]
material_object.diffuse_color = params["diffuse_color"]
material_object.specular_color = params["specular_color"]
material_object.specular_intensity = params["specular_intensity"]

# Modify Text for Arrival
text_object = bpy.data.curves["Text.001"]
text_object.body = params["arrive_title"]
text_object.extrude = params["extrude"]
text_object.bevel_depth = params["bevel_depth"]
text_object.size = params["text_size"]
text_object.space_character = params["width"]
text_object.font = font
material_object = bpy.data.materials["Material.003"]
material_object.diffuse_color = params["diffuse_color"]
material_object.specular_color = params["specular_color"]
material_object.specular_intensity = params["specular_intensity"]

# Modify the Line Material and Pins
material_object = bpy.data.materials["Material.002"]
material_object.diffuse_color = params["diffuse_color"]
material_object.specular_color = params["specular_color"]
material_object.specular_intensity = params["specular_intensity"]
material_object = bpy.data.materials["Material.004"]
material_object.diffuse_color = params["diffuse_color"]
material_object.specular_color = params["specular_color"]
material_object.specular_intensity = params["specular_intensity"]
material_object = bpy.data.materials["Material.005"]
material_object.diffuse_color = params["diffuse_color"]
material_object.specular_color = params["specular_color"]
material_object.specular_intensity = params["specular_intensity"]

# Set the render options.  It is important that these are set
# to the same values as the current OpenShot project.  These
# params are automatically set by OpenShot
bpy.context.scene.render.filepath = params["output_path"]
bpy.context.scene.render.fps = params["fps"]
bpy.context.scene.render.image_settings.file_format = params["file_format"]
bpy.context.scene.render.image_settings.color_mode = params["color_mode"]
bpy.context.scene.render.resolution_x = params["resolution_x"]
bpy.context.scene.render.resolution_y = params["resolution_y"]
bpy.context.scene.render.resolution_percentage = params["resolution_percentage"]
bpy.context.scene.frame_start = params["start_frame"]
bpy.context.scene.frame_end = params["end_frame"]

# Animation Speed (use Blender's time remapping to slow or speed up animation)
length_multiplier = int(params["length_multiplier"])  # time remapping multiplier
new_length = int(params["end_frame"]) * length_multiplier  # new length (in frames)
bpy.context.scene.frame_end = new_length
bpy.context.scene.render.frame_map_old = 1
bpy.context.scene.render.frame_map_new = length_multiplier
if params["start_frame"] == params["end_frame"]:
    bpy.context.scene.frame_start = params["end_frame"]
    bpy.context.scene.frame_end = params["end_frame"]

# Render the current animation to the params["output_path"] folder
bpy.ops.render.render(animation=params["animation"])
