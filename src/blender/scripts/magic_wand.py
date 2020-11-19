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
import bpy
import json

# Debug Info:
# ./blender -b test.blend -P demo.py
# -b = background mode
# -P = run a Python script within the context of the project file

# Init all of the variables needed by this script.  Because Blender executes
# this script, OpenShot will inject a dictionary of the required parameters
# before this script is executed.
params = {
    'output_path': '/tmp/',
    'file_format': 'PNG',
    'fps': 24,
    'quality': 90,
    'resolution_x': 1920,
    'resolution_y': 1080,
    'resolution_percentage': 100,
    'start_frame': 1,
    'end_frame': 250,
    'length_multiplier': 1,

    'color_mode': 'RGBA',
    'alpha_mode': 1.0,
    'horizon_color': (0.57, 0.57, 0.57),
    'diffuse_color': (1.0, 0.9, 0.0, 1.0),

    'particles_count': 5000,
    'particles_lifetime': 50,
    'particles_gravity': 1.0,
    'particle_scale': 0.03,
    'strength': 1,
    'glare_type': 'STREAKS',

    'velocity_x': 1.0,
    'velocity_y': 0.0,
    'velocity_z': 0.0,
    'start_x': 0,
    'start_y': 0,
    'start_z': 3,
    'end_x': 20,
    'end_y': 0,
    'end_z': 3,
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


def update_curve(curve, start, end):
    coords = [
        (1.0, start),
        (250.0, end),
        ]
    for i, coord in enumerate(coords):
        p = curve.keyframe_points[i]
        p.co = coord
        p.handle_left.y = coord[1]
        p.handle_right.y = coord[1]


# Modify the Location of the Wand
wand_object = bpy.data.objects["Wand"]
wand_object.location = (params["start_x"], params["start_y"], params["start_z"])

# Modify the Start and End keyframes
action = bpy.data.actions["CubeAction"]
update_curve(action.fcurves[0], params["start_x"], params["end_x"])
update_curve(action.fcurves[1], params["start_y"], params["end_y"])
update_curve(action.fcurves[2], params["start_z"], params["end_z"])

# Change the material settings (color, alpha, etc...)
material_object = bpy.data.materials["Material"]
mat_emission = material_object.node_tree.nodes["Emission"]
mat_emission.inputs[0].default_value = params["diffuse_color"]
mat_emission.inputs[1].default_value = params["strength"]
material_object.diffuse_color = params["diffuse_color"]

# Change size of particle
sval = params["particle_scale"]
bpy.data.objects["Sphere"].scale = (sval, sval, sval)

# Change glare type
bpy.data.scenes["Scene"].node_tree.nodes["Glare"].glare_type = params["glare_type"]

# Change particle settings
psettings = bpy.data.particles["ParticleSettings"]
psettings.count = params["particles_count"]
psettings.lifetime = params["particles_lifetime"]
psettings.effector_weights.gravity = params["particles_gravity"]
psettings.object_align_factor = (
    params["velocity_x"], params["velocity_y"], params["velocity_z"])

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
render.film_transparent = params["alpha_mode"]
render.resolution_x = params["resolution_x"]
render.resolution_y = params["resolution_y"]
render.resolution_percentage = params["resolution_percentage"]

bpy.data.worlds["World"].color = params["horizon_color"]

# Clear particle cache before remapping
bpy.ops.ptcache.free_bake_all()

# Animation Speed (use Blender's time remapping to slow or speed up animation)
length_multiplier = int(params["length_multiplier"])  # time remapping multiplier
new_length = int(params["end_frame"]) * length_multiplier  # new length (in frames)
render.frame_map_old = 1
render.frame_map_new = length_multiplier

# Set render length/position
bpy.context.scene.frame_start = params["start_frame"]
bpy.context.scene.frame_end = new_length

if "preview_frame" not in params:
    bpy.ops.ptcache.bake_all()
