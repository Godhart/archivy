import sys
import os
import archivy.render.common as render_unit
from archivy.render.render import render as ssr

render_unit.DATA_ROOT_PATH = os.path.join(os.getcwd(), "tests", "render")
render_unit.DATA_ROOT_PREFIX = "/dataobjs"
render_unit.IMG_ROOT_PATH = os.path.join(os.getcwd(), "tests", "render", ".out")
render_unit.IMG_ROOT_PREFIX = "/image"
render_unit.CACHE_ROOT_PATH = os.path.join(os.getcwd(), "tests", "render", ".cache")
render_unit.PARAMS = {

}


def html(title, content, output_path):
    html_data = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>{title}</title>
</head><body>
{content}
</body></html>
"""
    if output_path is None:
        print(html_data)
    else:
        if not os.path.exists(output_path):
            with open(output_path, "w", encoding='utf-8') as f:
                f.write(html_data)
        else:
            raise ValueError(f"Output path '{output_path}' for test result is already occupied!")


def test1(output_path=None):
    content = ssr("ssr", "Test--Test1--SomeFile",
"""---
src : drawings/test1_drawing.odg
caption : test1
ref : test1_img
---
""")
    html("test1", content, output_path)


def test2(output_path=None):
    content = ssr("ssr", "Test--Test2--SomeFile2",
"""---
src  : drawings/test2_drawing_ssr.md
page : ""  # NOTE: pages aren't supported. This disables page specified in ssr.md
---
""")
    html("test2", content, output_path)


tests = {
    "test1": test1,
    "test2": test2,
}

