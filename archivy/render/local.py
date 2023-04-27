import subprocess
import os
import shutil

from archivy.render.common import digest, get_param, get_cache


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
    custom_result_lookup = None,
    post_process = None,
    custom_cache = None,
):
    # At this level only data from source is supported
    if src == "":
        raise ValueError("render_local requires src to be specified!")

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

    # Make target dir
    if not os.path.exists(os.path.split(d_path)[0]):
        os.makedirs(os.path.split(d_path)[0], exist_ok=True)

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

        if custom_result_lookup is None:
            result_path = d_path
        else:
            result_path = custom_result_lookup()

        if result_path is not None:
            # Do necessary post processing
            if post_process is not None:
                post_process(result_path)
            # Copy from custom path to destination path
            if custom_result_lookup is not None:
                if os.path.exists(d_path):
                    os.unlink(d_path)
                shutil.copy2(result_path, d_path)
            # Store results to cache
            if cache and cache_path != "":
                os.makedirs(cache_dir, exist_ok=True)
                if os.path.exists(cache_path):
                    os.unlink(cache_path)
                shutil.copy2(result_path, cache_path)
                if custom_cache is not None:
                    if os.path.exists(cache_path+".custom"):
                        shutil.rmtree(cache_path+".custom")
                    for custom_name, custom_path in custom_cache().items():
                        if not os.path.exists(custom_path):
                            continue
                        cached_path = os.path.join(cache_path+".custom", custom_name)
                        if os.path.isfile(custom_path):
                            shutil.copy2(custom_path, cached_path)
                        else:
                            shutil.copytree(custom_path, cached_path)

    else:
        # Otherwise copy cached data into destination path
        if os.path.exists(d_path):
            os.unlink(d_path)
        shutil.copy2(cache_path, d_path)
        if custom_cache is not None:
            for custom_name, custom_path in custom_cache().items():
                cached_path = os.path.join(cache_path+".custom", custom_name)
                if os.path.exists(custom_path):
                    if os.path.isfile(custom_path):
                        os.unlink(custom_path)
                    else:
                        shutil.rmtree(custom_path)
                if not os.path.exists(cached_path):
                    continue
                if os.path.isfile(cached_path):
                    shutil.copy2(cached_path, custom_path)
                else:
                    shutil.copytree(cached_path, custom_path)

    return True, None
