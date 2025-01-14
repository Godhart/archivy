from pathlib import Path
from os.path import sep
from pkg_resources import require
from shutil import which
from datetime import datetime

import archivy.markdown_adapter as frontmatter
from flask import (
    render_template,
    flash,
    redirect,
    request,
    url_for,
    send_file,
    send_from_directory,
)
from flask_login import login_user, current_user, logout_user
from tinydb import Query
from werkzeug.security import check_password_hash, generate_password_hash

from archivy.models import DataObj, User
from archivy import app, forms, csrf
from archivy.constants import IPS
from archivy.db import layer
from archivy.data import image_exists2, valid_image_filename
from archivy.helpers import get_db, write_config, is_safe_redirect_url
from archivy.search import search, search_frontmatter_tags
from archivy.config import Config

from urllib.parse import urlencode as ue

import re
import os


@app.context_processor
def pass_defaults():
    dataobjs = layer().get_items(load_content=False)
    version = require("archivy")[0].version
    SEP = sep
    # check windows parsing for js (https://github.com/Uzay-G/archivy/issues/115)
    if SEP == "\\":
        SEP += "\\"
    return dict(dataobjs=dataobjs, SEP=SEP, version=version, config=app.config)


@app.before_request
def check_perms():
    allowed_path = (
        request.path.startswith("/login")
        or request.path.startswith("/static")
        or request.path.startswith("/api/login")
    )
    if not current_user.is_authenticated and not allowed_path:
        return redirect(url_for("login", next=request.path))
    return


@app.route("/")
@app.route("/index")
def index():
    path = request.args.get("path", "").strip("/")
    if path != "":
        path += "/"
    try:
        files = layer().get_items(path=path)
        process_modified = lambda x: datetime.strptime(x.get("modified_at"), "%x %H:%M")
        recent_notes = list(
            filter(
                lambda x: "modified_at" in x,
                layer().get_items(path=path, structured=False),
            )
        )
        most_recent = sorted(recent_notes, key=process_modified, reverse=True)[:5]
        tag_cloud = set()
        for f in files.child_files:
            for tag in f.get("tags", []):
                tag_cloud.add(tag)
    except FileNotFoundError:
        flash("Directory does not exist.", "error")
        return redirect("/")

    return render_template(
        "home.html",
        title=path or "root",
        search_enabled=app.config["SEARCH_CONF"]["enabled"],
        dir=files,
        current_path=path,
        new_folder_form=forms.NewFolderForm(),
        delete_form=forms.DeleteFolderForm(),
        rename_form=forms.RenameDirectoryForm(),
        import_form=forms.ImportFolderForm(),
        view_only=os.environ.get("ARCHIVY_VIEW_ONLY", "True").lower() != "false",
        tag_cloud=tag_cloud,
        most_recent=most_recent,
    )


# TODO: refactor two following methods
@app.route("/bookmarks/new", methods=["GET", "POST"])
def new_bookmark():
    default_dir = app.config.get("DEFAULT_BOOKMARKS_DIR", "root directory")
    form = forms.NewBookmarkForm(path=default_dir)
    form.path.choices = [("", "root directory")] + [
        (pathname, pathname) for pathname in layer().get_dirs()
    ]
    if form.validate_on_submit():
        path = form.path.data
        tags = form.tags.data.split(",") if form.tags.data != "" else []
        tags = [tag.strip() for tag in tags]
        bookmark = DataObj(url=form.url.data, tags=tags, path=path, type="bookmark")
        bookmark.process_bookmark_url()
        bookmark_id = bookmark.insert()
        if bookmark_id:
            flash("Bookmark Saved!", "success")
            return redirect(f"/dataobj/{bookmark_id}")
        else:
            flash(bookmark.error, "error")
            return redirect("/bookmarks/new")
    # for bookmarklet
    form.url.data = request.args.get("url", "")
    path = request.args.get("path", default_dir).strip("/")
    # handle empty argument
    form.path.data = path
    return render_template("dataobjs/new.html", title="New Bookmark", form=form, current_path=path)


@app.route("/notes/new", methods=["GET", "POST"])
def new_note():
    form = forms.NewNoteForm()
    default_dir = "root directory"
    form.path.choices = [("", default_dir)] + [
        (pathname, pathname) for pathname in layer().get_dirs()
    ]
    if form.validate_on_submit():
        path = form.path.data
        tags = form.tags.data.split(",") if form.tags.data != "" else []
        tags = [tag.strip() for tag in tags]
        note = DataObj(title=form.title.data, path=path, tags=tags, type="note")
        note_id = note.insert()
        if note_id:
            flash("Note Saved!", "success")
            return redirect(f"/dataobj/{note_id}")
    path = request.args.get("path", default_dir).strip("/")
    # handle empty argument
    form.path.data = path
    return render_template("/dataobjs/new.html", title="New Note", form=form, current_path=path)


@app.route("/tags-all")
def show_all_tags():
    if not app.config["SEARCH_CONF"]["engine"] == "ripgrep" and not which("rg"):
        flash("Ripgrep must be installed to view pages about embedded tags.", "error")
        return redirect("/")
    tags = sorted(layer('tags').get_all_tags(force=True))
    return render_template("tags/all.html", title="All Tags", tags=tags)


@app.route("/tags")
def select_tags():
    if not app.config["SEARCH_CONF"]["engine"] == "ripgrep" and not which("rg"):
        flash("Ripgrep must be installed to view pages about embedded tags.", "error")
        return redirect("/")
    selected_tags = request.args.to_dict(flat=False).get('tag', [])

    obj_ids, tags = layer().select_by_tags(selected_tags)

    items = []
    for obj_id in obj_ids:
        items.append({'id': obj_id, 'path': obj_id.replace(IPS, '/')})

    selected_tags_href = []
    for tag in selected_tags:
        if len(selected_tags) > 1:
            href = "?" + "&".join([ue({'tag':t}) for t in selected_tags if t != tag])
        else:
            href = ""
        selected_tags_href.append({'tag': tag, 'href': href})

    href = "?" + "&".join([ue({'tag':t}) for t in selected_tags])
    for tag in tags:
        tag['href'] = href + ('','&')[len(href)>1] + ue({'tag':tag['tag']})

    return render_template("tags/select.html", title="Select Tags", tags=tags, selected_tags=selected_tags_href, items=items)

    # TODO: option to select by author


@app.route("/tags/<tag_name>")
def show_tag(tag_name):
    return redirect("/tags?"+ue({'tag': tag_name}))

    if not app.config["SEARCH_CONF"]["enabled"] and not which("rg"):
        flash(
            "Search (for example ripgrep) must be installed to view pages about embedded tags.",
            "error",
        )
        return redirect("/")

    results = search(f"#{tag_name}#", strict=True)
    res_ids = set(
        [item["id"] for item in results]
    )  # avoid duplication of results between context-aware embedded tags and metadata ones
    for res in search_frontmatter_tags(tag_name):
        if res["id"] not in res_ids:
            results.append(res)

    return render_template(
        "tags/show.html",
        title=f"Tags - {tag_name}",
        tag_name=tag_name,
        search_result=results,
    )


def _show_dataobj(dataobj, dataobj_id):
    get_title_id_pairs = lambda x: (x["title"], x["id"])
    titles = list(
        map(get_title_id_pairs, layer().get_items(structured=False, load_content=False))
    )
    js_ext = ""
    if app.config["DATAOBJ_JS_EXTENSION"]:
        js_ext = (
            (Path(app.config["USER_DIR"]) / app.config["DATAOBJ_JS_EXTENSION"])
            .open("r")
            .read()
        )

    if not dataobj:
        flash("Data could not be found!", "error")
        return redirect("/")

    if request.args.get("raw") == "1":
        return frontmatter.dumps(dataobj)

    backlinks = layer().get_back_links(dataobj_id)

    # Form for moving data into another folder
    move_form = forms.MoveItemForm()
    move_form.path.choices = [("", "root directory")] + [
        (pathname, pathname) for pathname in layer().get_dirs()
    ]

    post_title_form = forms.TitleForm()
    post_title_form.title.data = dataobj["title"]

    # Get all tags
    tag_list = layer('tags').get_all_tags()

    view_only = os.environ.get("ARCHIVY_VIEW_ONLY", "True").lower() != "false"
    if not view_only:
        view_only = dataobj.metadata.get('readonly', None) in (True, "yes", "true")

    return render_template(
        "dataobjs/show.html",
        title=dataobj["title"],
        dataobj=dataobj,
        backlinks=backlinks,
        current_path=dataobj["dir"],
        form=forms.DeleteDataForm(),
        view_only=view_only,
        search_enabled=app.config["SEARCH_CONF"]["enabled"],
        post_title_form=post_title_form,
        move_form=move_form,
        tag_list=tag_list,
        embedded_tags=[],
        titles=titles,
        js_ext=js_ext,
        icons=app.config["EDITOR_CONF"]["toolbar_icons"],
    )


@app.route("/dataobj/<path:path>")
def show_dataobj(path):
    dataobj_id = path
    goto = request.args.get("goto", None)
    if goto is not None:
        try:
            goto = int(goto)
        except ValueError:
            flash("Bad goto arg!", "error")
            return redirect("/")
        if goto in (-1, 1):
            dataobj = layer().get_neighbor_item(dataobj_id, goto)
            return redirect(f"/dataobj/{dataobj['id']}")
        else:
            flash("Bad goto arg!", "error")
            return redirect("/")
    else:
        dataobj = layer().get_item(dataobj_id)
    return _show_dataobj(dataobj, dataobj_id)


@app.route("/dataobj/lookup/<key>")
def lookup_dataobj(key):
    lookup_result = layer().lookup_items(key)

    if len(lookup_result) == 1:
        return redirect(f"/dataobj/{lookup_result[0]['id']}")

    if len(lookup_result) == 0:
        flash("Data could not be found!", "error")
        return redirect("/")

    return redirect(f"/dataobj/select/{key}")


@app.route("/dataobj/select/<key>")
def select_dataobj(key):
    lookup_result = layer().lookup_items(key)

    if len(lookup_result) == 0:
        flash("Data could not be found!", "error")
        return redirect("/")

    items = []
    for item in sorted(lookup_result, key=lambda x: x['path']):
        items.append({'id': item['id'], 'path': item['path']})

    return render_template(
        "dataobjs/select.html",
        title=f"Select page for '{key}'",
        items=items,
    )


@app.route("/dataobj/move/<path:path>", methods=["POST"])
def move_item(path):
    dataobj_id = path
    form = forms.MoveItemForm()
    out_dir = form.path.data if form.path.data != "" else "root directory"
    if form.path.data == None:
        flash("No path specified.")
        return redirect(f"/dataobj/{dataobj_id}")
    try:
        if layer().move_item(dataobj_id, form.path.data):
            flash(f"Data successfully moved to {out_dir}.", "success")
            target_path = form.path.data.strip("/")
            new_dataobj_id = target_path.replace("/", IPS) + IPS + dataobj_id.split(IPS)[-1]
            return redirect(f"/dataobj/{new_dataobj_id}")
        else:
            flash(f"Data could not be moved to {out_dir}.", "error")
            return redirect(f"/dataobj/{dataobj_id}")
    except FileNotFoundError:
        flash("Data not found.", "error")
        return redirect("/")
    except FileExistsError:
        flash("Data already in target directory.", "error")
        return redirect(f"/dataobj/{dataobj_id}")


@app.route("/dataobj/delete/<path:path>", methods=["POST"])
def delete_data(path):
    dataobj_id = path
    try:
        layer().delete_item(dataobj_id)
    except BaseException:
        flash("Data could not be found!", "error")
        return redirect("/")
    flash("Data deleted!", "success")
    parent_path = Path(dataobj_id.replace(IPS, "/")).parent
    if parent_path == "":
        return redirect("/")
    else:
        return redirect(f"/?path={parent_path}/")


@app.route("/login", methods=["GET", "POST"])
def login():
    form = forms.UserForm()
    if form.validate_on_submit():
        db = get_db()
        user = db.search(
            (Query().username == form.username.data) & (Query().type == "user")
        )

        if user and check_password_hash(user[0]["hashed_password"], form.password.data):
            user = User.from_db(user[0])
            login_user(user, remember=True)
            flash("Login successful!", "success")

            next_url = request.args.get("next")
            if next_url and is_safe_redirect_url(next_url):
                return redirect(next_url)
            else:
                return redirect("/")

        flash("Invalid credentials", "error")
        return redirect("/login")
    return render_template("users/login.html", form=form, title="Login")


@app.route("/logout", methods=["DELETE", "GET"])
def logout():
    logout_user()
    flash("Logged out successfully", "success")
    return redirect("/")


@app.route("/user/edit", methods=["GET", "POST"])
def edit_user():
    form = forms.UserForm()
    if form.validate_on_submit():
        db = get_db()
        db.update(
            {
                "username": form.username.data,
                "hashed_password": generate_password_hash(form.password.data),
            },
            doc_ids=[current_user.id],
        )
        flash("Information saved!", "success")
        return redirect("/")
    form.username.data = current_user.username
    return render_template("users/edit.html", form=form, title="Edit Profile")


@app.route("/folders/create", methods=["POST"])
def create_folder():
    form = forms.NewFolderForm()
    if form.validate_on_submit():
        path = Path(form.parent_dir.data.strip("/")) / form.new_dir.data
        new_path = layer().create_dir(str(path))
        flash("Folder successfully created.", "success")
        return redirect(f"/?path={new_path}")
    flash("Could not create folder.", "error")
    return redirect(request.referrer or "/")


@app.route("/folders/delete", methods=["POST"])
def delete_folder():
    form = forms.DeleteFolderForm()
    if form.validate_on_submit():
        folder_path = form.dir_name.data
        if layer().delete_dir(folder_path):
            flash("Folder successfully deleted.", "success")
            parent_path = Path(folder_path).parent
            if parent_path == "":
                return redirect("/")
            else:
                return redirect(f"/?path={parent_path}/")
        else:
            flash("Folder not found.", "error")
            return redirect(request.referrer or "/", 404)
    flash("Could not delete folder.", "error")
    return redirect(request.referrer or "/")


@app.route("/folders/rename", methods=["POST"])
def rename_folder():
    form = forms.RenameDirectoryForm()
    if form.validate_on_submit():
        try:
            new_path = layer().rename_folder(form.current_path.data, form.new_name.data)
            if not new_path:
                flash("Invalid input.", "error")
            else:
                flash("Renamed successfully.", "success")
                return redirect(f"/?path={new_path}")
        except FileNotFoundError:
            flash("Directory not found.", "error")
        except FileExistsError:
            flash("Target directory exists.", "error")
    return redirect("/")


@app.route("/folders/import", methods=["POST"])
def import_folder():
    form = forms.ImportFolderForm()
    if form.validate_on_submit():
        try:
            success, errors = layer().import_folder(
                form.current_path.data, form.recursive.data, form.readonly.data, form.force.data)
            if len(success) > 0:
                flash(f"Successfully imported {len(success)} file(s).", "success")
            if len(errors) > 0:
                errors_str = '\n'.join(errors)
                flash(f"Import errors: {errors_str}", "error")
            return redirect(f"/?path={form.current_path.data}")
        except FileNotFoundError:
            flash("Directory not found.", "error")
    return redirect(f"/?path={form.current_path.data}")


@app.route("/bookmarklet")
def bookmarklet():
    return render_template("bookmarklet.html", title="Bookmarklet")


# @app.route("/images/<filename>")
# def serve_image(filename):
#     if filename and valid_image_filename(filename):
#         image_path = image_exists(filename)
#         if image_path:
#             return send_file(image_path)
#         else:
#             return "Image not found", 404
#     else:
#         return "Invalid file request", 413


@app.route("/images/<path:path>")
def serve_image2(path):
    filename = os.path.split(path)[1]
    if filename and valid_image_filename(filename):
        image_path = image_exists2(path)
        if image_path:
            return send_file(image_path)
        else:
            return "Image not found", 404
    else:
        return "Invalid file request", 413


@app.route("/static/custom.css")
def custom_css():
    if not app.config["THEME_CONF"].get("use_custom_css", False):
        return ""
    return send_from_directory(
        Path(app.config["USER_DIR"]) / "css",
        app.config["THEME_CONF"]["custom_css_file"],
    )


@app.route("/config", methods=["GET", "POST"])
def config():
    """
    Web View to edit and update configuration.
    """

    def update_config_value(key, val, dictionary):
        if key != "SECRET_KEY":
            if type(val) is dict:
                for k, v in val.items():
                    update_config_value(k, v, dictionary[key])
            else:
                dictionary[key] = val

    form = forms.config_form(app.config)
    default = vars(Config())
    if form.validate_on_submit():
        changed_config = Config()
        changed_config.override(form.data)
        for k, v in vars(changed_config).items():
            # propagate changes to configuration
            update_config_value(k, v, app.config)
        write_config(vars(changed_config))  # save to filesystem config
        flash("Config successfully updated.", "success")
    elif request.method == "POST":
        flash("Could not update config.", "error")
    return render_template(
        "config.html", conf=form, default=default, title="Edit Config"
    )


@csrf.exempt  # exempt from CSRF to be able to submit info directly from bookmarklet
@app.route("/save_from_bookmarklet", methods=["POST"])
def save_raw_url():
    """
    Used in the bookmarklet - Saves a URL by taking its raw HTML.

    POST parameters:
    - html
    - url
    """
    html = request.form.get("html")
    if not html:
        return "No HTML provided", 400
    bookmark = DataObj(url=request.form.get("url"), type="bookmark")
    bookmark.process_bookmark_url(html)
    if bookmark.insert():
        return redirect(f"/dataobj/{bookmark.id}")
    else:
        return "Could not save bookmark", 500
