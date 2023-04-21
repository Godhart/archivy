from archivy.render.local import render_local

def render_drawio(
    data,           # NOTE: data is not used by render_drawio
    src,
    dformat,
    d_path,
    serviceUrl,     # NOTE: serviceUrl is not used by render_drawio
    engine,
    page,
    force,
    opts,
):
    if src == "":
        raise ValueError("Draw.io supports input from files only!")

    # Command line for converting image with drawio
    drawio_opts = ["-x", "-f", dformat, "-o", d_path, ]

    width = opts.get("width", None)
    if width not in (None, ""):
        drawio_opts += ["--width", width]

    height = opts.get("height", None)
    if height not in (None, ""):
        drawio_opts += ["--height", height]

    if page != "":
        drawio_opts += ["-p", f"{page}"]
    else:
        if dformat == "pdf":
            drawio_opts += ["-a"]

    if dformat == "pdf":
        drawio_opts += ["--crop"]

    if dformat == "svg":
        drawio_opts += ["--embed-svg-images"]

    transp = opts.get("transparent", None)
    if transp.lower() in ("yes", "true"):
        drawio_opts += ["-t"]

    layers = opts.get("layers", None)
    if layers not in (None, ""):
        drawio_opts += ["-l", layers]

    serviceUrl = ["draw.io", *drawio_opts, src]

    return render_local(data, src, dformat, d_path, serviceUrl, engine, page, force, opts)
