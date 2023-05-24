# A DB to contain files info / meta and reduce disk i/o and text paring ops

# DB Structure

# Dirs
# - Info whether dir is hidden or not
# - Ref to parent dir
# - Refs to nested dirs
# - Refs to dir's files

# Tags
# - Tagname
# - Refs to files

# Files
# - Metadata - read from front-matter
# - Ref to dir
# - Tags refs
# - Direct Refs to files
# - Back Refs to files

import os
import re
from datetime import datetime
from pathlib import Path
import yaml

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker

from frontmatter import Post

from flask import current_app

from archivy import data, tags
from archivy.data import is_relative_to, Directory

from archivy.db_models import Base
from archivy.db_models import Folder, Document, Tag, Link

from archivy.search import search


DB = {}


# FIXME: ugly hack to make sure the app path is evaluated at the right time
def get_data_dir():
    """Returns the directory where dataobjs are stored"""
    return Path(current_app.config["USER_DIR"]) / "data"


class ArchDB(object):

    def __init__(self, latest, sqlite_filepath):
        self._db_not_exists = False
        if latest:
            sqlite_filepath = os.environ.get("ARCHIVY_DBG_LATEST_DB") or ":memory:" # "file::memory:?cache=shared"
            # NOTE: store in local path while debugging to speedup roll-up and db debug
            if sqlite_filepath == ":memory:" or not os.path.exists(sqlite_filepath):
                self._db_not_exists = True
        self._latest = latest
        # TODO: prohibit editing functions if not latest
        self._sqlite_file_path = sqlite_filepath

        if sqlite_filepath == ":memory:":
            engine = create_engine("sqlite:///file:latest?mode=memory&cache=shared&uri=true&check_same_thread=False") # , echo=True, future=True
        else:
            engine = create_engine(f"sqlite:///{sqlite_filepath}?check_same_thread=False")
        # TODO: check_same_thread is quick and unsafe hack. Use scoped sessions or Flask-SQLAlchemy

        # engine = create_engine(f"sqlite:///{sqlite_filepath}")
        Base.metadata.create_all(engine)
        Session = sessionmaker()
        Session.configure(bind=engine)
        self._session = Session()

        if latest is True:
            DB['latest'] = self
        else:
            DB['stored'] = self

    @property
    def session(self):
        return self._session

    def update(self, force=False):
        if self._db_not_exists:
            self._db_not_exists = False
            self._update_db()

    def commit(self):
        self._session.commit()

    def flush(self):
        self._session.flush()

    def _doc_to_post(self, doc: Document, load_content = True):
        content = ""
        if load_content:
            content = doc.content
        post = Post(
            content,
            None,
            ** {
                "id"    : doc.doc_id,
                "type"  : doc.type,
                "title" : doc.title,
                "date"  : doc.date,
                "_file_path_": str(get_data_dir() / doc.path),
                "modified_at" : doc.modified_at,
                "tags"  : [tag.name for tag in doc.tags],
                "readonly" : doc.readonly,
                "import" : doc.import_en,
            },
        )
        return post

    def _update_db(self, path=None):
        if path is None:
            start_name = "root"
            path = get_data_dir()
        else:
            start_name = Path(path).parts[-1]
            path = Path(path)
        dir = data.build_dir_tree(start_name, path, load_content=True)

        # files_scan is object with:
        # - name of dir
        # - child_files as list with result of frontmatter load
        # - child_dirs as dict of same objects

        def _add_dir(dir, path: Path):
            folder = Folder(
                name = dir.name,
                path = str(path.relative_to(get_data_dir())),
            )
            for cf in dir.child_files:
                doc_name = cf.metadata["id"].split("--")[-1]
                try:
                    timestamp   = int(datetime.strptime(cf.metadata["modified_at"], r"%x %H:%M").timestamp())
                except Exception as e:
                    timestamp = 0
                extra_data = {
                    "tags": cf.metadata.get('tags', []),
                }

                doc = Document(
                    name        = doc_name,
                    path        = str((path / doc_name).relative_to(get_data_dir())),
                    doc_id      = cf.metadata["id"],
                    type        = cf.metadata["type"],
                    title       = cf.metadata["title"],
                    timestamp   = timestamp,
                    date        = cf.metadata["date"],
                    modified_at = cf.metadata["modified_at"],
                    readonly    = cf.metadata.get("import", False),
                    import_en   = cf.metadata.get("import", False),
                    data_yaml   = yaml.safe_dump(extra_data),
                    content     = cf.content,
                )
                self._session.add(doc)
                folder.documents.append(doc)

            for cd in dir.child_dirs.values():
                subfolder = _add_dir(cd, path / cd.name)
                folder.folders.append(subfolder)

            self._session.add(folder)
            return folder

        root = _add_dir(dir, path)
        self.flush()

        self._update_links([root], recurse=True)
        self._update_tags([root], recurse=True)
        self.flush()


    def _update_links(self, objs, recurse=False):
        for obj in objs:
            if isinstance(obj, Folder):
                self._update_links(obj.documents)
                if recurse:
                    self._update_links(obj.folders, recurse)
            elif not isinstance(obj, Document):
                return  # TODO: raise error
            else:
                text = obj.content

                # Remove existing links
                obj_refs = (
                    self._session.query(Link)
                    .filter(Link.source_id == obj.ID)
                    .all())
                for link in obj_refs:   # TODO: use 'list(obj.refs)' after fixing DB
                    self._session.delete[link]

                # Find all links within object
                links_search = re.finditer(r"\[\[(?:([^|\]]+)\|)*(@?[^|#\]]+?)(#[^|\]]+)*\]\]", text)
                for m in links_search:
                    # add each link to refs list of document
                    target_id = m.groups()[1]
                    # TODO: also do 'obj.refs.append(link)' after fixing DB

                    # look for referred objects, and update their refbacks
                    if target_id[:1] != "@":
                        targets = (
                            self._session.query(Document)
                            .filter(Document.doc_id == target_id)
                            .all()
                        )
                    else:
                        target_pattern = "%--" + target_id[1:]
                        targets = (
                            self._session.query(Document)
                            .filter(or_(Document.doc_id.like(target_pattern), Document.doc_id == target_id[1:]))
                            .all()
                        )
                    for t in targets:
                        if t is None:
                            continue
                        # TODO: one link per multiple targets after fixing DB
                        link = Link(
                            full = m.group(),
                            text = m.groups()[0] or m.string[m.start():m.end()],
                            source_id = obj.ID, # TODO: remove after fixing DB
                            objid = target_id,
                            section = m.groups()[2] or "",
                        )
                        self._session.add(link)
                        t.refbacks.append(link)
                        pass


    def _update_tags(self, objs, recurse=False):
        for obj in objs:
            if isinstance(obj, Folder):
                self._update_tags(obj.documents)
                if recurse:
                    self._update_tags(obj.folders, recurse)
            elif not isinstance(obj, Document):
                return  # TODO: raise error
            else:
                header_tags = yaml.safe_load(obj.data_yaml).get('tags', [])
                text = obj.content

                # Remove existing tags relation
                previous_tags = obj.tags
                obj.tags = []

                # Find all tags within object
                text_tags = list(m.groups()[0] for m in re.finditer(r"#("+tags.TAG_REGEX+r")#", text))

                obj_tags = set(header_tags + text_tags)

                for tag_name in obj_tags:
                    # create tag if necessary
                    tag = (
                        self._session.query(Tag)
                        .filter(Tag.name == tag_name)
                        .one_or_none()
                    )
                    if tag is None:
                        tag = Tag(name = tag_name)
                        self._session.add(tag)
                        self.flush()
                    obj.tags.append(tag)

                self.flush()        # flush to update tags and relationships

                # Remove empty tags
                deleted = False
                for tag in previous_tags:
                    if len(tag.documents) == 0:
                        self._session.delete(tag)
                        deleted = True
                if deleted:
                    self.flush()    # flush if at least one tag were deleted

    def on_fs_change(self, path, changes):
        # TODO: Update DB record(s)
        pass

    def build_dir_tree(self, path, query_dir, load_content=True):
        self.update()
        """
        args:
            path        - last name of path segment
            query_dir   - absolute path to start from
        """
        folder = (
            self._session.query(Folder)
            .filter(Folder.path == str(Path(query_dir).relative_to(get_data_dir())))
            .one_or_none()
        )

        def _dig_dir(dir: Directory, folder: Folder):
            for doc in folder.documents:
                dir.child_files.append(self._doc_to_post(doc, load_content))
            for subfolder in folder.folders:
                subdir = Directory(subfolder.name)
                _dig_dir(subdir, subfolder)
                dir.child_dirs[subfolder.name] = subdir

        if folder is None:
            raise FileNotFoundError
        else:
            result = Directory(folder.name)
            _dig_dir(result, folder)

        return result

    def get_items(self,
        collections=[], path="", structured=True, json_format=False, load_content=True
    ):
        """
        Gets all dataobjs.

        Parameters:

        - **collections** - filter dataobj by type, eg. bookmark / note
        - **path** - filter by path
        - **structured: if set to True, will return a Directory object, otherwise
        data will just be returned as a list of dataobjs
        - **json_format**: boolean value used internally to pre-process dataobjs
        to send back a json response.
        - **load_content**: internal value to disregard post content and not save them in memory if they won't be accessed.
        """
        self.update()

        # old_result = data.get_items(collections, path, structured, json_format, load_content)

        data_dir = get_data_dir()
        query_dir = data_dir / path
        if not is_relative_to(query_dir, data_dir) or not query_dir.exists():
            raise FileNotFoundError
        if structured:
            # TODO: looks like some original args are missing here, like collection, json_format, load_content
            result = self.build_dir_tree(path, query_dir)
            return result
        else:
            folder = (
                self._session.query(Folder)
                .filter(Folder.path == str(Path(query_dir).relative_to(data_dir)))
                .one_or_none()
            )

            def _dig_dir(result: list, folder: Folder):
                for doc in folder.documents:
                    post = self._doc_to_post(doc, load_content)
                    post['fullpath'] = str((data_dir / doc.path).parent.relative_to(query_dir))
                    if len(collections) == 0 or any(
                        [collection == post['type'] for collection in collections]
                    ):
                        if json_format:
                            post_dict = post.__dict__
                            # remove unnecessary yaml handler
                            post_dict.pop("handler")
                            result.append(post_dict)
                        else:
                            result.append(post)

                for subfolder in folder.folders:
                    _dig_dir(result, subfolder)

            if folder is None:
                raise FileNotFoundError
            else:
                result = []
                _dig_dir(result, folder)

        return result

    def create(self, contents, title, path=""):
        return data.create(contents, title, path)
        # TODO: update DB in case of success

    def get_item(self, dataobj_id):
        self.update()
        item = (
            self._session.query(Document)
            .filter(Document.doc_id == dataobj_id)
            .one_or_none()
        )
        if item is None:
            return None
        post = self._doc_to_post(item)
        post['fullpath'] = str(get_data_dir() / item.path)
        post['dir'] = str(Path(item.path).parent)
        if post['dir'] in (".", "/"):
            post['dir'] = ""
        return post

    def lookup_items(self, key):
        self.update()
        items = (
            self._session.query(Document)
            .filter(or_(Document.doc_id.like("%--" + key), Document.doc_id == key))
            .all()
        )
        result = [{
            'id': item.doc_id,
            'path': item.path
        } for item in items]
        return result

    def move_item(self, dataobj_id, new_path):
        # TODO: remove item from database
        return data.move_item(dataobj_id, new_path)

    def rename_folder(self, old_path, new_name):
        # TODO: remove folder with it's children from database
        return data.rename_folder(old_path, new_name)

    def import_folder(self, folder_path, recursive, readonly, force):
        return data.import_folder(folder_path, recursive, readonly, force)
        # NOTE: database update would be triggered by FS change

    def delete_item(self, dataobj_id):
        # TODO: remove item from database
        return data.delete_item(dataobj_id)

    def update_item_md(self, dataobj_id, new_content):
        # TODO: remove item from database
        return data.update_item_md(dataobj_id, new_content)

    def update_item_frontmatter(self, dataobj_id, new_frontmatter):
        # TODO: remove item from database
        return data.update_item_frontmatter(dataobj_id, new_frontmatter)

    def get_dirs(self):
        self.update()
        dirnames = [folder.path for folder in self._session.query(Folder).all()]
        return dirnames

    def create_dir(self, name):
        # TODO: add dir into database
        return data.create_dir()

    def delete_dir(self, name):
        # TODO: remove folder with it's children from database
        return data.delete_dir(name)

    def open_file(self, path):
        # TODO: only if it's latest db
        return data.open_file(path)

    def get_all_tags(self, force=False):
        # NOTE: force arg is for compatibility with tags.py
        self.update()
        tags = [tag.name for tag in self._session.query(Tag).all()]
        return tags

    def select_by_tags(self, selected_tags):
        """
        Returns:
        - list of object ids, with mentioned tags
        - list with dict items, containing nested tags names and occurrences count
        """
        self.update()
        if selected_tags is None or len(selected_tags) == 0:
            all_tags = self._session.query(Tag).all()
            result_tags = sorted([{'tag': t.name, 'count': len(t.documents)} for t in all_tags], key = lambda x: x['tag'].lower())
            return [], result_tags
        items = self._session.query(Document).all()
        selected_tags = [tag.lower() for tag in selected_tags]
        items = [item for item in items if any(tag.name.lower() in selected_tags for tag in item.tags)]
        nested_tags = {}
        for item in items:
            for tag in item.tags:
                tag_name = tag.name.lower()
                if tag_name in selected_tags:
                    continue
                if tag_name not in nested_tags:
                    nested_tags[tag_name] = 0
                nested_tags[tag_name] += 1

        result_tags = sorted([{'tag': k, 'count': v} for k,v in nested_tags.items()], key = lambda x: x['tag'].lower())
        return sorted([item.doc_id for item in items]), result_tags

    def get_back_links(self, dataobj_id):
        # TODO: should return same result as search
        self.update()

        item = (
            self._session.query(Document)
            .filter(Document.doc_id == dataobj_id)
            .one_or_none()
        )
        if item is None:
            return []
        backlinks = {}
        for link in item.refbacks:
            src = (
                self._session.query(Document)
                .filter(Document.ID == link.source_id)
                .one_or_none()
            )
            if src is None:
                continue
            # TODO: fixup DB structure and simply use src = link.source.doc_id
            if src.doc_id not in backlinks:
                backlinks[src.doc_id] = []
            backlinks[src.doc_id].append((link.full, item.title))
        result = []
        for doc_id, v in backlinks.items():
            matches = []
            for text, title in v:
                matches.append(text)
            result.append({
                'id': doc_id,
                'title': title,
                'matches': matches,
            })

        return result

    def is_tag_format(self, tag_name):
        return tags.is_tag_format(tag_name)

    def add_tag_to_index(self, tag_name):
        self.update()
        tag = (
            self._session.query(Tag)
            .filter(Tag.name == tag_name)
            .one_or_none()
        )
        if tag is None:
            tag = Tag(
                name = tag_name
            )
            self._session.add(tag)
            self.flush()
        return True


LATEST = ArchDB(latest=True, sqlite_filepath=None)


def layer(layer="data", legacy=False):
    if not legacy:
        if layer == "data":
            return LATEST
        elif layer == "tags":
            return LATEST
        else:
            # TODO: version
            return None
    else:
        if layer == "data":
            return data
        elif layer == "tags":
            return tags
        else:
            return None
