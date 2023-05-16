import os
import re
import hashlib
import random
import datetime
import json
import filecmp
from pathlib import Path
import shutil


PARAMS = {}
IMG_ROOT_PATH = None
IMG_ROOT_PREFIX = None
DATA_ROOT_PATH = None
DATA_ROOT_PREFIX = None
CACHE_ROOT_PATH = None
PATH_SEP = os.path.join("a","b")[1]
IMAGE_FORMATS = ("svg", "png", "pdf", "jpg", "gif")
SSR_RE = r"(ss[qr](?:-[\w]+(?:--[\w]+)?)?)"

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


def temp_file_path(opts, extension):
    # Cache things
    _, cache_dir = get_cache(opts)

    return os.path.join(
        cache_dir,
        f"temp-{int(datetime.datetime.now().timestamp()*1000000)}-"
        f"{random.randint(0, 1000000)}{extension}"
        )


def sync_files(src, dst, allow_delete=False):
    if not os.path.exists(src):
        if not allow_delete:
            return
        if os.path.exists(dst):
            if os.path.isfile(dst):
                os.unlink(dst)
            else:
                shutil.rmtree(dst)
        return False

    if os.path.isfile(src):
        if not os.path.exists(dst) or not os.path.isfile(dst):
            pass
        else:
            if filecmp.cmp(src, dst, shallow=False):
                return True
    else:
        if not os.path.exists(dst) or not os.path.isdir(dst):
            pass
        else:
            src_files = tuple(Path(src).glob("**/*"))
            dst_files = tuple(Path(dst).glob("**/*"))
            if len(src_files) == len(dst_files) and src_files == dst_files:
                _, mismatch, errors = filecmp.cmpfiles(src, dst, src_files, shallow=False)
                if len(mismatch) == 0 and len(errors) == 0:
                    return True

    if os.path.exists(dst):
        if os.path.isfile(dst):
            os.unlink(dst)
        else:
            shutil.rmtree(dst)

    os.makedirs(os.path.split(dst)[0], exist_ok=True)

    if os.path.isfile(src):
        shutil.copy2(src, dst)
    else:
        shutil.copytree(src, dst)

    return True


def get_cached_name(src, dformat, page, extras):
    if page not in (None, ""):
        page = "-" + page
    extras_digest = ""
    if extras is not None and len(extras) > 0:
        extras_digest = "-" + hashlib.md5(json.dumps(extras, sort_keys=True).encode()).hexdigest()
    result = f"{digest(file = src)}{page}{extras_digest}.{dformat}"
    return result


def update_from_cache(cached_name, dst, opts, custom_cache=None):
    cache, cache_dir = get_cache(opts)
    if not cache:
        return False
    cached_path = os.path.join(cache_dir, cached_name)
    result = sync_files(cached_path, dst, allow_delete=True)
    if custom_cache is not None:
        custom_cache_path = cached_path+".custom"
        if not result:
            if os.path.exists(custom_cache_path):
                shutil.rmtree(custom_cache_path)
            for custom_name, custom_path in custom_cache().items():
                if not os.path.exists(custom_path):
                    continue
                if os.path.isfile(custom_path):
                    os.unlink(custom_path)
                else:
                    shutil.rmtree(custom_path)
        else:
            for custom_name, custom_path in custom_cache().items():
                sync_files(os.path.join(custom_cache_path, custom_name), custom_path, allow_delete=True)
    return result


def update_cache(cached_name, path, opts, custom_cache=None):
    cache, cache_dir = get_cache(opts)
    if not cache:
        return False
    cached_path = os.path.join(cache_dir, cached_name)
    result = sync_files(path, cached_path, allow_delete=True)
    if custom_cache is not None:
        custom_cache_path = cached_path+".custom"
        if not result:
            if os.path.exists(custom_cache_path):
                shutil.rmtree(custom_cache_path)
        else:
            for custom_name, custom_path in custom_cache().items():
                sync_files(custom_path, os.path.join(custom_cache_path, custom_name), allow_delete=True)
    return result


class handler_engine(object):

    def __init__(
            self,
            exts: dict,
            formats:dict,
    ):
        self.exts = exts
        self.formats = formats


class handler_info(object):

    def __init__(
            self,
            service:str,
            alias:str,
            opts:dict,
            env:dict,
            engines:dict,
            serviceUrl:str,
            fun,
            ):
        self.service = service
        self.alias = alias
        self.opts = opts
        self.env = env
        self.engines = engines
        self.serviceUrl = serviceUrl
        self.fun = fun


class ssr_handlers(object):

    _supported_fields = {
        "ref"         : ("",      str),
        "format"      : (None,    str),
        "src"         : ("",      str),
        "dformat"     : ("",      str),
        "rawsvg"      : (os.environ.get("RENDER_DEFAULT_RAWSVG", "false").lower() == "true",
                                  bool),
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
        "auto-fit-width"        : (None, str),
        "auto-fit-height"       : (None, str),
        "html-default-out-width": (None, str),
        "inversion"             : ("auto", str),
        "dark-theme"            : (False, bool),
        "background"            : (None, str),
    }

    _opts = (
        "caption"               ,
        "width"                 ,
        "height"                ,
        "align"                 ,
        "auto-fit-width"        ,
        "auto-fit-height"       ,
        "html-default-out-width",
        "inversion"             ,
        "dark-theme"            ,
        "background"            ,
    )

    _env_vars = (
        "RENDER_DEBUG"          ,
        "RENDER_AUTO_FIT_WIDTH" ,
        "RENDER_AUTO_FIT_HEIGHT",
        "RENDER_GENERATED_PATH" ,
        "RENDER_BREAK_ON_ERR"   ,
        "RENDER_CACHE"          ,
        "RENDER_CACHE_PATH"     ,

        "RENDER_FORCE"          ,
        "RENDER_DEFAULT_BACKGROUND",
    )

    def __init__(self):
        self._handlers = {}

    def register_handler(self, handler:handler_info):
        if handler not in self._handlers:
            self._handlers[handler.service] = handler
        # TODO: misc checks like unique alias, ext cross

    def services(self):
        return self._handlers.keys()

    def aliases(self):
        return [v.alias for v in self._handlers.values()]

    def service_dealias(self, alias):
        for service, v in self._handlers.items():
            if alias == v.alias:
                return service
        raise ValueError(f"No service is registered with alias '{alias}'")

    def service_render(self, service):
        if service not in self._handlers:
            raise ValueError(f"No service is registered with name '{service}'")
        return self._handlers[service].fun

    def service_map(self, src):
        for service, v in self._handlers.items():
            for eng, eng_v in v.engines.items():
                for ext in eng_v.exts:
                    if src[-len(ext):] == ext:
                        return service, eng
        return None, None

    def service_defaultUrl(self, service):
        if service not in self._handlers:
            raise ValueError(f"No service is registered with name '{service}'")
        return self._handlers[service].serviceUrl

    def general_fields(self):
        return [k for k in self._supported_fields.keys() if k not in self._opts]

    def supported_field(self, service, field, value):
        result = False, []
        if service is not None:
            if service not in self._handlers:
                raise ValueError(f"No service is registered with name '{service}'")

        if field in self._supported_fields:
            if not isinstance(value, self._supported_fields[field][1]):
                return True, [self._supported_fields[field][1]]
            else:
                return True, True

        if service is not None:
            s = service
            if field in self._handlers[s].opts:
                if not isinstance(value, self._handlers[s].opts[field][1]):
                    return True, [self._handlers[s].opts[field][1]]
                else:
                    return True, True
            else:
                return result

        for s in self._handlers:
            if field in self._handlers[s].opts:
                if not isinstance(value, self._handlers[s].opts[field][1]):
                    result[1].append(self._handlers[s].opts[field][1])
                else:
                    return True, True

        return result

    def opts(self, service):
        if service not in self._handlers:
            raise ValueError(f"No service is registered with name '{service}'")
        return [*self._opts, *list(self._handlers[service].opts.keys())]

    def env_vars(self, service):
        if service is not None:
            if service not in self._handlers:
                raise ValueError(f"No service is registered with name '{service}'")
            return [*self._env_vars] + list(self._handlers[service].env.keys())
        else:
            result = [*self._env_vars]
            for s in self._handlers.keys():
                result += list(self._handlers[s].env.keys())
            return result

    def service_defaults(self, service):
        result = {k: v[0] for k, v in self._supported_fields.items()}
        if service is not None:
            if service not in self._handlers:
                raise ValueError(f"No service is registered with name '{service}'")
            for k, v in self._handlers[service].opts.items():
                result[k] = v[0]
        return result

    def engines(self, service):
        if service not in self._handlers:
            raise ValueError(f"No service is registered with name '{service}'")
        return self._handlers[service].engines.keys()

    def formats(self, service, engine):
        if engine not in self.engines(service):
            raise ValueError(f"No engine '{engine}' for service '{service}' is found!")
        eng_data = self._handlers[service].engines[engine]
        return [*eng_data.formats]

default_handlers = ssr_handlers()
