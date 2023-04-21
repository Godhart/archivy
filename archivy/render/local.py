import subprocess
import os
import shutil

from archivy.render.common import digest, get_param, get_cache
import random
import datetime


def render_local(
    data,
    src,
    dformat,
    d_path,
    serviceUrl,     # NOTE: should be a list of args
    engine,
    page,
    force,
    opts,
):
    # Cache things
    cache, cache_dir = get_cache(opts)

    # If data is given - save it into cache dir and then use as source
    if src == "":
        if cache:
            src = os.path.join(
                cache_path,
                f"{int(datetime.datetime.now().timestamp*1000000)}-"
                f"{random.randint(0, 1000000)}.inline"
                )
        else:
            raise ValueError("Enable cache for rendering from inline data")

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

        # Convert
        result = subprocess.run(serviceUrl)

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
