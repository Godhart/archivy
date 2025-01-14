from archivy.render import common as common
from archivy.render.local import render_local
from archivy.render.common import default_handlers, handler_info, handler_engine, temp_file_path, get_param
import os
import re


def render_y4s_html(
    data,
    src,
    dformat,
    d_path,
    serviceUrl,     # NOTE: serviceUrl is not used by render_y4s
    engine,
    page,
    force,
    opts,
):

    if engine is None:
        raise ValueError("'engine' option is mandatory for y4s!")

    extras = {"service": "yaml4schm", }

    y4s_id = opts.get("y4s-id", None)
    if y4s_id in (None, "",):
        raise ValueError("'y4s-id' option is mandatory for y4s!")
    y4s_id = re.sub(r"\\W", "-", y4s_id)

    extras['y4s-id'] = y4s_id

    # If data is given - save it into cache dir and then use as source
    src_is_temporary = False
    if src == "":
        src_is_temporary = True

        src = temp_file_path(opts, ".yaml")
        with open(src, "w", encoding='utf-8') as f:
            f.write(data)

    y4s_path = get_param(opts, "Y4S_PATH", os.environ.get("YES_PATH"))
    if y4s_path is None:
        raise ValueError("Specify Y4S_PATH environment variable to use y4s!")

    extras['y4s-path'] = y4s_path

    y4s_root = get_param(opts, "y4s-root", os.path.split(src)[0])
    # TODO: make sure y4s_root is within some safe path

    extras['y4s-root'] = y4s_root

    serviceUrl = [
        "python", os.path.join(y4s_path, "yaml4schm.py"),
        "-t", engine,
        "-f", "HTML_SNIPPET",
        "--snippet-name", y4s_id,
        "--root", y4s_root,
    ]

    if get_param(opts, "y4s-shell", False) is True:
        serviceUrl.append("--shell")
        extras['y4s-shell'] = True
    else:
        extras['y4s-shell'] = False

    width = get_param(opts, "width", None)
    if width in (None, ""):
        width = opts.get("auto-fit-width", None)
    if width in (None, ""):
        width = "100%"
    if width not in (None, ""):
        serviceUrl += ["--width", width]
    extras['width'] = width

    height = get_param(opts, "height", None)
    if height in (None, ""):
        height = opts.get("auto-fit-height", None)
    if height in (None, ""):
        height = "800px"
    if height not in (None, ""):
        serviceUrl += ["--height", height]
    extras['height'] = height

    zoom = get_param(opts, "y4s-zoom", False)
    if zoom is not True:
        serviceUrl += ["--zoom", "no"]
        extras['y4s-zoom'] = True
    else:
        extras['y4s-zoom'] = False

    serviceUrl += [src, d_path, ]

    result = render_local(src, dformat, d_path, serviceUrl, engine, page, force, opts, extras = extras)

    if src_is_temporary:
        os.unlink(src)

    return result


default_handlers.register_handler(
    handler_info(
        service     = "yaml4schm",
        alias       = "y4s",
        opts        = {
            "y4s-id"     : (None, str),   # id for y4s drawing
            "y4s-root"   : (None, str),   # Root of y4s files to lookup
            "y4s-shell"  : (None, bool),  # True to box-around
            "y4s-zoom"   : (False, bool), # True to enable zoom on D3HW diagram
            "inversion-all"  : (True, bool),  # Option to force apply inversion to whole div
        },
        env         = {
            "Y4S_PATH"   : None,          # Path to folder with y4s script
        },
        engines     = {
            "hdelk": handler_engine(
                exts =      {},
                formats =   ["html",]
            ),
            "d3hw": handler_engine(
                exts =      {},
                formats =   ["html",]
            ),
        },
        serviceUrl  = "local",
        fun         = render_y4s_html
    )
)
