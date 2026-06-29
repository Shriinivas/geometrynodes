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

    measurement_mode: bpy.props.EnumProperty(
        name="Measurement Mode",
        description="How modifier settings are applied",
        items=[
            ('ABSOLUTE', "Absolute", "Use exact values defined in preferences"),
            ('RELATIVE', "Relative", "Scale values dynamically based on the actual length (values are for 1 unit length)"),
        ],
        default='ABSOLUTE',
    )

    default_output_type: bpy.props.EnumProperty(
        name="Output Type",
        description="Default output type for measurements",
        items=[
            ('Grease Pencil', "Grease Pencil", ""),
            ('Mesh', "Mesh", ""),
        ],
        default='Grease Pencil',
    )

    default_precision: bpy.props.IntProperty(
        name="Precision",
        description="Default number of decimal places",
        default=2,
        min=0,
        max=6,
    )

    default_unit_distance: bpy.props.EnumProperty(
        name="Distance Unit",
        description="Default unit for distance measurements",
        items=[
            ('Meter', "Meter", ""),
            ('Foot', "Foot", ""),
            ('Inch', "Inch", ""),
            ('Foot-Inch', "Foot-Inch", ""),
            ('Vector', "Vector", ""),
        ],
        default='Meter',
    )

    default_unit_angle: bpy.props.EnumProperty(
        name="Angle Unit",
        description="Default unit for angle measurements",
        items=[
            ('Degree', "Degree", ""),
            ('Radian', "Radian", ""),
        ],
        default='Degree',
    )

    default_offset: bpy.props.FloatProperty(
        name="Offset",
        description="Default offset from target geometry",
        default=0.1,
        step=1.0,
        precision=4,
    )

    default_substitute_text: bpy.props.StringProperty(
        name="Substitute Text",
        description="Default text to show instead of the measured value (leave blank for value)",
        default="",
    )

    default_text_size: bpy.props.FloatProperty(
        name="Text Size",
        description="Default size of the text",
        default=0.05,
        min=0.0,
        step=0.1,
        precision=4,
    )

    default_text_gap: bpy.props.FloatProperty(
        name="Text Gap",
        description="Default gap between text and measurement line",
        default=0.02,
        min=0.0,
        step=0.1,
        precision=4,
    )

    default_text_rotation: bpy.props.IntProperty(
        name="Text Rotation",
        description="Default rotation of the text in degrees",
        default=0,
        min=-360,
        max=360,
    )

    default_scale: bpy.props.FloatProperty(
        name="Scale (Distance)",
        description="Default scale factor for distance measurements",
        default=1.0,
        min=0.0,
        step=1.0,
        precision=4,
    )

    default_radius: bpy.props.FloatProperty(
        name="Radius (Angle)",
        description="Default radius for angle arc",
        default=0.5,
        min=0.0,
        step=1.0,
        precision=4,
    )

    default_rotation: bpy.props.IntProperty(
        name="Rotation (Distance)",
        description="Default rotation of distance marker",
        default=0,
        min=-360,
        max=360,
    )

    default_line_thickness: bpy.props.FloatProperty(
        name="Line Thickness",
        description="Default thickness of main measurement line",
        default=0.3,
        min=0.0,
        step=0.1,
        precision=4,
    )

    default_ref_line_thickness: bpy.props.FloatProperty(
        name="Ref Line Thickness",
        description="Default thickness of reference/extension lines",
        default=0.2,
        min=0.0,
        step=0.1,
        precision=4,
    )

    default_conn_line_thickness: bpy.props.FloatProperty(
        name="Conn Line Thickness",
        description="Default thickness of connection lines",
        default=0.2,
        min=0.0,
        step=0.1,
        precision=4,
    )

    default_arrowhead_width: bpy.props.FloatProperty(
        name="Arrowhead Width",
        description="Default width of arrowheads",
        default=1.5,
        min=0.0,
        step=0.1,
        precision=4,
    )

    default_arrowhead_length: bpy.props.FloatProperty(
        name="Arrowhead Length",
        description="Default length of arrowheads",
        default=8.0,
        min=0.0,
        step=0.1,
        precision=4,
    )

    default_point_radius: bpy.props.FloatProperty(
        name="Point Radius",
        description="Default radius of point markers",
        default=0.75,
        min=0.0,
        step=0.1,
        precision=4,
    )

    default_flip_text: bpy.props.BoolProperty(
        name="Flip Text",
        description="Default setting to flip measurement text upside down",
        default=False,
    )

    default_text_thickness: bpy.props.FloatProperty(
        name="Text Thickness",
        description="Default thickness of mesh text (3D depth)",
        default=0.001,
        min=0.0,
        step=0.01,
        precision=5,
    )

    default_outer_angle: bpy.props.BoolProperty(
        name="Outer Angle",
        description="Default setting to measure outer angle (> 180 degrees)",
        default=False,
    )

    default_arrow_color: bpy.props.FloatVectorProperty(
        name="Arrow / Arc Color",
        description="Default color for arrows and angle arcs",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=(0.4, 1.0, 0.7, 1.0),
    )

    default_ref_line_color: bpy.props.FloatVectorProperty(
        name="Ref Line Color",
        description="Default color for reference lines",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=(0.8, 0.8, 0.8, 0.2),
    )

    default_conn_line_color: bpy.props.FloatVectorProperty(
        name="Conn / Main Line Color",
        description="Default color for connection and main lines",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=(0.6, 0.6, 0.6, 0.5),
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

        # Dynamic Scaling Mode
        box_mode = layout.box()
        box_mode.label(text="Measurement Mode:")
        box_mode.prop(self, "measurement_mode", expand=True)

        # Modifier Defaults
        box_defaults = layout.box()
        box_defaults.label(text="Default Modifier Inputs:")

        col = box_defaults.column(align=True)
        col.prop(self, "default_output_type")
        col.prop(self, "default_precision")

        row_units = box_defaults.row()
        row_units.prop(self, "default_unit_distance")
        row_units.prop(self, "default_unit_angle")

        row_toggles = box_defaults.row()
        row_toggles.prop(self, "default_flip_text")
        row_toggles.prop(self, "default_outer_angle")

        # Two-column layout for numeric settings
        row_params = box_defaults.row()

        col_left = row_params.column(align=True)
        col_left.label(text="Placement & Scaling:")
        col_left.prop(self, "default_offset")
        col_left.prop(self, "default_text_size")
        col_left.prop(self, "default_text_gap")
        col_left.prop(self, "default_text_thickness")
        col_left.prop(self, "default_scale")
        col_left.prop(self, "default_radius")

        col_right = row_params.column(align=True)
        col_right.label(text="Thickness & Lines:")
        col_right.prop(self, "default_line_thickness")
        col_right.prop(self, "default_ref_line_thickness")
        col_right.prop(self, "default_conn_line_thickness")
        col_right.prop(self, "default_arrowhead_width")
        col_right.prop(self, "default_arrowhead_length")
        col_right.prop(self, "default_point_radius")

        row_rot = box_defaults.row()
        row_rot.prop(self, "default_text_rotation")
        row_rot.prop(self, "default_rotation")

        row_sub = box_defaults.row()
        row_sub.prop(self, "default_substitute_text")

        # Colors Section
        box_colors = box_defaults.box()
        box_colors.label(text="Default Colors:")

        col_colors = box_colors.column(align=True)
        col_colors.prop(self, "default_arrow_color")
        col_colors.prop(self, "default_ref_line_color")
        col_colors.prop(self, "default_conn_line_color")

