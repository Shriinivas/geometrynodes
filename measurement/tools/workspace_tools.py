# Workspace tools for measurement


import os
from bpy.types import WorkSpaceTool

# Calculate absolute path to icons directory
# __file__ is .../measure/tools/workspace_tools.py
# icons is .../measure/icons
ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons")
DISTANCE_ICON_PATH = os.path.join(ICONS_DIR, "distance")
ANGLE_ICON_PATH = os.path.join(ICONS_DIR, "angle")


class DistanceTool(WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = "my_tool.distance_tool"
    bl_label = "Distance Measurement"
    bl_description = "Measure distance by clicking start and end points"
    bl_icon = DISTANCE_ICON_PATH
    bl_widget = None
    bl_keymap = (("mouse.draw_distance", {"type": "MOUSEMOVE", "value": "ANY"}, None),)


class AngleTool(WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = "my_tool.angle_tool"
    bl_label = "Angle Measurement"
    bl_description = "Measure angle by clicking 3 points"
    bl_icon = ANGLE_ICON_PATH
    bl_keymap = (("mouse.draw_angle", {"type": "MOUSEMOVE", "value": "ANY"}, None),)
