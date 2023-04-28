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

    y4s_id = opts.get("y4s-id", None)
    if y4s_id in (None, "",):
        raise ValueError("'y4s-id' option is mandatory for y4s!")
    y4s_id = re.sub(r"\\W", "-", y4s_id)

    y4s_zoom = opts.get("y4s-zoom", False)

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
    
    y4s_root = get_param(opts, "y4s-root", os.path.split(src)[0])
    # TODO: make sure y4s_root is within some safe path

    serviceUrl = [
        "python", os.path.join(y4s_path, "yaml4schm.py"),
        "-t", engine,
        "-f", "HTML_SNIPPET",
        "--snippet-name", y4s_id,
        "--root", y4s_root,
    ]

    if get_param(opts, "y4s_-hell", False) is True:
        serviceUrl.append("--shell")

    width = get_param(opts, "width", None)
    if width not in (None, ""):
        serviceUrl += ["--width", width]

    height = get_param(opts, "height", None)
    if height not in (None, ""):
        serviceUrl += ["--height", height]

    zoom = get_param(opts, "zoom", False)
    if zoom is not True:
        serviceUrl += ["--zoom", "no"]

    serviceUrl += [src, d_path, ]

    result = render_local(data, src, dformat, d_path, serviceUrl, engine, page, force, opts)

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
