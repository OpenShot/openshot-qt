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
def createExplodeTxt(title,particle_number,extrude,bevel_depth,spacemode,textsize,width,font,ground):
	""" Create aned animate the exploding texte """

	newText = title
	#create text
	bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=(0, 0, 0), rotation=(0, 0, 0))
	
	newtext = bpy.context.scene.objects.active

	if bpy.context.scene.objects.active.name != 'Text':
		bpy.ops.object.select_all(action='DESELECT')
		#selecting Text
		bpy.context.scene.objects.active  = bpy.data.objects['Text']
		bpy.context.scene.objects.active.select = True
		bpy.ops.object.delete(use_global=False)
		bpy.ops.object.select_all(action='DESELECT')
		#selecting Text
		bpy.context.scene.objects.active  = newtext
		bpy.context.scene.objects.active.select = True
		
	#naming the text
	bpy.context.scene.objects.active.name = 'Text';
	
	bpy.context.scene.objects.active = bpy.data.objects['Text']
	
	#modifying the text
	bpy.context.scene.objects.active.data.size = textsize
	bpy.context.scene.objects.active.data.space_character = width
	bpy.context.scene.objects.active.data.font = font
	#centering text
	#bpy.data.objects['Text'].data.align='CENTER'
	bpy.data.objects['Text'].data.align=spacemode

	#extrude text
	#bpy.data.objects['Text'].data.extrude=0.1
	bpy.data.objects['Text'].data.extrude=extrude

	#bevel text
	#bpy.data.objects['Text'].data.bevel_depth = 0.01
	bpy.data.objects['Text'].data.bevel_depth = bevel_depth
	bpy.data.objects['Text'].data.bevel_resolution = 10

	#rotating text
	#angles are in radians
	#bpy.ops.transform.rotate(value=(pi/2,), axis=(1.0, 0.0, 0.0), constraint_axis=(False, False, False), constraint_orientation='GLOBAL', mirror=False, proportional='DISABLED', proportional_edit_falloff='SMOOTH', proportional_size=1, snap=False, snap_target='CLOSEST', snap_point=(0, 0, 0), snap_align=False, snap_normal=(0, 0, 0), release_confirm=False)
	#second solution
	bpy.data.objects['Text'].rotation_euler[0]=pi/2 #xaxis
	bpy.data.objects['Text'].rotation_euler[1]=0.0  #yaxis
	bpy.data.objects['Text'].rotation_euler[2]=0.0  #zaxis

	#changing text
	#bpy.data.curves['Text'].body = 'Hello World' #not working
	bpy.context.scene.objects.active=bpy.data.objects['Text']
	bpy.ops.object.editmode_toggle()
	bpy.ops.font.delete()
	bpy.ops.font.text_insert(text=newText, accent=False)
	bpy.ops.object.editmode_toggle()
	
	#convert to mesh to apply effect
	bpy.ops.object.convert(target='MESH', keep_original=False)

	#solidify 
	bpy.ops.object.modifier_add(type='SOLIDIFY')

	#apply quick explode
	bpy.ops.object.quick_explode(style='EXPLODE', amount=100, frame_duration=50, frame_start=1, frame_end=51, velocity=1, fade=True)

	#modifying Particle System
	#emitfrom
	bpy.data.objects['Text'].particle_systems['ParticleSystem'].settings.emit_from = 'VERT'
	#particle number
	#bpy.data.objects['Text'].particle_systems['ParticleSystem'].settings.count=200
	bpy.data.objects['Text'].particle_systems['ParticleSystem'].settings.count=particle_number
	#particle lifetime
	bpy.data.objects['Text'].particle_systems['ParticleSystem'].settings.lifetime=200 # 200 +48 > 150 ;-)z
	# start/end explosion
	bpy.data.objects['Text'].particle_systems['ParticleSystem'].settings.frame_end = 48
	bpy.data.objects['Text'].particle_systems['ParticleSystem'].settings.frame_start = 48
	#explosion power
	bpy.data.objects['Text'].particle_systems['ParticleSystem'].settings.normal_factor=5.5
	#integration method
	bpy.data.objects['Text'].particle_systems['ParticleSystem'].settings.integrator='RK4'#aa'MIDPOINT' #'RK4'
	#size of particles
	bpy.data.objects['Text'].particle_systems['ParticleSystem'].settings.particle_size = 0.1
	#particles time step
	bpy.data.objects['Text'].particle_systems['ParticleSystem'].settings.timestep = 0.02
	#mass of particles
	bpy.data.objects['Text'].particle_systems['ParticleSystem'].settings.mass = 2.0
	bpy.data.objects['Text'].particle_systems['ParticleSystem'].settings.use_multiply_size_mass = True
	
	#affect an existing material
	bpy.data.objects['Text'].material_slots[0].material = bpy.data.materials['TextMaterial']
	
	#solidifiy parameter
	bpy.data.objects['Text'].modifiers['Solidify'].edge_crease_inner=0.01
	bpy.data.objects['Text'].modifiers['Solidify'].thickness = 0.02
	#ground management
	bpy.data.objects['Text'].particle_systems['ParticleSystem'].point_cache.frame_step = 1
	if ground=='1':
		bpy.ops.object.select_all(action='DESELECT')
		#selecting Text
		bpy.context.scene.objects.active  = bpy.data.objects['Ground']
		bpy.context.scene.objects.active.select = True
		if bpy.data.objects['Ground'].modifiers.keys()[0] != 'Collision':
			bpy.ops.object.modifier_add(type="COLLISION")
		#else:
		#	print("OK")
		  
		bpy.data.objects['Ground'].hide_render = False
		
	else:
		bpy.ops.object.select_all(action='DESELECT')
		#selecting Text
		bpy.context.scene.objects.active  = bpy.data.objects['Ground']
		bpy.context.scene.objects.active.select = True
		bpy.ops.object.modifier_remove(modifier="Collision")
		bpy.data.objects['Ground'].hide_render = True
	    
	bpy.ops.ptcache.free_bake_all()   # erase baked dynamics
	bpy.ops.ptcache.bake_all() # bake dynamics : take time but needed before rendering animation
	
	
# Debug Info:
# ./blender -b test.blend -P demo.py
# -b = background mode
# -P = run a Python script within the context of the project file

# Init all of the variables needed by this script.  Because Blender executes
# this script, OpenShot will inject a dictionary of the required parameters
# before this script is executed.
params = {		
			'title' : 'Oh Yeah! OpenShot!',
			'particle_number' : 100,
			'ground_on_off' : 1,
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

# set the font
#text_object.font = font

createExplodeTxt(params["title"],params["particle_number"],params["extrude"],params["bevel_depth"],params["spacemode"],params["text_size"],params["width"], font, params["ground_on_off"])

# Change the material settings (color, alpha, etc...)
material_object = bpy.data.materials["TextMaterial"]
material_object.diffuse_color = params["diffuse_color"]
material_object.specular_color = params["specular_color"]
material_object.specular_intensity = params["specular_intensity"]
material_object.alpha = params["alpha"]



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
