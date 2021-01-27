# Enable CYCLES renderer, using GPU (if found)
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'GPU'

cprefs = bpy.context.preferences.addons['cycles'].preferences

# Attempt to set GPU device types if available
for compute_device_type in ('CUDA', 'OPENCL', 'NONE'):
    try:
        cprefs.compute_device_type = compute_device_type
        break
    except TypeError:
        pass

# Enable all CPU and GPU devices
for device in cprefs.devices:
    device.use = True
