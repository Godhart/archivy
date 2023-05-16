import frontmatter
from frontmatter import dumps as _dumps
from frontmatter import loads as _loads
from frontmatter import load  as _load

import os
import re
import yaml
from flask import current_app
from pathlib import Path
from datetime import datetime

from archivy.import_fenced import import_markdown
from archivy.render.pandoc import import_pandoc

from archivy.render.common import to_abs_path
import archivy.render.common as common

SEP = os.path.join("a", "b")[1]


Post = frontmatter.Post


# FIXME: ugly hack to make sure the app path is evaluated at the right time
def get_data_dir():
    """Returns the directory where dataobjs are stored"""
    return Path(current_app.config["USER_DIR"]) / "data"


def _import_foreign(data, relative_path):

    class importers(object):

        @staticmethod
        def import_markdown(fenced_code):
            m = re.match(r"^(?:~+|`+)import(?:--([\w-]+))?.*?$", fenced_code[0])
            if m is None:
                return "`failed to parse import string!`"
            else:
                engine = m.groups()[0]
            if engine is None:
                engine = 'pandoc'

            if engine not in ('pandoc', ):
                raise ValueError("`Only 'pandoc' engine is supported yet!`")

            try:
                import_options = yaml.safe_load("\n".join(fenced_code[1:-1]))
            except Exception as e:
                return f"`````\nFailed to parse yaml due to exception: {e}\n`````"

            if 'src' not in import_options.keys():
                return "`'src' is required option!`"

            src_abs = str(import_options['src']).replace("\\", "/")
            if len(src_abs) > 0:
                if src_abs[:1] != "/":
                    if relative_path is not None:
                        src_abs = os.path.join(relative_path, src_abs)
                src_abs = to_abs_path(common.DATA_ROOT_PATH, src_abs)
            else:
                return "`'src' can't be empty!`"

            folder, filename = os.path.split(src_abs)
            if import_options.get('inplace', False) is True:
                import_folder = folder
            else:
                import_folder = os.path.join(folder, ".import")
                os.makedirs(import_folder, exist_ok=True)
                if not os.path.exists(os.path.join(import_folder, ".hidden")):
                    with open(os.path.join(import_folder, ".hidden"), "w") as f:
                        pass

            d_path = os.path.join(import_folder, filename +f".{engine}")
            if 'page' in import_options:
                d_path += f"-{import_options.get('page')}"

            opts = {}
            for k, v in import_options.items():
                if k not in ("src", "page", "force"):
                    opts[k] = v
                    # TODO: update d_path safely

            if import_options.get('inplace', False) is True:
                d_path += ".md"
                opts['import_note'] = True
                opts['readonly'] = True
            else:
                d_path += ".mdi"
                opts['base_path'] = os.path.join(get_data_dir(), relative_path)

            try:
                success, error = import_pandoc(
                    src=src_abs,
                    d_path=d_path,
                    engine=engine,
                    page=import_options.get('page', None),
                    force=import_options.get('force', False),
                    opts=opts,
                )
            except Exception as e:
                success, error = False, f"`````\nFailed to import {import_options['src']} due to exception: {e}\n`````"
            if not success:
                return f"{error}"
            with open(d_path, "r", encoding='utf-8') as f:
                data = f.read()
            return data

    data.content = import_markdown(data.content, importers)


def _override_note(data):

    if data.get('type', 'note') == 'note':
        filepath = data.get('_file_path_', None)
        if filepath is not None:
            filepath = Path(filepath)
            relative_path = filepath.relative_to(get_data_dir())
            data['type'] = 'note'
            data['id'] = str(relative_path).replace(SEP, "--")[:-3]
            data['path'] = str(relative_path.parent).replace(SEP, "/")
            title = relative_path.stem.replace('_', ' ')
            m = re.match(r"^(\d+(?:[.]\d+)?)[-](.+)$", title)
            if m is not None:
                title = m.groups()[1]
                data['_order_'] = float(m.groups()[0])
            title = title[:1].title() + title[1:]
            data['_fallback_title_'] = title
            if 'title' not in data:
                data['title'] = title
                data['_auto_title_'] = True
            dt = datetime.fromtimestamp(os.path.getmtime(str(filepath)))
            data['date'] = dt.strftime(r"%x")
            data['modified_at'] = dt.strftime(r"%x %H:%M")
    if 'tags' not in data:
        data['tags'] = []

def load(filepath):
    data = _load(str(filepath))
    if data.get('type', 'note') == 'note':
        if not isinstance(filepath, Path):
            filepath = Path(filepath)
        data["_file_path_"] = str(filepath.absolute())
    _override_note(data)
    _import_foreign(data, filepath.relative_to(get_data_dir()).parent)
    return data

def loads(text):
    data = _loads(text)
    _override_note(data)
    _import_foreign(data, None)
    return data

def dumps(data, raw=False):
    dataobj = data
    if raw or 'type' in dataobj and dataobj['type'] != 'note':
        return _dumps(dataobj)
    dataobj = _loads(_dumps(data))  # Making a copy
    del dataobj['type']
    del dataobj['id']
    del dataobj['date']
    del dataobj['modified_at']
    del dataobj['path']
    if len(dataobj['tags']) == 0:
        del dataobj['tags']
    if dataobj.get('_auto_title_', False) is True:
        del dataobj['title']
    for key in [k for k in dataobj.metadata.keys() if isinstance(k, str) and k[:1] == "_"]:
        del dataobj[key]
    if len(dataobj.keys()) > 0:
        return _dumps(dataobj)
    else:
        return dataobj.content
