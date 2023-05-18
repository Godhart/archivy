Following changes were made to archivy:

# 1. ID from Filename

A major change, non compatible with current mainstream version.

Front-matter part is optional for notes. ID of document is made from it's filename (without last suffix) and names of their parent folders in following manner: `<parent_folder1>--<parent_subfolder>--...--<file_name>`, like `Docs--General--Intro` for example.

Default title for note is generated from filename, with first letter capital and '_' (underscores) replaced with spaces.
For custom title set it via front-matter header, as previously.
Modification date is set from file's attribute in file system.

## PROs and CONs

### PROs

1. No need to maintain IDs database. Before change it was hard or even impossible to simply merge two knowledge bases together. For example if two people are using self-hosted solution and synchronizing documents via git.
2. Easy mix different approaches to fill knowledge base - simply make/copy files at their places, no extra actions required
3. ID is not present in file name

### CONs

1. When renaming/moving file it's required to maintain references (which is not done yet automatically)
2. When syncing via vcs extra setup is required to match file's date with commit's date

Example for git:
```bash
sudo apt install git-restore-mtime		
cd [repo]
git restore-mtime
```

# 2. Partial reference name

Refer to documents using only part of their ID. If part is ambiguous then document selection page is shown

# 3. Joined tags selection

Select documents that are containing all selected tags

# 4. Search improvements

1. Search bar in header
2. Limit scope of search to current path in folder view

# 5. Layout improvements

1. File editing actions are hidden until edit button pressed (previously only editor were hidden)
2. Actions for folders are hidden until action button pressed
3. Nav bar can be hidden

# 6. Quick Light/Dark theme toggler

Made via button in header part. Selected option is stored in browser's local storage for persistence

# 7. Fenced code is highlighted with highlightjs by default

Set fenced section language to 'raw' to put code without decorations

# 8. Copy button for fenced code

Copy-button in the right-top of code section to copy content into clipboard

# 9. Custom rendering of fenced code

1. Wavedrom, done on client side
2. Server side rendering for things that hard to handle in browser

# 10. Readonly option

Make document readonly setting 'readonly' field in front-matter section to true

# 11. Custom graphic formats via SSR

Embedding Visio, Open Document Format drawings requires no conversion.

> But page selection isn't supported

# 12. Pictures inversion depending on theme

> Uses SSR approach to generalize with custom graphics support

Pictures inversion may be set, depending on light/dark theme in following manner:

- auto      - invert in dark mode
- opposite  - invert in light mode
- true      - always invert
- no        - never invert

# Server side rendering aka SSR

Allows to render data using non-web apps that running on server or web apps, accessible from server
- using fenced code as source for data
- using local files, referred from fenced code

Uses caching to save server's time and energy

Following data formats are supported:

- TODO: formats

# Importing data from foreign formats

Non-markdown documents can be converted into markdown format via Archivy folder's action.

TODO: more details
