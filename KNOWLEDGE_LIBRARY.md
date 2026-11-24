# Content Pack Format

Repetorium starts without a learning library. Download `RepetoriumSkills.MD`
from Library to review the supported library structure, field
requirements, and ZIP layout. New packs should include a root-level `INFO.md`
that records the pack's purpose, scope, user intent, metadata, quiz inventory,
and any work still in progress. The Library's Info button displays this
document for each installed pack. Existing packs without `INFO.md` remain
importable and show a notice that the document is missing. Use any authoring
tools you prefer.

Import a validated ZIP from Library, or set
`REPETORIUM_CONTENT_DIR` to a local content directory. Settings lets you select
one installed pack or mix lessons across packs. Individual exports include a
pack plus its point-in-time progress and Skill Map snapshot. **Export All**
asks for a filename suffix (the current date by default) and writes one
`<pack-id>-<suffix>.zip` per installed pack to a selected folder. It will not
overwrite existing files. The shared **Include progress** checkbox (on by
default) controls whether individual and batch exports include progress
snapshots; when unchecked, existing snapshots are omitted too.
If an imported pack has the same name or ID as an installed pack, Repetorium
asks you to add suffixes to both names so the packs remain distinct. Existing
pack IDs, content, and saved progress are preserved; a unique ID is generated
for the incoming pack if its original ID is already installed.

The ZIP may contain `INFO.md` at its root alongside `library.yaml` or
`pack.yaml`. It is UTF-8 Markdown, limited to 1 MB, and is preserved on export.
It is documentation only; Repetorium does not execute it or use it to configure
practice. See the downloaded skills file for the required content and counting
rules.

The application treats content as data: it accepts registered generators,
validates references, and does not execute content-provided code. Validation is
not a sandbox; only import packs from sources you trust.

The Library's copyright acknowledgment does not grant permission to reproduce
or share source material. Pack authors are responsible for following the
source's license and using verbatim text or exercises only when authorized.
