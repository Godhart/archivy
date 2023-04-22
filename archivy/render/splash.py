from archivy.render.common import default_handlers, handler_info, handler_engine, get_param

def render_splash(
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
    raise NotImplementedError("TODO: render_splash")


default_handlers.register_handler(
    handler_info(
        service     = "splash",
        alias       = "spl",
        opts        = {
            "splash_engine" : (None, str),
        },
        env         = {
            "RENDER_SVC_SPLASH"     : None,
            "RENDER_SPLASH_ENGINE"  : None,
        },
        engines     = {
            "chromium": handler_engine(
                exts =      [],
                formats =   ["html",]
            ),
        },
        serviceUrl  = get_param({}, "RENDER_SVC_SPLASH",   "http://127.0.0.1:8050"),
        fun         = render_splash
    )
)
