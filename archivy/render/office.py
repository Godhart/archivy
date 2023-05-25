from archivy.render.local import render_local
from archivy.render.common import default_handlers, handler_info, handler_engine
import os
import re

def render_office(
    data,           # NOTE: data is not used by render_office
    src,
    dformat,
    d_path,
    serviceUrl,     # NOTE: serviceUrl is not used by render_office
    engine,
    page,
    force,
    opts,
):
    if src == "":
        raise ValueError("Office supports input from files only!")

    # Command line for converting image with Libre Office
    if page == "":
        cformat = f"{dformat}:{engine}_{dformat}_Export"
    else:
        raise ValueError("Pages are not supported :( !")
        cformat = (
            f"{dformat}:{engine}_{dformat}_Export:"
            # TODO: PageRange is not working (at least for draw). Selection should be used instead but no docs about it
            # Clues:
            # - https://cgit.freedesktop.org/libreoffice/core/tree/filter/source/config/fragments/filters
            # - https://github.com/unoconv/unoconv/blob/master/doc/filters.adoc
            '{"PageRange":{"type":"string","value":"'
            f"{page}"
            '"}}')
            # TODO: It seems that export filter properties specification not works at all this way

    serviceUrl = [
        "soffice",      "--headless", "--quickstart",
        "--convert-to", cformat,
        "--outdir",     os.path.split(d_path)[0],
        src
    ]

    def custom_result_lookup():
        ## First - lets see where output file is saved by Libre Office
        ### get only file name
        r_path = os.path.split(src)[1]
        ### replace source's file name extension according to dformat
        r_path = re.sub(r"\.[^.]*$", f".{dformat}", r_path)
        ### join generated path and filename
        r_path = os.path.join(os.path.split(d_path)[0], r_path)
        return r_path

    result = render_local(
        src, dformat, d_path, serviceUrl, engine, page, force, opts,
        output_path=custom_result_lookup(),
        output_path_cleanup=True
    )

    return result


default_handlers.register_handler(
    handler_info(
        service     = "office",
        alias       = "ofc",
        opts        = {},
        env         = {},
        engines     = {
            "draw": handler_engine(
                exts =      [".odg", ".vsd", ".emf", ".wmf"],
                formats =   ["svg", "png", "pdf"]
            ),
        },
        serviceUrl  = "local",
        fun         = render_office
    )
)
