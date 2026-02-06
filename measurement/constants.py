# Measurement Tools Addon - Constants and Registry

# Centralized keymap registry: all keybindings in one place
# Each entry: key, modifiers, description, tools (list of tool types)
# handler/param fields are optional for implementation reference
KEYMAP_REGISTRY = [
    # Mouse actions
    {"key": "LMB", "mods": "", "desc": "Set start point", "tools": ["distance"], "phase": "idle"},
    {"key": "LMB", "mods": "", "desc": "Confirm endpoint", "tools": ["distance"], "phase": "drawing"},
    {"key": "LMB", "mods": "", "desc": "Set vertex", "tools": ["angle"], "phase": "idle"},
    {"key": "LMB", "mods": "", "desc": "Set next vertex", "tools": ["angle"], "phase": "drawing"},
    {"key": "Mouse Move", "mods": "", "desc": "Preview position", "tools": ["distance", "angle"]},
    
    # Keyboard - common
    {"key": "Esc / RMB", "mods": "", "desc": "Cancel", "tools": ["distance", "angle"]},
    {"key": "H", "mods": "Ctrl+Alt", "desc": "Toggle help", "tools": ["distance", "angle"], "handler": "toggle_help"},
    
    # Keyboard - distance specific
    {"key": "E", "mods": "", "desc": "Align to surface", "tools": ["distance"], "handler": "align_to_geometry"},
    
    # Keyboard - angle specific
    {"key": "Backspace", "mods": "", "desc": "Remove last point", "tools": ["angle"], "handler": "remove_point"},
    
    # Scroll bindings - Distance
    {"key": "Scroll", "mods": "Ctrl", "desc": "Adjust Rotation", "tools": ["distance"], "param": ("Rotation", 5, "INT")},
    {"key": "Scroll", "mods": "Shift", "desc": "Adjust Text Rotation", "tools": ["distance"], "param": ("Text Rotation", 5, "INT")},
    {"key": "Scroll", "mods": "Alt", "desc": "Adjust Offset", "tools": ["distance"], "param": ("Offset", 0.01, "FLOAT")},
    
    # Scroll bindings - Angle
    {"key": "Scroll", "mods": "Ctrl", "desc": "Adjust Radius", "tools": ["angle"], "param": ("Radius", 0.01, "FLOAT")},
    {"key": "Scroll", "mods": "Shift", "desc": "Adjust Text Rotation", "tools": ["angle"], "param": ("Text Rotation", 5, "INT")},
    {"key": "Scroll", "mods": "Alt", "desc": "Adjust Offset", "tools": ["angle"], "param": ("Offset", 0.01, "FLOAT")},
]


# Socket type sets for parameter validation
FLOAT_TYPES = {
    "NodeSocketFloat",
    "NodeSocketFloatDistance",
    "NodeSocketFloatFactor",
}

INT_TYPES = {
    "NodeSocketInt",
    "NodeSocketFloat",
    "NodeSocketIntUnsigned",
    "NodeSocketFloatAngle",
}


def get_bindings_for_tool(tool_type):
    """Filter registry for given tool type."""
    return [b for b in KEYMAP_REGISTRY if tool_type in b["tools"]]
