from pathlib import Path
from shutil import which
from subprocess import run, PIPE
import json

from flask import current_app

from archivy.constants import IPS
from archivy.helpers import get_elastic_client

from archivy.hacks import Hacks
get_data_dir = Hacks.get_data_dir


# Example command ["rg", RG_MISC_ARGS, RG_FILETYPE, RG_REGEX_ARG, query, str(get_data_dir())]
#  rg -il -t md -e query files
# -i -> case insensitive
# -l -> only output filenames
# -t -> file type
# -e -> regexp
RG_MISC_ARGS = "-it"
RG_REGEX_ARG = "-e"
RG_FILETYPE = "md"


def add_to_index(model):
    """
    Adds dataobj to given index. If object of given id already exists, it will be updated.

    Params:

    - **index** - String of the ES Index. Archivy uses `dataobj` by default.
    - **model** - Instance of `archivy.models.Dataobj`, the object you want to index.
    """
    es = get_elastic_client()
    if not es:
        return
    payload = {}
    for field in model.__searchable__:
        payload[field] = getattr(model, field)
    es.index(
        index=current_app.config["SEARCH_CONF"]["index_name"], id=model.id, body=payload
    )
    return True


def remove_from_index(dataobj_id):
    """Removes object of given id"""
    es = get_elastic_client()
    if not es:
        return
    es.delete(index=current_app.config["SEARCH_CONF"]["index_name"], id=dataobj_id)


def query_es_index(query, strict=False):
    """
    Returns search results for your given query

    Specify strict=True if you want only exact result (in case you're using ES.
    """
    es = get_elastic_client()
    if not es:
        return []
    search = es.search(
        index=current_app.config["SEARCH_CONF"]["index_name"],
        body={
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["*"],
                    "analyzer": "rebuilt_standard",
                }
            },
            "highlight": {
                "fragment_size": 0,
                "fields": {
                    "content": {
                        "pre_tags": "",
                        "post_tags": "",
                    }
                },
            },
        },
    )

    hits = []
    for hit in search["hits"]["hits"]:
        formatted_hit = {"id": hit["_id"], "title": hit["_source"]["title"]}
        if "highlight" in hit:
            formatted_hit["matches"] = hit["highlight"]["content"]
            reformatted_match = " ".join(formatted_hit["matches"])
            if strict and not (query in reformatted_match):
                continue
        hits.append(formatted_hit)
    return hits


def parse_ripgrep_line(line):
    """Parses a line of ripgrep JSON output"""
    hit = json.loads(line)
    data = {}
    if hit["type"] == "begin":
        curr_file = (
            Path(hit["data"]["path"]["text"]).parts[-1].replace(".md", "").split("-")
        )  # parse target note data from path
        curr_id = str(Path(hit["data"]["path"]["text"]).relative_to(get_data_dir())).replace("/", IPS)[:-3]
        title = curr_file[-1].replace("_", " ")
        data = {"title": title, "matches": [], "id": curr_id}
    elif hit["type"] == "match":
        data = hit["data"]["lines"]["text"].strip()
    else:
        return None  # only process begin and match events, we don't care about endings
    return (data, hit["type"])


def query_ripgrep(query, start_path=None):
    """
    Uses ripgrep to search data with a simpler setup than ES.
    Returns a list of dicts with detailed matches.
    """

    from archivy.data import get_data_dir

    if not which("rg"):
        return []

    global_search = (query[:1] == '/' and query[:2] != '//')
    if global_search:
        query = query[1:]
    else:
        if query[:2] == '//':
            query = query[1:]

    if start_path is None or global_search:
        start_path = get_data_dir()
    else:
        start_path = get_data_dir() / Path(start_path)
        if not start_path.is_relative_to(get_data_dir()):
            return []
    rg_cmd = ["rg", RG_MISC_ARGS, RG_FILETYPE, "--json", query, str(start_path)]
    rg = run(rg_cmd, stdout=PIPE, stderr=PIPE, timeout=60)
    output = rg.stdout.decode().splitlines()
    hits = []
    for line in output:
        parsed = parse_ripgrep_line(line)
        if not parsed:
            continue
        if parsed[1] == "begin":
            hits.append(parsed[0])
        if parsed[1] == "match":
            if not (parsed[0].startswith("tags: [") or parsed[0].startswith("title:")):
                hits[-1]["matches"].append(parsed[0])
    return sorted(
        hits, key=lambda x: len(x["matches"]), reverse=True
    )  # sort by number of matches


def search_frontmatter_tags(tag=None):
    """
    Returns a list of dataobj ids that have the given tag.
    """
    from archivy.data import get_data_dir

    if not which("rg"):
        return []
    META_PATTERN = r"(^|\n)tags:(\n- [_a-zA-ZÀ-ÖØ-öø-ÿА-Яа-я0-9]+)+"
    hits = []
    rg_cmd = [
        "rg",
        "-Uo",
        RG_MISC_ARGS,
        RG_FILETYPE,
        "--json",
        RG_REGEX_ARG,
        META_PATTERN,
        str(get_data_dir()),
    ]
    rg = run(rg_cmd, stdout=PIPE, stderr=PIPE, timeout=60)
    output = rg.stdout.decode().splitlines()
    for line in output:
        parsed = parse_ripgrep_line(line)
        if not parsed:  # the event doesn't interest us
            continue
        if parsed[1] == "begin":
            hits.append(parsed[0])  # append current hit data
            continue
        if parsed[1] == "match":
            sanitized = parsed[0].replace("- ", "").split("\n")[2:]
            hits[-1]["tags"] = hits[-1].get("tags", []) + sanitized  # get tags
    if tag:
        hits = list(filter(lambda x: tag in x["tags"], hits))
    return hits


def query_ripgrep_tags():
    """
    Uses ripgrep to search for tags.
    Mandatory reference: https://xkcd.com/1171/
    """

    EMB_PATTERN = r"(^|\n| )#([-_a-zA-ZÀ-ÖØ-öø-ÿА-Яа-я0-9]+)#"
    from archivy.data import get_data_dir

    if not which("rg"):
        return []

    # embedded tags
    # io: case insensitive
    rg_cmd = ["rg", "-Uio", RG_FILETYPE, RG_REGEX_ARG, EMB_PATTERN, str(get_data_dir())]
    rg = run(rg_cmd, stdout=PIPE, stderr=PIPE, timeout=60)
    hits = set()
    for line in rg.stdout.splitlines():
        tag = Path(line.decode()).parts[-1].split(":")[-1]
        tag = tag.replace("#", "").lstrip()
        hits.add(tag)
    # metadata tags
    for item in search_frontmatter_tags():
        for tag in item["tags"]:
            hits.add(tag)
    return hits


def query_ripgrep_tags_selection(tags):
    """
    Uses ripgrep to search for tags combinations.
    Returns:
    - list of object ids, with mentioned tags
    - list with dict items, containing nested tags names and occurrences count
    """

    EMB_PATTERN = r"(^|\n| )#([-_a-zA-ZÀ-ÖØ-öø-ÿА-Яа-я0-9]+)#"
    from archivy.data import get_data_dir

    if not which("rg"):
        return [], []
    
    # embedded tags
    # io: case insensitive
    rg_cmd = ["rg", "-Uio", RG_FILETYPE, RG_REGEX_ARG, EMB_PATTERN, str(get_data_dir())]
    rg = run(rg_cmd, stdout=PIPE, stderr=PIPE, timeout=60)

    obj_tags = {}
    matching = {}

    for line in rg.stdout.splitlines():
        path = Path(line.decode()).relative_to(get_data_dir())
        path, tag = str(path).split(":")
        path = path[:-len(Path(path).suffix)]
        tag = tag.replace("#", "").lstrip()
        if path[:2] in ("./", ".\\"):
            path = path[2:]
        obj_id = path.replace('/', IPS).replace('\\', IPS)
        if obj_id not in obj_tags:
            obj_tags[obj_id] = []
        obj_tags[obj_id].append(tag)

    for item in search_frontmatter_tags():
        obj_id = item['id']
        if obj_id not in obj_tags:
            obj_tags[obj_id] = []
        obj_tags[obj_id] = set(obj_tags[obj_id] + item['tags'])

    if tags is not None and len(tags) > 0:
        for obj_id, lookup in obj_tags.items():
            if all(tag in lookup for tag in tags):
                matching[obj_id] = lookup
    else:
        matching = obj_tags

    nested_tags = {}
    for lookup in matching.values():
        for tag in lookup:
            if tag in tags:
                continue
            if tag not in nested_tags:
                nested_tags[tag] = 1
            else:
                nested_tags[tag] += 1

    result_tags = sorted([{'tag': k, 'count': v} for k,v in nested_tags.items()], key = lambda x: x['tag'])
    if tags is not None and len(tags) > 0:
        return sorted(matching.keys()), result_tags
    else:
        return [], result_tags


def search(query, strict=False, start_path=None):
    """
    Wrapper to search methods for different engines.

    If using ES, specify strict=True if you only want results that strictly match the query, without parsing / tokenization.
    """
    force_rg = query[:2].lower() == "r:"
    if force_rg:
        query = query[2:]
    if not force_rg and current_app.config["SEARCH_CONF"]["engine"] == "elasticsearch":
        return query_es_index(query, strict=strict)
    elif current_app.config["SEARCH_CONF"]["engine"] == "ripgrep" or which("rg"):
        return query_ripgrep(query, start_path=start_path)
