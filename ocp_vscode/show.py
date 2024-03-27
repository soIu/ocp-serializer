"""Show CAD objects in Visual Studio Code"""

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

import re

from ocp_tessellate import PartGroup
from ocp_tessellate.convert import (
    tessellate_group,
    get_normal_len,
    combined_bb,
    to_assembly,
    mp_get_results,
    conv,
)
from ocp_tessellate.utils import numpy_to_buffer_json, Timer, Color
from ocp_tessellate.ocp_utils import (
    is_vector,
    is_topods_shape,
    is_topods_compound,
    is_cadquery,
    is_cadquery_assembly,
    is_cadquery_sketch,
    is_build123d,
    is_toploc_location,
    is_wrapped,
)

from ocp_tessellate.mp_tessellator import init_pool, keymap, close_pool
from ocp_tessellate.cad_objects import (
    OCP_PartGroup,
    OCP_Edges,
    OCP_Faces,
    OCP_Part,
    OCP_Vertices,
)
import ocp_tessellate.convert as oc

from .config import (
    preset,
    get_changed_config,
    workspace_config,
    combined_config,
    get_default,
    get_defaults,
    Camera,
    Collapse,
    check_deprecated,
)
from .comms import send_backend, send_data
from .colors import get_colormap, web_to_rgb, BaseColorMap

__all__ = ["show", "show_object", "reset_show", "show_all", "show_clear"]

OBJECTS = {"objs": [], "names": [], "colors": [], "alphas": []}

LAST_CALL = "other"


def _tessellate(
    *cad_objs, names=None, colors=None, alphas=None, progress=None, **kwargs
):
    if workspace_config().get("_splash"):
        conf = combined_config(use_status=False)
        reset_camera = Camera.RESET
    else:
        conf = combined_config(use_status=True)
        reset_camera = conf.get("reset_camera", Camera.RESET)

    conf["reset_camera"] = reset_camera.value

    collapse = conf.get("collapse", Collapse.LEAVES)
    conf["collapse"] = collapse.value

    if kwargs.get("default_facecolor") is not None:
        oc.FACE_COLOR = Color(kwargs["default_facecolor"]).percentage
        del kwargs["default_facecolor"]
    else:
        oc.FACE_COLOR = Color(conf["default_facecolor"]).percentage

    if kwargs.get("default_thickedgecolor") is not None:
        oc.THICK_EDGE_COLOR = Color(kwargs["default_thickedgecolor"]).percentage
        del kwargs["default_thickedgecolor"]
    else:
        oc.THICK_EDGE_COLOR = Color(conf["default_thickedgecolor"]).percentage

    if kwargs.get("default_vertexcolor") is not None:
        oc.VERTEX_COLOR = Color(kwargs["default_vertexcolor"]).percentage
        del kwargs["default_vertexcolor"]
    else:
        oc.VERTEX_COLOR = Color(conf["default_vertexcolor"]).percentage

    # only use clipping settings when reset_camera is not RESET
    if reset_camera == Camera.RESET or kwargs.get("reset_camera") == Camera.RESET:
        clip_defaults = {
            k: v for k, v in get_defaults().items() if k.startswith("clip")
        }
        if conf.get("clip_slider_0") is not None:
            del conf["clip_slider_0"]
        if conf.get("clip_slider_1") is not None:
            del conf["clip_slider_1"]
        if conf.get("clip_slider_2") is not None:
            del conf["clip_slider_2"]
        if conf.get("clip_normal_0") is not None:
            conf["clip_normal_0"] = [-1, 0, 0]
        if conf.get("clip_normal_1") is not None:
            conf["clip_normal_1"] = [0, -1, 0]
        if conf.get("clip_normal_2") is not None:
            conf["clip_normal_2"] = [0, 0, -1]
        if conf.get("clip_intersection") is not None:
            conf["clip_intersection"] = False
        if conf.get("clip_planes") is not None:
            conf["clip_planes"] = False
        if conf.get("clip_object_colors") is not None:
            conf["clip_object_colors"] = False

        conf.update(clip_defaults)

    timeit = preset("timeit", kwargs.get("timeit"))

    if timeit is None:
        timeit = False

    if progress is None:
        progress = Progress([c for c in "-+c"])

    with Timer(timeit, "", "to_assembly", 1):
        changed_config = get_changed_config()
        part_group = to_assembly(
            *cad_objs,
            names=names,
            colors=colors,
            alphas=alphas,
            render_mates=kwargs.get("render_mates", changed_config.get("render_mates")),
            render_joints=kwargs.get(
                "render_joints", changed_config.get("render_joints")
            ),
            helper_scale=kwargs.get("helper_scale", changed_config.get("helper_scale")),
            default_color=kwargs.get(
                "default_color", changed_config.get("default_color")
            ),
            show_parent=kwargs.get("show_parent", changed_config.get("show_parent")),
            show_sketch_local=kwargs.get(
                "show_sketch_local", changed_config.get("show_sketch_local")
            ),
            progress=progress,
        )

        if len(part_group.objects) == 1 and isinstance(
            part_group.objects[0], PartGroup
        ):
            part_group = part_group.objects[0]

    params = {
        k: v
        for k, v in conf.items()
        if not k
        in (
            "position",
            "rotation",
            "target",
            # controlled by VSCode panel size
            "cad_width",
            "height",
            # controlled by VSCode settings
            "tree_width",
            "theme",
        )
    }

    for k, v in kwargs.items():
        if k in ["cad_width", "height"]:
            print(
                f"Setting {k} cannot be set, it is determined by the VSCode panel size"
            )

        elif k in [
            "tree_width",
            "theme",
        ]:
            print(f"Setting {k} can only be set in VSCode config")

        elif v is not None:
            if k == "reset_camera" and params.get("_splash") is True:
                continue
            params[k] = v

    parallel = preset("parallel", params.get("parallel"))
    if parallel and not any(
        [isinstance(obj, OCP_PartGroup) for obj in part_group.objects]
    ):
        print("parallel only works for assemblies, setting it to False")
        parallel = False
        params["parallel"] = False

    if kwargs.get("debug") is not None and kwargs["debug"]:
        print("\ntessellation parameters:\n", params)

    with Timer(timeit, "", "tessellate", 1):
        if parallel:
            init_pool()
            keymap.reset()

        instances, shapes, states, mapping = tessellate_group(
            part_group, params, progress, params.get("timeit")
        )

        if parallel:
            instances, shapes = mp_get_results(instances, shapes, progress)
            close_pool()

    params["normal_len"] = get_normal_len(
        preset("render_normals", params.get("render_normals")),
        shapes,
        preset("deviation", params.get("deviation")),
    )

    with Timer(timeit, "", "bb", 1):
        bb = combined_bb(shapes).to_dict()

    # add global bounding box
    shapes["bb"] = bb

    return instances, shapes, states, params, part_group.count_shapes(), mapping


def _convert(
    *cad_objs,
    names=None,
    colors=None,
    alphas=None,
    progress=None,
    **kwargs,
):
    timeit = preset("timeit", kwargs.get("timeit"))

    if progress is None:
        progress = Progress([c for c in "-+c"])

    instances, shapes, states, config, count_shapes, mapping = _tessellate(
        *cad_objs,
        names=names,
        colors=colors,
        alphas=alphas,
        progress=progress,
        **kwargs,
    )

    if config.get("dark") is not None:
        config["theme"] = "dark"
    elif config.get("orbit_control") is not None:
        config["control"] = "orbit" if config["control"] else "trackball"

    if config.get("debug") is not None and config["debug"]:
        print("\nconfig:\n", config)

    if kwargs.get("explode") is not None:
        config["explode"] = kwargs["explode"]

    with Timer(timeit, "", "create data obj", 1):
        return {
            "data": numpy_to_buffer_json(
                dict(instances=instances, shapes=shapes, states=states)
            ),
            "type": "data",
            "config": config,
            "count": count_shapes,
        }, mapping


class Progress:
    """Progress indicator for tessellation"""

    def __init__(self, levels=None):
        if levels is None:
            self.levels = ["+", "c", "-"]
        else:
            self.levels = levels

    def update(self, mark="+"):
        """Update progress indicator"""
        if mark in self.levels:
            print(mark, end="", flush=True)


def align_attrs(attr_list, length, default, tag, explode=True):
    """Align attributes to the length of the cad_objs"""
    if attr_list is None:
        return [None] * length if explode else None
    elif len(attr_list) < length:
        print(f"Too few {tag}, using defaults to fill")
        return list(attr_list) + [default] * (length - len(attr_list))
    elif len(attr_list) > length:
        print(f"Too many {tag}, trimming to length {length}")
        return attr_list[:length]
    else:
        return attr_list


# pylint: disable=unused-argument
def show(
    *cad_objs,
    names=None,
    colors=None,
    alphas=None,
    port=None,
    progress="-+c",
    glass=None,
    tools=None,
    measure_tools=None,
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
    explode=None,
    ticks=None,
    center_grid=None,
    up=None,
    zoom=None,
    position=None,
    quaternion=None,
    target=None,
    reset_camera=None,
    clip_slider_0=None,
    clip_slider_1=None,
    clip_slider_2=None,
    clip_normal_0=None,
    clip_normal_1=None,
    clip_normal_2=None,
    clip_intersection=None,
    clip_planes=None,
    clip_object_colors=None,
    pan_speed=None,
    rotate_speed=None,
    zoom_speed=None,
    deviation=None,
    angular_tolerance=None,
    edge_accuracy=None,
    default_color=None,
    default_edgecolor=None,
    default_facecolor=None,
    default_thickedgecolor=None,
    default_vertexcolor=None,
    ambient_intensity=None,
    direct_intensity=None,
    metalness=None,
    roughness=None,
    render_edges=None,
    render_normals=None,
    render_mates=None,
    render_joints=None,
    show_parent=None,
    show_sketch_local=None,
    parallel=None,
    helper_scale=None,
    mate_scale=None,  # DEPRECATED
    debug=None,
    timeit=None,
    _force_in_debug=False,
):
    # pylint: disable=line-too-long
    """Show CAD objects in Visual Studio Code
    Parameters
        cad_objs:                All cad objects that should be shown as positional parameters

    Keywords for show:
        names:                   List of names for the cad_objs. Needs to have the same length as cad_objs
        colors:                  List of colors for the cad_objs. Needs to have the same length as cad_objs
        alphas:                  List of alpha values for the cad_objs. Needs to have the same length as cad_objs
        port:                    The port the viewer listens to. Typically use 'set_port(port)' instead
        progress:                Show progress of tessellation with None is no progress indicator. (default="-+c")
                                 for object: "-": is reference, "+": gets tessellated, "c": from cache

    Valid keywords to configure the viewer (**kwargs):
    - UI
        glass:                   Use glass mode where tree is an overlay over the cad object (default=False)
        measure_tools:           Show measure tools (default=False)
        tools:                   Show tools (default=True)
        tree_width:              Width of the object tree (default=240)

    - Viewer
        axes:                    Show axes (default=False)
        axes0:                   Show axes at (0,0,0) (default=False)
        grid:                    Show grid (default=False)
        ortho:                   Use orthographic projections (default=True)
        transparent:             Show objects transparent (default=False)
        default_opacity:         Opacity value for transparent objects (default=0.5)
        black_edges:             Show edges in black color (default=False)
        orbit_control:           Mouse control use "orbit" control instead of "trackball" control (default=False)
        collapse:                Collapse.LEAVES: collapse all single leaf nodes,
                                 Collapse.ROOT: expand root only,
                                 Collapse.ALL: collapse all nodes,
                                 Collapse.NONE: expand all nodes
                                 (default=Collapse.LEAVES)
        ticks:                   Hint for the number of ticks in both directions (default=10)
        center_grid:             Center the grid at the origin or center of mass (default=False)
        up:                      Use z-axis ('Z') or y-axis ('Y') as up direction for the camera (default="Z")
        explode:                 Turn on explode mode (default=False)

        zoom:                    Zoom factor of view (default=1.0)
        position:                Camera position
        quaternion:              Camera orientation as quaternion
        target:                  Camera look at target
        reset_camera:            Camera.RESET: Reset camera position, rotation, toom and target
                                 Camera.CENTER: Keep camera position, rotation, toom, but look at center
                                 Camera.KEEP: Keep camera position, rotation, toom, and target
                                 (default=Camera.RESET)

        clip_slider_0:           Setting of clipping slider 0 (default=None)
        clip_slider_1:           Setting of clipping slider 1 (default=None)
        clip_slider_2:           Setting of clipping slider 2 (default=None)
        clip_normal_0:           Setting of clipping normal 0 (default=None)
        clip_normal_1:           Setting of clipping normal 1 (default=None)
        clip_normal_2:           Setting of clipping normal 2 (default=None)
        clip_intersection:       Use clipping intersection mode (default=False)
        clip_planes:             Show clipping plane helpers (default=False)
        clip_object_colors:      Use object color for clipping caps (default=False)

        pan_speed:               Speed of mouse panning (default=1)
        rotate_speed:            Speed of mouse rotate (default=1)
        zoom_speed:              Speed of mouse zoom (default=1)

    - Renderer
        deviation:               Shapes: Deviation from linear deflection value (default=0.1)
        angular_tolerance:       Shapes: Angular deflection in radians for tessellation (default=0.2)
        edge_accuracy:           Edges: Precision of edge discretization (default: mesh quality / 100)

        default_color:           Default mesh color (default=(232, 176, 36))
        default_edgecolor:       Default color of the edges of a mesh (default=#707070)
        default_facecolor:       Default color of the edges of a mesh (default=#ee82ee)
        default_thickedgecolor:  Default color of the edges of a mesh (default=#ba55d3)
        default_vertexcolor:     Default color of the edges of a mesh (default=#ba55d3)
        ambient_intensity:       Intensity of ambient light (default=1.00)
        direct_intensity:        Intensity of direct light (default=1.10)
        metalness:               Metalness property of the default material (default=0.30)
        roughness:               Roughness property of the default material (default=0.65)

        render_edges:            Render edges  (default=True)
        render_normals:          Render normals (default=False)
        render_mates:            Render mates for MAssemblies (default=False)
        render_joints:           Render build123d joints (default=False)
        parallel:                Tessellate objects in parallel (default=False)
        show_parent:             Render parent of faces, edges or vertices as wireframe (default=False)
        show_sketch_local:       In build123d show local sketch in addition to relocate sketch (default=True)
        helper_scale:            Scale of rendered helpers (locations, axis, mates for MAssemblies) (default=1)

    - Debug
        debug:                   Show debug statements to the VS Code browser console (default=False)
        timeit:                  Show timing information from level 0-3 (default=False)
    """
    global LAST_CALL  # pylint: disable=global-statement

    kwargs = {
        k: v
        for k, v in locals().items()
        if v is not None
        and k
        not in [
            "cad_objs",
            "names",
            "colors",
            "alphas",
            "port",
            "progress",
            "LAST_CALL",
        ]
    }

    kwargs = check_deprecated(kwargs)

    if kwargs.get("grid") is not None:
        if isinstance(kwargs["grid"], bool):
            kwargs["grid"] = [kwargs["grid"]] * 3

    timeit = preset("timeit", timeit)

    if measure_tools is None:
        measure_tools = get_default("measure_tools")
        if measure_tools is None:
            conf = workspace_config()
            measure_tools = conf["measure_tools"]
    kwargs["measure_tools"] = measure_tools

    if measure_tools and kwargs.get("collapse") is None:
        kwargs["collapse"] = Collapse.ROOT

    names = align_attrs(names, len(cad_objs), None, "names", explode=measure_tools)

    # Handle colormaps

    if isinstance(colors, BaseColorMap):
        colors = [next(colors) for _ in range(len(cad_objs))]
        alphas = [None] * len(cad_objs)  # alpha is encoded in colors
    else:
        colors = align_attrs(colors, len(cad_objs), None, "colors")
        alphas = align_attrs(alphas, len(cad_objs), None, "alphas")

    map_colors = None
    colormap = get_colormap()
    if colormap is not None:
        map_colors = [next(colormap) for _ in range(len(cad_objs))]

    for i in range(len(cad_objs)):
        if isinstance(colors[i], str):
            colors[i] = web_to_rgb(colors[i])
        if colors[i] is None and map_colors is not None:
            colors[i] = map_colors[i][:3]
            if alphas[i] is None and len(map_colors[i]) == 4:
                alphas[i] = map_colors[i][3]
        elif colors[i] is not None:
            if alphas[i] is None and len(colors[i]) == 4:
                alphas[i] = colors[i][3]
            colors[i] = colors[i][:3]

    if default_edgecolor is not None:
        default_edgecolor = Color(default_edgecolor).web_color

    progress = Progress([] if progress is None else [c for c in progress])

    with Timer(timeit, "", "overall"):
        t, mapping = _convert(
            *cad_objs,
            names=names,
            colors=colors,
            alphas=alphas,
            progress=progress,
            **kwargs,
        )

        if not _force_in_debug:
            LAST_CALL = "show"
        else:
            LAST_CALL = "other"

    return data

    with Timer(timeit, "", "send"):
        send_data(t, port=port, timeit=timeit)

    if measure_tools:
        send_backend({"model": mapping}, port=port, timeit=timeit)


def reset_show():
    """Reset the stack of objects to be shown"""
    global OBJECTS  # pylint: disable=global-statement

    OBJECTS = {"objs": [], "names": [], "colors": [], "alphas": []}


# pylint: disable=too-many-locals,too-many-arguments
def show_object(
    obj,
    name=None,
    options=None,
    parent=None,
    clear=False,
    port=None,
    progress="-+c",
    glass=None,
    tools=None,
    measure_tools=None,
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
    center_grid=None,
    up=None,
    zoom=None,
    position=None,
    quaternion=None,
    target=None,
    reset_camera=None,
    clip_slider_0=None,
    clip_slider_1=None,
    clip_slider_2=None,
    clip_normal_0=None,
    clip_normal_1=None,
    clip_normal_2=None,
    clip_intersection=None,
    clip_planes=None,
    clip_object_colors=None,
    pan_speed=None,
    rotate_speed=None,
    zoom_speed=None,
    deviation=None,
    angular_tolerance=None,
    edge_accuracy=None,
    default_color=None,
    default_facecolor=None,
    default_thickedgecolor=None,
    default_vertexcolor=None,
    default_edgecolor=None,
    ambient_intensity=None,
    metalness=None,
    roughness=None,
    direct_intensity=None,
    render_edges=None,
    render_normals=None,
    render_mates=None,
    render_joints=None,
    parallel=None,
    show_parent=None,
    show_sketch_local=None,
    helper_scale=None,
    mate_scale=None,  # DEPRECATED
    debug=None,
    timeit=None,
):
    # pylint: disable=line-too-long
    """Incrementally show CAD objects in Visual Studio Code

    Parameters:
        obj:                     The CAD object to be shown

    Keywords for show_object:
        name:                    The name of the CAD object
        options:                 A dict of color and alpha value: {"alpha":0.5, "color": (64, 164, 223)}
                                 0 <= alpha <= 1.0 and color is a 3-tuple of values between 0 and 255
        parent:                  Add another object, usually the parent of e.g. edges or vertices with alpha=0.25
        clear:                   In interactice mode, clear the stack of objects to be shown
                                 (typically used for the first object)
        port:                    The port the viewer listens to. Typically use 'set_port(port)' instead
        progress:                Show progress of tessellation with None is no progress indicator. (default="-+c")
                                 for object: "-": is reference, "+": gets tessellated, "c": from cache

    Valid keywords to configure the viewer (**kwargs):
    - UI
        glass:                   Use glass mode where tree is an overlay over the cad object (default=False)
        measure_tools:           Show measure tools (default=False)
        tools:                   Show tools (default=True)
        tree_width:              Width of the object tree (default=240)

    - Viewer
        axes:                    Show axes (default=False)
        axes0:                   Show axes at (0,0,0) (default=False)
        grid:                    Show grid (default=False)
        ortho:                   Use orthographic projections (default=True)
        transparent:             Show objects transparent (default=False)
        default_opacity:         Opacity value for transparent objects (default=0.5)
        black_edges:             Show edges in black color (default=False)
        orbit_control:           Mouse control use "orbit" control instead of "trackball" control (default=False)
        collapse:                Collapse.LEAVES: collapse all single leaf nodes,
                                 Collapse.ROOT: expand root only,
                                 Collapse.ALL: collapse all nodes,
                                 Collapse.NONE: expand all nodes
                                 (default=Collapse.LEAVES)
        ticks:                   Hint for the number of ticks in both directions (default=10)
        center_grid:             Center the grid at the origin or center of mass (default=False)
        up:                      Use z-axis ('Z') or y-axis ('Y') as up direction for the camera (default="Z")

        zoom:                    Zoom factor of view (default=1.0)
        position:                Camera position
        quaternion:              Camera orientation as quaternion
        target:                  Camera look at target
        reset_camera:            Camera.RESET: Reset camera position, rotation, toom and target
                                 Camera.CENTER: Keep camera position, rotation, toom, but look at center
                                 Camera.KEEP: Keep camera position, rotation, toom, and target
                                 (default=Camera.RESET)

        clip_slider_0:           Setting of clipping slider 0 (default=None)
        clip_slider_1:           Setting of clipping slider 1 (default=None)
        clip_slider_2:           Setting of clipping slider 2 (default=None)
        clip_normal_0:           Setting of clipping normal 0 (default=[-1,0,0])
        clip_normal_1:           Setting of clipping normal 1 (default=[0,-1,0])
        clip_normal_2:           Setting of clipping normal 2 (default=[0,0,-1])
        clip_intersection:       Use clipping intersection mode (default=[False])
        clip_planes:             Show clipping plane helpers (default=False)
        clip_object_colors:      Use object color for clipping caps (default=False)

        pan_speed:               Speed of mouse panning (default=1)
        rotate_speed:            Speed of mouse rotate (default=1)
        zoom_speed:              Speed of mouse zoom (default=1)

    - Renderer
        deviation:               Shapes: Deviation from linear deflection value (default=0.1)
        angular_tolerance:       Shapes: Angular deflection in radians for tessellation (default=0.2)
        edge_accuracy:           Edges: Precision of edge discretization (default: mesh quality / 100)

        default_color:           Default mesh color (default=(232, 176, 36))
        default_edgecolor:       Default color of the edges of a mesh (default=(128, 128, 128))
        default_facecolor:       Default color of the edges of a mesh (default=#ee82ee / Violet)
        default_thickedgecolor:  Default color of the edges of a mesh (default=#ba55d3 / MediumOrchid)
        default_vertexcolor:     Default color of the edges of a mesh (default=#ba55d3 / MediumOrchid)
        ambient_intensity:       Intensity of ambient light (default=1.00)
        direct_intensity:        Intensity of direct light (default=1.10)
        metalness:               Metalness property of the default material (default=0.30)
        roughness:               Roughness property of the default material (default=0.65)


        render_edges:            Render edges  (default=True)
        render_normals:          Render normals (default=False)
        render_mates:            Render mates for MAssemblies (default=False)
        render_joints:           Render build123d joints (default=False)
        parallel:                Tessellate objects in parallel (default=False)
        show_parent:             Render parent of faces, edges or vertices as wireframe (default=False)
        show_sketch_local:       In build123d show local sketch in addition to relocate sketch (default=True)
        helper_scale:            Scale of rendered helpers (locations, axis, mates for MAssemblies) (default=1)

    - Debug
        debug:                   Show debug statements to the VS Code browser console (default=False)
        imeit:                   Show timing information from level 0-3 (default=False)
    """

    kwargs = {
        k: v
        for k, v in locals().items()
        if v is not None
        and k not in ["obj", "name", "options", "parent", "clear", "port", "progress"]
    }

    if clear:
        reset_show()

    if parent is not None:
        OBJECTS["objs"].append(parent)
        OBJECTS["names"].append("parent")
        OBJECTS["colors"].append(None)
        OBJECTS["alphas"].append(None)

    color = None
    alpha = None
    if options is None:
        colormap = get_colormap()
        if colormap is not None:
            for _ in range(len(OBJECTS["names"]) + 1):
                *color, alpha = next(colormap)
    else:
        color = options.get("color")
        alpha = options.get("alpha", 1.0)

    OBJECTS["objs"].append(obj)
    OBJECTS["names"].append(name)
    OBJECTS["colors"].append(color)
    OBJECTS["alphas"].append(alpha)

    show(
        *OBJECTS["objs"],
        names=OBJECTS["names"],
        colors=OBJECTS["colors"],
        alphas=OBJECTS["alphas"],
        port=port,
        progress=progress,
        **kwargs,
    )


def show_clear():
    """Clear the viewer"""
    data = {
        "type": "clear",
    }
    send_data(data)


def ocp_group(obj, name):

    def to_group(obj, name, group):
        if isinstance(obj, list):
            sub_group = OCP_PartGroup([], name=name)
            for i, el in enumerate(obj):
                new_obj = to_group(el, f"{name}[{i}]", sub_group)
                if new_obj is not None:
                    sub_group.add(new_obj)
            group.add(sub_group)
        elif isinstance(obj, dict):
            sub_group = OCP_PartGroup([], name=name)
            for name, el in obj.items():
                new_obj = to_group(el, name, sub_group)
                if new_obj is not None:
                    sub_group.add(new_obj)
            group.add(sub_group)
        else:
            if (
                (is_wrapped(obj) and not obj.__class__.__name__ == "Color")
                or is_build123d(obj)
                or is_cadquery(obj)
            ):
                new_obj = conv(obj)
                new_obj.name = name
                group.add(new_obj)
            else:
                ...
                # print(
                #     f"show_all: Type {type(obj)} for name {name} cannot be visualized"
                # )

    group = OCP_PartGroup([], name=name)
    to_group(obj, name, group)
    return group.objects[0]


def show_all(variables=None, exclude=None, classes=None, _visual_debug=False, **kwargs):
    """Show all variables in the current scope"""
    import inspect  # pylint: disable=import-outside-toplevel

    global LAST_CALL  # pylint: disable=global-statement

    if not _visual_debug:
        LAST_CALL = "other"

    if _visual_debug and LAST_CALL == "show":
        LAST_CALL = "other"
        print("\nSkip visual debug step after a show() command")
        return

    if variables is None:
        cf = inspect.currentframe()
        variables = cf.f_back.f_locals

    if exclude is None:
        exclude = []

    objects = []
    names = []
    for name, obj in variables.items():
        if (
            isinstance(obj, type)
            or name in ["_", "__", "___"]
            or name.startswith("__")
            or re.search("_\\d+", name) is not None
        ):
            continue  # ignore classes and jupyter variables
        if hasattr(obj, "area") and obj.area > 1e99:  # inifinite face
            print(f"infinite face {name} skipped")
            continue

        if name not in exclude and (classes is None or isinstance(obj, tuple(classes))):
            if (
                hasattr(obj, "_obj")
                and obj._obj is None  # pylint: disable=protected-access
            ):
                continue

            if hasattr(obj, "locations") and hasattr(obj, "local_locations"):
                obj = obj.locations

            if hasattr(obj, "local_coord_system"):
                obj = obj.location

            if (
                (
                    hasattr(obj, "wrapped")
                    and (
                        is_topods_shape(obj.wrapped)
                        or is_topods_compound(obj.wrapped)
                        or is_toploc_location(obj.wrapped)
                    )
                )
                or is_vector(obj)  # Vector
                or is_cadquery(obj)
                or is_build123d(obj)
                or is_cadquery_assembly(obj)
                or (
                    hasattr(obj, "wrapped")
                    and hasattr(obj, "position")
                    and hasattr(obj, "direction")
                )
            ):
                objects.append(obj)
                names.append(name)

            elif isinstance(
                obj, (OCP_PartGroup, OCP_Edges, OCP_Faces, OCP_Part, OCP_Vertices)
            ):
                objects.append(obj)
                obj.name = name
                names.append(name)

            elif is_cadquery_sketch(obj):
                pg = to_assembly([obj], names=[name])
                pg.name = name
                objects.append(pg)
                names.append(name)

            elif isinstance(obj, (list, tuple, dict)):
                if not name in [
                    "_ih",
                    "_oh",
                    "_dh",
                    "Out",
                    "In",
                ]:  # no IPython dicts and lists
                    obj = ocp_group(obj, name)
                    if len(obj.objects) > 0:
                        objects.append(obj)
                        obj.name = name
                        names.append(name)

    if len(objects) > 0:
        show(
            *objects,
            names=names,
            collapse=Collapse.ROOT,
            _force_in_debug=_visual_debug,
            **kwargs,
        )
    else:
        show_clear()
