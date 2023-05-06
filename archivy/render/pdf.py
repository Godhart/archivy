from archivy.render.common import default_handlers, handler_info, handler_engine, sync_files
import archivy.render.common as common
import os
import re
import shutil

def render_pdf(
    data,           # NOTE: data is not used by render_pdf
    src,
    dformat,
    d_path,
    serviceUrl,     # NOTE: serviceUrl is not used by render_pdf
    engine,
    page,
    force,
    opts,
):
    if src == "":
        raise ValueError("pdf supports input from files only!")

    result = True, None

    if os.path.isdir(src):
        result[0] = False
        result[1].append([f"src '{src}' should point to a file!"])

    if not os.path.exists(src):
        result[0] = False
        result[1].append([f"Source document '{src}' is not found!"])

    if not result[0]:
        if os.path.exists(d_path):
            if os.path.isfile(d_path):
                os.unlink(d_path)
            else:
                shutil.rmtree(d_path)
        return result

    if sync_files(src, d_path, allow_delete=True):
        return result
    else:
        return False, [f"Failed to sync '{src}' to '{d_path}'"]


default_handlers.register_handler(
    handler_info(
        service     = "pdf",
        alias       = "pdf",
        opts        = {
            "inversion-all"  : (True, bool),  # Option to force apply inversion to whole div
        },
        env         = {},
        engines     = {
            "pdf": handler_engine(
                exts =      [".pdf"],
                formats =   ["pdf"]
            ),
        },
        serviceUrl  = "local",
        fun         = render_pdf
    )
)
