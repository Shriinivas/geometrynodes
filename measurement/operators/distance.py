# Distance measurement operator

import bpy
import bmesh
import math
import mathutils

from .base import BaseDrawTool, get_prefs
from ..constants import FLOAT_TYPES, INT_TYPES
from ..core.nodegroup import create_wrapper_modifier, get_asset_nodegroup


class MOUSE_OT_draw_distance(BaseDrawTool):
    """Measure distance by drawing a line between two points."""

    bl_idname = "mouse.draw_distance"
    bl_label = "Draw Distance"
    bl_idname_tool = "my_tool.distance_tool"
    tool_type = "distance"

    def get_scroll_bindings(self):
        bindings = super().get_scroll_bindings()
        prefs = get_prefs(bpy.context)
        step = int(prefs.angle_increment) if prefs else 5
        bindings["CTRL"] = ("Rotation", step, INT_TYPES)
        return bindings

    def invoke(self, context, event):
        self.waiting_for_move = False
        self.report({"INFO"}, "Click start. Ctrl snap. Esc cancel.")
        return super().invoke(context, event)

    def create_line_object(self, context, loc):
        mesh = bpy.data.meshes.new("Distance Measurement")
        self.obj = bpy.data.objects.new("Distance Measurement", mesh)
        context.collection.objects.link(self.obj)
        bm = bmesh.new()
        v1 = bm.verts.new(loc)
        v2 = bm.verts.new(loc)
        bm.edges.new((v1, v2))
        bm.to_mesh(mesh)
        bm.free()
        bpy.ops.object.select_all(action="DESELECT")
        self.obj.select_set(True)
        target_group = get_asset_nodegroup("Distance Measurement")
        if target_group:
            create_wrapper_modifier(self.obj, target_group)
        context.view_layer.objects.active = self.obj

    def align_to_geometry(self, context):
        if not self.last_hit or not self.obj:
            return
        hit, _, normal, _, _, _ = self.last_hit

        # 1. Tangent
        v0 = self.obj.matrix_world @ self.obj.data.vertices[0].co
        v1 = self.obj.matrix_world @ self.obj.data.vertices[1].co
        diff = v1 - v0
        if diff.length < 0.0001:
            return
        tangent = diff.normalized()

        # 2. Reference Normal (Z-up projected)
        z = mathutils.Vector((0, 0, 1))
        ref_normal = (
            mathutils.Vector((1, 0, 0))
            if abs(tangent.dot(z)) > 0.9999
            else (z - (z.dot(tangent) * tangent)).normalized()
        )

        # 3. Target (Surface Tangent)
        target_proj = normal.cross(tangent)

        # 4. Angle
        rot_val = 0
        if target_proj.length > 0.001:
            target_proj.normalize()
            angle = ref_normal.angle(target_proj)
            if ref_normal.cross(target_proj).dot(tangent) < 0:
                angle = -angle
            rot_val = int(round(math.degrees(angle)))

        # 5. Apply
        self.set_modifier_value(
            context,
            "Rotation",
            rot_val,
            {
                "NodeSocketInt",
                "NodeSocketFloat",
                "NodeSocketIntUnsigned",
                "NodeSocketFloatAngle",
            },
            toggle_flip=True,
        )

    def modal(self, context, event):
        if not context.area:
            self.cancel_op(context)
            return {"CANCELLED"}

        context.area.tag_redraw()

        # 1. Pass Through Checks (UI, Outside Area)
        if self.is_over_ui(context, event):
            if self.drawing and event.type == "MOUSEMOVE":
                pass
            else:
                self.mouse_loc_3d = None
                return {"PASS_THROUGH"}

        # 2. Tool Switch/Key Cancel
        exit_code = self.check_exit(context, event)
        if exit_code is True:
            return {"CANCELLED"}

        # Handle common keys (e.g., Ctrl+Alt+H to toggle help)
        if self.handle_common_keys(context, event):
            return {"RUNNING_MODAL"}

        # Navigation
        if event.type in {
            "MIDDLEMOUSE",
            "WHEELUPMOUSE",
            "WHEELDOWNMOUSE",
            "NUMPAD_PLUS",
            "NUMPAD_MINUS",
        } and not (event.shift or event.ctrl or event.alt):
            return {"PASS_THROUGH"}

        # Parameter Adjustment Logic
        if self.handle_modal_scroll(context, event):
            return {"RUNNING_MODAL"}

        if event.type in {
            "MIDDLEMOUSE",
            "WHEELUPMOUSE",
            "WHEELDOWNMOUSE",
            "NUMPAD_PLUS",
            "NUMPAD_MINUS",
        }:
            return {"PASS_THROUGH"}

        if event.type == "MOUSEMOVE":
            loc = self.get_location(context, event)
            
            if self.waiting_for_move and loc:
                dist = (mathutils.Vector(loc) - mathutils.Vector(self.start_point)).length
                if dist > 0.001:
                    self.create_line_object(context, self.start_point)
                    self.waiting_for_move = False
                    self.drawing = True
                    if self._handle:
                        bpy.types.SpaceView3D.draw_handler_remove(
                            self._handle, "WINDOW"
                        )
                        self._handle = None

            if self.drawing and self.obj and loc:
                inv = self.obj.matrix_world.inverted()
                local_loc = inv @ loc
                self.obj.data.vertices[1].co = local_loc
                self.obj.data.update()
            return {"RUNNING_MODAL"}

        elif event.type == "LEFTMOUSE" and event.value == "PRESS":
            if not self.drawing:
                for region in context.area.regions:
                    if region.type != "WINDOW":
                        if (
                            region.x <= event.mouse_x <= region.x + region.width
                            and region.y <= event.mouse_y <= region.y + region.height
                        ):
                            return {"PASS_THROUGH"}
                loc = self.get_location(context, event)
                if loc:
                    self.start_point = loc
                    self.waiting_for_move = True
                return {"RUNNING_MODAL"}
            else:
                return {"FINISHED"}

        elif event.type == "E" and event.value == "PRESS":
            if self.drawing:
                self.align_to_geometry(context)
                return {"RUNNING_MODAL"}

        elif event.type in {"RIGHTMOUSE", "ESC"}:
            self.cancel_op(context)
            return {"CANCELLED"}

        return {"PASS_THROUGH"}
