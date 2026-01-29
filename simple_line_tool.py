bl_info = {
    "name": "Draw Mesh Line",
    "author": "Antigravity",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Toolbar",
    "description": "Draw a mesh line by clicking start and end points",
    "category": "Mesh",
}

import bpy
import bmesh
from bpy_extras import view3d_utils
from bpy.types import Operator, WorkSpaceTool
import traceback

from pathlib import Path


def create_wrapper_modifier(obj, target_group):
    # --- 1. Resolve Target Group ---
    target_group_name = target_group.name

    if not obj or obj.type not in {"MESH", "CURVE", "POINTCLOUD", "VOLUME"}:
        print("Error: Select a valid geometry object.")
        return

    # --- 2. Setup Modifier & Group ---
    mod = obj.modifiers.new(name=f"Wrap_{target_group_name}", type="NODES")
    wrapper_group = bpy.data.node_groups.new(
        name=f"Wrapper_{target_group_name}", type="GeometryNodeTree"
    )

    # We MUST define the interface before assigning it to the modifier
    nodes = wrapper_group.nodes
    nodes.clear()

    defVals = {}
    # --- 3. Build Wrapper Interface from Target ---
    for item in target_group.interface.items_tree:
        if item.item_type == "SOCKET" and item.in_out == "INPUT":
            new_socket = wrapper_group.interface.new_socket(
                name=item.name, in_out="INPUT", socket_type=item.socket_type
            )

            # Replicate Menu Items
            if item.socket_type == "NodeSocketMenu":
                source_items = getattr(item, "items", None)
                if source_items and not callable(source_items):
                    for menu_item in source_items:
                        new_socket.items.new(name=menu_item.name)

            # Sync Default Values & Limits
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

    # --- 4. Assign Group to Modifier ---
    mod.node_group = wrapper_group

    # --- 5. Internal Node Setup & Linking ---
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
    # 1. Quick check: Is it already in the current file?
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]

    # Collect locations to search
    search_locations = []

    # 2. Current Folder (if file is saved)
    if bpy.data.filepath:
        current_dir = Path(bpy.data.filepath).parent
        # Search current directory (non-recursive for safety)
        search_locations.append((current_dir, "*.blend"))

    # 3. Addon Folder (Directory of this script)
    try:
        # Resolve to handle potential symlinks or relative paths
        addon_dir = Path(__file__).parent.resolve()
        search_locations.append((addon_dir, "*.blend"))
    except (NameError, FileNotFoundError):
        pass

    # 4. Asset Libraries
    prefs = bpy.context.preferences
    for asset_library in prefs.filepaths.asset_libraries:
        library_path = Path(asset_library.path)
        # Search asset libraries (recursive)
        search_locations.append((library_path, "**/*.blend"))

    # Track checked files to avoid duplicates
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
                        # We must exit the context manager for data_to to be populated with objects

                # Check data_to outside the with block
                if data_to.node_groups:
                    return data_to.node_groups[0]

            except Exception as e:
                print(f"Could not read {blend_path_str}: {e}")

    print(f"Target node group '{group_name}' not found in any search location.")
    return None


class MOUSE_OT_draw_mesh_line(Operator):
    bl_idname = "mouse.draw_mesh_line"
    bl_label = "Draw Mesh Line"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        self.obj = None
        self.start_point = None
        self.drawing = False

        if context.area.type == "VIEW_3D":
            # Handle the first click immediately
            loc = self.get_location(context, event)
            if loc:
                self.start_point = loc
                self.create_line_object(context, loc)
                self.drawing = True
                context.window_manager.modal_handler_add(self)
                return {"RUNNING_MODAL"}
            else:
                return {"CANCELLED"}
        else:
            self.report({"WARNING"}, "View3D not found, cannot run operator")
            return {"CANCELLED"}

    def get_location(self, context, event):
        scene = context.scene
        region = context.region
        rv3d = context.region_data
        coord = event.mouse_region_x, event.mouse_region_y

        # Get the ray from the viewport
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)

        # Raycast into the scene
        # We need a depsgraph for raycasting
        depsgraph = context.view_layer.depsgraph
        hit, loc, normal, index, obj, matrix = scene.ray_cast(
            depsgraph, ray_origin, view_vector
        )

        if hit:
            return loc
        else:
            # If we didn't hit anything, project onto a plane at the 3D cursor's depth
            # or simply the plane passing through the cursor location orthogonal to view?
            # Let's try intersecting with the Z=0 plane (Global XY) for convenience if nothing is hit
            # Or use 3D Cursor location as a reference depth.

            # Simple fallback: Plane Z=0
            # return view3d_utils.region_2d_to_location_3d(region, rv3d, coord, (0,0,0))

            # Better fallback: use 3d cursor location
            cursor_loc = scene.cursor.location
            return view3d_utils.region_2d_to_location_3d(
                region, rv3d, coord, cursor_loc
            )

    def create_line_object(self, context, loc):
        # Create mesh and object
        mesh = bpy.data.meshes.new("MeshLine")
        self.obj = bpy.data.objects.new("MeshLine", mesh)

        # Link to active collection
        context.collection.objects.link(self.obj)

        # Create vertices (both at start loc initially)
        bm = bmesh.new()
        v1 = bm.verts.new(loc)
        v2 = bm.verts.new(loc)
        bm.edges.new((v1, v2))
        bm.to_mesh(mesh)
        bm.free()

        # Select and make active
        bpy.ops.object.select_all(action="DESELECT")
        self.obj.select_set(True)
        target_group = get_asset_nodegroup("Distance Measurement")
        if target_group:
            create_wrapper_modifier(self.obj, target_group)
        else:
            self.report(
                {"WARNING"},
                "Node Group 'Distance Measurement' not found, line created without modifier.",
            )
        context.view_layer.objects.active = self.obj

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == "MOUSEMOVE":
            if self.drawing and self.obj:
                loc = self.get_location(context, event)
                if loc:
                    # Update second vertex (index 1)
                    # We need to transform the global loc to local if the object has transforms
                    # But newly created object is at identity, so global matches local (unless parented)
                    # For safety, let's just use global since we are setting co directly
                    inv = self.obj.matrix_world.inverted()
                    local_loc = inv @ loc
                    self.obj.data.vertices[1].co = local_loc
                    self.obj.data.update()

        elif event.type == "LEFTMOUSE" and event.value == "PRESS":
            # This handles the second click to finish
            if self.drawing:
                return {"FINISHED"}

            # Note: The first click is handled in invoke if triggered by keymap
            # But if we were just running modal, we might handle it here.
            # However, since we use the Tool system with keymap, 'invoke' catches the first click.

        elif event.type in {"RIGHTMOUSE", "ESC"}:
            if self.obj:
                bpy.data.objects.remove(self.obj, do_unlink=True)
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}


class MeshLineTool(WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"

    bl_idname = "my_tool.mesh_line"
    bl_label = "Mesh Line"
    bl_description = "Draw a mesh line by clicking start and end points"
    bl_icon = "ops.mesh.primitive_cube_add"
    bl_widget = None
    bl_keymap = (
        ("mouse.draw_mesh_line", {"type": "LEFTMOUSE", "value": "PRESS"}, None),
    )

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
