##############################################################################
# Renders diagram from textual description and inserts it into document
# Diagram is as reference to svg/png file or as raw SVG code if applicable
#  (raw svg can be turned off via arguments)
#
# Rendering is done with Kroki! in first place or by other services
# Even office documents rendering is supported (with libre office)
#
# Accepts text data with frontmatter header
# Frontmatter part contains arguments for rendering control
#
####
# data          - Main part after frontmatter header
#                 Diagram description in text form (should be compatible with
#                 rendering engine).
#                 Ignored if value for `src` is specified.
####
# Arguments:
# src           - Path to outer file with diagram description in text form.
#                 See `diagrams/README.md` for details.
#                 Should be omitted if `data` is to be used.
# dformat       - Specify data format for downloaded diagram.
#                 See https://kroki.io/#support for details.
#                 `svg` would be used by default if value is omitted
#                 or empty string.
#                 Sometimes SVG conversion to PDF/PNG not works good on client
#                 side (default). In that case it's suggested to use PNG or PDF.
#                 Take a NOTE: not all Kroki services provide diagrams
#                 in PNG / PDF format.
# rawsvg        - Option to insert SVG as code right into HTML.
#                 This way text on diagrams is searchable.
#                 Enabled (TRUE) by default.
#                 Set to FALSE to embed SVG as image.
#                 Applicable only for HTML output and only if `dformat`
#                 is "SVG" or empty string.
# downloadName  - File name (part before extension) for local diagram's files.
# downloadOnly  - Only generate and download diagram, don't insert into doc.
#                 Use for custom diagram embedding later in the doc.
#                 All the necessary format conversions will be completed.
#                 Result would be in `docs_src/generated` dir.
#                 If `downloadName` is specified then it would be used for
#                 file name, otherwise label would be used if diagram is
#                 specified via data, otherwise file name would be generated
#                 from `src` path.
#                 File extension would depend on `dformat` argument and on
#                 `fig.ext` options for R chunk
# service       - Rendering service ("kroki", "office", "splash", "yaml4schm",
#                 "drawio")
# serviceUrl    - Rendering service base url.
#                 This is starting part of url for service access.
#                 Default is path `http://kroki:8000` to local Kroki
#                 instance that is started with `make_doc.sh`
# engine        - Diagram rendering engine. Specify one of supported engines
#                 (see Kroki for engines list)
# page          - Page for rendering. For use with multipage office documents
#                 (multipage office documents support should become available
#                 after august of 2022)
# force         - If False(default) then existing rendered diagram data
#                 would be used. Set to True to regenerate diagram from scratch


##############################################################################

import os
import re
from flask import json
import yaml
from copy import deepcopy

import archivy.render.common as common
from archivy.render.common import get_param, to_abs_path
from archivy.render.kroki import render_kroki
from archivy.render.splash import render_splash
from archivy.render.office import render_office
from archivy.render.drawio import render_drawio
from archivy.render.svg_tools import resize as svg_resize
from archivy.render.svg_tools import convert_to as svg_convert

# TODO: everything that is printed into HTML should be made safe 

service_alias = {
    "krk" : "kroki",
    "ofc" : "office",
    "y4s" : "yaml4schm",
    "spl" : "splash",
    "drw" : "drawio",
}

service_render = {
    "kroki"     : render_kroki,
    "splash"    : render_splash,
    "office"    : render_office,
    "drawio"    : render_drawio,
    "yaml4schm" : None,             # NOTE: redirected to be rendered with splash
}

service_map = {
    ".vsd"      : ("office",    "draw"),
    ".odg"      : ("office",    "draw"),
    ".drawio"   : ("drawio",    "draw"),
}

# TODO: supported formats map

html_default_out_width_fallback = 672


def to_diagram(
      ref="",
      format="svg",
      data = "",
      src = "",
      dformat = "",
      rawsvg = True,
      downloadOnly = False,
      downloadName = "",
      service = "kroki",
      serviceUrl = None,
      engine = None,
      page = None,
      force = False,
      opts = {},
    ):

    service_defaults = {
        "kroki"     : get_param(opts, "RENDER_SVC_KROKI",    "http://127.0.0.1:8081"),
        "office"    : "local",
        "yaml4schm" : get_param(opts, "RENDER_SVC_Y4S",      "http://127.0.0.1:8088"),
        "splash"    : get_param(opts, "RENDER_SVC_SPLASH",   "http://127.0.0.1:8050"),
        "drawio"    : "local",
    }

    def get_service_url(service):
        # TODO: this seems to be redundant
        return get_param(opts, f"service_{service.lower()}", service_defaults[service])

    DEBUG = get_param(opts, "RENDER_DEBUG", False)
    is_html_output = True   # NOTE: option form R version of script. In this case - always True
    is_latex_output = False # NOTE: same case as above, but this time value is always False
    splash_engine = None
    auto_fit_width = None
    auto_fit_height = None

    errors = []

    if service in service_alias:
        service = service_alias[service]

    if service not in service_defaults:
        raise ValueError(
            f"service should be one of {', '.join(list(service_defaults.keys()) + list(service_alias.keys()))} but got '{service}'")

    if serviceUrl is None:
        serviceUrl = get_service_url(service)
    if service_defaults[service] == "local":
        serviceUrl = "local"

    # File name for downloaded diagram
    if downloadName != "":
        # Explicit case
        fname = downloadName
    elif src != "":
        # If source file is specified
        # then it's path would be used for downloaded file name
        fname = re.sub(r"[.]+/", "", src)
        fname = re.sub(r"[./: ]", "--", fname)
    else:
        # Otherwise use ref for file name
        fname = re.sub(r"[./: ]", "--", ref)

    if page is None:
        page = ""
    else:
        page = str(page)
        fname += "-"+page

    # Select download and output formats
    if dformat == "":
        dformat = "svg" # If format is not specified - svg would be used

    # Yaml4Schm is rendered with Splash
    # (due to the fact that schematic is rendered live and it takes some time)
    if service == "yaml4schm":
        is_y4s = True
        y4s_src = src
        draw_method = "draw"
        if engine == "d3hw" and (not is_html_output or dformat != "svg"):
            # NOTE: for d3hw engine with non-HTML output and non-SVG data
            # 'show' should be used instead of 'draw' (due to styles)
            draw_method = "show"
            if dformat == "svg":
               # SVG dformat should be used in this case for same reasons
               dformat = "png"
               format = "png"

        src = "/".join(serviceUrl, engine, draw_method, src)
        if engine == "d3hw":
            splash_engine = "chromium"
            auto_fit_width = ""
            auto_fit_height = ""

        fname += f"-{engine}"

        service = "splash"
        serviceUrl = get_service_url(service)
        engine = dformat
    else:
        is_y4s = False
        y4s_src = None

    # for Splash SVGs are grabbed out of HTML
    if service == "splash":
        fname += f"-{engine}"
        if engine == "svg":
            # For Splash and SVG output data should be obtained as HTML
            engine = "html"
            dformat = "svg"
        else:
            dformat = engine
            format = dformat
        if splash_engine is None:
            splash_engine = get_param(opts, "splash_engine", "chromium")
        fname += f"-{splash_engine}"

    # If download format is SVG then conversion for output format may be required
    if dformat == "svg":
        # If output format is not specified - use defaults
        if format is None:
            if is_latex_output:
                format = "pdf"      # PDF for PDF
            elif is_html_output:
                format = "svg"      # SVG for HTML
            else:
                format = "png"      # PNG for anything else
        # If it's office then dformat should be same as format
        if service == "office":
            dformat = format
    else:
        # If download format is other than SVG
        # then output format should be same as download format
        format = dformat

    # If output format is not svg then rawsvg is impossible
    if format != "svg":
        rawsvg = False

    # rawsvg can be used with HTML only
    if not is_html_output:
        rawsvg = False

    # Placement options (NOTE: in original script this is for Raw SVG only)
    if True or rawsvg:
        caption = opts.get("caption", None)
        width   = opts.get("width", None)
        height  = opts.get("height", None)
        align   = opts.get("align", None)
        if auto_fit_width is None:
            auto_fit_width = opts.get("auto_fit_width", None)
        if auto_fit_height is None:
            auto_fit_height = opts.get("auto_fit_height", None)

        html_default_out_width = get_param(
            opts, "html_default_out_width", html_default_out_width_fallback)

        if is_html_output and str(width) == str(html_default_out_width):
            width = None

        if caption is None:
            caption = ""

        if width is None:
            width = ""

        if height is None:
            height = ""

        if align is None:
            align = "center"

        if auto_fit_width is None:
            auto_fit_width = get_param(opts, "RENDER_AUTO_FIT_WIDTH", "84%")

        if auto_fit_height is None:
            auto_fit_height = get_param(opts, "RENDER_AUTO_FIT_HEIGHT", "800px")

    # Determine download and target path
    g_path = get_param(opts, "RENDER_GENERATED_PATH", ".dia-generated").replace(".", "_")
    if common.IMG_ROOT_PATH is not None:
        g_path = os.path.join(common.IMG_ROOT_PATH, g_path)
    if not os.path.exists(g_path):
        os.makedirs(g_path, exist_ok=True)

    g_path += common.PATH_SEP

    d_path = g_path + f"{fname}.{dformat}"
    t_path = g_path + f"{fname}.{format}"

    # Initialize file with error message
    # In case of success it will be replaced
    if True:
        with open(d_path, "w", encoding='utf-8') as f:
            f.write(f"Failed to get diagram image from service '{service}' ({serviceUrl})\n")

    # Render diagram
    if True:
        src_abs = src.replace("\\", "/")
        if len(src_abs) > 0:
            if src_abs[:1] != "/":
                src_abs = os.path.join(opts["__start_path__"], src)
            src_abs = to_abs_path(common.DATA_ROOT_PATH, src_abs)
        try:
            render_result, render_errors = service_render[service](
                data,
                src_abs,
                dformat,
                d_path,
                serviceUrl,
                engine,
                page,
                force,
                opts,
            )
            if render_errors is not None:
                errors += render_errors
            else:
                if render_result is not True:
                    errors.append(f"Didn't received positive result from service '{service}'!")
        except Exception as e:
            errors.append(f"Failed due to exception: {e}")

    if len(errors) > 0:
        with open(d_path, "w", encoding='utf-8') as f:
            f.write(f"Failed to get diagram image from service '{service}' ({serviceUrl})\n")
            f.write("\n")
            params = {
                "data": data,
                "src": src,
                "dformat": dformat,
                "service": service,
                "serviceUrl": serviceUrl,
                "engine": engine,
                "page": page,
                "force": force,
                "opts": opts,
            }
            yaml.safe_dump(params, f, indent=2, allow_unicode=True)
            f.write("\n")
            f.write("\n".join(errors))

    if len(errors) == 0:
        # Get SVG out of HTML using resizeSVG (it fits for current usecases)
        if dformat == "svg" and service == "splash":
            try:
                svg_resize(d_path, d_path, "-", "-")    # width and height are set to '-' to avoid resize
            except Exception as e:
                errors.append(f"Ripping SVG out of splash has been failed due to exception: {e}")

    if len(errors) == 0:
        # Convert SVG to necessary format
        if dformat == "svg" and format != "svg":
            if not os.path.exists(t_path):
                try:
                    svg_convert(format, d_path, t_path)
                except Exception as e:
                    errors.append(f"Converting SVG to 'format' failed due to exception: {e}")

    # Insert rendered diagram or errors message
    if not downloadOnly:
        img_path = t_path.replace("\\", "/")
        if common.IMG_ROOT_PATH is not None:
            img_path = t_path[len(common.IMG_ROOT_PATH):]
        if common.IMG_ROOT_PREFIX is not None:
            img_path = common.IMG_ROOT_PREFIX + img_path
        img_tag = ""
        result = []
        div_ref = ""
        if rawsvg and ref != "":
            div_ref = f'id="{ref}"'
        result.append(f'<div align="{align}" {div_ref}>')
        if len(errors) == 0:
            if rawsvg:
                try:
                    # TODO: add color rotate to svg if necessary
                    inline_svg = svg_resize(t_path, None, width, height, auto_fit_width, auto_fit_height)
                except Exception as e:
                    errors.append(f"Placing SVG inline failed due to exception: {e}")

        if len(errors) == 0:
            if rawsvg:
                if get_param(opts, "RENDER_BREAK_ON_ERR", "false").lower()=="true" \
                and os.path.exists(t_path+".err"):
                    return f"There were errors while generating '{t_path}'!"
                result.append(inline_svg)
            else:
                # TODO: add color rotate to div if necessary and it's not rawsvg
                img_tag = f'src="{img_path}"'
                if ref != "":
                    img_tag += f' id="{ref}"'
                if caption != "":
                    img_tag += f' alt="{caption}"'
                if re.match(width, "^\d+[%]?$"):
                    img_tag += f' width="{width}"'
                if re.match(height, "^\d+[%]?$"):
                    img_tag += f' height="{height}"'
                img_tag = f'<img {img_tag}>'
                result.append(img_tag)
        else:
            for err in errors:
                result.append(f"<p>{err}</p>")
        result.append("</div>")

        # Add caption and reference
        if caption != "":
            result.append(f'<div align="{align}">')
            result.append(f'<a href="{img_path}">{caption}</a>')
            result.append(f'</div>')

        result.append("\n")
        result = "\n".join(result)
    else:
        result = ""
    return result


def _extract_ssr(content):
    result = []
    fenced = ""
    kind = ""
    for line in content.split("\n"):
        if len(fenced) == 0:
            if line[:3] not in ("~~~", "```"):
                continue
            m = re.match(r"^(~+|`+)(ssr)\s*?$", line)
            if m is None:
                continue
            fenced = m.groups()[0]
            kind = m.groups()[1]
        else:
            if line.strip() == fenced:
                break
            result.append(line)
    return kind, "\n".join(result)

def _read_content(kind, content_path, content, fallback=True):
    # strip frontmatter header
    # parse header into args
    # set rest part as data
    # render at last
    lines = content.split('\n')
    if len(lines) < 3:
        return ["[ERROR]: Front matter header expected!"], None
    fm_raw = []
    if lines[0].strip() == "---":
        i = 1
        while i < len(lines):
            if lines[i] == "---":
                break
            fm_raw.append(lines[i].replace("\t", "    "))
            i += 1
        data = lines[i+1:]
    fm_raw = "\n".join(fm_raw)
    try:
        fm = yaml.safe_load(fm_raw)
    except Exception as e:
        return [f"[ERROR]:  Failed to parse header due to exception: {e}"], None

    supported_fields = {
        "ref"         : ("",      str),
        "format"      : ("svg",   str),
        "src"         : ("",      str),
        "dformat"     : ("",      str),
        "rawsvg"      : (True,    bool),
        "downloadOnly": (False,   bool),
        "downloadName": ("",      str),
        "service"     : ("kroki", str),
        "serviceUrl"  : (None,    str),
        "engine"      : (None,    str),
        "page"        : (None,    (int, str)),
        "force"       : (False,   bool),
        "env"         : (None,    dict),

        "caption"               : (None, str),
        "width"                 : (None, str),
        "height"                : (None, str),
        "align"                 : (None, str),
        "auto_fit_width"        : (None, str),
        "auto_fit_height"       : (None, str),
        "html_default_out_width": (None, str),
        "splash_engine"         : (None, str),
        "layers"                : (None, str),
        "transparent"           : (None, str),
    }

    opts = (
        "caption"               ,
        "width"                 ,
        "height"                ,
        "align"                 ,
        "auto_fit_width"        ,
        "auto_fit_height"       ,
        "html_default_out_width",
        "splash_engine"         ,
        "layers"                ,
        "transparent"           ,
    )

    env_vars = (
        "RENDER_SVC_KROKI"      ,
        "RENDER_SVC_Y4S"        ,
        "RENDER_SVC_SPLASH"     ,
        "RENDER_SPLASH_ENGINE"  ,
        "RENDER_DEBUG"          ,
        "RENDER_AUTO_FIT_WIDTH" ,
        "RENDER_AUTO_FIT_HEIGHT",
        "RENDER_GENERATED_PATH" ,
        "RENDER_BREAK_ON_ERR"   ,
        "RENDER_CACHE"          ,
        "RENDER_CACHE_PATH"     ,

        "RENDER_FORCE"          ,
    )

    render_args = {"opts": {}}
    errors = []
    for k, v in fm.items():
        if k not in supported_fields:
            errors.append(f"[ERROR]: Unsupported argument '{k}'!")
        else:
            if not isinstance(v, supported_fields[k][1]):
                errors.append(f"[ERROR]: Field '{k}' should be of type '{supported_fields[1]}'!")
            else:
                if k in opts:
                    render_args["opts"][k] = v
                else:
                    if k != "env":
                        render_args[k] = v
                    else:
                        for ek, ev in v:
                            if ek not in env_vars:
                                errors.append(f"[ERROR]: Unsupported env var '{ek}'!")
                            else:
                                if not isinstance(ev, str):
                                    errors.append(f"[ERROR]: Env var '{ek}' should be of type 'str'!")
                                else:
                                    render_args["opts"][ek] = ev
    if len(errors) > 0:
        return errors, None

    if render_args.get('src', "") != "":
        # Recurse if source is md
        if render_args['src'][-6:].lower() == "ssr.md":
            src_abs = render_args['src'].replace("\\", "/")
            if src_abs[:1] != "/":
                src_abs = os.path.join(os.path.split(content_path)[0], src_abs)
            src_abs = to_abs_path(common.DATA_ROOT_PATH, src_abs)
            if not os.path.exists(src_abs):
                errors.append(f"[ERROR]: Not found source '{render_args['src']}', referenced from '{content_path}'")
            elif not os.path.isfile(src_abs):
                errors.append(f"[ERROR]: Not a file at path '{render_args['src']}', referenced from '{content_path}'")
            else:
                try:
                    with open(src_abs, "r", encoding='utf-8') as f:
                        sub_content = f.read()
                    kind, sub_content = _extract_ssr(sub_content)
                    if kind == "":
                        sub_errors = [f"[ERROR]: Failed to find ssr section in source '{render_args['src']}', from '{content_path}'"]
                        sub_args = None
                    else:
                        sub_errors, sub_args = _read_content("from_file", src_abs, sub_content, fallback=False)
                except Exception as e:
                    errors += [f"[ERROR]: Failed to load source '{render_args['src']}', from '{content_path}' due to exception: {e}"]
                errors += sub_errors
                if len(errors) > 0:
                    return errors, None
                del render_args["src"]
                for sk, sv in sub_args.items():
                    if sk not in ("opts") and sk not in render_args:
                        render_args[sk] = sv
                for sk, sv in sub_args["opts"].items():
                    if sk not in render_args["opts"]:
                        render_args["opts"][sk] = sv
                # TODO: probably it would be better to update src, not set __start_path__
                if "__start_path__" not in render_args["opts"]:
                    drp_norm = os.path.normpath(common.DATA_ROOT_PATH)
                    render_args["opts"]["__start_path__"] = os.path.split(src_abs[len(drp_norm)+1:])[0]
    else:
        # Use data from content
        render_args['data'] = data

    # Map params by extension:
    if "src" in render_args:
        if "service" not in render_args:
            for k, v in service_map.items():
                if render_args["src"][-len(k):].lower() == k:
                    render_args["service"] = v[0]
                    render_args["engine"] = v[1]
                    break

    # Fallback non initialized values to defaults
    if fallback:
        for k, v in supported_fields.items():
            if k not in opts and k != "env":
                if k not in render_args:
                    render_args[k] = supported_fields[k][0]

    return [], render_args


def render(kind, objid, content):
    content_path = objid.replace("--", "/") + ".md"
    errors, render_args = _read_content(kind, content_path, content)

    if len(errors) > 0:
        return "\n".join(errors)    # TODO: HTML escaping

    if "RENDER_GENERATED_PATH" not in render_args["opts"]:
        render_args["opts"]["RENDER_GENERATED_PATH"] = content_path + "/generated"

    if "__start_path__" not in render_args["opts"]:
        render_args["opts"]["__start_path__"] = os.path.split(content_path)[0]

    return to_diagram(**render_args)
