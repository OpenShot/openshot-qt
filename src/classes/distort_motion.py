"""Mesh poses for the Ribbon, Wave, and Lens Resolve motion presets.

Offsets are fractions of the source image dimensions. Each column has its own
settling time, so these cannot be reduced to whole-clip scale/shear animation.
"""
import math


def smooth(value):
    """Quintic easing with zero velocity and acceleration at both ends."""
    value = max(0.0, min(1.0, value))
    return value ** 3 * (value * (value * 6.0 - 15.0) + 10.0)


def mesh_pose(style, progress, exiting=False):
    """Return sixteen (x, y) offsets, including an exactly neutral resting pose."""
    if style not in ("ribbon", "stretch", "lens_resolve"):
        raise ValueError("Unknown distortion animation: %s" % style)
    progress = max(0.0, min(1.0, progress))
    if (not exiting and progress == 1.0) or (exiting and progress == 0.0):
        return [(0.0, 0.0)] * 16
    # Use a curved, progressively opening sheet rather than a masked wipe.
    phase = 1.0 - progress if exiting else progress
    points = []
    for row in range(4):
        v = row / 3.0
        for column in range(4):
            u = column / 3.0
            if style == "ribbon":
                remaining = 1.0 - smooth((phase - 0.22 * u) / 0.76)
                dx = 0.12 * (u - 0.5) * remaining
                dy = (-0.90 * (v - 0.5) + 0.22 * math.sin(math.pi * u)) * remaining
            elif style == "stretch":
                # Keep the original slow pull. Add one broad, low-amplitude
                # return ripple across the interior, without reversing the pull.
                local = (progress - 0.28 * (1.0 - u)) / 0.70
                remaining = smooth(local) if exiting else 1.0 - smooth(local)
                dx = (u ** 0.4 - u) * remaining
                dy = -0.16 * (v - 0.5) * remaining
                ripple_time = progress / 0.70 if exiting else (progress - 0.35) / 0.65
                if 0.0 < ripple_time < 1.0:
                    center = 1.20 - 1.40 * ripple_time
                    distance = (u - center) / 0.60
                    envelope = math.sin(math.pi * ripple_time) ** 2
                    dy += (0.018 * math.sin(math.pi * distance)
                           * math.exp(-distance * distance) * envelope
                           * math.sin(math.pi * v))
            else:
                remaining = 1.0 - smooth(phase / 0.92)
                radial = 0.85 * math.sin(math.pi * u) * math.sin(math.pi * v) * remaining
                dx, dy = (u - 0.5) * radial, (v - 0.5) * radial
            points.append((dx, dy))
    return points


def wave_pose(progress):
    """A single traveling bend; outer edges and both endpoints stay fixed."""
    progress = max(0.0, min(1.0, progress))
    if progress in (0.0, 1.0):
        return [(0.0, 0.0)] * 16
    envelope = math.sin(math.pi * progress) ** 2
    points = []
    for row in range(4):
        v = row / 3.0
        for column in range(4):
            u = column / 3.0
            interior = math.sin(math.pi * u) * math.sin(math.pi * v)
            wave = math.sin(2.0 * math.pi * (u - 1.4 * progress))
            points.append((0.035 * interior * envelope * wave,
                           0.24 * interior * envelope * wave))
    return points
