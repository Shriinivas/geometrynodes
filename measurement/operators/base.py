# Base operator class for measurement tools

import bpy
import mathutils
from bpy.types import Operator
from bpy_extras import view3d_utils

from ..constants import FLOAT_TYPES, INT_TYPES
from ..core.drawing import draw_callback_px, draw_help_overlay, register_draw_handler, unregister_operator_handlers
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
        
        self.init_session_params(context)

        if context.area.type == "VIEW_3D":
            self.get_location(context, event)
            self._handle = register_draw_handler(self, draw_callback_px, "POST_VIEW")
            self._help_handle = register_draw_handler(self, draw_help_overlay, "POST_PIXEL")
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

    def remove_draw_handlers(self, context):
        """Cleanly remove the view draw handlers."""
        unregister_operator_handlers(self)
        self._handle = None
        self._help_handle = None
        if context and context.area:
            context.area.tag_redraw()

    def cancel(self, context):
        """Called by Blender when modal operator finishes or cancels."""
        self.remove_draw_handlers(context)

    def cancel_op(self, context):
        self.remove_draw_handlers(context)
        if self.obj:
            try:
                bpy.data.objects.remove(self.obj, do_unlink=True)
            except Exception:
                pass
            self.obj = None

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

    def init_session_params(self, context):
        prefs = get_prefs(context)
        if not prefs:
            return
        
        socket_to_pref = {
            "Output Type": "default_output_type",
            "Precision": "default_precision",
            "Offset": "default_offset",
            "Substitute Text": "default_substitute_text",
            "Text Size": "default_text_size",
            "Text Gap": "default_text_gap",
            "Text Rotation": "default_text_rotation",
            "Scale": "default_scale",
            "Radius": "default_radius",
            "Rotation": "default_rotation",
            "Line Thickness": "default_line_thickness",
            "Ref Line Thickness": "default_ref_line_thickness",
            "Conn Line Thickness": "default_conn_line_thickness",
            "Arrowhead Width": "default_arrowhead_width",
            "Arrowhead Length": "default_arrowhead_length",
            "Point Radius": "default_point_radius",
            "Flip Text": "default_flip_text",
            "Text Thickness": "default_text_thickness",
            "Outer Angle": "default_outer_angle",
            # Colors
            "Arrow Color": "default_arrow_color",
            "GP Arc Color": "default_arrow_color",
            "Ref Line Color": "default_ref_line_color",
            "GP Ref Line Color": "default_ref_line_color",
            "Conn Line Color": "default_conn_line_color",
            "GP Main Line Color": "default_conn_line_color",
        }
        
        self.session_params = {}
        for socket_name, pref_attr in socket_to_pref.items():
            if hasattr(prefs, pref_attr):
                val = getattr(prefs, pref_attr)
                if hasattr(val, "to_list"):
                    val = val.to_list()
                elif hasattr(val, "__len__") and not isinstance(val, str):
                    val = list(val)
                self.session_params[socket_name] = val
        
        # Unit special cases
        self.session_params["Unit_Distance"] = prefs.default_unit_distance
        self.session_params["Unit_Angle"] = prefs.default_unit_angle

    def get_actual_length(self):
        if not self.obj or not self.obj.data.vertices:
            return 1.0
        verts = self.obj.data.vertices
        if len(verts) < 2:
            return 1.0
        
        v0 = self.obj.matrix_world @ verts[0].co
        v1 = self.obj.matrix_world @ verts[1].co
        
        if self.tool_type == "angle" and len(verts) >= 3:
            v2 = self.obj.matrix_world @ verts[2].co
            d1 = (v0 - v1).length
            d2 = (v2 - v1).length
            return (d1 + d2) / 2.0
        else:
            return (v1 - v0).length

    def get_angle_info(self):
        """Returns the angle (in degrees) and the shorter leg length of the angle."""
        if not self.obj or len(self.obj.data.vertices) < 2:
            return 0.0, 1.0
        
        verts = self.obj.data.vertices
        mw = self.obj.matrix_world
        w0 = mw @ verts[0].co
        w1 = mw @ verts[1].co # Corner/Vertex
        
        if len(verts) < 3:
            return 0.0, (w1 - w0).length
            
        w2 = mw @ verts[2].co
        
        u = w0 - w1
        v = w2 - w1
        
        u_len = u.length
        v_len = v.length
        
        if u_len < 0.0001 or v_len < 0.0001:
            return 0.0, 0.0
            
        import math
        cos_angle = u.dot(v) / (u_len * v_len)
        cos_angle = max(-1.0, min(1.0, cos_angle))
        angle_rad = math.acos(cos_angle)
        angle_deg = math.degrees(angle_rad)
        
        shorter_len = min(u_len, v_len)
        return angle_deg, shorter_len

    def apply_session_params_to_modifier(self, context):
        if not self.obj:
            return
        
        mod = next(
            (m for m in self.obj.modifiers if m.type == "NODES" and "Wrap" in m.name),
            None,
        )
        if not mod or not mod.node_group:
            return

        prefs = get_prefs(context)
        is_relative = prefs.measurement_mode == 'RELATIVE' if prefs else False

        actual_length = max(0.001, self.get_actual_length())

        scale_dependent_sockets = {
            "Offset",
            "Text Size",
            "Text Gap",
            "Scale",
            "Radius",
            "Line Thickness",
            "Ref Line Thickness",
            "Conn Line Thickness",
            "Arrowhead Width",
            "Arrowhead Length",
            "Point Radius",
            "Text Thickness",
        }

        # Reference angles for different socket groups to maintain perfect proportions
        socket_ref_angles = {
            "Radius": 90.0,
            "Arrowhead Length": 90.0,
            "Offset": 75.0,
            "Arrowhead Width": 75.0,
            "Line Thickness": 75.0,
            "Ref Line Thickness": 75.0,
            "Conn Line Thickness": 75.0,
            "Text Thickness": 75.0,
            "Point Radius": 75.0,
            "Text Size": 60.0,
            "Text Gap": 60.0,
        }

        angle_deg, shorter_len = 0.0, actual_length
        if self.tool_type == "angle":
            angle_deg, shorter_len = self.get_angle_info()

        # Dynamic mapping of enum strings to their indices on the modifier
        def get_enum_value(socket_name, identifier, value_str, default_idx):
            try:
                items = mod.id_properties_ui(identifier).as_dict().get('items', [])
                for item in items:
                    if item[0] == value_str or item[1] == value_str:
                        return item[4]
            except Exception:
                pass

            static_maps = {
                "Output Type": {
                    "Grease Pencil": 2,
                    "Mesh": 3,
                },
                "Unit_Distance": {
                    "Meter": 2,
                    "Foot": 3,
                    "Inch": 4,
                    "Foot-Inch": 5,
                    "Vector": 6,
                },
                "Unit_Angle": {
                    "Degree": 2,
                    "Radian": 3,
                }
            }
            return static_maps.get(socket_name, {}).get(value_str, default_idx)

        for item in mod.node_group.interface.items_tree:
            if item.item_type != "SOCKET" or item.in_out != "INPUT":
                continue
            
            socket_name = item.name
            
            # Unit special cases
            if socket_name == "Unit":
                if "Distance" in mod.node_group.name:
                    val_str = self.session_params.get("Unit_Distance", "Meter")
                    val = get_enum_value("Unit_Distance", item.identifier, val_str, 2)
                else:
                    val_str = self.session_params.get("Unit_Angle", "Degree")
                    val = get_enum_value("Unit_Angle", item.identifier, val_str, 2)
            elif socket_name == "Output Type":
                val_str = self.session_params.get("Output Type", "Grease Pencil")
                val = get_enum_value("Output Type", item.identifier, val_str, 2)
            else:
                val = self.session_params.get(socket_name)

            if val is not None:
                # If relative mode, scale length-dependent properties
                if is_relative and socket_name in scale_dependent_sockets:
                    if isinstance(val, (int, float)):
                        val = val * actual_length

                # Angle-specific scaling and constraints
                if self.tool_type == "angle":
                    if socket_name in socket_ref_angles:
                        ref_angle = socket_ref_angles[socket_name]
                        min_angle = 10.0
                        clamped_angle = max(min_angle, min(ref_angle, angle_deg))
                        angle_scale = clamped_angle / ref_angle
                        if isinstance(val, (int, float)):
                            val = val * angle_scale
                    if socket_name == "Radius":
                        val = min(val, shorter_len)

                # Handle color tuple conversion if needed
                if item.socket_type == 'NodeSocketColor':
                    val = list(val)

                try:
                    mod[item.identifier] = val
                except Exception as e:
                    print(f"Failed to set modifier parameter {socket_name}: {e}")

        # Force update
        mod.show_viewport = False
        mod.show_viewport = True
        context.view_layer.update()
        if context.area:
            context.area.tag_redraw()

    def set_modifier_value(
        self, context, keyword, value, valid_types, toggle_flip=False
    ):
        """Unified method to set/toggle modifier values and update viewport."""
        mod, target_id, name = self.get_target_socket(keyword, valid_types)
        if not mod or not name:
            return

        try:
            curr_val = self.session_params.get(name)
            if curr_val is None:
                curr_val = mod.get(target_id)
            
            final_val = value

            if toggle_flip and isinstance(curr_val, (int, float)):
                curr_int = int(round(curr_val))
                target_int = int(round(value))
                if curr_int == target_int:
                    final_val = target_int + 180
                elif curr_int == target_int + 180:
                    final_val = target_int

            if isinstance(final_val, float):
                final_val = round(final_val, 4)

            # Type preservation
            if isinstance(curr_val, int) and isinstance(final_val, float):
                final_val = int(round(final_val))

            # Store in session parameters
            self.session_params[name] = final_val
            self.report({"INFO"}, f"{name}: {final_val}")

            # Re-apply updated parameters to the modifier
            self.apply_session_params_to_modifier(context)

        except Exception as e:
            print(f"Set '{name}' failed: {e}")

    def adjust_parameter(self, context, keyword, step, valid_types):
        mod, target_id, name = self.get_target_socket(keyword, valid_types)
        if mod and name:
            curr = self.session_params.get(name)
            if curr is None:
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
