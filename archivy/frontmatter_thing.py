import frontmatter
from frontmatter import dumps as _dumps
from frontmatter import loads as _loads
from frontmatter import load  as _load

import os
import re
from flask import current_app
from pathlib import Path
from datetime import datetime


SEP = os.path.join("a", "b")[1]


Post = frontmatter.Post


# FIXME: ugly hack to make sure the app path is evaluated at the right time
def get_data_dir():
    """Returns the directory where dataobjs are stored"""
    return Path(current_app.config["USER_DIR"]) / "data"


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
    return data

def loads(text):
    data = _loads(text)
    _override_note(data)
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
