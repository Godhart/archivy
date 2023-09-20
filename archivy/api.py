from flask import Response, jsonify, request, Blueprint, current_app, json
from werkzeug.security import check_password_hash
from flask_login import login_user
from tinydb import Query

from archivy.db import layer
from archivy.data import valid_image_filename, save_image
from archivy.search import search
from archivy.models import DataObj, User
from archivy.helpers import get_db
from archivy.render.render import render as ssr


api_bp = Blueprint("api", __name__)


@api_bp.route("/login", methods=["POST"])
def login():
    """
    Logs in the API client using
    [HTTP Basic Auth](https://en.wikipedia.org/wiki/Basic_access_authentication).
    Pass in the username and password of your account.
    """
    db = get_db()
    user = db.search(Query().username == request.authorization["username"])
    if user and check_password_hash(
        user[0]["hashed_password"], request.authorization["password"]
    ):
        # user is verified so we can log him in from the db
        user = User.from_db(user[0])
        login_user(user, remember=True)
        return Response(status=200)
    return Response(status=401)


@api_bp.route("/bookmarks", methods=["POST"])
def create_bookmark():
    """
    Creates a new bookmark

    **Parameters:**

    All parameters are sent through the JSON body.
    - **url** (required)
    - **tags**
    - **path**
    """
    json_data = request.get_json()
    bookmark = DataObj(
        url=json_data["url"],
        tags=json_data.get("tags", []),
        path=json_data.get("path", current_app.config["DEFAULT_BOOKMARKS_DIR"]),
        type="bookmark",
    )
    bookmark.process_bookmark_url()
    bookmark_id = bookmark.insert()
    if bookmark_id:
        return jsonify(
            bookmark_id=bookmark_id,
        )
    return Response(status=400)


@api_bp.route("/notes", methods=["POST"])
def create_note():
    """
    Creates a new note.

    **Parameters:**

    All parameters are sent through the JSON body.
    - **title** (required)
    - **content** (required)
    - **tags**
    - **path**
    """
    json_data = request.get_json()
    note = DataObj(
        title=json_data["title"],
        content=json_data["content"],
        path=json_data.get("path", ""),
        tags=json_data.get("tags", []),
        type="note",
    )

    note_id = note.insert()
    if note_id:
        return jsonify(note_id=note_id)
    return Response(status=400)


@api_bp.route("/dataobjs/<path:path>")
def get_dataobj(path):
    dataobj_id = path
    """Returns dataobj of given id"""
    dataobj = layer().get_item(dataobj_id)

    return (
        jsonify(
            dataobj_id=dataobj_id,
            title=dataobj["title"],
            content=dataobj.content,
            md_path=dataobj["fullpath"],
        )
        if dataobj
        else Response(status=404)
    )


@api_bp.route("/dataobjs/<path:path>", methods=["DELETE"])
def delete_dataobj(path):
    dataobj_id = path
    """Deletes object of given id"""
    if not layer().get_item(dataobj_id):
        return Response(status=404)
    layer().delete_item(dataobj_id)
    return Response(status=204)


@api_bp.route("/dataobjs/<path:path>", methods=["PUT"])
def update_dataobj(path):
    """
    Updates object of given id.

    Parameter in JSON body:

    - **content**: markdown text of new dataobj.
    """
    dataobj_id = path
    if request.json.get("content"):
        try:
            layer().update_item_md(dataobj_id, request.json.get("content"))
            return Response(status=200)
        except BaseException:
            return Response(status=404)
    return Response("Must provide content parameter", status=401)


@api_bp.route("/dataobjs/frontmatter/<path:path>", methods=["PUT"])
def update_dataobj_frontmatter(path):
    """
    Updates frontmatter of object of given id.

    Parameter in JSON body:

    - **title**: (optional) the new title of the dataobj.
    - **tags**:  (optional) the tags.
    """
    dataobj_id = path
    new_frontmatter = {}
    for key in ("title", "tags", ):
        if key in request.json:
            new_frontmatter[key] = request.json[key]

    # TODO: error in case of unknown key in json

    try:
        layer().update_item_frontmatter(dataobj_id, new_frontmatter)
        return Response(status=200)
    except BaseException:
        return Response(status=404)


@api_bp.route("/dataobjs", methods=["GET"])
def get_dataobjs():
    """Gets all dataobjs"""
    cur_dir = layer().get_items(structured=False, json_format=True)
    return jsonify(cur_dir)


@api_bp.route("/tags/add_to_index", methods=["PUT"])
def add_tag_to_index():
    """Add a tag to the database."""
    tag = request.json.get("tag", False)
    if tag and type(tag) is str and layer('tags').is_tag_format(tag):
        if layer('tags').add_tag_to_index(tag):
            return Response(status=200)
        else:
            return Response(status=404)

    return Response("Must provide valid tag name.", status=401)


@api_bp.route("/dataobj/local_edit/<path:path>", methods=["GET"])
def local_edit(path):
    dataobj_id = path
    dataobj = layer().get_item(dataobj_id)
    if dataobj:
        layer().open_file(dataobj["fullpath"])
        return Response(status=200)
    return Response(status=404)


@api_bp.route("/folders/new", methods=["POST"])
def create_folder():
    """
    Creates new directory

    Parameter in JSON body:
    - **path** (required) - path of newdir
    """
    directory = request.json.get("path")
    try:
        sanitized_name = layer().create_dir(directory)
        if not sanitized_name:
            return Response("Invalid dirname", status=400)
    except FileExistsError:
        return Response("Directory already exists", status=400)
    return Response(sanitized_name, status=200)


@api_bp.route("/folders/delete", methods=["DELETE"])
def delete_folder():
    """
    Deletes directory.

    Parameter in JSON body:
    - **path** of dir to delete
    """
    directory = request.json.get("path")
    if directory == "":
        return Response("Cannot delete root dir", status=401)
    if layer().delete_dir(directory):
        return Response("Successfully deleted", status=200)
    return Response("Could not delete directory", status=400)


@api_bp.route("/search", methods=["GET"])
def search_endpoint():
    """
    Searches the instance.

    Request URL Parameter:
    - **query**
    - **start_path**
    """
    if not current_app.config["SEARCH_CONF"]["enabled"]:
        return Response("Search is disabled", status=401)
    query = request.args.get("query")
    if query[:1] == "[" and query[-1:] == "]":
        search_results = layer().search_items(query[1:-1])
    else:
        start_path = request.args.get("start_path", None)
        search_results = search(query, start_path=start_path)
    result = jsonify(search_results)
    return result


@api_bp.route("/images", methods=["POST"])
def image_upload():
    CONTENT_TYPES = ["image/jpeg", "image/png", "image/gif"]
    if "image" not in request.files:
        return jsonify({"error": "400"}), 400
    image = request.files["image"]
    if (
        valid_image_filename(image.filename)
        and image.headers["Content-Type"].strip() in CONTENT_TYPES
    ):
        saved_to = save_image(image)
        return jsonify({"data": {"filePath": f"/images/{saved_to}"}}), 200
    return jsonify({"error": "415"}), 415


@api_bp.route("/render", methods=["POST"])
def render():
    """
    Server side rendering for fenced code

    Parameter in JSON body:
     - **kind**:    (required) - renderer kind
     - **objid**:   (required) - id of object for which rendering is done
     - **content**: (required) - source content to render
    """
    kind    = request.json.get("kind")
    objid   = request.json.get("objid")
    content = request.json.get("content")
    options = request.json.get("options")
    # TODO: check args
    try:
        if False:
            return Response("TODO", status=400)
    except FileExistsError:
        return Response("TODO", status=400)
    try:
        result = ssr(kind, objid, content, options)
    except Exception as e:
        return Response(f"{e}", status=422) # Unprocessable content

    response = Response(
        response=json.dumps({"data": result}),
        status=200,
        mimetype="application/json",
    )
    return response

