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
from bpy.props import *
from math import pi


# Load a font
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
# the stuff
#  
#  name: createDissolveText
#  @param
#  @return
#  
def createDissolveText(title,extrude,bevel_depth,spacemode,textsize,width,font):
	""" Create aned animate the exploding texte """

	newText = title
	#create text
	bpy.ops.object.text_add(view_align=False, enter_editmode=False,location=(0, 0, 0), rotation=(0, 0, 0))
	ActiveObjectText = bpy.context.scene.objects.active

	newtext = bpy.context.scene.objects.active
	#erasing previous objects
	if bpy.context.scene.objects.active.name != 'Text':
		bpy.ops.object.select_all(action='DESELECT')
		#selecting and erasing Text
		bpy.context.scene.objects.active  = bpy.data.objects['Text']
		bpy.context.scene.objects.active.select = True
		bpy.ops.object.delete(use_global=False)
		bpy.ops.object.select_all(action='DESELECT')
		
		#need to delete other objects
		bpy.ops.object.select_all(action='DESELECT')
		#selecting and erasing Turbulence field
		bpy.context.scene.objects.active  = bpy.data.objects['TurbulenceField']
		bpy.context.scene.objects.active.select = True
		bpy.ops.object.delete(use_global=False)

		bpy.ops.object.select_all(action='DESELECT')
		#selecting and erasing Plane
		bpy.context.scene.objects.active  = bpy.data.objects['Plane']
		bpy.context.scene.objects.active.select = True
		bpy.ops.object.delete(use_global=False)

		bpy.ops.object.select_all(action='DESELECT')
		#selecting and erasing WindField
		bpy.context.scene.objects.active  = bpy.data.objects['WindField']
		bpy.context.scene.objects.active.select = True
		bpy.ops.object.delete(use_global=False)

		#selecting newText
		bpy.context.scene.objects.active  = newtext
		bpy.context.scene.objects.active.select = True
		
	#naming/renaming the text
	bpy.context.scene.objects.active.name = 'Text';
	bpy.context.scene.objects.active = bpy.data.objects['Text']
	
	#placing text in position
	ActiveObjectText.rotation_euler[0]=pi/2 #xaxis
	ActiveObjectText.rotation_euler[1]=0.0  #yaxis
	ActiveObjectText.rotation_euler[2]=0.0  #zaxis
	ActiveObjectText.location[0]=0
	ActiveObjectText.location[1]=0
	ActiveObjectText.location[2]=0 
	#changing text
	ActiveObjectText.data.body = title
	
	#text size 
	ActiveObjectText.data.size = textsize
	ActiveObjectText.data.space_character = width
	ActiveObjectText.data.font = font
	#centering text
	#ActiveObjectText.data.align_x='CENTER'
	ActiveObjectText.data.align_x=spacemode
	#extrude text
	ActiveObjectText.data.extrude=extrude #0.04

	#bevel text
	ActiveObjectText.data.bevel_depth = bevel_depth #0.005
	ActiveObjectText.data.bevel_resolution = 5
	#adjust text position
	ActiveObjectText.location.z= -ActiveObjectText.dimensions[1]/3
	
	#convert to mesh to apply effect
	bpy.ops.object.convert(target='MESH', keep_original=False)
	
	#affect dissolve material
	ActiveObjectText.data.materials.append(bpy.data.materials['DissolveMaterial'])
	ActiveObjectText = bpy.context.scene.objects.active
	
	#Don't forget to deselect before select!
	bpy.ops.object.select_all(action='DESELECT')
	
	#selecting Text
	bpy.context.scene.objects.active  = ActiveObjectText
	bpy.context.scene.objects.active.select = True
	
	#add remesh modifier to text
	bpy.ops.object.modifier_add(type='REMESH')
	#modifying parameters
	ActiveObjectText.modifiers['Remesh'].octree_depth = 9 #10 best quality but vertices number too high
	ActiveObjectText.modifiers['Remesh'].scale=0.99
	ActiveObjectText.modifiers['Remesh'].mode='SMOOTH'
	ActiveObjectText.modifiers['Remesh'].use_remove_disconnected=False
	#apply this mofifier
	bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Remesh")
	
	#Nb quads for particle system be careful of API version
	if bpy.app.version[1] < 62 :
		NbQuads = len(ActiveObjectText.data.faces)
	if bpy.app.version[1] == 62 :
		if bpy.app.version[2] >= 2 :
			NbQuads = len(ActiveObjectText.data.polygons.values()) #API 2.62.2 and up
		else:
			NbQuads = len(ActiveObjectText.data.faces)
	if bpy.app.version[1] > 62 :
			NbQuads = len(ActiveObjectText.data.polygons.values()) #API 2.63 and up

	#Add Particle System
	bpy.ops.object.particle_system_add()
	#Particle parameters
	ActiveObjectText.particle_systems['ParticleSystem'].settings.count = NbQuads
	ActiveObjectText.particle_systems['ParticleSystem'].settings.frame_start = 10
	ActiveObjectText.particle_systems['ParticleSystem'].settings.frame_end = 60
	ActiveObjectText.particle_systems['ParticleSystem'].settings.lifetime = 80
	ActiveObjectText.particle_systems['ParticleSystem'].point_cache.frame_step = 1
	ActiveObjectText.particle_systems['ParticleSystem'].settings.normal_factor = 0.0
	#not useful
	ActiveObjectText.particle_systems['ParticleSystem'].settings.use_dynamic_rotation = True
	ActiveObjectText.particle_systems['ParticleSystem'].settings.render_type='NONE'
	ActiveObjectText.particle_systems['ParticleSystem'].settings.draw_method='DOT'
	ActiveObjectText.particle_systems['ParticleSystem'].settings.effector_weights.gravity = 0
	ActiveObjectText.particle_systems['ParticleSystem'].settings.use_adaptive_subframes = True
	ActiveObjectText.particle_systems['ParticleSystem'].settings.courant_target = 0.2

	bpy.ops.object.select_all(action='DESELECT')

	#Adding Wind force field on center and rotate it -90 on Y
	bpy.ops.object.effector_add(type='WIND', view_align=False, enter_editmode=False, location=(0, 0, 0), rotation=(0, -pi/2, 0), layers=(True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False))
	ActiveObjectWindField = bpy.context.scene.objects.active
	ActiveObjectWindField.name = 'WindField'
	#settings
	ActiveObjectWindField.field.strength = 1.0
	ActiveObjectWindField.field.flow = 1.0
	ActiveObjectWindField.field.noise = 0.0
	ActiveObjectWindField.field.seed = 27
	ActiveObjectWindField.field.apply_to_location = True
	ActiveObjectWindField.field.apply_to_rotation = True
	ActiveObjectWindField.field.use_absorption = False

	#Adding Turbulence Force Field
	bpy.ops.object.effector_add(type='TURBULENCE', view_align=False, enter_editmode=False, location=(0, 0, 0), rotation=(0, 0, 0), layers=(True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False))
	ActiveObjectTurbulenceField = bpy.context.scene.objects.active
	ActiveObjectTurbulenceField.name = 'TurbulenceField'
	#settings
	ActiveObjectTurbulenceField.field.strength = 15
	ActiveObjectTurbulenceField.field.size = 0.75
	ActiveObjectTurbulenceField.field.flow = 0.5
	ActiveObjectTurbulenceField.field.seed = 23
	ActiveObjectTurbulenceField.field.apply_to_location = True
	ActiveObjectTurbulenceField.field.apply_to_rotation = True
	ActiveObjectTurbulenceField.field.use_absorption = False


	#Don't forget to deselect before select!
	bpy.ops.object.select_all(action='DESELECT')

	#selecting Text
	bpy.context.scene.objects.active  = ActiveObjectText
	bpy.context.scene.objects.active.select = True

	#adding wipe texture to text

	sTex = bpy.data.textures.new('Wipe', type = 'BLEND')
	sTex.use_color_ramp = True

	TexSlot=ActiveObjectText.particle_systems['ParticleSystem'].settings.texture_slots.add()
	TexSlot.texture = sTex

	bpy.ops.object.select_all(action='DESELECT')

	#Create plane for controlling action of particle system (based on time)
	#if text is created on the fly 'Wipe' texture does not work! don't know really why!
	# so use of an existing plane, and resize it to the text x dimension
	bpy.ops.mesh.primitive_plane_add(view_align=False, enter_editmode=False, location=(0, 0, 0), rotation=(pi/2, 0, 0), layers=(True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False))
	ActiveObjectPlane = bpy.context.scene.objects.active
	ActiveObjectPlane.name = 'Plane'
	#Change dimensions
	ActiveObjectPlane.dimensions = ((ActiveObjectText.dimensions[0]*1.2),(ActiveObjectText.dimensions[1]*1.2),0)
	#hide plane for render
	ActiveObjectPlane.hide_render = True
	#show as wire in 3D
	ActiveObjectPlane.draw_type = 'WIRE'

	bpy.ops.object.select_all(action='DESELECT')

	#selecting Text
	bpy.context.scene.objects.active  = ActiveObjectText
	bpy.context.scene.objects.active.select = True

	TexSlot.texture_coords = 'OBJECT'
	TexSlot.object = ActiveObjectPlane
	TexSlot.use_map_time = True


	ActiveObjectText.data.update()

	bpy.ops.object.modifier_add(type='EXPLODE')
	bpy.ops.mesh.uv_texture_add() #name UVMap by default
	ActiveObjectText.data.materials['DissolveMaterial'].texture_slots['Texture'].texture_coords = 'UV'
	ActiveObjectText.data.materials['DissolveMaterial'].texture_slots['Texture'].uv_layer = 'UVMap'
	ActiveObjectText.data.materials['DissolveMaterial'].texture_slots['Texture'].use_map_alpha = True
	ActiveObjectText.data.materials['DissolveMaterial'].texture_slots['Texture'].alpha_factor = 1.0

	ActiveObjectText.modifiers['Explode'].particle_uv = 'UVMap'
	ActiveObjectText.data.update()


	#Don't forget to deselect before select!
	bpy.ops.object.select_all(action='DESELECT')

	#selecting Text
	bpy.context.scene.objects.active  = ActiveObjectText
	bpy.context.scene.objects.active.select = True
	TexSlot.texture_coords = 'OBJECT'
	TexSlot.object = ActiveObjectPlane

	TexSlot.use_map_time = False
	TexSlot.use_map_time = True

	ActiveObjectText.data.update()


# Debug Info:
# ./blender -b test.blend -P demo.py
# -b = background mode
# -P = run a Python script within the context of the project file

# Init all of the variables needed by this script.  Because Blender executes
# this script, OpenShot will inject a dictionary of the required parameters
# before this script is executed.
params = {		
			'title' : 'Oh Yeah! OpenShot!',
			'extrude' : 0.05,
			'bevel_depth' : 0.01,
			'spacemode' : 'CENTER',
			'text_size' : 1,
			'width' : 1.0,
			'fontname' : 'Bfont',
			
			'color' : [0.8,0.8,0.8],
			'alpha' : 1.0,
			
			'output_path' : '/tmp/',
			'fps' : 24,
			'quality' : 90,
			'file_format' : 'PNG',
			'color_mode' : 'RGBA',
			'horizon_color' : [0, 0, 0],
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

# Modify Text / Curve settings
#print (bpy.data.curves.keys())


#text_object = bpy.data.curves["txtName1"]
#text_object.extrude = params["extrude"]
#text_object.bevel_depth = params["bevel_depth"]
#text_object.body = params["title"]
#text_object.align = params["spacemode"]
#text_object.size = params["text_size"]
#text_object.space_character = params["width"]

# Get font object
font = None
if params["fontname"] != "Bfont":
	# Add font so it's available to Blender
	font = load_font(params["fontname"])
else:
	# Get default font
	font = bpy.data.fonts["Bfont"]

createDissolveText(params["title"],params["extrude"],params["bevel_depth"],params["spacemode"],params["text_size"],params["width"], font)

# Change the material settings (color, alpha, etc...)
material_object = bpy.data.materials["DissolveMaterial"]
material_object.diffuse_color = params["diffuse_color"]
material_object.specular_color = params["specular_color"]
material_object.specular_intensity = params["specular_intensity"]
#don't modify alpha!!!!!
#material_object.alpha = params["alpha"]



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
