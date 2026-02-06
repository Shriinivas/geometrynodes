# Addon preferences for measurement tools

import bpy


class MeasureToolPreferences(bpy.types.AddonPreferences):
    bl_idname = "measurement"

    show_help_overlay: bpy.props.BoolProperty(
        name="Show Help Overlay",
        description="Display keyboard shortcuts overlay in viewport",
        default=True,
    )

    help_pos_x: bpy.props.IntProperty(
        name="Help X Position",
        description="Horizontal position of help overlay (pixels from left)",
        default=20,
        min=0,
        max=1000,
    )

    help_pos_y: bpy.props.IntProperty(
        name="Help Y Position",
        description="Vertical position of help overlay (pixels from bottom)",
        default=20,
        min=0,
        max=1000,
    )

    angle_increment: bpy.props.FloatProperty(
        name="Angle Increment",
        description="Rotation step size (degrees) when scrolling",
        default=15.0,
        min=0.1,
        max=90.0,
    )

    distance_increment: bpy.props.FloatProperty(
        name="Distance Increment",
        description="Distance/Offset step size (meters) when scrolling",
        default=0.1,
        min=0.001,
        max=1.0,
        precision=4,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "show_help_overlay")

        row = layout.row()
        row.prop(self, "help_pos_x")
        row.prop(self, "help_pos_y")

        box = layout.box()
        box.label(text="Scroll Adjustments:")
        row = box.row()
        row.prop(self, "angle_increment")
        row.prop(self, "distance_increment")
