# Node group utilities for geometry nodes

import bpy
from pathlib import Path


def create_wrapper_modifier(obj, target_group):
    """Create a wrapper modifier for a geometry node group."""
    target_group_name = target_group.name

    if not obj or obj.type not in {"MESH", "CURVE", "POINTCLOUD", "VOLUME"}:
        print("Error: Select a valid geometry object.")
        return

    mod = obj.modifiers.new(name=f"Wrap_{target_group_name}", type="NODES")
    wrapper_group = bpy.data.node_groups.new(
        name=f"{target_group_name}", type="GeometryNodeTree"
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
                except Exception:
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
            except Exception:
                pass

    mod.show_viewport = mod.show_viewport
    return mod


def get_asset_nodegroup(group_name):
    """Load a node group from asset libraries."""
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]

    search_locations = []
    if bpy.data.filepath:
        current_dir = Path(bpy.data.filepath).parent
        search_locations.append((current_dir, "*.blend"))

    try:
        addon_dir = Path(__file__).parent.parent.resolve()
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
