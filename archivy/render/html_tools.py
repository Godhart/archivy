import sys
from lxml import etree


def _h_find_all(root, tag):
    for item in root.iterfind(tag):
        yield item
    for node in root:
        for item in _h_find_all(node, tag):
            yield item


def get_body(path, update_image_style):
    parser = etree.HTMLParser()
    with open(path, "rb") as f:
        page = etree.parse(f, parser)

    # print(dir(page))
    # result = etree.tostring(page.find("body"), pretty_print=True, method="html")
    result = []
    if update_image_style is not None and update_image_style != "":
        for image in _h_find_all(page.find("body"), "img"):
            style = image.get("class", "")
            if len(style) > 0:
                style += " "
            style += update_image_style
            image.set("class", style)

    for node in page.find("body"):
        result.append(etree.tostring(node, pretty_print=True, method="html").decode(encoding='utf-8'))
    return "".join(result)


if __name__ == "__main__":
    if sys.argv[1] == "test1":
        a = get_body(sys.argv[2], "filter: invert();") # TODO: now it should be a style
    pass
