import subprocess
import os
import shutil

from archivy.render.common import get_param, get_cached_name, update_from_cache, update_cache, sync_files


def render_local(
    src,
    dformat,
    d_path,
    serviceUrl,     # NOTE: should be a list of args
    engine,
    page,
    force,
    opts,
    output_path = None,
    output_path_cleanup = True,
    custom_result_lookup = None,
    post_process = None,
    custom_cache = None,
    extras = None,
    shell = False,
):
    # At this level only data from source is supported
    if src == "":
        raise ValueError("render_local requires src to be specified!")
    
    if extras is None:
        extras = {}

    if "service" not in extras:
        extras['service'] = serviceUrl[0]

    if "engine" not in extras:
        extras['engine'] = engine

    cached_name = get_cached_name(src, dformat, page, extras)

    # If image is not cached or forced - get image
    if force or get_param(opts, "RENDER_FORCE", "false").lower() == "true" \
    or not update_from_cache(cached_name, d_path, opts, custom_cache):

        # Determine output results path
        if output_path is None:
            result_path = d_path
        else:
            result_path = output_path

        # Determine whether or not output path is dir
        if result_path[-1:] in ("\\", "/"):
            result_path_is_dir = True
            result_path = result_path[:-1]
        else:
            result_path_is_dir = False

        # Cleanup result path
        if os.path.exists(result_path):
            if os.path.isfile(result_path):
                os.unlink(result_path)
            else:
                shutil.rmtree(result_path)

        # Make target dir
        if not os.path.exists(os.path.split(d_path)[0]):
            os.makedirs(os.path.split(d_path)[0], exist_ok=True)

        # Make output host dir
        if not os.path.exists(os.path.split(result_path)[0]):
            os.makedirs(os.path.split(result_path)[0], exist_ok=True)

        # Make output dir if necessary:
        if result_path_is_dir:
            os.makedirs(result_path, exist_ok=True)

        # Convert
        sub_result = subprocess.run(serviceUrl, shell=shell)

        # Lookup for necessary result output if specified
        if custom_result_lookup is not None:
            result_path = custom_result_lookup()

        if os.path.exists(result_path):
            # Do necessary post processing
            if post_process is not None:
                post_process(result_path)
            # Copy from custom path to destination path
            if result_path != d_path:
                sync_files(result_path, d_path)
            # Store results to cache
            update_cache(cached_name, d_path, opts, custom_cache)

            # Cleanup temporary result path
            if result_path != d_path:
                if os.path.exists(result_path):
                    if os.path.isfile(result_path):
                        os.unlink(result_path)
                    else:
                        shutil.rmtree(result_path)

            # Cleanup output path
            if output_path is not None and output_path_cleanup:
                if os.path.exists(output_path):
                    if os.path.isfile(output_path):
                        os.unlink(output_path)
                    else:
                        shutil.rmtree(output_path)

        else:
            return False, [f"No results on expected path '{result_path}'!"]

    return True, None
