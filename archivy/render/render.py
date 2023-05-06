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
from archivy.render.common import get_param, to_abs_path, default_handlers
from archivy.render.svg_tools import modify as svg_modify
from archivy.render.svg_tools import convert_to as svg_convert
from archivy.render.html_tools import get_body as html_get_body
from archivy.data import sanitize_path

import archivy.render.office
import archivy.render.drawio
import archivy.render.symbolator
import archivy.render.pandoc
import archivy.render.y4s
import archivy.render.picture
import archivy.render.pdf

# TODO: everything that is printed into HTML should be made safe


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
      handlers = default_handlers
    ):

    DEBUG = get_param(opts, "RENDER_DEBUG", False)
    is_html_output = True   # NOTE: option form R version of script. In this case - always True
    is_latex_output = False # NOTE: same case as above, but this time value is always False
    auto_fit_width = None
    auto_fit_height = None

    background = opts.get("background", [os.environ.get("RENDER_DEFAULT_BACKGROUND", "#FFFFFF"), "#FFFFFF00"][rawsvg])

    errors = []

    if service in handlers.aliases():
        service = handlers.service_dealias(service)
    else:
        if service not in handlers.services():
            raise ValueError(
                f"service should be one of {', '.join(list(handlers.services()) + list(handlers.aliases()))} but got '{service}'")

    if serviceUrl is None:
        serviceUrl = handlers.service_defaultUrl(service)

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
    formats = handlers.formats(service, engine)

    # If output format is not specified - use defaults
    if format is None:
        if is_latex_output:
            format = "pdf"      # PDF for PDF
        elif is_html_output:
            format = "svg"      # SVG for HTML
        else:
            format = "png"      # PNG for anything else
        # If format is not supported by tool - fallback to first supported
        # TODO: make sure it's compatible with output
        if format not in formats:
            format = formats[0]

    if format in formats:
        # If format is supported by service
        if dformat == "":
            # if not specified explicitly then download format should be the same
            dformat = format
        elif dformat == "svg":
            # if dformat is specified explicitly then make sure it's compatible
            if dformat not in formats:
                raise ValueError(f"dformat '{dformat}' is not supported by service '{service}'!")
            # Conversion is supported only for pdf and png
            if format not in ("pdf", "svg"):
                raise ValueError(f"Conversion from '{dformat}' to '{format}' is not supported!")
        elif format != dformat:
            raise ValueError("Only conversion 'svg' to 'pdf' or 'png' is supported!")
    else:
        # If service not supports this format then try to get svg then convert
        if dformat == "":
            # Automatically pick download format
            if format in ("pdf", "png"):
                if "svg" not in formats:
                    raise ValueError(
                        f"Format '{format}' is not supported by '{service}'"
                        f" and also there is no supported format ('svg') to convert from!"
                        f" Chose format one of ({', '.join(formats)})")
                else:
                    dformat = "svg"
            else:
                raise ValueError(
                    f"Format '{format}' is not supported by '{service}'"
                    f" and conversion from other formats also is not supported!"
                    f" Chose format one of ({', '.join(formats)})")
        else:
            # If download format is specified explicitly
            # (everything is defined, only do checks)
            if format in ("pdf", "png"):
                if format != dformat and dformat != "svg":
                    raise ValueError("Only conversion 'svg' to 'pdf' or 'png' is supported!")
                if dformat not in formats:
                    raise ValueError(
                        f"Format '{format}' is not supported by '{service}'"
                        f" and also there is no supported format ('svg') to convert from!"
                        f" Chose format one of ({', '.join(formats)})")
            else:
                raise ValueError(
                    "Only conversion 'svg' to 'pdf' or 'png' is supported!"
                    f" Chose format one of ({', '.join(formats)})"
                )
                if dformat not in formats:
                    raise ValueError(f"dformat '{dformat}' is not supported by service '{service}'!")

    # If output format is not svg then rawsvg is impossible
    if format != "svg":
        rawsvg = False

    # rawsvg can be used with HTML only
    if not is_html_output:
        rawsvg = False

    # Get misc options
    caption = opts.get("caption", None)
    if caption is None:
        caption = ""

    # Placement options
    if format not in common.IMAGE_FORMATS:
        # Fallback for non-image format
        width   = ""
        height  = ""
        align   = "center"
        auto_fit_width = "100%"
        auto_fit_height = "800px"
    else:
        width   = opts.get("width", None)
        height  = opts.get("height", None)
        align   = opts.get("align", None)
        if auto_fit_width is None:
            auto_fit_width = opts.get("auto-fit-width", None)
        if auto_fit_height is None:
            auto_fit_height = opts.get("auto-fit-height", None)

        html_default_out_width = get_param(
            opts, "html_default_out_width", html_default_out_width_fallback)

        if is_html_output and str(width) == str(html_default_out_width):
            width = None

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

    inversion   = opts.get("inversion", "auto").lower()
    dark_theme = opts.get("dark-theme", False)
    if inversion not in ("auto", "opposite", "yes", "true", "no", "false"):
        raise ValueError(f"'inversion' property should be on of ('auto', 'none', 'yes', 'true', 'no', 'false'), got '{inversion}'!")
    if inversion in ('yes', 'true'):
        inversion = True
    elif inversion in ('no', 'false'):
        inversion = False
    elif inversion == "auto":
        inversion = dark_theme
    else:
        inversion = not dark_theme

    if not inversion:
        inversion = ""
    else:
        inversion = 'filter: brightness(0.85) invert() hue-rotate(180deg);'


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
            render_result, render_errors = handlers.service_render(service)(
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
        # Get SVG out of HTML using modify_svg (it fits for current usecases)
        if dformat == "svg" and service == "splash":
            try:
                svg_modify(d_path, d_path, "-", "-", background=background)    # width and height are set to '-' to avoid resize
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
            img_path = img_path[len(common.IMG_ROOT_PATH):]
        if common.IMG_ROOT_PREFIX is not None:
            img_path = common.IMG_ROOT_PREFIX + img_path
        img_path = sanitize_path(img_path)
        img_tag = ""
        result = []
        div_ref = ""
        if rawsvg and ref != "":
            div_ref = f'id="{ref}"'

        if format in common.IMAGE_FORMATS and format != "pdf":
            image_style = ""
            if inversion != "":
                image_style = f'style="{inversion}"'
            result.append(f'<div align="{align}" {div_ref} {image_style}>')
            if len(errors) == 0:
                if rawsvg:
                    try:
                        if os.path.exists(t_path+".err"):
                            os.unlink(t_path+".err")
                        inline_svg = svg_modify(t_path, None, width, height, auto_fit_width, auto_fit_height, background)
                    except Exception as e:
                        errors.append(f"Placing SVG inline failed due to exception: {e}")

            if len(errors) == 0:
                if rawsvg:
                    if get_param(opts, "RENDER_BREAK_ON_ERR", "false").lower()=="true" \
                    and os.path.exists(t_path+".err"):
                        return f"There were errors while generating '{t_path}'!"
                    result.append(inline_svg)
                else:
                    img_tag = f'src="{img_path}"'
                    if ref != "":
                        img_tag += f' id="{ref}"'
                    if caption != "":
                        img_tag += f' alt="{caption}"'
                    if width not in (None, ""):
                        img_tag += f' width="{width}"'
                    if height not in (None, ""):
                        img_tag += f' height="{height}"'
                    img_tag = f'<img {img_tag}>'
                    result.append(img_tag)
            else:
                for err in errors:
                    result.append(f"<code>{err}</code>")
            result.append("</div>")
        elif format == "html":
            if opts.get("inversion-all", False) is True:        # NOTE: Implicit option, defined and set only by specific renders
                result.append(f'<div {div_ref} style="{inversion}">')
                html_content = html_get_body(t_path, "no")
            else:
                result.append(f'<div {div_ref}>')
                html_content = html_get_body(t_path, inversion)
            result.append(html_content)
            result.append("</div>")
        elif format == "pdf":
            result.append(f'<div {div_ref} style="{inversion}">')
            pdf_tag = f'<embed src="{img_path}" '

            if width in (None, ""):
                width = opts.get("auto-fit-width", None)
            if width in (None, ""):
                width = "100%"

            if height in (None, ""):
                height = opts.get("auto-fit-height", None)
            if height in (None, ""):
                height = "800px"

            if width not in (None, ""):
                pdf_tag += f' width="{width}"'
            if height not in (None, ""):
                pdf_tag += f' height="{height}"'

            pdf_tag += ' type="application/pdf">'
            result.append(pdf_tag)
            result.append("</div>")
        else:
            result.append(f'<div align="{align}" {div_ref}>')
            errors.append(f"Data format '{format}' is not supported yet!")
            if len(errors) == 0:
                pass
            else:
                for err in errors:
                    result.append(f"<p>{err}</p>")
            result.append("</div>")

        # Add caption
        if caption != "":
            result.append(f'<div align="{align}">')
            link = opts.get("_link_", None)
            if link is None and format in common.IMAGE_FORMATS:
                link = img_path
            if link != "":
                result.append(f'<a href="{link}">{caption}</a>')
            else:
                result.append(f'{caption}')
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
            m = re.match(r"^(~{3,}|`{3,})"+common.SSR_RE+"\s*?$", line)
            if m is None:
                continue
            fenced = m.groups()[0]
            kind = m.groups()[1]
        else:
            if line.strip() == fenced:
                break
            result.append(line)
    return kind, "\n".join(result)

def _get_service_engine(kind):
    m = re.match(r"^"+common.SSR_RE+r"$", kind)
    if m is None:
        raise ValueError(f"Unexpected kind: {kind}")
    quick = kind[2] == "q"
    if len(kind) == 3:
        return quick, None, None
    if "--" in kind[4:]:
        return quick, *(kind[4:].split("--", 1))
    else:
        return quick, kind[4:], None

def _read_content(content_source, content_path, content, service=None, engine=None, quick=False, fallback=True):
    # strip frontmatter header
    # parse header into args
    # set rest part as data
    # render at last
    if not quick:
        lines = content.split('\n')
        if service is None:
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
        data = "\n".join(lines)
    else:
        fm_raw = content
        data = ""
    if fm_raw != "":
        try:
            fm = yaml.safe_load(fm_raw)
        except Exception as e:
            return [f"[ERROR]:  Failed to parse header due to exception: {e}"], None
    else:
        fm = {}

    render_args = {"opts": {}}
    errors = []

    # Load nested first:
    if fm.get("src", "")[-6:].lower() == "ssr.md":
        src_abs = fm['src'].replace("\\", "/")
        if src_abs[:1] != "/":
            src_abs = os.path.join(os.path.split(content_path)[0], src_abs)
        src_abs = to_abs_path(common.DATA_ROOT_PATH, src_abs)
        if not os.path.exists(src_abs):
            errors.append(f"[ERROR]: Not found source '{fm['src']}', referenced from '{content_path}'")
        elif not os.path.isfile(src_abs):
            errors.append(f"[ERROR]: Not a file at path '{fm['src']}', referenced from '{content_path}'")
        else:
            try:
                with open(src_abs, "r", encoding='utf-8') as f:
                    sub_content = f.read()
                kind, sub_content = _extract_ssr(sub_content)
                if kind == "":
                    sub_errors = [f"[ERROR]: Failed to find ssr section in source '{fm['src']}', from '{content_path}'"]
                    sub_args = None
                else:
                    sub_quick, sub_service, sub_engine = _get_service_engine(kind)
                    sub_errors, sub_args = _read_content(
                        f"{content_source}:{fm['src']}", src_abs, sub_content, sub_service, sub_engine, sub_quick, fallback=False)
            except Exception as e:
                errors += [f"[ERROR]: Failed to load source '{fm['src']}', from '{content_path}' due to exception: {e}"]
            errors += sub_errors
            if len(errors) > 0:
                return errors, None

            del fm["src"]

            for sk, sv in sub_args.items():
                if sk not in ("opts"):
                    render_args[sk] = sv
            for sk, sv in sub_args["opts"].items():
                render_args["opts"][sk] = sv
            # Store path for referencing
            drp_norm = os.path.normpath(common.DATA_ROOT_PATH)
            render_args["opts"]["__start_path__"] = os.path.split(src_abs[len(drp_norm)+1:])[0]

    if len(errors) > 0:
        return errors, None

    # Prohibit service and engine opts if they are specified via args
    if service is not None:
        if "service" in fm:
            errors += [f"[ERROR]: 'service' option is not allowed if service is determined by fenced chunk name!"]

    if engine is not None:
        if "engine" in fm:
            errors += [f"[ERROR]: 'engine' option is not allowed if service is determined by fenced chunk name!"]

    if len(errors) > 0:
        return errors, None

    # Determine service and engine from options if not specified yet
    if service is None:
        if "service" in fm:
            k, v = "service", fm["service"]
            supported, required_type = common.default_handlers.supported_field(service, k, v)
            if required_type is not True:
                errors.append(f"[ERROR]: Option '{k}' should be one of following types [{', '.join([str(rt)] for rt in required_type)}]!")
            service = v

    if engine is None:
        if "engine" in fm:
            k, v = "service", fm["service"]
            supported, required_type = common.default_handlers.supported_field(service, k, v)
            if required_type is not True:
                errors.append(f"[ERROR]: Option '{k}' should be one of following types [{', '.join([str(rt)] for rt in required_type)}]!")
            engine = v

    # Determine service and engine from source
    if service is None or engine is None:
        if "src" in fm:
            predict_service, predict_engine = common.default_handlers.service_map(fm["src"])
            if service is None:
                service = predict_service
            if engine is None:
                engine = predict_engine

    # Fallback to values from nested source
    if service is None:
        service = render_args.get("service", None)
    if engine is None:
        engine = render_args.get("engine", None)

    # Service should be known at this moment
    if service is None:
        errors.append(f"[ERROR]: Can't determine required ssr service!")

    if len(errors) > 0:
        return errors, None

    # Dealias service
    if service in common.default_handlers.aliases():
        service = common.default_handlers.service_dealias(service)

    # Sanity checks for service and engine
    if service not in common.default_handlers.services():
        errors.append(f"[ERROR]: Service '{service}' is not supported!")
    else:
        if engine is not None:
            if engine not in common.default_handlers.engines(service):
                errors.append(f"[ERROR]: Engine '{engine}' is not supported by service '{service}'!")

    if len(errors) > 0:
        return errors, None

    render_args["service"] = service

    if engine is not None:
        render_args["engine"] = engine

    # Get other options
    general_fields = common.default_handlers.general_fields()
    env_vars = common.default_handlers.env_vars(service)
    for k, v in fm.items():
        if k != "env":
            if k in ("service", "engine"):
                continue
            supported, required_type = common.default_handlers.supported_field(service, k, v)
            if not supported:
                errors.append(f"[ERROR]: Unsupported option '{k}'!")
            elif required_type is not True:
                errors.append(f"[ERROR]: Option '{k}' should be one of following types [{', '.join([str(rt)] for rt in required_type)}]!")
            else:
                if k not in general_fields:
                    render_args["opts"][k] = v
                else:
                    render_args[k] = v
        else:
            for ek, ev in v:
                if ek not in env_vars:
                    errors.append(f"[ERROR]: Unsupported env var '{ek}'!")
                else:
                    if not isinstance(ev, str):
                        errors.append(f"[ERROR]: Env var '{ek}' should be of type 'str'!")
                    else:
                        supported, _ = common.default_handlers.supported_field(service, k, v)
                        if supported:
                            errors.append(f"[ERROR]: Environment variable name '{ek}' has been crossed with option name!")
                        else:
                            render_args["opts"][ek] = ev
    if len(errors) > 0:
        return errors, None

    # Use data from content if source is not given
    if render_args.get('src', "") == "":
        render_args['data'] = data

    # Fallback non initialized values to defaults
    if fallback:
        service_defaults = common.default_handlers.service_defaults(service)
        for k, v in service_defaults.items():
            if k == "env":
                continue
            if k in general_fields:
                if k not in render_args:
                    render_args[k] = v
            else:
                if k not in render_args["opts"]:
                    render_args["opts"][k] = v

    return [], render_args


def render(kind, objid, content, options):
    try:
        content_path = objid.replace("--", "/") + ".md"
        quick, service, engine = _get_service_engine(kind)
        errors, render_args = _read_content("request", content_path, content, service, engine, quick)

        if len(errors) > 0:
            return "\n".join(errors)    # TODO: HTML escaping

        for k, v in options.items():
            render_args["opts"][k] = v

        if "RENDER_GENERATED_PATH" not in render_args["opts"]:
            render_args["opts"]["RENDER_GENERATED_PATH"] = content_path + "/generated"

        if "__start_path__" not in render_args["opts"]:
            render_args["opts"]["__start_path__"] = os.path.split(content_path)[0]

        return to_diagram(**render_args)
    except Exception as e:
        return f"<code>Failed due to exception: {e}</code>"
