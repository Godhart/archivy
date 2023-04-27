from archivy.render.local import render_local
from archivy.render.common import default_handlers, handler_info, handler_engine, temp_file_path
import os
import shutil

def render_symbolator(
    data,
    src,
    dformat,
    d_path,
    serviceUrl,     # NOTE: serviceUrl is not used by render_symbolator
    engine,
    page,
    force,
    opts,
):

    # If data is given - save it into cache dir and then use as source
    src_is_temporary = False
    if src == "":
        src_is_temporary = True
        src = temp_file_path(opts, ".vhdl")
        with open(src, "w", encoding='utf-8') as f:
            f.write(data)

    # Command line for generating image with symbolator
    sym_o = d_path+".tmp"
    symbolator_opts = ["-i", src, "-f", dformat, "-o", sym_o, ]

    # TODO: path for libs

    transp = opts.get("transparent", None)
    if transp is not None and transp.lower() in ("yes", "true"):
        symbolator_opts += ["-t"]   # TODO: transparency not works

    if opts.get("no-type", False) is True:
        symbolator_opts += ["--no-type"]

    if opts.get("title", False) is True:
        symbolator_opts += ["--title"]

    serviceUrl = ["symbolator", *symbolator_opts, src]

    def custom_result_lookup():
        # TODO: this one is a hack, need to rework
        for root, _, files in os.walk(sym_o):
            if len(files) == 1:
                for f in files:
                    return os.path.join(root, f)
            elif len(files) > 1:
                with open(d_path, "w", encoding='utf-8') as f:
                    f.write(f"More than one output file were produced. Make sure there is only entity / component in a source data!")
                return None
            else:
                with open(d_path, "w", encoding='utf-8') as f:
                    f.write(f"Failed to produce result!")
                return None

    if os.path.exists(sym_o):
        # TODO: won't there be conflicts with other threads?
        shutil.rmtree(sym_o)
    os.makedirs(sym_o, exist_ok=True)

    result = render_local(data, src, dformat, d_path, serviceUrl, engine, page, force, opts, custom_result_lookup)

    shutil.rmtree(sym_o)

    if src_is_temporary:
        os.unlink(src)
    return result


default_handlers.register_handler(
    handler_info(
        service     = "symbolator",
        alias       = "sym",
        opts        = {
            "transparent"   : ("yes", str),
            "no-type"       : (False, bool),
            "title"         : (False, bool),
        },
        env         = {},
        engines     = {
            "vhdl": handler_engine(
                exts =      [".vhd", ".vhdl"],
                formats =   ["svg", "pdf"]
            ),
        },
        serviceUrl  = "local",
        fun         = render_symbolator
    )
)
