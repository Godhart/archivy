import re


def import_markdown(text, importers):

    result = []

    fenced = ""
    style = ""
    kind = ""

    to_render = None

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
                to_render = [line]
            else:
                result.append(line)
        else:
            if to_render is None:
                result.append(line)
            else:
                to_render.append(line)

            if line.strip() == fenced:
                fenced = ""
                if to_render is not None:
                    if importers is None:
                        # TODO: render data
                        result.append(f"![Rendered data {style}](/rendered/data)")
                    else:
                        result.append(importers.import_markdown(to_render))
                    to_render = None

    return "\n".join(result)


if __name__ == "__main__":
    text = """
# Here is some md

```mermaid
  graph TD;
      A-->B;
      A-->C;
      B-->D;
      C-->D;
```

```import
  graph TD;
      A-->B;
      A-->C;
      B-->D;
      C-->D;
```

````
```import
  graph TD;
      A-->B;
      A-->C;
      B-->D;
      C-->D;
```
````

```{qwerty}
  graph TD;
      A-->B;
      A-->C;
      B-->D;
      C-->D;
```

Fin!

"""
    rendered = import_markdown(text)

    rendered = rendered.split("\n")
    pass
