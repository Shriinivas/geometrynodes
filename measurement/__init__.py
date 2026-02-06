# Measurement Tools Addon for Blender
# Provides distance and angle measurement tools using geometry nodes

bl_info = {
    "name": "Measure Tools",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Toolbar",
    "description": "Measure distance and angles by clicking in the viewport",
    "category": "Mesh",
}

import bpy

from .preferences import MeasureToolPreferences
from .operators import MOUSE_OT_draw_distance, MOUSE_OT_draw_angle
from .tools import DistanceTool, AngleTool


classes = (
    MeasureToolPreferences,
    MOUSE_OT_draw_distance,
    MOUSE_OT_draw_angle,
)



def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.utils.register_tool(DistanceTool, separator=True)
    bpy.utils.register_tool(AngleTool)


def unregister():
    bpy.utils.unregister_tool(AngleTool)
    bpy.utils.unregister_tool(DistanceTool)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
