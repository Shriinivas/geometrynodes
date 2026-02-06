# Angle measurement operator

import bpy
import bmesh
import mathutils

from .base import BaseDrawTool, get_prefs
from ..constants import FLOAT_TYPES, INT_TYPES
from ..core.nodegroup import create_wrapper_modifier, get_asset_nodegroup


class MOUSE_OT_draw_angle(BaseDrawTool):
    """Measure angle by clicking 3 points."""

    bl_idname = "mouse.draw_angle"
    bl_label = "Draw Angle"
    bl_idname_tool = "my_tool.angle_tool"
    tool_type = "angle"

    def get_scroll_bindings(self):
        bindings = super().get_scroll_bindings()
        prefs = get_prefs(bpy.context)
        step = prefs.distance_increment if prefs else 0.01
        bindings["CTRL"] = ("Radius", step, FLOAT_TYPES)
        return bindings

    def invoke(self, context, event):
        self.phase = 0
        self.waiting_for_move = False
        self.pending_point_loc = None
        self.report({"INFO"}, "Click 3 points for angle.")
        return super().invoke(context, event)

    def create_angle_object(self, context, loc):
        mesh = bpy.data.meshes.new("Angle Measurement")
        self.obj = bpy.data.objects.new("Angle Measurement", mesh)
        context.collection.objects.link(self.obj)
        bm = bmesh.new()
        v1 = bm.verts.new(loc)
        v2 = bm.verts.new(loc)
        bm.edges.new((v1, v2))
        bm.to_mesh(mesh)
        bm.free()
        bpy.ops.object.select_all(action="DESELECT")
        self.obj.select_set(True)
        context.view_layer.objects.active = self.obj

    def update_geometry(self, loc, vert_index):
        if not self.obj or not loc:
            return
        inv = self.obj.matrix_world.inverted()
        self.obj.data.vertices[vert_index].co = inv @ loc
        self.obj.data.update()

    def add_point(self, loc):
        bm = bmesh.new()
        bm.from_mesh(self.obj.data)
        bm.verts.ensure_lookup_table()
        last_v = bm.verts[-1]
        new_v = bm.verts.new(last_v.co)
        bm.edges.new((last_v, new_v))
        bm.to_mesh(self.obj.data)
        bm.free()
        self.obj.data.update()

    def modal(self, context, event):
        if not context.area:
            self.cancel_op(context)
            return {"CANCELLED"}

        context.area.tag_redraw()

        # 1. Pass Through Checks
        if self.is_over_ui(context, event):
            if self.drawing and event.type == "MOUSEMOVE":
                pass
            else:
                self.mouse_loc_3d = None
                return {"PASS_THROUGH"}

        exit_code = self.check_exit(context, event)
        if exit_code is True:
            return {"CANCELLED"}

        # Handle common keys (e.g., Ctrl+Alt+H to toggle help)
        if self.handle_common_keys(context, event):
            return {"RUNNING_MODAL"}

        if event.type in {
            "MIDDLEMOUSE",
            "WHEELUPMOUSE",
            "WHEELDOWNMOUSE",
            "NUMPAD_PLUS",
            "NUMPAD_MINUS",
        } and not (event.shift or event.ctrl or event.alt):
            return {"PASS_THROUGH"}

        if self.handle_modal_scroll(context, event):
            return {"RUNNING_MODAL"}

        if event.type == "BACK_SPACE" and event.value == "PRESS":
            if self.phase == 2:
                bm = bmesh.new()
                bm.from_mesh(self.obj.data)
                bm.verts.ensure_lookup_table()
                bm.verts.remove(bm.verts[-1])
                bm.to_mesh(self.obj.data)
                bm.free()
                self.obj.data.update()

                # Remove modifier when going back to 2 points
                mod = self.obj.modifiers.get("Wrap_Angle Measurement")
                if mod:
                    self.obj.modifiers.remove(mod)

                self.phase = 1
                if self.mouse_loc_3d:
                     self.update_geometry(self.mouse_loc_3d, 1)
                return {"RUNNING_MODAL"}

        if event.type == "MOUSEMOVE":
            loc = self.get_location(context, event)

            if self.waiting_for_move and self.phase == 1 and loc:
                dist = (mathutils.Vector(loc) - mathutils.Vector(self.pending_point_loc)).length
                if dist > 0.001:
                    self.add_point(self.pending_point_loc)
                    # Add modifier when we have 3 points
                    target_group = get_asset_nodegroup("Angle Measurement")
                    if target_group:
                        create_wrapper_modifier(self.obj, target_group)
                    self.phase = 2
                    self.waiting_for_move = False

            if self.drawing and self.obj:
                target_idx = 1 if self.phase == 1 else 2
                self.update_geometry(loc, target_idx)
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
                    self.create_angle_object(context, loc)
                    self.drawing = True
                    self.phase = 1
                    if self._handle:
                        bpy.types.SpaceView3D.draw_handler_remove(
                            self._handle, "WINDOW"
                        )
                        self._handle = None
                return {"RUNNING_MODAL"}

            else:
                loc = self.get_location(context, event)
                if self.phase == 1:
                    # self.add_point(loc) -> Delayed
                    self.pending_point_loc = loc
                    self.waiting_for_move = True
                elif self.phase == 2:
                    return {"FINISHED"}
                return {"RUNNING_MODAL"}

        return {"PASS_THROUGH"}
