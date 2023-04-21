import subprocess
import os
import re
import shutil

from archivy.render.common import digest, get_param, get_cache


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

    c_url = [
        "soffice",      "--headless", "--quickstart",
        "--convert-to", cformat,
        "--outdir",     os.path.split(d_path)[0],
        src
    ]

    # Cache things
    cache, cache_dir = get_cache(opts)

    if cache:
        if page == "":
            c_page = ""
        else:
            c_page = "-" + page
        cache_path = os.path.join(cache_dir, f"{digest(file = src)}{c_page}.{dformat}")
    else:
        cache_path = ""

    # If image is not cached or forced - get image
    if force or get_param(opts, "RENDER_FORCE", "false").lower() == "true" \
    or not cache or not os.path.exists(cache_path):
        # Write error message, it would be overwritten in case of success
        with open(d_path, "w", encoding='utf-8') as f:
            f.write("Failed to get diagram image")
        # Libre Office don't allows to set output file name,
        # so we need to do more actions than usual

        ## First - lets see where output file is saved by Libre Office
        ### get only file name
        r_path = os.path.split(src)[1]
        ### replace source's file name extension according to dformat
        r_path = re.sub(r"\.[^.]*$", f".{dformat}", r_path)
        ### join generated path and filename
        r_path = os.path.join(os.path.split(d_path)[0], r_path)

        # Unlink existing Libre Office's output file
        if os.path.exists(r_path):
            os.unlink(r_path)

        # Convert
        result = subprocess.run(c_url)

        # TODO: try to use unoserver https://github.com/unoconv/unoserver
        # as it saves time and probably may provide pages selection

        ## Rename Libre Office's output file
        if r_path != d_path:
            if os.path.exists(d_path):
                os.unlink(d_path)
            shutil.copy2(r_path, d_path)
            os.unlink(r_path)

        # Store results to cache
        if cache and cache_path != "":
            os.makedirs(cache_dir, exist_ok=True)
            if os.path.exists(cache_path):
                os.unlink(cache_path)
            shutil.copy2(d_path, cache_path)
    else:
        # Otherwise copy cached data into destination path
        if os.path.exists(d_path):
            os.unlink(d_path)
        shutil.copy2(cache_path, d_path)

    return True, None
