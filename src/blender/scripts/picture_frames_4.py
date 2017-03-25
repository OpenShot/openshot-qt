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

def get_scale_values(height, width):
	""" Calculate the correct scale parameters to display an image with the 
	correct height / width ratio in Blender. """
	
	height_ratio = 1.0
	width_ratio = float(width) / float(height)
	
	return (height_ratio, width_ratio)
	

#INJECT_PARAMS_HERE

# The remainder of this script will modify the current Blender .blend project
# file, and adjust the settings.  The .blend file is specified in the XML file
# that defines this template in OpenShot.
#----------------------------------------------------------------------------

# Split the picture information
picture1 = params["project_files1"].split("|")
if len(picture1) > 1:
	picture1_scale = get_scale_values(picture1[1], picture1[2])

picture2 = params["project_files2"].split("|")
if len(picture2) > 1:
	picture2_scale = get_scale_values(picture2[1], picture2[2])

picture3 = params["project_files3"].split("|")
if len(picture3) > 1:
	picture3_scale = get_scale_values(picture3[1], picture3[2])

picture4 = params["project_files4"].split("|")
if len(picture4) > 1:
	picture4_scale = get_scale_values(picture4[1], picture4[2])

# Modify picture paths
if len(picture1) > 1:
	bpy.data.objects["Plane.001"].scale.y = picture1_scale[0]
	bpy.data.objects["Plane.001"].scale.x = picture1_scale[1]
	
	if picture1[3] == "image":
		bpy.data.textures["Texture.002"].image.source = 'FILE'
		bpy.data.textures["Texture.002"].image.filepath = picture1[0]
	else:
		bpy.data.textures["Texture.002"].image.source = 'MOVIE'
		bpy.data.textures["Texture.002"].image.filepath = picture1[0]
		bpy.data.textures["Texture.002"].image_user.use_cyclic = True
		bpy.data.textures["Texture.002"].image_user.frame_duration = 230.0

if len(picture2) > 1:
	bpy.data.objects["Plane.002"].scale.y = picture2_scale[0]
	bpy.data.objects["Plane.002"].scale.x = picture2_scale[1]
	
	if picture2[3] == "image":
		bpy.data.textures["Texture.003"].image.source = 'FILE'
		bpy.data.textures["Texture.003"].image.filepath = picture2[0]
	else:
		bpy.data.textures["Texture.003"].image.source = 'MOVIE'
		bpy.data.textures["Texture.003"].image.filepath = picture2[0]
		bpy.data.textures["Texture.003"].image_user.use_cyclic = True
		bpy.data.textures["Texture.003"].image_user.frame_duration = 230.0


if len(picture3) > 1:
	bpy.data.objects["Plane.003"].scale.y = picture3_scale[0]
	bpy.data.objects["Plane.003"].scale.x = picture3_scale[1]
	
	if picture3[3] == "image":
		bpy.data.textures["Texture.004"].image.source = 'FILE'
		bpy.data.textures["Texture.004"].image.filepath = picture3[0]
	else:
		bpy.data.textures["Texture.004"].image.source = 'MOVIE'
		bpy.data.textures["Texture.004"].image.filepath = picture3[0]
		bpy.data.textures["Texture.004"].image_user.use_cyclic = True
		bpy.data.textures["Texture.004"].image_user.frame_duration = 230.0

if len(picture4) > 1:
	bpy.data.objects["Plane.004"].scale.y = picture4_scale[0]
	bpy.data.objects["Plane.004"].scale.x = picture4_scale[1]
	
	if picture4[3] == "image":
		bpy.data.textures["Texture.005"].image.source = 'FILE'
		bpy.data.textures["Texture.005"].image.filepath = picture4[0]
	else:
		bpy.data.textures["Texture.005"].image.source = 'MOVIE'
		bpy.data.textures["Texture.005"].image.filepath = picture4[0]
		bpy.data.textures["Texture.005"].image_user.use_cyclic = True
		bpy.data.textures["Texture.005"].image_user.frame_duration = 230.0



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
bpy.context.scene.render.alpha_mode = params["alpha_mode"]
bpy.data.worlds[0].horizon_color = params["horizon_color"]
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

