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
# run from the context of Blender.  Blender contains its own version of Python
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

def deselect():
    bpy.ops.object.select_all(action='DESELECT')

def select(obj):
    deselect()
    bpy.context.view_layer.objects.active = obj

def acquireAndName(name):
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    return obj

def createDissolveText(title, extrude, bevel_depth, spacemode, textsize, width, font):
    """ Create aned animate the exploding texte """

    # create text
    bpy.ops.object.text_add(
        radius=1.0,
        enter_editmode=False, align='WORLD',
        location=(0.0, 0.0, 0.0),
        rotation=(pi / 2, 0.0, 0.0),
    )
    Text = acquireAndName('Text')

    Text.data.body = title

    # text size
    Text.data.size = textsize
    Text.data.space_character = width
    Text.data.font = font
    # centering text
    Text.data.align_x = spacemode
    # extrude text
    Text.data.extrude = extrude

    # bevel text
    Text.data.bevel_depth = bevel_depth
    Text.data.bevel_resolution = 5
    # adjust text position
    Text.location.z = -Text.dimensions[1] / 3

    # affect dissolve material
    Text.data.materials.append(bpy.data.materials['DissolveMaterial'])

    # convert to mesh to apply effect
    bpy.ops.object.convert(target='MESH', keep_original=False)

    # add remesh modifier to text
    bpy.ops.object.modifier_add(type='REMESH')
    # modifying parameters
    Text.modifiers['Remesh'].octree_depth = 9  # 10 best quality but vertices number too high
    Text.modifiers['Remesh'].scale = 0.99
    Text.modifiers['Remesh'].mode = 'SMOOTH'
    Text.modifiers['Remesh'].use_remove_disconnected = False
    # apply this modifier
    bpy.ops.object.modifier_apply(modifier="Remesh")

    # Nb quads for particle system
    NbQuads = len(Text.data.polygons.values())

    # Add Particle System
    bpy.ops.object.particle_system_add()
    ParticleSystem = Text.particle_systems[0]
    PSSettings = ParticleSystem.settings

    # Particle parameters
    PSSettings.count = NbQuads
    PSSettings.frame_start = 10
    PSSettings.frame_end = 60
    PSSettings.lifetime = 80
    ParticleSystem.point_cache.frame_step = 1
    PSSettings.normal_factor = 0.0
    # not useful
    PSSettings.render_type = 'OBJECT'
    PSSettings.instance_object = bpy.data.objects['Sphere']
    PSSettings.effector_weights.gravity = 0
    PSSettings.use_dynamic_rotation = True
    PSSettings.use_adaptive_subframes = True
    PSSettings.courant_target = 0.2

    # Adding Wind force field on center and rotate it -90 on Y
    bpy.ops.object.effector_add(
        type='WIND', radius=1.0,
        enter_editmode=False, align='WORLD',
        location=(0.0, 0.0, 0.0),
        rotation=(0, -pi / 2, 0),
    )
    WindField = acquireAndName('WindField')

    # settings
    WindField.field.strength = 1.0
    WindField.field.flow = 1.0
    WindField.field.noise = 0.0
    WindField.field.seed = 27
    WindField.field.apply_to_location = True
    WindField.field.apply_to_rotation = True
    WindField.field.use_absorption = False

    # Adding Turbulence Force Field
    bpy.ops.object.effector_add(
        type='TURBULENCE', radius=1.0,
        enter_editmode=False, align='WORLD',
        location=(0.0, 0.0, 0.0),
        rotation=(0, 0, 0),
    )
    TurbulenceField = acquireAndName('TurbulenceField')

    # settings
    TurbulenceField.field.strength = 15
    TurbulenceField.field.size = 0.75
    TurbulenceField.field.flow = 0.5
    TurbulenceField.field.seed = 23
    TurbulenceField.field.apply_to_location = True
    TurbulenceField.field.apply_to_rotation = True
    TurbulenceField.field.use_absorption = False

    select(Text)

    # adding wipe texture to text
    sTex = bpy.data.textures.new('Wipe', type='BLEND')
    sTex.use_color_ramp = True

    TexSlot = PSSettings.texture_slots.add()
    TexSlot.texture = sTex
    TexSlot.use_map_time = True

    deselect()

    # Create plane for controlling action of particle system (based on time)
    # if text is created on the fly 'Wipe' texture does not work! don't know really why!
    # so use of an existing plane, and resize it to the text x dimension
    bpy.ops.mesh.primitive_plane_add(
        size=2.0, calc_uvs=True,
        enter_editmode=False, align='WORLD',
        location=(0.0, 0.0, 0.0),
        rotation=(pi / 2, 0, 0),
    )
    Plane = acquireAndName('Plane')
    # Change dimensions
    Plane.dimensions = (
        (Text.dimensions[0] * 1.2),
        (Text.dimensions[1] * 1.2),
        0)
    # hide plane for render
    Plane.hide_render = True

    select(Text)

    TexSlot.texture_coords = 'OBJECT'
    TexSlot.object = Plane
    TexSlot.use_map_time = True

    Text.data.update()

    bpy.ops.object.modifier_add(type='EXPLODE')
    bpy.ops.mesh.uv_texture_add()  # name UVMap by default
    Text.modifiers['Explode'].particle_uv = 'UVMap'
    Text.modifiers['Explode'].show_dead = False
    Text.data.update()

    select(Text)

    TexSlot.texture_coords = 'OBJECT'
    TexSlot.object = Plane

    TexSlot.use_map_time = False
    TexSlot.use_map_time = True

    Text.data.update()


# Debug Info:
# ./blender -b test.blend -P demo.py
# -b = background mode
# -P = run a Python script within the context of the project file

# Init all of the variables needed by this script.  Because Blender executes
# this script, OpenShot will inject a dictionary of the required parameters
# before this script is executed.
params = {
    'title': 'Oh Yeah! OpenShot!',
    'extrude': 0.05,
    'bevel_depth': 0.01,
    'spacemode': 'CENTER',
    'text_size': 1,
    'width': 1.0,
    'fontname': 'Bfont',

    'color': [0.8, 0.8, 0.8],
    'alpha': 1.0,
    'alpha_mode': 1,

    'output_path': '/tmp/',
    'fps': 24,
    'quality': 90,
    'file_format': 'PNG',
    'color_mode': 'RGBA',
    'horizon_color': [0, 0, 0],
    'resolution_x': 1920,
    'resolution_y': 1080,
    'resolution_percentage': 100,
    'start_frame': 1,
    'end_frame': 120,
    'animation': True,
    'length_multiplier': 1,
    'diffuse_color': [0.57, 0.57, 0.57, 1.0],
}

# INJECT_PARAMS_HERE

# The remainder of this script will modify the current Blender .blend project
# file, and adjust the settings.  The .blend file is specified in the XML file
# that defines this template in OpenShot.
# ----------------------------------------------------------------------------

# Get font object
font = None
if params["fontname"] != "Bfont":
    # Add font so it's available to Blender
    font = load_font(params["fontname"])
else:
    # Get default font
    font = bpy.data.fonts["Bfont"]

# Create dissolve text changes (slow)
createDissolveText(
    params["title"], params["extrude"], params["bevel_depth"],
    params["spacemode"], params["text_size"], params["width"], font,
)

# Change the material settings (color, alpha, etc...)
DissolveMaterial = bpy.data.materials["DissolveMaterial"]
DissolveMaterial.node_tree.nodes["Principled BSDF"].inputs['Emission'].default_value = params["diffuse_color"]
TextMaterial = bpy.data.materials["TextMaterial"]
TextMaterial.node_tree.nodes["Principled BSDF"].inputs['Emission'].default_value = params["diffuse_color"]

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
bpy.data.worlds['World'].color = params["horizon_color"]
render.resolution_x = params["resolution_x"]
render.resolution_y = params["resolution_y"]
render.resolution_percentage = params["resolution_percentage"]

# Unbake particle cache
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
    # bake dynamics : take time but needed before rendering animation
    bpy.ops.ptcache.bake_all()
