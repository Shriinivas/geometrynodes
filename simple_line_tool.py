bl_info = {
    "name": "Draw Mesh Line",
    "author": "Antigravity",
    "version": (1, 2),
    "blender": (3, 0, 0),
    "location": "View3D > Toolbar",
    "description": "Draw a mesh line by clicking start and end points",
    "category": "Mesh",
}

import bpy
import bmesh
import math
from bpy_extras import view3d_utils
from bpy.types import Operator, WorkSpaceTool
import traceback
from pathlib import Path


def create_wrapper_modifier(obj, target_group):
    target_group_name = target_group.name

    if not obj or obj.type not in {"MESH", "CURVE", "POINTCLOUD", "VOLUME"}:
        print("Error: Select a valid geometry object.")
        return

    mod = obj.modifiers.new(name=f"Wrap_{target_group_name}", type="NODES")
    wrapper_group = bpy.data.node_groups.new(
        name=f"Wrapper_{target_group_name}", type="GeometryNodeTree"
    )

    nodes = wrapper_group.nodes
    nodes.clear()

    defVals = {}
    for item in target_group.interface.items_tree:
        if item.item_type == "SOCKET" and item.in_out == "INPUT":
            new_socket = wrapper_group.interface.new_socket(
                name=item.name, in_out="INPUT", socket_type=item.socket_type
            )
            if item.socket_type == "NodeSocketMenu":
                source_items = getattr(item, "items", None)
                if source_items and not callable(source_items):
                    for menu_item in source_items:
                        new_socket.items.new(name=menu_item.name)
            if hasattr(item, "default_value"):
                try:
                    defVals[new_socket.identifier] = item.default_value
                    new_socket.default_value = item.default_value
                except Exception as _:
                    pass
            if hasattr(item, "min_value"):
                new_socket.min_value = item.min_value
            if hasattr(item, "max_value"):
                new_socket.max_value = item.max_value

    mod.node_group = wrapper_group

    group_in = nodes.new("NodeGroupInput")
    group_out = nodes.new("NodeGroupOutput")
    target_node = nodes.new("GeometryNodeGroup")
    target_node.node_tree = target_group

    group_in.location = (-400, 0)
    target_node.location = (0, 0)
    group_out.location = (400, 0)

    for item in target_group.interface.items_tree:
        if item.item_type == "SOCKET":
            if item.in_out == "INPUT":
                wrapper_group.links.new(
                    group_in.outputs[item.identifier],
                    target_node.inputs[item.identifier],
                )
            elif item.in_out == "OUTPUT":
                if item.identifier not in wrapper_group.interface.items_tree:
                    wrapper_group.interface.new_socket(
                        name=item.name, in_out="OUTPUT", socket_type=item.socket_type
                    )
                wrapper_group.links.new(
                    target_node.outputs[item.identifier],
                    group_out.inputs[item.identifier],
                )

    for item in wrapper_group.interface.items_tree:
        if item.socket_type == "NodeSocketMenu":
            socket_id = item.identifier
            defVal = defVals[socket_id]
            if socket_id in mod.keys():
                del mod[socket_id]
            try:
                item.default_value = defVal
            except Exception as _:
                pass

    mod.show_viewport = mod.show_viewport
    return mod


def get_asset_nodegroup(group_name):
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]

    search_locations = []
    if bpy.data.filepath:
        current_dir = Path(bpy.data.filepath).parent
        search_locations.append((current_dir, "*.blend"))

    try:
        addon_dir = Path(__file__).parent.resolve()
        search_locations.append((addon_dir, "*.blend"))
    except (NameError, FileNotFoundError):
        pass

    prefs = bpy.context.preferences
    for asset_library in prefs.filepaths.asset_libraries:
        library_path = Path(asset_library.path)
        search_locations.append((library_path, "**/*.blend"))

    checked_files = set()
    if bpy.data.filepath:
        checked_files.add(str(Path(bpy.data.filepath).resolve()))

    for root_path, pattern in search_locations:
        if not root_path.exists():
            continue
        for blend_file in root_path.glob(pattern):
            blend_path_str = str(blend_file.resolve())
            if blend_path_str in checked_files:
                continue
            checked_files.add(blend_path_str)
            try:
                with bpy.data.libraries.load(blend_path_str, assets_only=True) as (
                    data_from,
                    data_to,
                ):
                    if group_name in data_from.node_groups:
                        data_to.node_groups = [group_name]
                if data_to.node_groups:
                    return data_to.node_groups[0]
            except Exception as e:
                print(f"Could not read {blend_path_str}: {e}")

    print(f"Target node group '{group_name}' not found.")
    return None


import gpu
from gpu_extras.batch import batch_for_shader
import mathutils


def draw_callback_px(self, context):
    if not self.mouse_loc_3d:
        return
    try:
        shader = gpu.shader.from_builtin("POINT_UNIFORM_COLOR")
        batch = batch_for_shader(shader, "POINTS", {"pos": [self.mouse_loc_3d]})
        shader.bind()
        shader.uniform_float("color", (1.0, 0.5, 0.0, 1.0))
        gpu.state.point_size_set(10)
        gpu.state.blend_set("ALPHA")
        batch.draw(shader)
        gpu.state.point_size_set(1)
        gpu.state.blend_set("NONE")
    except Exception as e:
        print(f"Draw Error: {e}")


def apply_snapping(context, loc, region, rv3d):
    """
    Apply snapping with adaptive grid scaling.
    """
    if not context.tool_settings.use_snap:
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


class MOUSE_OT_draw_mesh_line(Operator):
    bl_idname = "mouse.draw_mesh_line"
    bl_label = "Draw Mesh Line"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        self.obj = None
        self.start_point = None
        self.drawing = False
        self._handle = None
        self.mouse_loc_3d = None
        self.last_hit = None  # Store (hit, loc, normal, index, obj, matrix)

        if context.area.type == "VIEW_3D":
            self.get_location(context, event)
            args = (self, context)
            self._handle = bpy.types.SpaceView3D.draw_handler_add(
                draw_callback_px, args, "WINDOW", "POST_VIEW"
            )
            self.report(
                {"INFO"}, "Click to set start point. Hold Ctrl to snap. Esc to Cancel."
            )
            context.window_manager.modal_handler_add(self)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        else:
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

        depsgraph = context.view_layer.depsgraph
        scene = context.scene
        hit, loc, normal, index, obj, matrix = scene.ray_cast(
            depsgraph, ray_origin, view_vector
        )

        final_loc = None

        if hit:
            # Store hit info for feature use (e.g. alignment)
            self.last_hit = (hit, loc, normal, index, obj, matrix)

            # Vertex Snapping (Proximity Check)
            if (
                context.tool_settings.use_snap
                and "VERTEX" in context.tool_settings.snap_elements
            ):
                if obj.type == "MESH":
                    mw = obj.matrix_world
                    mwi = mw.inverted()
                    loc_local = mwi @ loc

                    if index is not None and index < len(obj.data.polygons):
                        poly = obj.data.polygons[index]
                        min_dist = 999999.0
                        nearest_v_co = None
                        for v_idx in poly.vertices:
                            v_co = obj.data.vertices[v_idx].co
                            dist = (v_co - loc_local).length
                            if dist < min_dist:
                                min_dist = dist
                                nearest_v_co = v_co

                        if nearest_v_co:
                            world_v_co = mw @ nearest_v_co
                            screen_pos = view3d_utils.location_3d_to_region_2d(
                                region, rv3d, world_v_co
                            )
                            if screen_pos:
                                dist_px = (
                                    mathutils.Vector(screen_pos)
                                    - mathutils.Vector(coord)
                                ).length
                                if dist_px < 20.0:
                                    final_loc = world_v_co

            if final_loc is None:
                final_loc = loc
        else:
            # Reset last_hit if we aim at void
            self.last_hit = None
            cursor_loc = scene.cursor.location
            final_loc = view3d_utils.region_2d_to_location_3d(
                region, rv3d, coord, cursor_loc
            )

        did_vert_snap = (final_loc != loc) if hit else False

        if not did_vert_snap:
            final_loc = apply_snapping(context, final_loc, region, rv3d)

        self.mouse_loc_3d = final_loc
        return final_loc

    def create_line_object(self, context, loc):
        mesh = bpy.data.meshes.new("MeshLine")
        self.obj = bpy.data.objects.new("MeshLine", mesh)
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

    def cancel_op(self, context):
        if self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        if self.obj:
            bpy.data.objects.remove(self.obj, do_unlink=True)
        context.area.tag_redraw()

    def get_rotation_target(self):
        """Helper to find the modifier and the specific rotation input identifier."""
        if not self.obj:
            return None, None, None

        mod = None
        for m in self.obj.modifiers:
            if m.type == "NODES" and "Wrap" in m.name:
                mod = m
                break
        
        if mod and mod.node_group:
             for item in mod.node_group.interface.items_tree:
                 if item.item_type == "SOCKET" and item.in_out == "INPUT":
                     if "rotation" in item.name.lower():
                         if item.socket_type in {'NodeSocketInt', 'NodeSocketFloat', 'NodeSocketIntUnsigned', 'NodeSocketFloatAngle'}:
                             return mod, item.identifier, item.name
        return None, None, None

    def update_viewport(self, context, mod):
        """Force immediate visual update."""
        mod.show_viewport = False
        mod.show_viewport = True
        context.view_layer.update()
        context.area.tag_redraw()

    def adjust_rotation(self, context, step):
        mod, target_identifier, name = self.get_rotation_target()
        if mod and target_identifier:
            try:
                current_val = mod.get(target_identifier)
                if isinstance(current_val, (int, float)):
                    new_val = int(round(current_val + step))
                    mod[target_identifier] = new_val
                    self.report({"INFO"}, f"Rotation: {new_val}°")
                    self.update_viewport(context, mod)
            except Exception as e:
                print(f"Failed to adjust rotation: {e}")

    def align_to_geometry(self, context):
        if not self.last_hit or not self.obj:
            return

        hit, loc, normal, index, obj, matrix = self.last_hit

        # 1. Get Line Vector (Tangent)
        v0 = self.obj.matrix_world @ self.obj.data.vertices[0].co
        v1 = self.obj.matrix_world @ self.obj.data.vertices[1].co
        
        diff = v1 - v0
        if diff.length < 0.0001:
            return
            
        tangent = diff.normalized()
        
        # 2. Compute Reference Normal (Z-up projected)
        z_axis = mathutils.Vector((0, 0, 1))
        
        if abs(tangent.dot(z_axis)) > 0.9999: 
            ref_normal = mathutils.Vector((1, 0, 0)) 
        else:
            ref_normal = (z_axis - (z_axis.dot(tangent) * tangent)).normalized()
            
        # 3. Project Target Vector (Surface Tangent)
        target_normal = normal
        face_tangent = target_normal.cross(tangent)
        target_proj = face_tangent 
        
        rot_val = 0
        if target_proj.length > 0.001:
            target_proj.normalize()
            
            # 4. Calculate Signed Angle
            angle_rad = ref_normal.angle(target_proj)
            cross = ref_normal.cross(target_proj)
            if cross.dot(tangent) < 0:
                angle_rad = -angle_rad
                
            rotation_degrees = math.degrees(angle_rad)
            rot_val = int(round(rotation_degrees))
        
        # 5. Apply to Modifier
        mod, target_identifier, name = self.get_rotation_target()
            
        if target_identifier:
            try:
                current_val = mod.get(target_identifier)
                final_val = rot_val
                
                # Toggle Logic
                if isinstance(current_val, (int, float)):
                    current_int = int(round(current_val))
                    if current_int == rot_val:
                        final_val = rot_val + 180
                    elif current_int == rot_val - 180: # Just in case
                        final_val = rot_val
                    elif current_int == rot_val + 180:
                        final_val = rot_val

                mod[target_identifier] = final_val
                self.report({"INFO"}, f"Aligned to {name}: {final_val}°")
                self.update_viewport(context, mod)
                
            except Exception as e:
                print(f"Failed to set modifier prop: {e}")
                self.report({"WARNING"}, f"Could not set {name}")
        else:
            self.report({"WARNING"}, "No Integer/Float 'Rotation' input found")

    def modal(self, context, event):
        context.area.tag_redraw()

        # Tool Watch
        try:
            active_tool = context.workspace.tools.from_space_view3d_mode(context.mode)
            if active_tool and active_tool.idname != "my_tool.mesh_line":
                self.cancel_op(context)
                return {"CANCELLED"}
        except Exception:
            pass

        # Area check
        area = context.area
        if not (
            area.x <= event.mouse_x <= area.x + area.width
            and area.y <= event.mouse_y <= area.y + area.height
        ):
            self.mouse_loc_3d = None
            return {"PASS_THROUGH"}

        if not self.drawing:
            for region in context.area.regions:
                if region.type != "WINDOW":
                    if (
                        region.x <= event.mouse_x <= region.x + region.width
                        and region.y <= event.mouse_y <= region.y + region.height
                    ):
                        self.mouse_loc_3d = None
                        return {"PASS_THROUGH"}

        # Manual Rotation Adjustment (Ctrl + Scroll / +/-)
        if event.ctrl and self.drawing:
             if event.type in {'WHEELUPMOUSE', 'NUMPAD_PLUS'} and event.value == 'PRESS':
                  self.adjust_rotation(context, 5)
                  return {"RUNNING_MODAL"}
             elif event.type in {'WHEELDOWNMOUSE', 'NUMPAD_MINUS'} and event.value == 'PRESS':
                  self.adjust_rotation(context, -5)
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
                    self.create_line_object(context, loc)
                    self.drawing = True
                    if self._handle:
                        bpy.types.SpaceView3D.draw_handler_remove(
                            self._handle, "WINDOW"
                        )
                        self._handle = None
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


class MeshLineTool(WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = "my_tool.mesh_line"
    bl_label = "Mesh Line"
    bl_description = "Draw a mesh line by clicking start and end points"
    bl_icon = "ops.mesh.primitive_cube_add"
    bl_widget = None
    bl_keymap = (("mouse.draw_mesh_line", {"type": "MOUSEMOVE", "value": "ANY"}, None),)


def draw_settings(context, layout, tool):
    pass


classes = (MOUSE_OT_draw_mesh_line,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.utils.register_tool(MeshLineTool, separator=True)


def unregister():
    bpy.utils.unregister_tool(MeshLineTool)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
