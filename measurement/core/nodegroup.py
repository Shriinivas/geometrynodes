# Node group utilities for geometry nodes

import bpy
from pathlib import Path


def create_wrapper_modifier(obj, target_group):
    """Create a modifier for a geometry node group."""
    target_group_name = target_group.name

    if not obj or obj.type not in {"MESH", "CURVE", "POINTCLOUD", "VOLUME"}:
        print("Error: Select a valid geometry object.")
        return None

    # Use Wrap_ prefix to identify measurement modifiers
    mod = obj.modifiers.new(name=f"Wrap_{target_group_name}", type="NODES")
    mod.node_group = target_group

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
