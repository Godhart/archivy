import frontmatter
from frontmatter import dumps as _dumps
from frontmatter import loads as _loads
from frontmatter import load  as _load
from frontmatter import Post

import os
import re
import yaml
from flask import current_app
from pathlib import Path
import time
from datetime import datetime
import shutil

from archivy.render.pandoc import import_pandoc

from archivy.render.common import to_abs_path
import archivy.render.common as common

from archivy.hacks import Hacks
get_data_dir = Hacks.get_data_dir

SEP = os.path.join("a", "b")[1]


Post = frontmatter.Post


class importers(object):

    @staticmethod
    def import_fenced(fenced_code, relative_path):
        src_relative = None

        m = re.match(r"^(?:~+|`+)import(?:--([\w-]+))?.*?$", fenced_code[0])
        if m is None:
            return False, "`failed to parse fenced import preamble!`", src_relative
        else:
            engine = m.groups()[0]
        if engine is None:
            engine = 'pandoc'

        if engine not in ('pandoc', ):
            return False, "`Only 'pandoc' engine is supported yet!`", src_relative

        try:
            import_options = yaml.safe_load("\n".join(fenced_code[1:-1]))
        except Exception as e:
            return False, f"`````\nFailed to parse yaml due to exception: {e}\n`````", src_relative

        if 'src' not in import_options.keys():
            return False, "`'src' is required option!`", src_relative

        src_abs = str(import_options['src']).replace("\\", "/")
        if len(src_abs) > 0:
            if src_abs[:1] != "/":
                if relative_path is not None:
                    src_abs = os.path.join(relative_path, src_abs)
            src_abs = to_abs_path(common.DATA_ROOT_PATH, src_abs)
        else:
            return False, "`'src' can't be empty!`", src_relative

        src_relative = Path(src_abs).relative_to(get_data_dir())

        if not os.path.exists(src_abs):
            return False, "`'src' should exist!`", src_relative

        if not os.path.isfile(src_abs):
            return False, "`'src' should point to a file!`", src_relative
        
        inplace = import_options.get('inplace', False) is True

        folder, filename = os.path.split(src_abs)
        if inplace:
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

        if inplace:
            # Result is placed along with original with markdown extension
            output_name = opts.get('name', None)
            if output_name is not None and output_name.strip() == '':
                output_name = None
            if output_name is None:
                d_path += ".md"
            else:
                d_path += ".tmp"
            opts['import_note'] = True
            if 'readonly' not in opts:
                opts['readonly'] = True

            d_path = os.path.join(os.path.split(d_path)[0], output_name + ".md")

            if os.path.exists(d_path):
                if not import_options.get('force', False):
                    return None, (f"File at path '{Path(d_path).relative_to(get_data_dir())}' already exists!\n"
                            "Use 'force' option if you want to override it"), src_relative
                else:
                    os.unlink(d_path)
        else:
            output_name = None
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
            return False, f"{error}", src_relative

        with open(d_path, "r", encoding='utf-8') as f:
            text = f.read()

        current_date = datetime.fromtimestamp(time.time()).strftime(r"%Y-%m-%d %H:%M:%S")
        text = f"<!-- following section is imported at {current_date} with " + "\n".join(fenced_code) + \
            "-->\n" + text + "<!-- end of imported data -->\n"

        return True, text, src_relative


def _import_foreign(text, relative_path):

    result = []
    errors = []
    successfully = []

    fenced = ""
    style = ""
    kind = ""

    to_import = None

    for line in text.split("\n"):
        if len(fenced) == 0:
            if line[:3] not in ("~~~", "```"):
                result.append(line)
                continue
            m = re.match(r"^(~+|`+)\{(.*?)\}$", line)
            if m is None:
                m = re.match(r"^(~+|`+)([\w-]*).*?$", line)
                assert m is not None, "Something went wrong!"
                style = "M"
            else:
                style = "R"
            fenced = m.groups()[0]
            kind = m.groups()[1]
            if style == "R" or kind == "import" or kind[:8] == "import--":
                to_import = [line]
            else:
                result.append(line)
        else:
            if to_import is None:
                result.append(line)
            else:
                to_import.append(line)

            if line.strip() == fenced:
                fenced = ""
                if to_import is not None:
                    success, text, src = importers.import_fenced(to_import, relative_path)
                    if success is not None:
                        if not success:
                            errors.append(text)
                        else:
                            successfully.append(src)
                    result.append(text) # NOTE: in case of error - message about error would be within result
                    to_import = None

    return "\n".join(result), errors, successfully


def import_foreign(file_path, readonly, force):
    text = f"""
```import
inplace : true
src : {file_path}
readonly : {readonly}
name : "{Path(file_path).stem}"
force : {force}
```
"""
    _, errors, successfully = _import_foreign(text, None)
    return successfully, errors


def _override_note(data):

    if data.get('type', 'note') == 'note':
        data['type'] = 'note'
        filepath = data.get('_file_path_', None)
        if filepath is not None:
            filepath = Path(filepath)
            relative_path = filepath.relative_to(get_data_dir())
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
    failed = False

    try:
        data = _load(str(filepath))
    except Exception as e:
        failed = True
        data = Post(f"""
Failed to load from '{filepath}' due to exception:

```
{e}
```
""")
        data['type'] = 'note'
        data['id'] = "failed"
        data['path'] = "failed"
        title = "Failed"
        data['title'] = title
        data['_fallback_title_'] = title
        data['_auto_title_'] = True
        dt = datetime.fromtimestamp(time.time())
        data['date'] = dt.strftime(r"%x")
        data['modified_at'] = dt.strftime(r"%x %H:%M")
        data['tags'] = []

    data["_file_path_"] = str(Path(filepath).absolute())
    try:
        if not failed:
            _override_note(data)
    except Exception as e:
        failed = True
        data.content = f"""
Failed to override note data due to exception:

```
{e}
```
""" + data.content
        if data.get('type', 'note') == 'note':
            data['type'] = 'note'
            data['id'] = "failed"
            data['path'] = "failed"
            title = "Failed"
            data['title'] = title
            data['_fallback_title_'] = title
            data['_auto_title_'] = True
            dt = datetime.fromtimestamp(time.time())
            data['date'] = dt.strftime(r"%x")
            data['modified_at'] = dt.strftime(r"%x %H:%M")
            data['tags'] = []

    if not failed and data.metadata.get("import", False):
        try:
            imported_content, errors, _ = _import_foreign(data.content, filepath.relative_to(get_data_dir()).parent)
            if len(errors) == 0:
                data.content = imported_content
            else:
                data.content = f"""
Following errors were detected when importing foreign content:

```
{errors}
```
""" + data.content
        except Exception as e:
            failed = True
            data.content = f"""
Failed to import foreign data due to exception:

```
{e}
```
""" + data.content
    # NOTE: in case of errors fenced code of import section in result is replaced with error message,
    # errors processing is not necessary in this case
    if failed:
        data['readonly'] = True
    return data

def loads(text):
    failed = False
    try:
        data = _loads(text)
    except Exception as e:
        failed = True
        data = Post(f"""
Failed to load due to exception:

```
{e}
```

source text:
``````
{text}
``````
""")

    try:
        if not failed:
            _override_note(data)
        # TODO: actually there is not much to override if source file path is unknown
    except Exception as e:
        failed = True
        data.content = f"""
Failed to override note data due to exception:

```
{e}
```
""" + data.content
        if data.get('type', 'note') == 'note':
            data['type'] = 'note'
            data['id'] = "failed"
            data['path'] = "failed"
            title = "Failed"
            data['title'] = title
            data['_fallback_title_'] = title
            data['_auto_title_'] = True
            dt = datetime.fromtimestamp(time.time())
            data['date'] = dt.strftime(r"%x")
            data['modified_at'] = dt.strftime(r"%x %H:%M")
            data['tags'] = []

    if not failed and data.metadata.get("import", False):
        try:
            imported_content, errors, _ = _import_foreign(data.content, None)
            if len(errors) == 0:
                data.content = imported_content
            else:
                data.content = f"""
Following errors were detected when importing foreign content:

```
{errors}
```
""" + data.content
        except Exception as e:
            failed = True
            data.content = f"""
Failed to import foreign data due to exception:

```
{e}
```
""" + data.content

    # NOTE: in case of errors fenced code of import section in result is replaced with error message,
    # errors processing is not necessary in this case
    if failed:
        data['readonly'] = True
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
