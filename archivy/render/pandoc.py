from archivy.render import common as common
from archivy.render.local import render_local
from archivy.render.common import default_handlers, handler_info, handler_engine, temp_file_path
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen


_EXT_MAP        = {
    "markdown"  : ".md",
    "textile"   : ".textile",
    "rst"       : ".rst",
    "mediawiki" : ".mediawiki",
    "dokuwiki"  : ".dokuwiki",
    "latex"     : ".latex",
    "csv"       : ".csv",
    "tsv"       : ".tsv",
}


_EXT_MAP_BLOB   = {
    "docx"      : ".docx",
    "odt"       : ".odt",
    "rtf"       : ".rtf",
}


def render_pandoc_html(
    data,
    src,
    dformat,
    d_path,
    serviceUrl,     # NOTE: serviceUrl is not used by render_pandoc
    engine,
    page,
    force,
    opts,
):

    if engine is None:
        engine = "auto"

    from_format = opts.get("from", None)

    extras = {"service": "pandoc-html", "extension": opts.get("extension", None)}

    # If data is given - save it into cache dir and then use as source
    src_is_temporary = False
    if src == "":
        src_is_temporary = True

        if engine in _EXT_MAP:
            from_format = engine
            ext = _EXT_MAP[engine]
        elif engine == "auto":
            ext = opts.get("extension", None)
            if ext is None:
                raise ValueError("specify 'extension' property for 'auto' engine")
        else:
            raise ValueError(f"inline data is not supported for '{engine}'")

        src = temp_file_path(opts, ext)
        with open(src, "w", encoding='utf-8') as f:
            f.write(data)

    d_path = os.path.normpath(d_path)
    media_path = list(os.path.split(d_path))
    media_path[1] = re.sub(r"\W", "_", media_path[1]) + "_images"
    media_path = os.path.join(*media_path)
    if os.path.exists(media_path):
        shutil.rmtree(media_path)

    serviceUrl = [
        "pandoc", src,
        f"--extract-media={os.path.join(common.IMG_ROOT_PATH, media_path)}",
        "-s",
        "-t", "html",
        "-o", d_path,
    ]

    if from_format is not None:
        serviceUrl += ["-f", from_format]

    def post_process(path):
        # Normalize links to images
        with open(path, "r", encoding='utf-8') as f:
            html = f.read()

        html = re.sub(common.IMG_ROOT_PATH.replace("\\", "\\\\"), "/images", html)

        # TODO: ripoff only necessary part of document (skip/include by specified headers)

        with open(path, "w", encoding='utf-8') as f:
            f.write(html)

    def custom_cache():
        return {os.path.split(media_path)[1]: media_path}

    result = render_local(
        src, dformat, d_path, serviceUrl, engine, page, force, opts,
        post_process=post_process, custom_cache=custom_cache, extras=extras)

    if src_is_temporary:
        os.unlink(src)

    return result


default_handlers.register_handler(
    handler_info(
        service     = "pandoc-html",
        alias       = "pdh",
        opts        = {
            "ext"   : (None, str),   # Specify extension for inline file
            "from"  : (None, str),   # Specify from parameter for pandoc
        },
        env         = {},
        engines     = {
            **{k: handler_engine(exts=[v], formats=["html",]) for k, v in _EXT_MAP.items()},
            **{k: handler_engine(exts=[v], formats=["html",]) for k, v in _EXT_MAP_BLOB.items()},
            "auto": handler_engine(
                exts =      [],
                formats =   ["html",]
            ),
        },
        serviceUrl  = "local",
        fun         = render_pandoc_html
    )
)


def import_pandoc(
    src,
    d_path,
    engine,
    page,
    force,
    opts,
):

    if engine is None:
        engine = "auto"

    from_format = opts.get("from", None)

    pic_inversion = opts.get("pic-inversion", "auto")

    extras = {"service": "pandoc-markdown",
              "pic-inversion": pic_inversion}

    # If src is url - save it into cache dir and then use as source
    src_is_temporary = False
    if src[:5] == "http:" or src[:6] == "https:":
        src_is_temporary = True

        if engine in _EXT_MAP:
            from_format = engine
            ext = _EXT_MAP[engine]
        elif engine == "auto":
            ext = opts.get("extension", None)
            if ext is None:
                raise ValueError("specify 'extension' property for 'auto' engine")
        else:
            raise ValueError(f"inline data is not supported for '{engine}'")

        url = src
        f = urlopen(url)
        data = f.read()
        src = temp_file_path(opts, ext)
        with open(src, "w", encoding='utf-8') as f:
            f.write(data)

    d_path = os.path.normpath(d_path)
    media_path = list(os.path.split(d_path))
    media_path[1] = re.sub(r"\W", "_", media_path[1]) + "_images"
    media_path = os.path.join(*media_path)
    if os.path.exists(media_path):
        shutil.rmtree(media_path)

    to_format = "gfm-raw_html"

    serviceUrl = [
        "pandoc", src,
        f"--extract-media={media_path}",
        "-s",
        "-t", to_format,
        "-o", d_path,
    ]

    if from_format is not None:
        serviceUrl += ["-f", from_format]

    def post_process(path):
        with open(path, "r", encoding='utf-8') as f:
            lines = f.read()

        subst_path = media_path.replace('\\', '\\\\')
        subst_expr = f"\!\[[^]]*\]\({subst_path}([^)]+)\)"
        base_path = opts.get('base_path', None)
        if base_path is None:
            base_path = Path(d_path).parent
        else:
            base_path = Path(base_path)
        subst_value = str(Path(media_path).relative_to(base_path))
        # replace values like ![](<media_path>/<picture_path>) with picture fence and path relative to md file
        fenced_value = f"""```ssq-pic
src : {subst_value}\\1
inversion: {pic_inversion}
```
"""
        lines = re.sub(subst_expr, fenced_value, lines)

        if opts.get('import_note', False) is True:
            current_date = datetime.fromtimestamp(time.time()).strftime(r"%Y-%m-%d %H:%M:%S")
            lines = f"<!-- following section is imported at {current_date} from '{src}' -->\n" + \
                lines + "<!-- end of imported data -->\n"

        if opts.get('readonly', False) is True:
            lines = """---
readonly : true
---
""" + lines

        with open(path, "w", encoding='utf-8') as f:
            f.write(lines)
        # TODO: ripoff only necessary part of document (skip/include by specified headers)
        return

    def custom_cache():
        return {os.path.split(media_path)[1]: media_path}

    result = render_local(
        src, "md", d_path, serviceUrl, f"{engine}-{to_format}", page, force, opts,
        post_process=post_process, custom_cache=custom_cache, extras=extras)

    if src_is_temporary:
        os.unlink(src)

    return result

