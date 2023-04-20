import os
import re
import hashlib


PARAMS = {}
IMG_ROOT_PATH = None
IMG_ROOT_PREFIX = None
DATA_ROOT_PATH = None
DATA_ROOT_PREFIX = None
CACHE_ROOT_PATH = None
PATH_SEP = os.path.join("a","b")[1]

# TODO: data domains and paths to them

def get_param(opts, param, fallback):
    if param in opts and opts[param] is not None:
        return opts[param]
    if PARAMS is None or param not in PARAMS:
        return os.environ.get(param.upper(), fallback)
    else:
        return PARAMS[param]


def get_cache(opts):
    cache = get_param(opts, "RENDER_CACHE", "true").lower() == "true"
    cache_dir = get_param(opts, "RENDER_CACHE_PATH", ".render-cache")
    if cache and cache_dir == "":
        raise ValueError("using cache without cache dir (RENDER_CACHE_PATH) specified!")
    if CACHE_ROOT_PATH is None:
        raise ValueError("using cache without CACHE_ROOT_PATH specified!")
    cache_dir = os.path.join(CACHE_ROOT_PATH, cache_dir)
    return cache, cache_dir


def digest(data=None, file=None):
    if data is None and file is None:
        raise ValueError("digest: data or file should be specified!")
    if data is not None and file is not None:
        raise ValueError("digest: only one of data or file should be specified!")
    if file is not None:
        with open(file, "rb") as f:
            data = f.read()
    return hashlib.md5(data).hexdigest()


def to_abs_path(root_path, path):
    path_abs = path
    if path_abs [:1] == "/":
        path_abs = re.sub("^/+", "", path_abs)
        path_abs = os.path.normpath(os.path.join(root_path, path_abs))
    else:
        path_abs = os.path.normpath(os.path.join(root_path, path_abs))
    drp_norm = os.path.normpath(root_path)
    if path_abs[:len(drp_norm)+1] != drp_norm + PATH_SEP:
        raise ValueError(f"Path {path} is outside root path!")
    return path_abs