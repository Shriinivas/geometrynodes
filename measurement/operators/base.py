# Base operator class for measurement tools

import bpy
import mathutils
from bpy.types import Operator
from bpy_extras import view3d_utils

from ..constants import FLOAT_TYPES, INT_TYPES
from ..core.drawing import draw_callback_px, draw_help_overlay
from ..core.snapping import apply_snapping


def get_prefs(context):
    addon = context.preferences.addons.get("measurement")
    return addon.preferences if addon else None


class BaseDrawTool(Operator):
    """Base class for measurement drawing tools."""
    bl_options = {"REGISTER", "UNDO"}
    
    # Subclasses should override this
    tool_type = None

    def invoke(self, context, event):
        self.obj = None
        self.start_point = None
        self.drawing = False
        self._handle = None
        self._help_handle = None
        self.mouse_loc_3d = None
        self.last_hit = None

        if context.area.type == "VIEW_3D":
            self.get_location(context, event)
            args = (self, context)
            self._handle = bpy.types.SpaceView3D.draw_handler_add(
                draw_callback_px, args, "WINDOW", "POST_VIEW"
            )
            # Add help overlay handler
            self._help_handle = bpy.types.SpaceView3D.draw_handler_add(
                draw_help_overlay, args, "WINDOW", "POST_PIXEL"
            )
            context.window_manager.modal_handler_add(self)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        self.report({"WARNING"}, "View3D not found")
        return {"CANCELLED"}

    def get_location(self, context, event):
        region = context.region
        rv3d = context.region_data

        if region.type != "WINDOW":
            found_r = None
            for r in context.area.regions:
                if r.type == "WINDOW":
                    found_r = r
                    break
            if found_r:
                region = found_r
                rv3d = region.data
            else:
                return None

        coord = (event.mouse_x - region.x, event.mouse_y - region.y)
        self.mouse_loc_3d = None

        try:
            view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
            ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        except Exception:
            return None

        hit, loc, normal, index, obj, matrix = context.scene.ray_cast(
            context.view_layer.depsgraph, ray_origin, view_vector
        )
        final_loc = None

        use_snap = context.tool_settings.use_snap
        if event.ctrl:
            use_snap = not use_snap

        if hit:
            self.last_hit = (hit, loc, normal, index, obj, matrix)
            if (
                use_snap
                and "VERTEX" in context.tool_settings.snap_elements
            ):
                if obj.type == "MESH":
                    mw = obj.matrix_world
                    loc_local = mw.inverted() @ loc
                    if index is not None and index < len(obj.data.polygons):
                        poly = obj.data.polygons[index]
                        
                        # Gather candidates: Vertices and Edge Midpoints
                        candidates = []
                        p_verts_indices = poly.vertices
                        num_verts = len(p_verts_indices)
                        
                        for i in range(num_verts):
                            v_curr = obj.data.vertices[p_verts_indices[i]].co
                            v_next = obj.data.vertices[p_verts_indices[(i + 1) % num_verts]].co
                            
                            candidates.append(v_curr)          # Vertex
                            candidates.append((v_curr + v_next) / 2) # Edge Midpoint

                        nearest_co = min(candidates, key=lambda c: (c - loc_local).length)
                        world_v = mw @ nearest_co
                        screen_pos = view3d_utils.location_3d_to_region_2d(
                            region, rv3d, world_v
                        )
                        if (
                            screen_pos
                            and (
                                mathutils.Vector(screen_pos) - mathutils.Vector(coord)
                            ).length
                            < 20.0
                        ):
                            final_loc = world_v

            if final_loc is None:
                final_loc = loc
        else:
            self.last_hit = None
            final_loc = view3d_utils.region_2d_to_location_3d(
                region, rv3d, coord, context.scene.cursor.location
            )

        if not hit or final_loc == loc:
            final_loc = apply_snapping(context, final_loc, region, rv3d, use_snap=use_snap)

        self.mouse_loc_3d = final_loc
        return final_loc

    def cancel_op(self, context):
        if self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        if self._help_handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._help_handle, "WINDOW")
            self._help_handle = None
        if self.obj:
            bpy.data.objects.remove(self.obj, do_unlink=True)
        if context.area:
            context.area.tag_redraw()

    def is_over_ui(self, context, event):
        """Check if mouse is over UI elements."""
        area = context.area
        if not area:
            return True

        if not (
            area.x <= event.mouse_x <= area.x + area.width
            and area.y <= event.mouse_y <= area.y + area.height
        ):
            return True

        for region in area.regions:
            if region.type != "WINDOW":
                if (
                    region.x <= event.mouse_x <= region.x + region.width
                    and region.y <= event.mouse_y <= region.y + region.height
                ):
                    return True
        return False

    def get_target_socket(self, keyword, valid_types):
        """Finds modifier and input socket by keyword."""
        if not self.obj:
            return None, None, None

        mod = next(
            (m for m in self.obj.modifiers if m.type == "NODES" and "Wrap" in m.name),
            None,
        )
        if mod and mod.node_group:
            # 1. Try exact match first
            for item in mod.node_group.interface.items_tree:
                if (
                    item.item_type == "SOCKET"
                    and item.in_out == "INPUT"
                    and keyword.lower() == item.name.lower()
                    and item.socket_type in valid_types
                ):
                    return mod, item.identifier, item.name
            
            # 2. Fallback to substring match
            for item in mod.node_group.interface.items_tree:
                if (
                    item.item_type == "SOCKET"
                    and item.in_out == "INPUT"
                    and keyword.lower() in item.name.lower()
                    and item.socket_type in valid_types
                ):
                    return mod, item.identifier, item.name
        return None, None, None

    def set_modifier_value(
        self, context, keyword, value, valid_types, toggle_flip=False
    ):
        """Unified method to set/toggle modifier values and update viewport."""
        mod, target_id, name = self.get_target_socket(keyword, valid_types)
        if not mod or not target_id:
            return

        try:
            curr_val = mod.get(target_id)
            final_val = value

            if toggle_flip and isinstance(curr_val, (int, float)):
                curr_int = int(round(curr_val))
                target_int = int(round(value))
                if curr_int == target_int:
                    final_val = target_int + 180
                elif curr_int == target_int + 180:
                    final_val = target_int

            # Type preservation
            if isinstance(curr_val, int) and isinstance(final_val, float):
                final_val = int(round(final_val))

            mod[target_id] = final_val
            self.report({"INFO"}, f"{name}: {final_val}")

            # Force update
            mod.show_viewport = False
            mod.show_viewport = True
            context.view_layer.update()
            if context.area:
                context.area.tag_redraw()

        except Exception as e:
            print(f"Set '{name}' failed: {e}")

    def adjust_parameter(self, context, keyword, step, valid_types):
        mod, target_id, _ = self.get_target_socket(keyword, valid_types)
        if mod and target_id:
            curr = mod.get(target_id, 0)
            self.set_modifier_value(context, keyword, curr + step, valid_types)

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def check_exit(self, context, event):
        """Check if tool should exit."""
        if context.mode != "OBJECT":
            self.cancel_op(context)
            return True

        try:
            active = context.workspace.tools.from_space_view3d_mode(context.mode)
            if active:
                if active.idname != self.bl_idname_tool:
                    self.cancel_op(context)
                    return True
        except Exception:
            pass

        if event.type in {"RIGHTMOUSE", "ESC"}:
            self.cancel_op(context)
            return True

        return None

    def get_scroll_bindings(self):
        """Returns dict: { 'CTRL'|'SHIFT'|'ALT': (param_name, step, type_set) }"""
        # Default bindings common to both tools
        prefs = get_prefs(bpy.context)
        angle_step = int(prefs.angle_increment) if prefs else 5
        dist_step = prefs.distance_increment if prefs else 0.01

        return {
             "SHIFT": ("Text Rotation", angle_step, INT_TYPES),
             "ALT": ("Offset", dist_step, FLOAT_TYPES),
        }

    def handle_modal_scroll(self, context, event):
        if not self.drawing:
            return False

        is_scroll_up = (
            event.type in {"WHEELUPMOUSE", "NUMPAD_PLUS"} and event.value == "PRESS"
        )
        is_scroll_down = (
            event.type in {"WHEELDOWNMOUSE", "NUMPAD_MINUS"} and event.value == "PRESS"
        )

        if is_scroll_up or is_scroll_down:
            direction = 1 if is_scroll_up else -1
            bindings = self.get_scroll_bindings()

            target = None
            if event.ctrl:
                target = bindings.get("CTRL")
            elif event.shift:
                target = bindings.get("SHIFT")
            elif event.alt:
                target = bindings.get("ALT")

            if target:
                param, step, valid_types = target
                self.adjust_parameter(context, param, step * direction, valid_types)
                return True

        return False

    def toggle_help_overlay(self, context):
        """Toggle the help overlay visibility."""
        prefs = context.preferences.addons.get("measurement")
        if prefs:
            prefs = prefs.preferences
            prefs.show_help_overlay = not prefs.show_help_overlay
            if context.area:
                context.area.tag_redraw()
            state = "shown" if prefs.show_help_overlay else "hidden"
            self.report({"INFO"}, f"Help overlay {state}")

    def handle_common_keys(self, context, event):
        """Handle common keybindings shared across tools. Returns True if handled."""
        # Ctrl+Alt+H: Toggle help overlay
        if (event.type == "H" and event.value == "PRESS" 
            and event.ctrl and event.alt and not event.shift):
            self.toggle_help_overlay(context)
            return True
        return False
