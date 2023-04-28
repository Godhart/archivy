from archivy.render.common import default_handlers, handler_info, handler_engine, get_param
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
    
    width = get_param(opts, "width", None)
    if width in (None, ""):
        width = opts.get("auto-fit-width", None)
    if width in (None, ""):
        width = "100%"

    height = get_param(opts, "height", None)
    if height in (None, ""):
        height = opts.get("auto-fit-height", None)
    if height in (None, ""):
        height = "800px"

    pdf_path = re.sub(r"\.\w+$", ".pdf", d_path)
    pdf_path = os.path.normpath(pdf_path)
    images_path = os.path.normpath(common.IMG_ROOT_PATH)
    pdf_rel_path = common.IMG_ROOT_PREFIX + "/" + pdf_path[len(images_path)+1:]

    if os.path.exists(d_path):
        os.unlink(d_path)
    if os.path.exists(pdf_path):
        os.unlink(pdf_path)
    if not os.path.exists(src):
        return False, [f"Source document '{src}' is not found!"]
    shutil.copy2(src, pdf_path)

    html = f"""
<html>
<body>
<embed src="{pdf_rel_path}" width="{width}" height="{height}" type="application/pdf">
</body>
</html>
"""
    with open(d_path, "w", encoding='utf-8') as f:
        f.write(html)

    result = True, None

    return result


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
                formats =   ["html"]
            ),
        },
        serviceUrl  = "local",
        fun         = render_pdf
    )
)
