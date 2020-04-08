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
from math import pi


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


def createExplodeTxt(title, particle_number, extrude, bevel_depth, spacemode,
                     textsize, width, font, ground, frame_count):
    """ Create aned animate the exploding texte """

    newText = title
    # create text
    bpy.ops.object.text_add(
        radius=1.0, enter_editmode=False, align='WORLD',
        location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0)
    )
    newtext = bpy.context.view_layer.objects.active

    # modifying the text
    newtext.data.size = textsize
    newtext.data.space_character = width
    newtext.data.font = font

    # centering text
    newtext.data.align_x = spacemode

    # extrude text
    newtext.data.extrude = extrude

    # bevel text
    newtext.data.bevel_depth = bevel_depth
    newtext.data.bevel_resolution = 10

    # rotating text
    # angles are in radians
    # bpy.ops.transform.rotate(value=(pi/2,), axis=(1.0, 0.0, 0.0), constraint_axis=(False, False, False),
    # constraint_orientation='GLOBAL', mirror=False, proportional='DISABLED', proportional_edit_falloff='SMOOTH',
    # proportional_size=1, snap=False, snap_target='CLOSEST', snap_point=(0, 0, 0), snap_align=False,
    # snap_normal=(0, 0, 0), release_confirm=False)

    # second solution
    newtext.rotation_euler[0] = pi / 2  # xaxis
    newtext.rotation_euler[1] = 0.0  # yaxis
    newtext.rotation_euler[2] = 0.0  # zaxis

    # changing text
    bpy.ops.object.editmode_toggle()
    for x in range(20):
        bpy.ops.font.delete()
    bpy.ops.font.text_insert(text=newText, accent=False)
    bpy.ops.object.editmode_toggle()

    # convert to mesh to apply effect
    bpy.ops.object.convert(target='MESH', keep_original=False)

    # solidify
    bpy.ops.object.modifier_add(type='SOLIDIFY')

    # apply quick explode
    bpy.ops.object.quick_explode(
        style='EXPLODE', amount=100, frame_duration=50,
        frame_start=1, frame_end=51, velocity=1, fade=True
    )

    # modifying Particle System
    # emitfrom
    newtext.particle_systems[0].settings.emit_from = 'VERT'
    # particle number
    newtext.particle_systems[0].settings.count = particle_number
    # particle lifetime
    newtext.particle_systems[0].settings.lifetime = 200  # 200 + 48 > 150
    # start/end explosion
    newtext.particle_systems[0].settings.frame_end = 48
    newtext.particle_systems[0].settings.frame_start = 48
    # explosion power
    newtext.particle_systems[0].settings.normal_factor = 5.5
    # integration method
    # aa'MIDPOINT' #'RK4'
    newtext.particle_systems[0].settings.integrator = 'RK4'
    # size of particles
    newtext.particle_systems[0].settings.particle_size = 0.1
    # particles time step
    newtext.particle_systems[0].settings.timestep = 0.02
    # mass of particles
    newtext.particle_systems[0].settings.mass = 2.0
    newtext.particle_systems[0].settings.use_multiply_size_mass = True

    # affect an existing material
    newtext.material_slots[0].material = bpy.data.materials['TextMaterial']

    # solidify parameter
    newtext.modifiers['Solidify'].edge_crease_inner = 0.01
    newtext.modifiers['Solidify'].thickness = 0.02
    # ground management
    newtext.particle_systems[0].point_cache.frame_step = 1
    if ground == '1':
        bpy.ops.object.select_all(action='DESELECT')
        # selecting Text
        bpy.context.view_layer.objects.active = bpy.data.objects['Ground']
        if bpy.data.objects['Ground'].modifiers.keys()[0] != 'Collision':
            bpy.ops.object.modifier_add(type="COLLISION")
        bpy.data.objects['Ground'].hide_render = False

    else:
        bpy.ops.object.select_all(action='DESELECT')
        # selecting Text
        bpy.context.view_layer.objects.active = bpy.data.objects['Ground']
        bpy.ops.object.modifier_remove(modifier="Collision")
        bpy.data.objects['Ground'].hide_render = True

# Debug Info:
# ./blender -b test.blend -P demo.py
# -b = background mode
# -P = run a Python script within the context of the project file


# Init all of the variables needed by this script.  Because Blender executes
# this script, OpenShot will inject a dictionary of the required parameters
# before this script is executed.
params = {
    'title': 'Oh Yeah! OpenShot!',
    'particle_number': 100,
    'ground_on_off': 1,
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

# Modify Text / Curve settings
# print (bpy.data.curves.keys())

# Get font object
font = None
if params["fontname"] != "Bfont":
    # Add font so it's available to Blender
    font = load_font(params["fontname"])
else:
    # Get default font
    font = bpy.data.fonts["Bfont"]

# Compute animation length
length_multiplier = int(params["length_multiplier"])  # time remapping multiplier
frame_count = int(params["end_frame"]) * length_multiplier  # new length (in frames)

createExplodeTxt(
    params["title"], params["particle_number"], params["extrude"],
    params["bevel_depth"], params["spacemode"], params["text_size"],
    params["width"], font, params["ground_on_off"], frame_count
)

# Change the material settings (color, alpha, etc...)
material_object = bpy.data.materials["TextMaterial"]
material_object.diffuse_color = params["diffuse_color"]
material_object.specular_color = params["specular_color"]
material_object.specular_intensity = params["specular_intensity"]


# Set the render options.  It is important that these are set
# to the same values as the current OpenShot project.  These
# params are automatically set by OpenShot
bpy.context.scene.render.filepath = params["output_path"]
bpy.context.scene.render.fps = params["fps"]
if "fps_base" in params:
    bpy.context.scene.render.fps_base = params["fps_base"]
bpy.context.scene.render.image_settings.file_format = params["file_format"]
bpy.context.scene.render.image_settings.color_mode = params["color_mode"]
bpy.context.scene.render.film_transparent = params["alpha_mode"]
bpy.data.worlds[0].color = params["horizon_color"]
bpy.context.scene.render.resolution_x = params["resolution_x"]
bpy.context.scene.render.resolution_y = params["resolution_y"]
bpy.context.scene.render.resolution_percentage = params["resolution_percentage"]

bpy.ops.ptcache.free_bake_all()   # erase baked dynamics

# Animation Speed (use Blender's time remapping to slow or speed up animation)
length_multiplier = int(params["length_multiplier"])  # time remapping multiplier
new_length = int(params["end_frame"]) * length_multiplier  # new length (in frames)
bpy.context.scene.render.frame_map_old = 1
bpy.context.scene.render.frame_map_new = length_multiplier

# Set render length/position
bpy.context.scene.frame_start = params["start_frame"]
bpy.context.scene.frame_end = new_length

if "preview_frame" not in params:
    # bake dynamics : take time but needed before rendering animation
    bpy.ops.ptcache.bake_all()
