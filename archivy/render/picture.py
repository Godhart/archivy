from archivy.render.common import default_handlers, handler_info, handler_engine
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

    if os.path.exists(d_path):
        os.unlink(d_path)
    if not os.path.exists(src):
        return False, [f"Source image '{src}' is not found!"]
    shutil.copy2(src, d_path)

    result = True, None

    return result


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
