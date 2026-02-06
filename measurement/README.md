# Measurement Tools for Blender

This package provides utility tools for measuring distances and angles in the Blender viewport using procedural geometry nodes. It can be used either as a Python addon or as a library of Geometry Node assets.

## Installation

1.  Download `measurement.zip` from the **[Latest Release](../releases/latest)** assets.
2.  Open Blender and go to **Edit > Preferences > Add-ons**.
3.  Click **Install...** and select the zip file (or pointing to the folder if manual).
4.  Enable the **Measure Tools** addon.

## Features

### Addon Usage

Once enabled, two new tools appear in the **Toolbar** (T-panel) in the 3D Viewport (Object Mode).

#### 📏 Distance Measurement
*   **Click two points** to measure the distance between them.
*   The tool creates a new object with a procedural line and specific styling modifiers.
*   **Align to Surface (`E`)**: Automatically aligns the measurement text and Rotation to the underlying surface normal/tangent under the cursor.

#### 📐 Angle Measurement
*   **Click three points** to define an angle (Vertex A → Apex B → Vertex C).
*   Visualizes the angle arc and value in degrees.
*   **Undo Point (`Backspace`)**: Undo the last placed point during creation.

#### Controls & Shortcuts

| Action | Shortcut | Tool | Description |
| :--- | :--- | :--- | :--- |
| **Set Point** | `LMB` | Both | Place start/end/vertex points |
| **Cancel** | `Esc` / `RMB` | Both | Cancel current operation |
| **Align** | `E` | Distance | Align measurement to surface geometry |
| **Undo Point** | `Backspace` | Angle | Remove the last placed point |
| **Snap** | `Ctrl` (Hold) | Both | Snap to Grid / Vertices / Edge Midpoints (Orange Marker indicates snap point) |
| **Toggle Help** | `Ctrl` + `Alt` + `H` | Both | Show/Hide the help text overlay |

#### Parameter Adjustments (Scroll Wheel)

Adjust styling and offsets interactively while drawing or editing:

| Modifier | Parameter | Tool | Effect |
| :--- | :--- | :--- | :--- |
| **Ctrl + Scroll** | Rotation | Distance | Rotates the measurement plane |
| **Ctrl + Scroll** | Radius | Angle | Adjusts the arc radius |
| **Shift + Scroll** | Text Rotation | Both | Rotates the text label in 5° increments |
| **Alt + Scroll** | Offset | Both | Offsets the measurement from the points |

### Customization (Modifier Panel)

After creating a measurement, select the object and adjust detailed settings in the **Modifier Properties** panel:
*   **Output Type**: Toggle between **Mesh** and **Grease Pencil** rendering.
*   **Precision & Units**: Set decimal places and display units (Meters, Degrees, etc.).
*   **Text & Styling**: Adjust Text Size, Rotation, and Flip direction.
*   **Line Geometry**: Twist Line Thickness, Arrowhead size, and Dot radius.
*   **Colors**: Customize visualization colors for lines, text, and markers.

### Manual Editing & Asset Usage

All measurement objects are standard meshes. You can enter **Edit Mode** and move vertices to adjust the measurement points manually. This works for tool-created objects as well as assets:

#### 1. Geometry Node Groups
Drag and drop **"Distance Measurement"** or **"Angle Measurement"** node groups onto any existing mesh line or geometry to apply the measurement visualization.

#### 2. Object Assets
Drag and drop the **"Distance Measurement"** or **"Angle Measurement"** objects directly into the viewport.
*   **Make Local**: Select the object and go to **Object > Relations > Make Local > All**.
*   **Edit**: You can then edit the object (e.g. move vertices) to define the measurement points.

## Configuration including overlay position

Go to **Edit > Preferences > Add-ons > Measure Tools** to:
*   Toggle the **Help Overlay** visibility by default.
*   Adjust the **X / Y Position** of the help text (default: Bottom-Left).

## Notes

*   **Mode Support**: The addon tools are designed for **Object Mode**.
*   **Dependencies**: The addon relies on `measurement.blend` being present in the addon directory to load the node groups.
