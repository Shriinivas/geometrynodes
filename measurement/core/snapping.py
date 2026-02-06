# Snapping utilities for measurement tools

import math
import mathutils
from bpy_extras import view3d_utils


def apply_snapping(context, loc, region, rv3d, use_snap=None):
    """
    Apply snapping with adaptive grid scaling.
    """
    if use_snap is None:
        use_snap = context.tool_settings.use_snap

    if not use_snap:
        return loc

    snap_elements = context.tool_settings.snap_elements

    if "INCREMENT" in snap_elements:
        grid_scale = 1.0

        if region and rv3d:
            p1 = view3d_utils.location_3d_to_region_2d(region, rv3d, loc)
            if p1:
                p2 = view3d_utils.location_3d_to_region_2d(
                    region, rv3d, loc + mathutils.Vector((1.0, 0, 0))
                )
                if p2:
                    pixels_per_unit = (
                        mathutils.Vector(p1) - mathutils.Vector(p2)
                    ).length

                    if pixels_per_unit > 0.00001:
                        target_px = 30.0
                        raw_step = target_px / pixels_per_unit
                        exponent = math.floor(math.log10(raw_step))
                        grid_scale = 10**exponent

        if context.scene.unit_settings.system != "NONE":
            grid_scale *= context.scene.unit_settings.scale_length

        loc = mathutils.Vector(
            (
                round(loc.x / grid_scale) * grid_scale,
                round(loc.y / grid_scale) * grid_scale,
                round(loc.z / grid_scale) * grid_scale,
            )
        )

    return loc
