from archivy.render.common import default_handlers, handler_info, handler_engine, sync_files
import os
import shutil

def render_picture(
    data,           # NOTE: data is not used by render_picture
    src,
    dformat,
    d_path,
    serviceUrl,     # NOTE: serviceUrl is not used by render_picture
    engine,
    page,
    force,
    opts,
):
    if src == "":
        raise ValueError("picture supports input from files only!")

    result = [True, None]

    if os.path.isdir(src):
        result[0] = False
        result[1].append([f"src '{src}' should point to a file!"])

    if not os.path.exists(src):
        result[0] = False
        result[1].append([f"Source picture '{src}' is not found!"])

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
        service     = "picture",
        alias       = "pic",
        opts        = {},
        env         = {},
        engines     = {
            "png": handler_engine(
                exts =      [".png"],
                formats =   ["png"]
            ),
            "svg": handler_engine(
                exts =      [".svg"],
                formats =   ["svg"]
            ),
            "jpg": handler_engine(
                exts =      [".jpg", ".jpeg"],
                formats =   ["jpg"]
            ),
            "gif": handler_engine(
                exts =      [".jpg", ".jpeg"],
                formats =   ["gif"]
            ),
        },
        serviceUrl  = "local",
        fun         = render_picture
    )
)
