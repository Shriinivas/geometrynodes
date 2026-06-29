# Drawing utilities for measurement tools

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

from ..constants import get_bindings_for_tool


# Global list of registered draw handlers to prevent leaks during undo/redo/cancellation
_registered_handlers = []


def register_draw_handler(operator, callback, draw_type, region_type="WINDOW"):
    """Register a draw handler and track it globally."""
    args = (operator, bpy.context)
    handle = bpy.types.SpaceView3D.draw_handler_add(callback, args, region_type, draw_type)
    _registered_handlers.append({
        "operator": operator,
        "handle": handle,
        "type": region_type
    })
    return handle


def unregister_draw_handler(handle, region_type="WINDOW"):
    """Unregister a specific draw handler and remove it from tracking."""
    for item in _registered_handlers:
        if item["handle"] is handle:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(handle, region_type)
            except Exception:
                pass
            _registered_handlers.remove(item)
            break


def unregister_operator_handlers(operator):
    """Unregister all draw handlers associated with a specific operator."""
    to_remove = []
    for item in _registered_handlers:
        if item["operator"] is operator:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(item["handle"], item["type"])
            except Exception:
                pass
            to_remove.append(item)
    for item in to_remove:
        try:
            _registered_handlers.remove(item)
        except ValueError:
            pass


def cleanup_dead_handlers(operator):
    """Cleanup handlers for a dead operator reference."""
    unregister_operator_handlers(operator)


def draw_callback_px(self, context):
    """Draw cursor point indicator."""
    try:
        # Accessing bl_idname is guaranteed to raise ReferenceError if C++ operator is removed
        _ = self.bl_idname
    except ReferenceError:
        cleanup_dead_handlers(self)
        return
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


def draw_help_overlay(self, context):
    """Draw help text overlay showing keybindings for active tool."""
    try:
        # Accessing bl_idname is guaranteed to raise ReferenceError if C++ operator is removed
        _ = self.bl_idname
    except ReferenceError:
        cleanup_dead_handlers(self)
        return
    try:
        if not hasattr(self, 'tool_type') or not self.tool_type:
            return
    except ReferenceError:
        cleanup_dead_handlers(self)
        return
    
    # Get position settings from addon preferences
    prefs = context.preferences.addons.get("measurement")
    if prefs:
        prefs = prefs.preferences
        pos_x = prefs.help_pos_x
        pos_y = prefs.help_pos_y
        show_help = prefs.show_help_overlay
    else:
        pos_x = 20
        pos_y = 20  # Bottom-left default
        show_help = True
    
    if not show_help:
        return
    
    font_id = 0
    font_size = 14
    line_height = 22
    key_col_width = 130
    
    # Get bindings for current tool
    bindings = get_bindings_for_tool(self.tool_type)
    
    # Deduplicate entries with same key+mods (keep first occurrence)
    seen = set()
    unique_bindings = []
    for b in bindings:
        key_id = (b["key"], b["mods"])
        if key_id not in seen:
            seen.add(key_id)
            unique_bindings.append(b)
    
    # Calculate total height (draw from bottom up)
    total_lines = len(unique_bindings) + 2  # +2 for header and separator
    total_height = total_lines * line_height
    
    # Start position (bottom-left by default)
    y_start = pos_y + total_height
    
    # Draw header
    blf.size(font_id, font_size + 2)
    blf.color(font_id, 1.0, 0.8, 0.2, 1.0)  # Yellow/gold
    blf.position(font_id, pos_x, y_start, 0)
    title = f"{self.tool_type.title()} Measurement"
    blf.draw(font_id, title)
    
    # Draw separator line (using text)
    y = y_start - line_height * 1.2
    blf.size(font_id, font_size - 2)
    blf.color(font_id, 0.5, 0.5, 0.5, 1.0)
    blf.position(font_id, pos_x, y, 0)
    blf.draw(font_id, "─" * 20)
    
    # Draw bindings
    y -= line_height * 0.8
    blf.size(font_id, font_size)
    
    for binding in unique_bindings:
        # Format key text
        if binding["mods"]:
            key_text = f"{binding['mods']}+{binding['key']}"
        else:
            key_text = binding["key"]
        
        # Draw key (light blue)
        blf.color(font_id, 0.6, 0.85, 1.0, 1.0)
        blf.position(font_id, pos_x, y, 0)
        blf.draw(font_id, key_text)
        
        # Draw description (light gray)
        blf.color(font_id, 0.75, 0.75, 0.75, 1.0)
        blf.position(font_id, pos_x + key_col_width, y, 0)
        blf.draw(font_id, binding["desc"])
        
        y -= line_height
