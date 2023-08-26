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

from archivy import data, tags
from archivy.data import is_relative_to, Directory, load_data

from archivy.db_models import Base
from archivy.db_models import Folder, Document, Tag, Link

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from archivy.hacks import Hacks
get_data_dir = Hacks.get_data_dir


DB = {}


class ArchDB(object):

    def __init__(self, latest, sqlite_filepath, use_fs_watchdog=True):
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

        # engine = create_engine(f"sqlite:///{sqlite_filepath}")
        Base.metadata.create_all(engine)
        self._engine = engine

        if latest is True:
            DB['latest'] = self
        else:
            DB['stored'] = self

        self.__sorted_items = None

        self._fs_watchdog = None
        self._fs_event_handler = None
        self._use_fw_watchdog = use_fs_watchdog
        self._update_via_fs_watchdog_only = use_fs_watchdog


    @property
    def _sorted(self):
        # TODO: use DB
        return self.__sorted_items is not None

    @_sorted.setter
    def _sorted(self, value):
        # TODO: use DB
        if value is False:
            self.__sorted_items = None
        else:
            raise ValueError("_sorted property may be only set to False")

    @property
    def _sorted_items(self):
        # TODO: use DB
        if self.__sorted_items is None:
            self._sort_items()
        return self.__sorted_items

    @_sorted_items.setter
    def _sorted_items(self, value):
        # TODO: use DB
        self.__sorted_items = value

    def __del__(self):
        if self.latest:
            # Stop FS watchdog
            if self._fs_watchdog is not None:
                self._fs_watchdog.stop()
                self._fs_watchdog.join()
                self._fs_watchdog = None

    def _fs_start_watchdog(self):
        if not self._use_fw_watchdog:
            return
        patterns = ["*.md"] # file patterns we want to handle
        ignore_patterns = None # patterns that we don’t want to handle
        ignore_directories = False # True to be notified for regular files (not for directories)
        case_sensitive = True # made the patterns “case sensitive”
        self._fs_event_handler = PatternMatchingEventHandler(
            patterns,
            ignore_patterns,
            ignore_directories,
            case_sensitive)

        self._fs_event_handler.on_created = self._fs_on_created
        self._fs_event_handler.on_deleted = self._fs_on_deleted
        self._fs_event_handler.on_modified = self._fs_on_modified
        self._fs_event_handler.on_moved = self._fs_on_moved

        # create observer to monitor filesystem for changes
        # that will be handled by the event handler
        fs_watchdog_path = str(get_data_dir()) # data directory
        go_recursively = True # allow to catch all the events in the subdirs of current dir
        self._fs_watchdog = Observer()
        # call the schedule method on Observer object
        self._fs_watchdog.schedule(self._fs_event_handler, fs_watchdog_path, recursive=go_recursively)
        # start the observer thread to get all the events.
        self._fs_watchdog.start()

    def _fs_on_created(self, event):
        self._on_fs_change("add", event.src_path, None)

    def _fs_on_moved(self, event):
        self._on_fs_change("move", event.src_path, event.dest_path)

    def _fs_on_modified(self, event):
        self._on_fs_change("modify", event.src_path, None)

    def _fs_on_deleted(self, event):
        self._on_fs_change("delete", event.src_path, None)

    def session(self):
        Session = sessionmaker()
        Session.configure(bind=self._engine)
        return Session()

    def update(self, force=False):
        if self._db_not_exists:
            self._db_not_exists = False
            self._sorted = False
            _session = self.session()
            with _session.begin():
                self._update_db(_session)
            self._fs_start_watchdog()

    def _sort_items(self):
        self.update()
        def doc_key(doc: Document) -> tuple:
            keys = [(-1, "--"), (doc.order, doc.title.lower())]
            folder = doc.folder
            while isinstance(folder, Folder):
                keys = [(folder.order, folder.name.lower())] + keys
                if len(folder.parent) > 0:
                    folder = folder.parent[0]
                else:
                    folder = None
            return tuple(keys)

        _session = self.session()
        with _session.begin():
            items = _session.query(Document).filter(
                Document.nav_skip == False, Document.nav_hide == False
            ).all()
            items = [item for item in items if item.folder.nav_hide == False]
            sorted_items = sorted(items, key=lambda x: doc_key(x))
            self._sorted_items = tuple([item.doc_id for item in sorted_items])

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
                "order" : doc.order,
                "nav-skip": doc.nav_skip,
                "date"  : doc.date,
                "_file_path_": str(get_data_dir() / doc.path),
                "modified_at" : doc.modified_at,
                "tags"  : [tag.name for tag in doc.tags],
                "readonly" : doc.readonly,
                "import" : doc.import_en,
            },
        )
        return post

    def _post_to_doc(self, post, folder_path=None):
        doc_name = post.metadata["id"].split("--")[-1]
        try:
            timestamp   = int(datetime.strptime(post.metadata["modified_at"], r"%x %H:%M").timestamp())
        except Exception as e:
            timestamp = 0
        extra_data = {
            "tags": post.metadata.get('tags', []),
        }

        if folder_path is None:
            folder_path = Path(post["_file_path_"]).parent

        doc = Document(
            name        = doc_name,
            path        = str((folder_path / (doc_name+".md")).relative_to(get_data_dir())),
            doc_id      = post.metadata["id"],
            type        = post.metadata["type"],
            title       = post.metadata["title"],
            order       = post.metadata.get("order", 999999),
            nav_skip    = post.metadata.get("nav-skip", False),
            nav_hide    = post.metadata.get("nav-skip", False),
            timestamp   = timestamp,
            date        = post.metadata["date"],
            modified_at = post.metadata["modified_at"],
            readonly    = post.metadata.get("import", False),
            import_en   = post.metadata.get("import", False),
            data_yaml   = yaml.safe_dump(extra_data),
            content     = post.content,
        )
        return doc

    def _add_folder(self, session, folder_path):
        folder_path = Path(folder_path)
        folder = Folder(
            name = folder_path.parts[-1],
            order = 999999,
            nav_hide = False,
            path = str(folder_path.relative_to(get_data_dir())),
        )
        session.add(folder)
        self._sorted = False
        return folder

    def _add_doc(self, session, path):
        doc = (
            session.query(Document)
            .filter(Document.path == str(Path(path).relative_to(get_data_dir())))
            .one_or_none()
        )
        if doc is not None:
            raise ValueError(f"Document for path '{path}' already exists in database!")

        folder = (
            session.query(Folder)
            .filter(Folder.path == str(Path(path).parent.relative_to(get_data_dir())))
            .one_or_none()
        )
        new_folder = folder is None
        if new_folder:
            folder_path = Path(path).parent
            folder = self._add_folder(session, folder_path)

        post = load_data(path)
        doc = self._post_to_doc(post)
        session.add(doc)
        folder.documents.append(doc)
        self._sorted = False
        return doc

    def _update_db(self, session, path=None):
        if path is None:
            is_root = True
            start_name = "root"
            path = get_data_dir()
        else:
            is_root = False
            start_name = Path(path).parts[-1]
            path = Path(path)

        if not is_root:
            parent_folder = session.query(Folder).filter(Folder.path == str(path.relative_to(get_data_dir()).parent)).one_or_none()
            if parent_folder is None:
                raise ValueError(f"Can't find parent folder for {path} in DB!")

        dir_data = data.build_dir_tree(start_name, path, load_content=True)

        # files_scan is object with:
        # - name of dir
        # - child_files as list with result of frontmatter load
        # - child_dirs as dict of same objects

        def _add_folder_item(dir_data, path: Path):
            folder = self._add_folder(session, path)
            for cf in dir_data.child_files:
                doc = self._post_to_doc(cf, path)
                session.add(doc)
                folder.documents.append(doc)

            for cd in dir_data.child_dirs.values():
                subfolder = _add_folder_item(cd, path / cd.name)
                folder.folders.append(subfolder)

            return folder

        start_folder = _add_folder_item(dir_data, path)
        session.flush()

        if not is_root:
            parent_folder.folders.append(start_folder)
            session.flush()

        self._update_links(session, [start_folder], recurse=True)
        self._update_tags(session, [start_folder], recurse=True)
        session.flush()
        self._sorted = False

    def _remove_doc(self, session, doc: Document, remove_tags=False, remove_parent=False):
        # Get list of tags that could become empty after doc removal
        if remove_tags:
            check_tags = list(doc.tags)
        else:
            check_tags = []

        # Remove links
        links = session.query(Link).filter(Link.source_id == doc.doc_id).all()
        for link in links:
            session.delete(link)

        links = list(doc.refbacks)
        for link in links:
            session.delete(link)

        # Remove blobs
        blobs = list(doc.blob)
        for blob in blobs:
            session.delete(blob)

        parent = doc.folder
        session.delete(doc)

        # Remove empty folders
        if remove_parent:
            while parent is not None:
                if len(parent.documents) > 0:
                    parent = None
                    break
                if len(parent.folders) > 0:
                    parent = None
                    break
                next_parent = parent.parent
                session.delete(parent)
                parent = next_parent

        # Remove empty tags
        if remove_tags:
            for t in check_tags:
                if (t.documents) > 0:
                    continue
                session.delete(t)

        self._sorted = False
        return True

    def _remove_folder(self, session, folder: Document, remove_tags=False, remove_parent=False):
        for doc in list(folder.documents):
            self._remove_doc(session, doc, remove_tags=remove_tags, remove_parent=remove_parent)
        for subfolder in list(folder.folders):
            self._remove_folder(session, subfolder, remove_tags, remove_parent=remove_parent)
        parent = folder.parent
        session.delete(folder)

        # Remove empty folders
        if remove_parent:
            while parent is not None:
                if len(parent.documents) > 0:
                    parent = None
                    break
                if len(parent.folders) > 0:
                    parent = None
                    break
                next_parent = parent.parent
                session.delete(parent)
                parent = next_parent

        self._sorted = False
        return True

    def _remove_path(self, session, path, remove_tags=False, not_exist_ok=False, remove_parent=False):
        folder = (
            session.query(Folder)
            .filter(Folder.path == str(Path(path).relative_to(get_data_dir())))
            .one_or_none()
        )
        if folder is not None:
            result = self._remove_folder(session, folder, remove_tags, remove_parent = remove_parent)
            return result

        doc = (
            session.query(Document)
            .filter(Document.path == str(Path(path).relative_to(get_data_dir())))
            .one_or_none()
        )
        if doc is not None:
            result = self._remove_doc(session, doc, remove_tags, remove_parent = remove_parent)
            return result

        if not_exist_ok:
            return True

        raise ValueError(f"Path '{path}' wasn't found in database!")

    def _add_path(self, session, path):
        # make sure dst_path is not in database
        existing_folder = session.query(Folder).filter(Folder.path == str(Path(path).relative_to(get_data_dir()))).one_or_none()
        if existing_folder is not None:
            existing_doc = session.query(Document).filter(Document.path == str(Path(path).relative_to(get_data_dir()))).one_or_none()
        else:
            existing_doc = None

        if existing_folder is not None or existing_doc is not None:
            raise ValueError(f"Object for path {path} is already in database!")

        path = Path(path)
        if path.is_dir():
            self._update_db(session, path)
            return True
        else:
            doc = self._add_doc(session, path)
            session.flush()
            self._update_links(session, [doc])
            self._update_tags(session, [doc])
            session.flush()
            return True

    def _move_path(self, session, src_path, dst_path, remove_parent=False):
        # NOTE: it's easier to remove then re-add
        folder = session.query(Folder).filter(Folder.path == str(Path(src_path).relative_to(get_data_dir()))).one_or_none()
        if folder is None:
            doc = session.query(Document).filter(Document.path == str(Path(src_path).relative_to(get_data_dir()))).one_or_none()
        else:
            doc = None
        if folder is None and doc is None:
            raise ValueError(f"Object for path {src_path} wasn't found in database!")
        if doc is None:
            target_path = dst_path
        else:
            target_path = Path(dst_path) / Path(src_path).parts[-1]

        self._remove_path(session, src_path, remove_parent=remove_parent)
        session.begin_nested()
        try:
            self._add_path(session, target_path)
        except ValueError as e:
            session.rollback()
            return False
        return True

    def _update_path(self, session, path, not_exist_ok=False):
        # NOTE: it's easier to remove then re-add
        self._remove_path(session, path, not_exist_ok=not_exist_ok)
        session.begin_nested()
        try:
            self._add_path(session, path)
        except ValueError as e:
            session.rollback()
            return False
        return True

    def _update_links(self, session, objs, recurse=False):
        for obj in objs:
            if isinstance(obj, Folder):
                self._update_links(session, obj.documents)
                if recurse:
                    self._update_links(session, obj.folders, recurse)
            elif not isinstance(obj, Document):
                return  # TODO: raise error
            else:
                text = obj.content

                # Remove existing links
                obj_refs = (
                    session.query(Link)
                    .filter(Link.source_id == obj.ID)
                    .all())
                for link in obj_refs:   # TODO: use 'list(obj.refs)' after fixing DB
                    session.delete(link)

                # Find all links within object
                links_search = re.finditer(r"\[\[(?:([^|\]]+)\|)*(@?[^|#\]]+?)(#[^|\]]+)*\]\]", text)
                for m in links_search:
                    # add each link to refs list of document
                    target_id = m.groups()[1]
                    # TODO: also do 'obj.refs.append(link)' after fixing DB

                    # look for referred objects, and update their refbacks
                    if target_id[:1] != "@":
                        targets = (
                            session.query(Document)
                            .filter(Document.doc_id == target_id)
                            .all()
                        )
                    else:
                        target_pattern = "%--" + target_id[1:]
                        targets = (
                            session.query(Document)
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
                        session.add(link)
                        t.refbacks.append(link)
                        pass


    def _update_tags(self, session, objs, recurse=False):
        for obj in objs:
            if isinstance(obj, Folder):
                self._update_tags(session, obj.documents)
                if recurse:
                    self._update_tags(session, obj.folders, recurse)
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
                        session.query(Tag)
                        .filter(Tag.name == tag_name)
                        .one_or_none()
                    )
                    if tag is None:
                        tag = Tag(name = tag_name)
                        session.add(tag)
                        session.flush()
                    obj.tags.append(tag)

                session.flush()        # flush to update tags and relationships

                # Remove empty tags
                deleted = False
                for tag in previous_tags:
                    if len(tag.documents) == 0:
                        session.delete(tag)
                        deleted = True
                if deleted:
                    session.flush()    # flush if at least one tag were deleted

    def _on_fs_change(self, change_kind, src_path, dst_path):
        if self._db_not_exists:
            return
        else:
            _session = self.session()
            with _session.begin():
                if change_kind == "add":
                    self._add_path(_session, src_path)
                elif change_kind == "modify":
                    self._update_path(_session, src_path)
                elif change_kind == "move":
                    self._move_path(_session, src_path, dst_path)
                elif change_kind == "delete":
                    self._remove_path(_session, src_path)
                else:
                    raise ValueError("Change kind value should be on of 'add', 'modify', 'move', 'delete'!")

    def build_dir_tree(self, path, query_dir, load_content=True):
        """
        args:
            path        - last name of path segment
            query_dir   - absolute path to start from
        """
        self.update()
        _session = self.session()
        with _session.begin():
            folder = (
                _session.query(Folder)
                .filter(Folder.path == str(Path(query_dir).relative_to(get_data_dir())))
                .one_or_none()
            )

            def _dig_dir(dir_data: Directory, folder: Folder):
                for doc in folder.documents:
                    dir_data.child_files.append(self._doc_to_post(doc, load_content))
                for subfolder in folder.folders:
                    subdir = Directory(subfolder.name)
                    _dig_dir(subdir, subfolder)
                    dir_data.child_dirs[subfolder.name] = subdir

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

        data_dir = get_data_dir()
        query_dir = data_dir / path
        if not is_relative_to(query_dir, data_dir) or not query_dir.exists():
            raise FileNotFoundError
        if structured:
            # TODO: looks like some original args are missing here, like collection, json_format, load_content
            result = self.build_dir_tree(path, query_dir)
            return result
        else:
            _session = self.session()
            with _session.begin():
                folder = (
                    _session.query(Folder)
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
        self.update()
        _session = self.session()
        with _session.begin():
            result = data.create(contents, title, path)
            if result is not False:
                self._add_path(_session, result)
            return result

    def get_item(self, dataobj_id):
        self.update()
        _session = self.session()
        with _session.begin():
            item = (
                _session.query(Document)
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

    def get_neighbor_item(self, dataobj_id, goto):
        sorted_items = self._sorted_items
        try:
            idx = sorted_items.index(dataobj_id)
        except ValueError:
            return None

        if idx + goto < 0:
            neighbor = sorted_items[-1]
        elif idx + goto >= len(sorted_items):
            neighbor = sorted_items[0]
        else:
            neighbor = sorted_items[idx + goto]
        return self.get_item(neighbor)

    def lookup_items(self, key):
        self.update()
        _session = self.session()
        with _session.begin():
            items = (
                _session.query(Document)
                .filter(or_(Document.doc_id.like("%--" + key), Document.doc_id == key))
                .all()
            )
            result = [{
                'id': item.doc_id,
                'path': item.path
            } for item in items]
            return result

    def search_items(self, key):
        self.update()
        _session = self.session()
        with _session.begin():
            items = (
                _session.query(Document)
                .filter(or_(Document.doc_id.like("%"+key+"%"), Document.title.like("%"+key+"%")))
                .all()
            )
            result = [{
                'title': f"{item.title} ({item.doc_id})",
                'id': item.doc_id
            } for item in items]
        return sorted(result, key=lambda x: x['id'])

    def move_item(self, dataobj_id, new_path):
        self.update()
        _session = self.session()
        with _session.begin():
            doc = _session.query(Document).filter(Document.doc_id == dataobj_id).one_or_none()
            if doc is None:
                raise ValueError(f"Document with ID '{dataobj_id}' is not found in database!")
            src_path = get_data_dir() / doc.path
            result = data.move_item(dataobj_id, new_path)
            if result is False:
                db_result = self._remove_path(_session, src_path, remove_parent=False)
            else:
                db_result = self._move_path(_session, src_path, get_data_dir() / new_path, remove_parent=False)
        if result is False:
            return result
        elif db_result is False:
            raise ValueError(f"Failed to updated DB!")
        return result

    def rename_folder(self, old_path, new_name):
        old_path = old_path.strip("/")
        new_name = new_name.strip("/")
        self.update()
        _session = self.session()
        with _session.begin():
            folder = _session.query(Folder).filter(Folder.path == old_path).one_or_none()
            if folder is None:
                raise ValueError(f"Folder with path 'P{old_path}' is not found in database!")
            result = data.rename_folder(old_path, new_name)
            if result is False:
                db_result = self._remove_path(_session, get_data_dir() / old_path)
            else:
                db_result = self._move_path(_session, get_data_dir() / old_path, get_data_dir() / result)
        if result is False:
            return result
        elif db_result is False:
            raise ValueError(f"Failed to updated DB!")
        return result

    def import_folder(self, folder_path, recursive, readonly, force):
        folder_path = folder_path.strip("/")
        fs_result = data.import_folder(folder_path, recursive, readonly, force)
        self.update()
        _session = self.session()

        result = [], fs_result[1]
        with _session.begin():
            for path in fs_result[0]:
                if self._update_path(_session, get_data_dir() / path, not_exist_ok=True):
                    result[0].append(path)
                else:
                    result[1].append(path)
        return result

    def delete_item(self, dataobj_id):
        self.update()
        _session = self.session()
        with _session.begin():
            doc = _session.query(Document).filter(Document.doc_id == dataobj_id).one_or_none()
            if doc is None:
                raise ValueError(f"Document with ID '{dataobj_id}' is not found in database!")
            result = data.delete_item(dataobj_id)
            self._remove_path(_session, get_data_dir() / doc.path)
        return result

    def update_item_md(self, dataobj_id, new_content):
        self.update()
        _session = self.session()
        with _session.begin():
            doc = _session.query(Document).filter(Document.doc_id == dataobj_id).one_or_none()
            if doc is None:
                raise ValueError(f"Document with ID '{dataobj_id}' is not found in database!")
            result = data.update_item_md(dataobj_id, new_content)
            if self._update_via_fs_watchdog_only:
                db_result = True
            elif result is not False:
                db_result = self._update_path(_session, get_data_dir() / doc.path)
            else:
                db_result = False
        if result is False or db_result is False:
            return False
        return result

    def update_item_frontmatter(self, dataobj_id, new_frontmatter):
        self.update()
        _session = self.session()
        with _session.begin():
            doc = _session.query(Document).filter(Document.doc_id == dataobj_id).one_or_none()
            if doc is None:
                raise ValueError(f"Document with ID '{dataobj_id}' is not found in database!")
            result = data.update_item_frontmatter(dataobj_id, new_frontmatter)
            if result is not False:
                db_result = self._update_path(_session, get_data_dir() / doc.path)
            else:
                db_result = False
        if result is False or db_result is False:
            return False
        return result

    def get_dirs(self):
        self.update()
        _session = self.session()
        with _session.begin():
            dirnames = [folder.path for folder in _session.query(Folder).all()]
            return dirnames

    def create_dir(self, name):
        name = name.strip("/")
        self.update()
        _session = self.session()
        with _session.begin():
            folder = _session.query(Folder).filter(Folder.path == name).one_or_none()
            if folder is not None:
                raise ValueError(f"Folder with name '{name}' is already in database!")
            parent_folder = _session.query(Folder).filter(Folder.path == str(Path(name).parent)).one_or_none()
            if parent_folder is None:
                raise ValueError(f"Can't find parent folder for {name} in DB!")
            result = data.create_dir(name)
            if result is not False:
                folder = self._add_folder(_session, get_data_dir() / result)
                _session.flush()
                parent_folder.folders.append(folder)
        return result

    def delete_dir(self, name):
        name = name.strip("/")
        self.update()
        _session = self.session()
        with _session.begin():
            folder = _session.query(Folder).filter(Folder.path == name).one_or_none()
            if folder is None:
                raise ValueError(f"Folder with name '{name}' wasn't found in database!")
            result = data.delete_dir(name)
            self._remove_path(_session, get_data_dir() / folder.path)
            return result

    def open_file(self, path):
        # TODO: only if it's latest db
        return data.open_file(path)

    def get_all_tags(self, force=False):
        # NOTE: force arg is for compatibility with tags.py
        self.update()
        _session = self.session()
        with _session.begin():
            tags = [tag.name for tag in _session.query(Tag).all()]
            return tags

    def select_by_tags(self, selected_tags):
        """
        Returns:
        - list of object ids, with mentioned tags
        - list with dict items, containing nested tags names and occurrences count
        """
        self.update()
        _session = self.session()
        with _session.begin():
            if selected_tags is None or len(selected_tags) == 0:
                all_tags = _session.query(Tag).all()
                result_tags = sorted([{'tag': t.name, 'count': len(t.documents)} for t in all_tags], key = lambda x: x['tag'].lower())
                return [], result_tags
            docs = _session.query(Document).all()
            selected_tags = [tag.lower() for tag in selected_tags]
            items = []
            for item in docs:
                item_tags = [tag.name.lower() for tag in item.tags]
                if all(tag in item_tags for tag in selected_tags):
                    items.append(item)
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
        _session = self.session()
        with _session.begin():
            item = (
                _session.query(Document)
                .filter(Document.doc_id == dataobj_id)
                .one_or_none()
            )
            if item is None:
                return []
            backlinks = {}
            for link in item.refbacks:
                src = (
                    _session.query(Document)
                    .filter(Document.ID == link.source_id)
                    .one_or_none()
                )
                if src is None:
                    continue
                # TODO: fixup DB structure and simply use src = link.source.doc_id
                if src.doc_id not in backlinks:
                    backlinks[src.doc_id] = []
                    backlinks[src.doc_id].append((link.full, src.title))
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
        _session = self.session()
        with _session.begin():
            tag = (
                _session.query(Tag)
                .filter(Tag.name == tag_name)
                .one_or_none()
            )
            if tag is None:
                tag = Tag(
                    name = tag_name
                )
                _session.add(tag)
                _session.flush()
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
