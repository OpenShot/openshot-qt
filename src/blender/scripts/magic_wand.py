#	OpenShot Video Editor is a program that creates, modifies, and edits video files.
#   Copyright (C) 2009  Jonathan Thomas
#
#	This file is part of OpenShot Video Editor (http://launchpad.net/openshot/).
#
#	OpenShot Video Editor is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	OpenShot Video Editor is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with OpenShot Video Editor.  If not, see <http://www.gnu.org/licenses/>.


# Import Blender's python API.  This only works when the script is being
# run from the context of Blender.  Blender contains it's own version of Python
# with this library pre-installed.
import bpy

# Debug Info:
# ./blender -b test.blend -P demo.py
# -b = background mode
# -P = run a Python script within the context of the project file

# Init all of the variables needed by this script.  Because Blender executes
# this script, OpenShot will inject a dictionary of the required parameters
# before this script is executed.
params = {		
			'title' : 'Oh Yeah! OpenShot!',
			'extrude' : 0.1,
			'bevel_depth' : 0.02,
			'spacemode' : 'CENTER',
			'text_size' : 1.5,
			'width' : 1.0,
			'fontname' : 'Bfont',
			
			'color' : [0.8,0.8,0.8],
			'alpha' : 1.0,
			
			'output_path' : '/tmp/',
			'fps' : 24,
			'quality' : 90,
			'file_format' : 'PNG',
			'color_mode' : 'RGBA',
			'horizon_color' : [0.57, 0.57, 0.57],
			'resolution_x' : 1920,
			'resolution_y' : 1080,
			'resolution_percentage' : 100,
			'start_frame' : 20,
			'end_frame' : 25,
			'animation' : True,
		}

#INJECT_PARAMS_HERE

# The remainder of this script will modify the current Blender .blend project
# file, and adjust the settings.  The .blend file is specified in the XML file
# that defines this template in OpenShot.
#----------------------------------------------------------------------------

# Modify the Location of the Wand
wand_object = bpy.data.objects["Wand"]
wand_object.location = [params["start_x"], params["start_y"], params["start_z"]]

# Modify the Start and End keyframes
bpy.data.actions["CubeAction"].fcurves[0].keyframe_points[0].co = (1.0, params["start_x"])
bpy.data.actions["CubeAction"].fcurves[0].keyframe_points[0].handle_left.y = params["start_x"]
bpy.data.actions["CubeAction"].fcurves[0].keyframe_points[0].handle_right.y = params["start_x"]

bpy.data.actions["CubeAction"].fcurves[1].keyframe_points[0].co = (1.0, params["start_y"])
bpy.data.actions["CubeAction"].fcurves[1].keyframe_points[0].handle_left.y = params["start_y"]
bpy.data.actions["CubeAction"].fcurves[1].keyframe_points[0].handle_right.y = params["start_y"]

bpy.data.actions["CubeAction"].fcurves[2].keyframe_points[0].co = (1.0, params["start_z"])
bpy.data.actions["CubeAction"].fcurves[2].keyframe_points[0].handle_left.y = params["start_z"]
bpy.data.actions["CubeAction"].fcurves[2].keyframe_points[0].handle_right.y = params["start_z"]
#################
bpy.data.actions["CubeAction"].fcurves[0].keyframe_points[1].co = (250.0, params["end_x"])
bpy.data.actions["CubeAction"].fcurves[0].keyframe_points[1].handle_left.y = params["end_x"]
bpy.data.actions["CubeAction"].fcurves[0].keyframe_points[1].handle_right.y = params["end_x"]

bpy.data.actions["CubeAction"].fcurves[1].keyframe_points[1].co = (250.0, params["end_y"])
bpy.data.actions["CubeAction"].fcurves[1].keyframe_points[1].handle_left.y = params["end_y"]
bpy.data.actions["CubeAction"].fcurves[1].keyframe_points[1].handle_right.y = params["end_y"]

bpy.data.actions["CubeAction"].fcurves[2].keyframe_points[1].co = (250.0, params["end_z"])
bpy.data.actions["CubeAction"].fcurves[2].keyframe_points[1].handle_left.y = params["end_z"]
bpy.data.actions["CubeAction"].fcurves[2].keyframe_points[1].handle_right.y = params["end_z"]

# Change the material settings (color, alpha, etc...)
material_object = bpy.data.materials["Material"]
material_object.diffuse_color = params["diffuse_color"]
material_object.specular_color = params["specular_color"]
material_object.mirror_color = params["mirror_color"]
material_object.specular_intensity = params["specular_intensity"]


# Change Halo settings
material_object.halo.size = params["halo_size"]
material_object.halo.hardness = params["halo_hardness"]
if params["halo_use_lines"] == "Yes":
	material_object.halo.use_lines = True
else:
	material_object.halo.use_lines = False
material_object.halo.line_count = params["halo_line_count"]
if params["halo_use_ring"] == "Yes":
	material_object.halo.use_ring = True
else:
	material_object.halo.use_ring = False
material_object.halo.ring_count = params["halo_ring_count"]
if params["halo_use_star"] == "Yes":
	material_object.halo.use_star = True
else:
	material_object.halo.use_star = False 
material_object.halo.star_tip_count = params["halo_star_tip_count"]
if params["halo_use_flare_mode"] == "Yes":
	material_object.halo.use_flare_mode = True
else:
	material_object.halo.use_flare_mode = False

# Change particle settings
particle_object = bpy.data.particles[0]
particle_object.count = params["particles_count"]
particle_object.lifetime = params["particles_lifetime"]
particle_object.effector_weights.gravity = params["particles_gravity"]
particle_object.object_align_factor = (params["velocity_x"], params["velocity_y"], params["velocity_z"])

# Set the render options.  It is important that these are set
# to the same values as the current OpenShot project.  These
# params are automatically set by OpenShot
bpy.context.scene.render.filepath = params["output_path"]
bpy.context.scene.render.fps = params["fps"]
#bpy.context.scene.render.quality = params["quality"]
try:
	bpy.context.scene.render.file_format = params["file_format"]
	bpy.context.scene.render.color_mode = params["color_mode"]
except:
	bpy.context.scene.render.image_settings.file_format = params["file_format"]
	bpy.context.scene.render.image_settings.color_mode = params["color_mode"]
bpy.context.scene.render.film_transparent = params["alpha_mode"]
bpy.data.worlds[0].color = params["horizon_color"]
bpy.context.scene.render.resolution_x = params["resolution_x"]
bpy.context.scene.render.resolution_y = params["resolution_y"]
bpy.context.scene.render.resolution_percentage = params["resolution_percentage"]
bpy.context.scene.frame_start = params["start_frame"]
bpy.context.scene.frame_end = params["end_frame"]

# Animation Speed (use Blender's time remapping to slow or speed up animation)
animation_speed = int(params["animation_speed"])	# time remapping multiplier
new_length = int(params["end_frame"]) * animation_speed	# new length (in frames)
bpy.context.scene.frame_end = new_length
bpy.context.scene.render.frame_map_old = 1
bpy.context.scene.render.frame_map_new = animation_speed
if params["start_frame"] == params["end_frame"]:
	bpy.context.scene.frame_start = params["end_frame"]
	bpy.context.scene.frame_end = params["end_frame"]

# Render the current animation to the params["output_path"] folder
bpy.ops.render.render(animation=params["animation"])

