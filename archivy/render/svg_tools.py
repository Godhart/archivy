import sys
import os
import xml.dom.minidom as DOM
import re
import subprocess


DBG_PRINT = False


def dprint(*arg, **argv):
    if DBG_PRINT:
        print(*arg, **argv)


def resizeSVG(svg, width, height, auto_fit_width, auto_fit_height, background="#FFFFFF"):
    resize = width != "" or height != ""

    if resize:
        svg.removeAttribute("width")
        svg.removeAttribute("height")
        svg.setAttribute("preserveAspectRatio", "none")

    if svg.hasAttribute("style"):
        svg_style = svg.getAttribute("style")
        styles = svg_style.split(";")
        svg_style = ""
        for s in styles:
            if re.match(r"^(width|height):.*$", s) is None:
                svg_style += s + ";"
            elif not resize:
                svg_style += s + ";"
    else:
        svg_style = ""

    if "background:" not in svg_style:
        if background is not None:
            svg_style += f"background:{background};"

    if resize and width != "":
        svg.setAttribute("width", width)
        svg_style += "width:" + str(width) + ";"

    if resize and height != "":
        svg.setAttribute("height", height)
        svg_style += "height:" + str(height) + ";"

    if auto_fit_width != "":
        svg_style += "max-width:" + str(auto_fit_width) + ";"

    if auto_fit_height != "":
        svg_style += "max-height:" + str(auto_fit_height) + ";"

    svg.setAttribute("style", svg_style)
    svg.setAttribute("standalone", "yes")


def setDoctype(document, doctype):
    # source: https://stackoverflow.com/questions/1980380/how-to-render-a-doctype-with-pythons-xml-dom-minidom
    imp= document.implementation
    newdocument= imp.createDocument(doctype.namespaceURI, doctype.name, doctype)
    newdocument.xmlVersion= document.xmlVersion
    refel= newdocument.documentElement
    for child in document.childNodes:
        if child.nodeType==child.ELEMENT_NODE:
            newdocument.replaceChild(
                newdocument.importNode(child, True), newdocument.documentElement
            )
            refel= None
        elif child.nodeType!=child.DOCUMENT_TYPE_NODE:
            newdocument.insertBefore(newdocument.importNode(child, True), refel)
    return newdocument


def resize(input_path, output_path, width="", height="", auto_fit_width="", auto_fit_height="", background="#FFFFFF"):
    resize = True
    if width == "-" and height == "-":
        resize = False

    err_path = input_path+".err"
    err_msg = None
    result = "<svg><p>Something went wrong</p></svg>"

    if os.path.exists(err_path):
        os.unlink(err_path)
    try:
        svg_doc = DOM.parse(input_path)
    except Exception as e:
        svg_doc = None
        err_msg = f"Failed to open input file due to exception: {e}"
        try:
            # Copy input data into error message as it may contain info about error
            with open(input_path, "r") as f:
                err_msg += "\n\n" + f.read()
        except:
            pass

    if svg_doc is not None:
        try:
            svg = svg_doc.getElementsByTagName("svg")[0]
            if resize:
                dprint(
                    "\n\n`resizeSVG '" + width + "' '" + height + "' '" + auto_fit_width + "' '" + auto_fit_height + "'`\n\n".replace("\n", "\n<br>"))
                resizeSVG(svg, width, height, auto_fit_width, auto_fit_height, background)
            result = svg.toxml()
        except Exception as e:
            err_msg = f"SVG resize failed due to exception: {e}"

    if err_msg is not None:
        with open(err_path, "w") as f:
            f.write(err_msg)
        err_msg_html = err_msg.replace("\n", "<br>")
        result = f"<svg><p>{err_msg_html}</p><svg>"

    if result is not None:
        if output_path == "-":
            print(result)
        elif output_path == None:
            return result
        else:
            with open(output_path, "w") as f:
                f.write(result)


def convert_to(format, source_path, target_path):
    subprocess.run(['rsvg-convert', '-f', format, '-o', target_path, source_path])


if __name__ == "__main__":
    width = ""
    height = ""
    auto_fit_width = ""
    auto_fit_height = ""

    dprint("\n\n```\n"+" ".join(["'"+v+"'" for v in sys.argv])+"\n```\n\n".replace("\n", "\n<br>"))

    if len(sys.argv) < 3:
        print("""```
Usage: python3 _resizeSvg.py <input> <output> [width] [height] [auto_fit_width] [auto_fit_height]
```""")
        exit(0)

    if len(sys.argv) > 3:
        width = sys.argv[3]
    if len(sys.argv) > 4:
        height = sys.argv[4]
    if len(sys.argv) > 5:
        auto_fit_width = sys.argv[5]
    if len(sys.argv) > 6:
        auto_fit_height = sys.argv[6]

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    resize(input_path, output_path, width, height, auto_fit_width, auto_fit_height)

    exit(0)
