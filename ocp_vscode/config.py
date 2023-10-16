#
# Copyright 2023 Bernhard Walter
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from enum import Enum

from .comms import send_command, send_data, get_port

__all__ = [
    "workspace_config",
    "combined_config",
    "set_viewer_config",
    "set_defaults",
    "reset_defaults",
    "get_default",
    "get_defaults",
    "status",
    "Camera",
    "Collapse",
    "check_deprecated",
]


class Camera(Enum):
    RESET = "reset"
    CENTER = "center"
    KEEP = "keep"


class Collapse(Enum):
    NONE = 0
    LEAVES = 1
    ALL = 2
    ROOT = 3


CONFIG_UI_KEYS = [
    "axes",
    "axes0",
    "black_edges",
    "grid",
    "ortho",
    "transparent",
    "explode",
    "ambient_intensity",
    "direct_intensity",
    "metalness",
    "roughness",
]

CONFIG_WORKSPACE_KEYS = CONFIG_UI_KEYS + [
    # viewer
    "collapse",
    "dark",
    "glass",
    "orbit_control",
    "ticks",
    "tools",
    "tree_width",
    "up",
    # mouse
    "pan_speed",
    "rotate_speed",
    "zoom_speed",
    # render settings
    "ambient_intensity",
    "direct_intensity",
    "metalness",
    "roughness",
    "angular_tolerance",
    "default_color",
    "default_edgecolor",
    "default_facecolor",
    "default_thickedgecolor",
    "default_vertexcolor",
    "default_opacity",
    "deviation",
]

CONFIG_CONTROL_KEYS = [
    "edge_accuracy",
    "debug",
    "helper_scale",
    "render_edges",
    "render_mates",
    "render_joints",
    "render_normals",
    "reset_camera",
    "timeit",
]

CONFIG_KEYS = CONFIG_WORKSPACE_KEYS + CONFIG_CONTROL_KEYS + ["zoom"]

CONFIG_SET_KEYS = [
    "axes",
    "axes0",
    "grid",
    "ortho",
    "transparent",
    "black_edges",
    "explode",
    "zoom",
    "position",
    "quaternion",
    "target",
    "default_edgecolor",
    "default_opacity",
    "ambient_intensity",
    "direct_intensity",
    "metalness",
    "roughness",
    "zoom_speed",
    "pan_speed",
    "rotate_speed",
    "glass",
    "tools",
    "tree_width",
    "collapse",
]

DEFAULTS = {
    "render_edges": True,
    "render_normals": False,
    "render_mates": False,
    "render_joints": False,
    "helper_scale": 1.0,
    "timeit": False,
    "reset_camera": Camera.RESET,
    "debug": False,
}


def set_viewer_config(
    axes=None,
    axes0=None,
    grid=None,
    ortho=None,
    transparent=None,
    black_edges=None,
    explode=None,
    zoom=None,
    position=None,
    quaternion=None,
    target=None,
    default_edgecolor=None,
    default_opacity=None,
    ambient_intensity=None,
    direct_intensity=None,
    metalness=None,
    roughness=None,
    zoom_speed=None,
    pan_speed=None,
    rotate_speed=None,
    glass=None,
    tools=None,
    tree_width=None,
    collapse=None,
    reset_camera=None,
    states=None,
):
    config = {k: v for k, v in locals().items() if v is not None}
    data = {
        "type": "ui",
        "config": config,
    }
    send_data(data)


def get_default(key):
    return DEFAULTS.get(key)


def get_defaults():
    return DEFAULTS


def set_defaults(
    glass=None,
    tools=None,
    tree_width=None,
    axes=None,
    axes0=None,
    grid=None,
    ortho=None,
    transparent=None,
    default_opacity=None,
    black_edges=None,
    orbit_control=None,
    collapse=None,
    ticks=None,
    up=None,
    explode=None,
    zoom=None,
    reset_camera=None,
    pan_speed=None,
    rotate_speed=None,
    zoom_speed=None,
    deviation=None,
    angular_tolerance=None,
    edge_accuracy=None,
    default_color=None,
    default_edgecolor=None,
    ambient_intensity=None,
    direct_intensity=None,
    metalness=None,
    roughness=None,
    render_edges=None,
    render_normals=None,
    render_mates=None,
    render_joints=None,
    helper_scale=None,
    mate_scale=None,  # DEPRECATED
    debug=None,
    timeit=None,
):
    """Set viewer defaults
    Keywords to configure the viewer:
    - UI
        glass:             Use glass mode where tree is an overlay over the cad object (default=False)
        tools:             Show tools (default=True)
        tree_width:        Width of the object tree (default=240)

    - Viewer
        axes:              Show axes (default=False)
        axes0:             Show axes at (0,0,0) (default=False)
        grid:              Show grid (default=False)
        ortho:             Use orthographic projections (default=True)
        transparent:       Show objects transparent (default=False)
        default_opacity:   Opacity value for transparent objects (default=0.5)
        black_edges:       Show edges in black color (default=False)
        orbit_control:     Mouse control use "orbit" control instead of "trackball" control (default=False)
        collapse:          Collapse.LEAVES: collapse all single leaf nodes,
                           Collapse.ROOT: expand root only,
                           Collapse.ALL: collapse all nodes,
                           Collapse.NONE: expand all nodes
                           (default=Collapse.LEAVES)
        ticks:             Hint for the number of ticks in both directions (default=10)
        up:                Use z-axis ('Z') or y-axis ('Y') as up direction for the camera (default="Z")
        explode:           Turn on explode mode (default=False)

        zoom:              Zoom factor of view (default=1.0)
        position:          Camera position
        quaternion:        Camera orientation as quaternion
        target:            Camera look at target
        reset_camera:      Camera.RESET: Reset camera position, rotation, toom and target
                           Camera.CENTER: Keep camera position, rotation, toom, but look at center
                           Camera.KEEP: Keep camera position, rotation, toom, and target
                           (default=Camera.RESET)
        pan_speed:         Speed of mouse panning (default=1)
        rotate_speed:      Speed of mouse rotate (default=1)
        zoom_speed:        Speed of mouse zoom (default=1)

    - Renderer
        deviation:         Shapes: Deviation from linear deflection value (default=0.1)
        angular_tolerance: Shapes: Angular deflection in radians for tessellation (default=0.2)
        edge_accuracy:     Edges: Precision of edge discretization (default: mesh quality / 100)

        default_color:     Default mesh color (default=(232, 176, 36))
        default_edgecolor: Default mesh color (default=(128, 128, 128))
        ambient_intensity: Intensity of ambient light (default=1.00)
        direct_intensity:  Intensity of direct light (default=1.10)
        metalness:         Metalness property of the default material (default=0.30)
        roughness:         Roughness property of the default material (default=0.65)

        render_edges:      Render edges  (default=True)
        render_normals:    Render normals (default=False)
        render_mates:      Render mates for MAssemblies (default=False)
        render_joints:     Render mates for MAssemblies (default=False)
        helper_scale:      Scale of rendered helpers (locations, axis, mates for MAssemblies) (default=1)

    - Debug
        debug:             Show debug statements to the VS Code browser console (default=False)
        timeit:            Show timing information from level 0-3 (default=False)
    """

    kwargs = {k: v for k, v in locals().items() if v is not None}

    kwargs = check_deprecated(kwargs)

    global DEFAULTS
    for key, value in kwargs.items():
        if key in CONFIG_KEYS:
            DEFAULTS[key] = value
        else:
            print(f"'{key}' is an unkown config, ignored!")

    set_viewer_config(**{k: v for k, v in kwargs.items() if k in CONFIG_SET_KEYS})


def preset(key, value):
    return get_default(key) if value is None else value


def ui_filter(conf):
    return {k: v for k, v in conf.items() if k in CONFIG_UI_KEYS}


def status(port=None, debug=False):
    if port is None:
        port = get_port()
    try:
        response = send_command("status", port=port)
        if debug:
            return response.get("_debugStarted", False)
        else:
            return response.get("text", {})

    except Exception as ex:
        raise RuntimeError(
            "Cannot access viewer status. Is the viewer running?\n" + str(ex.args)
        )

global_config = {}
global_config.update(DEFAULTS)
global_config.update({key: None for key in CONFIG_KEYS})
global_config['collapse'] = Collapse.NONE
global_config['explode'] = True

def workspace_config(port=None):
    return global_config
    if port is None:
        port = get_port()
    try:
        conf = send_command("config", port=port)
        mapping = {
            "none": Collapse.NONE,
            "leaves": Collapse.LEAVES,
            "all": Collapse.ALL,
            "root": Collapse.ROOT,
            "E": Collapse.NONE,
            "1": Collapse.LEAVES,
            "C": Collapse.ALL,
            "R": Collapse.ROOT,
        }
        conf["collapse"] = mapping[conf["collapse"]]
        return conf

    except Exception as ex:
        raise RuntimeError(
            "Cannot access viewer config. Is the viewer running?\n" + str(ex.args)
        )


def combined_config(port=None, use_status=True):
    return global_config
    if port is None:
        port = get_port()

    try:
        wspace_config = workspace_config(port)
        wspace_status = status(port)

    except Exception as ex:
        raise RuntimeError(
            "Cannot access viewer config. Is the viewer running?\n" + str(ex.args)
        )

    if use_status and wspace_config["_splash"]:
        del wspace_config["_splash"]
        wspace_config["axes"] = False
        wspace_config["axes0"] = True
        wspace_config["grid"] = [True, False, False]
        wspace_config["ortho"] = False
        wspace_config["transparent"] = False
        wspace_config["black_edges"] = False

    wspace_config.update(DEFAULTS)
    if use_status:
        wspace_config.update(ui_filter(wspace_status))
    return wspace_config


def get_changed_config(key=None):
    wspace_config = workspace_config()
    wspace_config.update(DEFAULTS)
    if key is None:
        return wspace_config
    else:
        return wspace_config.get(key)


def reset_defaults():
    """Reset defaults not given in workspace config"""
    global DEFAULTS

    config = {
        key: value
        for key, value in workspace_config().items()
        if key in CONFIG_SET_KEYS
    }
    config["reset_camera"] = Camera.RESET

    set_viewer_config(**config)

    if config.get("transparent") is not None:
        set_viewer_config(transparent=config["transparent"])

    DEFAULTS = {
        "render_edges": True,
        "render_normals": False,
        "render_mates": False,
        "render_joints": False,
        "helper_scale": 1.0,
        "timeit": False,
        "reset_camera": Camera.RESET,
        "debug": False,
    }


def check_deprecated(kwargs):
    if kwargs.get("mate_scale") is not None:
        print("\nmate_scale is deprecated, use helper_scale instead\n")
        kwargs["helper_scale"] = kwargs["mate_scale"]
        del kwargs["mate_scale"]

    if kwargs.get("reset_camera") == True:
        print(
            "\n'reset_camera=True' is deprecated, use 'reset_camera=Camera.RESET' instead\n"
        )
        kwargs["reset_camera"] = Camera.RESET

    if kwargs.get("reset_camera") == False:
        print(
            "\n'reset_camera=False' is deprecated, use 'reset_camera=Camera.CENTER' instead\n"
        )
        kwargs["reset_camera"] = Camera.CENTER

    if kwargs.get("collapse") == "C":
        print("\n'collapse=\"C\"' is deprecated, use 'collapse=Collapse.ALL' instead\n")
        kwargs["collapse"] = Collapse.ALL

    if kwargs.get("collapse") == "1" or kwargs.get("collapse") == 1:
        print(
            "\n'collapse=\"1\"' is deprecated, use 'collapse=Collapse.LEAVES' instead\n"
        )
        kwargs["collapse"] = Collapse.LEAVES

    if kwargs.get("collapse") == "R":
        print(
            "\n'collapse=\"R\"' is deprecated, use 'collapse=Collapse.ROOT' instead\n"
        )
        kwargs["collapse"] = Collapse.ROOT

    if kwargs.get("collapse") == "E":
        print(
            "\n'collapse=\"E\"' is deprecated, use 'collapse=Collapse.NONE' instead\n"
        )
        kwargs["collapse"] = Collapse.NONE

    return kwargs
