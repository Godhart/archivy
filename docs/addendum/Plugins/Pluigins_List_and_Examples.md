# Simple Markdown's Markup Extensions

*[FPD]: Pan-Doc Friendly - rendered properly with pandoc

A markup that takes only few chars

| Example               | Example code                 | Feature     | How to use          | Plugin | FPD |
|-----------------------|------------------------------|-------------|---------------------|--------|-----|
| ==marked text==       | `==marked text==`            | Text marker | Words within two `=`| [markdownitMark](https://www.npmjs.com/package/markdown-it-mark) | :bb: |
| ++underlined text++   | `++underlined text++`        | Underline   | Words within two `+`| [markdownitIns](https://www.npmjs.com/package/markdown-it-ins) | :bb: |
| H~2~O                 | `H~2~O`                      | Subscript   | Letters between `~` | [markdownitSub](https://www.npmjs.com/package/markdown-it-sub) | :bb: |
| e^x^                  | `e^x^`                       | Superscript | Letters between `^` | [markdownitSup](https://www.npmjs.com/package/markdown-it-sup) | :bb: |
| $f(x) = x^2$          | `$f(x) = x^2$`               | TexMath     | Formula within `$`  | ??? | :bv: |
| :yum: ;)              | `:yum:`, `;)`                | Emoji       | Kind within `:` or smiles                       | [markdownitEmoji](https://www.npmjs.com/package/markdown-it-emoji) | :bb: |
| word^[Footnote text]  | `word^[Footnote text]`       | Footnotes   | More details at [footnotes](#footnotes-details) | [markdownitFootnote](https://github.com/markdown-it/markdown-it-footnote) | :bv: |
|                       | `- [ ] Text` or `- [x] Text` | Task lists  | More details at [task lists](#task-lists)       | [markdownitTaskLists](https://www.npmjs.com/package/markdown-it-task-list-plus) | :bv: |
| #alpha-numeric-minus# | `#alpha-numeric-minus#`      | Tags        | More details at [tags](#inline-tags)            | | :bx: |
| <!-- Some useful thoughts --> *nothing should be seen* | `<!-- Some useful thoughts -->` | Comments  | Words within `<!--` and `-->`. More details at [comments](#comments) | [markdownitInlineComments](https://www.npmjs.com/package/markdown-it-inline-comments)

## Footnotes details

- [x] Pandoc Friendly

Makes a footnotes.

In HTML footnotes are placed in the footer of the page.

When exported to non-HTML multipage formats (Office, PDF),
footnotes are placed on footer of the page where text with reference is (in native format where possible).

**Examples:**

```markdown
Footnote 1 link[^first].

Footnote 2 link[^second].

Inline footnote^[Text of inline footnote] definition.

Duplicated footnote reference[^second].

[^first]: Footnote **can have markup**

    and multiple paragraphs.

[^second]: Footnote text.
```

And here how it looks like:

Footnote 1 link[^first].

Footnote 2 link[^second].

Inline footnote^[Text of inline footnote] definition.

Duplicated footnote reference[^second].

[^first]: Footnote **can have markup**

    and multiple paragraphs.

[^second]: Footnote text.

::: styled warning
check links for complete understanding 
:::

## HTML Attributes

- :bb: Pandoc Friendly (partially?)

[markdownItAttrs](https://www.npmjs.com/package/@gerhobbelt/markdown-it-attrs)

Allows to specify HTML attributes for sections of text

**Settings:**

```python
{"allowedAttributes" : ["id", "class", "style"]}
```

**Examples:**

```
# Following attributes specification is for whole paragraph

id to paragraph, case 1 {#paragraph-id1}
id to paragraph, case 1 {id="paragraph-id2"}

class to paragraph,case 1 {.class-name}
class to paragraph,case 2 {class="class-name"}

style to paragraph {style="color: rgb(128,128,0);"}

all together {#paragraph-id3 .warning style="color: rgb(255,0,0)"}
```

```
# Following attributes specification is for whole text chunk

Following inline code would be custom styled `some inline code section`{style="color: rgb(255,0,0)"}

Following word{style="color: rgb(255,0,0)"} would be custom styled
```

::: styled warning
text chunk should be emphasized from other text in some manner (bold, italic, code, fenced, etc.)
:::


Color and background of this paragraph is set with attrs {#id-example .image-auto style="color: rgb(0,0,100); background-color: rgb(170,170,220)"}

Color (yellow) for this code `example code`{#id-example-2 style="color: rgb(255,255,0)"} is set with attrs

You can place links to paragraphs or text chunks with id.
For example - this [[link|@Plugins_Settings#id-example]] will transfer you to colorized paragraph above.
Link code: `[[like this|@Plugins_Settings#id-example]]`

## Comments

Allows to hide portions of document. Same usage as for HTML comments.

Comments opening / closing tags are ignored in code sections (inline code, fenced code, indented code)

**Multiline comments example:**

```markdown
Some text you want to see
<!-- This
part is hidden
by intent -->
continuation of visible text
```

will produce following:

Some text you want to see
<!-- This
part is hidden
by intent -->
continuation of visible text


## Task Lists

Display list with checkboxes.

Start your list item with `- [ ]` for empty checkbox or with `- [x]` for marked checkbox

**Example:**

```markdown
- [x] This is Done
- [ ] This is Not Done yet
```

will produce following:

- [x] This is Done
- [ ] This is Not Done yet

# Extra Markup

Text markup beyond Markdown's rules

## Custom section via [markdownitContainer](https://www.npmjs.com/package/markdown-it-container)

- [ ] Additional Support for non-HTML export is required (not done yet)

Custom sections allows place text into specific HTML element and customize it as necessary.

Custom sections are like fenced code, but starts and ends with triple `:`

Common format for custom section is:

```markdown
::: <name> [args]
Text for custom section
:::
```

::: styled warning
Note there is space between last `:` and `<name>`
:::

where:

- `<name>` is custom section kind (see below)
- `[args]` arguments to customize section, format depends on section kind
- `Text for custom section` - text that you want to place into specific HTML element. Markdown's markup rules are respected.

**For example:**

```markdown
::: styled warning
Warning message
:::
```

will display text in a `<div>` section, with class `warning`.

More on custom sections kind in following subsections.

### Styled section

Allows place chunk of text within a `<div>` section styled with specified classes
warning
- Kind: `styles`
- Args: optional, space separated classes list, `info bigger` for example

**Example:**

```
::: styled warning
This paragraph uses class 'warning'
:::
```

will produce following warning section:

::: styled warning
This paragraph uses class 'warning' :sunglasses:
:::

### Spoiler section

Hide large text under short 'spoiler'.

- Kind: `spoiler`
- Args: mandatory, text that would be used as short 'spoiler' message

**Example:**

```
::: spoiler click to show hidden text
this text is **hidden** with spoiler
:::
```

will produce following spoiler section:

::: spoiler click to show hidden text
this text is **hidden** with spoiler
:::

### Nested custom sections

::: styled warning
You can nest custom sections :sunglasses:

::: spoiler click to show hidden text
As many times as required

::: styled warning
Just use common closing `:::`
:::

::: styled warning
**TODO:** not quite sure about common closing `:::`, looks like *this-bug-is-a-feature*, probably some things may not work
:::


### More custom sections

To add more custom sections you'll have to modify Archivy's code (at least that's so right now)

Modify file `markdown-parser.html` after line `.use(window.markdownitContainer,`


# Structured Text

Following plugins allowing some kind of text structurization

## Definitions list via [markdownitDeflist](https://www.npmjs.com/package/markdown-it-deflist)

- [x] Pandoc Friendly

Render Terms in a commonly defined way. In plans to generate summary terms page when exporting to non-HTML formats.

Implements [pandoc's specification](https://pandoc.org/MANUAL.html#definition-lists)

**Example:**

```markdown
Term 1

:   Definition 1

Term 2 with *inline markup*

:   Definition 2

        { some code, part of Definition 2 }

    Third paragraph of definition 2.
```

will produce following:

Term 1

:   Definition 1

Term 2 with *inline markup*

:   Definition 2

        { some code, part of Definition 2 }

    Third paragraph of definition 2.

**More from Pandoc's guide for terms**

Each term must fit on one line, which may optionally be followed by a blank line, and must be followed by one or more definitions. A definition begins with a colon or tilde, which may be indented one or two spaces.

A term may have multiple definitions, and each definition may consist of one or more block elements (paragraph, code block, list, etc.), each indented four spaces or one tab stop. The body of the definition (not including the first line) should be indented four spaces. However, as with other Markdown lists, you can “lazily” omit indentation except at the beginning of a paragraph or other block element:

```markdown
Term 1

:   Definition
with lazy continuation.

    Second paragraph of the definition.
```

If you leave space before the definition (as in the example above), the text of the definition will be treated as a paragraph. In some output formats, this will mean greater spacing between term/definition pairs. For a more compact definition list, omit the space before the definition:

```markdown
Term 1
  ~ Definition 1

Term 2
  ~ Definition 2a
  ~ Definition 2b
```

Note that space between items in a definition list is required.

## Abbreviation via [markdownitAbbr](https://www.npmjs.com/package/@gerhobbelt/markdown-it-abbr)

- :bb: Pandoc Friendly

Add abbreviations explanations. Explanation is only visible when mouse is hovered over abbreviation.
In plans to generate summary abbreviations page.

**Example:**

```
*[HTML]: Hyper Text Markup Language
```

When hover over HTML word you'll explanation in a pop-up.

## Inline Tags

- [ ] Should be thrown away or rendered in special manner when exporting to non-HTML, but not done yet

To make a tag put word (or words, joined with `_` or `-`) within `#` chars

**Example:**

```
A following word #example# would ad a tag 'example' to a document
```

Is rendered as:

A following word #example# would ad a tag 'example' to a document

And adds tag 'example' to a document (you can see it in the header of the page)

The word it self becomes a link to select-by-tag page

# Extra Content

- [ ] Additional Export Support is required for export

## Picture

- [x] Done via SSR

Unified way to place a picture.

Allows to set size, add caption and reference to a picture.

Uses smart picture inversion so picture is looks fine on both light and dark themes.
Options to invert:

- auto (default) - invert when theme is dark
- opposite to theme - invert when theme is light
- permanent on/off

Colors are kept - red is red, blue is blue, green is green even if inverted

Converts to required media format if necessary

SVGs may be rendered inline, so search on page may find text on it.
Also when rendered inline blank space around drawing may be removed
(which is a vital option for inserting pictures in EMF/WMF format).
But **quite sometimes** inline rendering produces broken results, so use it with caution.

**Format:**

`````yaml
```
TODO:
```
`````

**Example:**

`````yaml
```
TODO:
```
`````

<!-- TODO:
## Table

- [x] Done via SSR

```yaml
TODO:
```

## Import structured text

- [x] Done via SSR

```yaml
TODO:
```

## Foreign docs

- [x] Done via SSR

```yaml
TODO:
```

## Mermaid

- [x] Done via SSR

```mermaid
TODO:
```

-->

## Wavedrom

- [x] Done in HTML

Draws waveforms with WaveDrom.

> Some other tools are also supports wavedrom in the same way

Data for waveform is specified as structure in JSON format.
Format is rather complex and even supports expressions. More info at https://wavedrom.com/

**Example:**

`````json
```wavedrom
{ signal: [
  { name: "clk",         wave: "p.....|..." },
  { name: "Data",        wave: "x.345x|=.x", data: ["head", "body", "tail", "data"] },
  { name: "Request",     wave: "0.1..0|1.0" },
  {},
  { name: "Acknowledge", wave: "1.....|01." }
]}
```
`````

```wavedrom
{ signal: [
  { name: "clk",         wave: "p.....|..." },
  { name: "Data",        wave: "x.345x|=.x", data: ["head", "body", "tail", "data"] },
  { name: "Request",     wave: "0.1..0|1.0" },
  {},
  { name: "Acknowledge", wave: "1.....|01." }
]}
```

::: styled warning
Wavedrom diagrams have issue with hot toggling light/dark theme. Reload page if you changed theme
:::

# Plugins working Under the Hood

## markdownItAnchor

Places permalink symbol after heading

**Settings:**

```python
{"permalink": True, "permalinkSymbol": "#"}
```

## markdownItTocDoneRight

Creates Table of Content in the header of document

**Settings:**

```python
{
    "listClass": "toc-list",
    "itemClass": "toc-list",
}
```

::: styled warning
`toc-list` class provides proper numbering for TOC items (that will correspond to headings numbers)
:::
