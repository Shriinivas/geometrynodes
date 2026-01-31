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



import gpu
from gpu_extras.batch import batch_for_shader
import mathutils


def draw_callback_px(self, context):
    if not self.mouse_loc_3d:
        return
    
    try:
        # Use POINT_UNIFORM_COLOR for 3D points in Blender 4.0+
        shader = gpu.shader.from_builtin('POINT_UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'POINTS', {"pos": [self.mouse_loc_3d]})
        
        shader.bind()
        shader.uniform_float("color", (1.0, 0.5, 0.0, 1.0)) # Orange
        
        # Ensure point size is set
        gpu.state.point_size_set(10)
        
        # Enable blending
        gpu.state.blend_set('ALPHA')
        
        batch.draw(shader)
        
        # Restore state defaults
        gpu.state.point_size_set(1)
        gpu.state.blend_set('NONE')
    except Exception as e:
        print(f"Draw Error: {e}")

def apply_snapping(context, loc, ignore_objects=None):
    """
    Apply snapping based on scene settings.
    Returns snapped location.
    """
    if not context.tool_settings.use_snap:
        return loc

    snap_elements = context.tool_settings.snap_elements
    # Snap elements is a set in 4.0+, or checking individual flags
    # In 4.0+ it's a set like {'INCREMENT', 'VERTEX', ...}
    
    # 1. Increment (Grid) Snapping
    if 'INCREMENT' in snap_elements:
        # Simple rounding to nearest 1.0 or user grid
        # For simplicity, assuming 1.0 unit or default grid
        grid_size = 1.0 
        # Ideally check context.space_data.overlay.grid_scale if available, 
        # but unit settings are safer
        if context.scene.unit_settings.system != 'NONE':
             grid_size = 1.0 * context.scene.unit_settings.scale_length
        
        loc = mathutils.Vector((
            round(loc.x / grid_size) * grid_size,
            round(loc.y / grid_size) * grid_size,
            round(loc.z / grid_size) * grid_size
        ))
        
    # 2. Vertex Snapping
    # We only snap to vertex if we hit an object (implemented via raycast in get_location)
    # If we didn't hit an object, vertex snap is irrelevant (or we'd need to project to world)
    # But get_location performs the raycast.
    
    # We need access to the hit object to snap to its vertices.
    # So we'll move the vertex snapping logic inside the Operator where we have the hit info.
    
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
        
        if context.area.type == "VIEW_3D":
            # Initial location check to update marker position
            # But do NOT set start_point yet. We enter "Hover" phase.
            self.get_location(context, event)
            
             # Register draw handler
            args = (self, context)
            self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, args, 'WINDOW', 'POST_VIEW')
            
            # Start in "Wait for Start" mode (Hover)
            self.report({'INFO'}, "Click to set start point. Hold Ctrl to snap (if enabled). Esc to Cancel.")
            context.window_manager.modal_handler_add(self)
            
            # Force a redraw so marker appears immediately if mouse is in view
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        else:
            self.report({"WARNING"}, "View3D not found, cannot run operator")
            return {"CANCELLED"}
    
    def apply_vertex_snapping(self, context, loc, hit_obj):
        if not context.tool_settings.use_snap or 'VERTEX' not in context.tool_settings.snap_elements:
            return loc
            
        if not hit_obj or hit_obj.type != 'MESH':
            return loc
            
        # Transform loc to local space
        mw = hit_obj.matrix_world
        mwi = mw.inverted()
        loc_local = mwi @ loc
        
        # Find nearest vertex
        # closest_point_on_mesh finds surface point, not vertex.
        # But we can iterate vertices? No, too slow for python without KDTree.
        # KDTree build is heavy for every frame.
        # Fallback: simple dist check on vertices? No, meshes can be huge.
        # Smart trick: closest_point_on_mesh gives us a location. 
        # If we are strictly snapping to VERTEX, we might need to rely on kdtree 
        # or Blender's internal snap if we could call it (we can't easily).
        # Actually `obj.closest_point_on_mesh` returns (result, location, normal, index).
        # But it's for surface.
        
        # Let's try KDTree from bmesh (built once?)
        # For a "simple" tool, maybe skip complex KDTree unless user really needs it.
        # But user asked for it. 
        # Optimization: Build KDTree only on first hover over an object?
        # Let's just implement Increment/Grid for now which covers 90% of use cases 
        # and simple surface snapping (implied by raycast).
        # If user strictly wants VERTEX snap, we can use a small heuristic:
        # Snap to the vertices of the *face* we hit?
        pass # To be implemented if surface raycast isn't enough
        
        return loc

    def get_location(self, context, event):
        scene = context.scene
        region = context.region
        rv3d = context.region_data
        
        # Check if we are in a valid 3D view region
        if region.type != 'WINDOW' or not rv3d:
            # If invokee from UI (button), we might need to find the specific window region
            # But simpler to just return None and wait for MOUSEMOVE in the viewport
            return None
            
        coord = event.mouse_region_x, event.mouse_region_y
        
        self.mouse_loc_3d = None # Reset

        # Get the ray from the viewport
        try:
            view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
            ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        except Exception:
            return None

        # Raycast into the scene
        depsgraph = context.view_layer.depsgraph
        hit, loc, normal, index, obj, matrix = scene.ray_cast(
            depsgraph, ray_origin, view_vector
        )

        final_loc = None
        
        if hit:
            # Vertex Snapping Logic
            if context.tool_settings.use_snap and 'VERTEX' in context.tool_settings.snap_elements:
                 if obj.type == 'MESH':
                    # Transform ray intersect to local
                    mw = obj.matrix_world
                    mwi = mw.inverted()
                    loc_local = mwi @ loc
                    
                    # Find nearest vertex efficiently-ish
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
                              # Check screen space distance to avoid aggressive snapping
                              world_v_co = mw @ nearest_v_co
                              screen_pos = view3d_utils.location_3d_to_region_2d(region, rv3d, world_v_co)
                              
                              if screen_pos:
                                   # Calculate 2D distance
                                   m_coord = mathutils.Vector(coord)
                                   s_coord = mathutils.Vector(screen_pos)
                                   dist_px = (s_coord - m_coord).length
                                   
                                   # Threshold: 20 pixels (typical snapping feel)
                                   if dist_px < 20.0:
                                        final_loc = world_v_co
            
            if final_loc is None:
                 final_loc = loc
        else:
            # fallback
            cursor_loc = scene.cursor.location
            final_loc = view3d_utils.region_2d_to_location_3d(
                region, rv3d, coord, cursor_loc
            )
        
        # Apply Grid/Increment Snapping (global) if not vertex snapped
        did_vert_snap = (final_loc != loc) if hit else False
        
        if not did_vert_snap:
             final_loc = apply_snapping(context, final_loc)
             
        self.mouse_loc_3d = final_loc # Update for drawing
        return final_loc

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
        
    def cancel_op(self, context):
        if self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        if self.obj:
             bpy.data.objects.remove(self.obj, do_unlink=True)
        context.area.tag_redraw()

    def modal(self, context, event):
        context.area.tag_redraw()
        
        # 0. Check if mouse is inside the 3D View Area at all
        # This allows interacting with other Editors (Properties, Outliner, Timeline, etc.)
        area = context.area
        if not (area.x <= event.mouse_x <= area.x + area.width and
                area.y <= event.mouse_y <= area.y + area.height):
            self.mouse_loc_3d = None
            return {'PASS_THROUGH'}
        
        # 1. Pass through events if mouse is inside any UI region (Header, Toolbar, Sidebar)
        # We iterate all regions in the area. If mouse is in a non-WINDOW region, we pass through.
        # This handles overlapping regions (like floating panels) correctly.
        for region in context.area.regions:
            if region.type != 'WINDOW':
                if (region.x <= event.mouse_x <= region.x + region.width and 
                    region.y <= event.mouse_y <= region.y + region.height):
                    self.mouse_loc_3d = None
                    return {'PASS_THROUGH'}
            
        # 2. Allow Navigation and Zooming to pass through
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'NUMPAD_PLUS', 'NUMPAD_MINUS'}:
            return {'PASS_THROUGH'}

        if event.type == "MOUSEMOVE":
            # Always track location but allow pass-through so standard cursor behavior works?
            # Actually, standard behavior is to consume if we are the active tool doing something.
            # But let's keep it safe.
            loc = self.get_location(context, event)
            
            if self.drawing and self.obj:
                if loc:
                    inv = self.obj.matrix_world.inverted()
                    local_loc = inv @ loc
                    self.obj.data.vertices[1].co = local_loc
                    self.obj.data.update()
            
            # We consumed the move to update our state, but we can return PASS_THROUGH 
            # if we want hover-highlights on other objects to work. 
            # However, returning RUNNING_MODAL is standard implementation for capture.
            return {"RUNNING_MODAL"}

        elif event.type == "LEFTMOUSE" and event.value == "PRESS":
            # 3. Capture Click ONLY if inside Viewport (already checked above)
            if not self.drawing:
                 # Phase 1: Set Start Point
                 loc = self.get_location(context, event)
                 if loc:
                      self.start_point = loc
                      self.create_line_object(context, loc)
                      self.drawing = True
                      # Stop drawing the marker, now we have the object
                      if self._handle:
                           bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
                           self._handle = None
                 return {"RUNNING_MODAL"}
            else:
                 # Phase 2: Finish
                 return {"FINISHED"}

        elif event.type in {"RIGHTMOUSE", "ESC"}:
            self.cancel_op(context)
            return {"CANCELLED"}
        
        # 4. Pass through Keyboard events (Shortcuts like Shift+Tab) and Modifiers
        return {"PASS_THROUGH"}



class MeshLineTool(WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"

    bl_idname = "my_tool.mesh_line"
    bl_label = "Mesh Line"
    bl_description = "Draw a mesh line by clicking start and end points"
    bl_icon = "ops.mesh.primitive_cube_add"
    bl_widget = None
    bl_keymap = (
        ("mouse.draw_mesh_line", {"type": "MOUSEMOVE", "value": "ANY"}, None),
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
