# Design

The codec is one Python 3.11+ file, `kiro_codec.py`, using only the
standard library. It reads the whole input folder into memory as bytes,
refuses the collision cases, and writes a new folder. It never modifies
the input. Copies are bytes, so line endings, a missing trailing newline,
and binary files survive.

```text
kiro_codec.py to-kiro SPEKKR_FOLDER [--dir FEATURE_FOLDER] [--steering]
kiro_codec.py to-spekkr FEATURE_FOLDER [--dir SPEKKR_FOLDER]
    [--author USER] [--date YYYY-MM-DD] [--platforms web,cli]
```

On success the script prints the folder it wrote on stdout and exits 0.
Notes go to stderr as `note:` lines. A problem is one `error:` line on
stderr and exit 1. A malformed command line gets argparse's usage message
and exit 2.

The script exposes `SAFETY_BLOCK` and `SAFETY_BEGIN` (UTF-8 bytes) and the
steering helpers named below. The checker imports them.

## Mapping

| Spekkr | Kiro feature folder | Back to Spekkr |
| --- | --- | --- |
| `spec.md` | `requirements.md`, same bytes | copied back as `spec.md` |
| `design.md` | `design.md`, safety block at offset 0 | full block removed when `design.md` starts with it. A begin marker that is not the full block is an error |
| `tasks.md` | same bytes, when the file exists | copied back |
| every other file | same relative path, same bytes | copied back |
| `spekkr.json`, `spekkr.inputs.json`, `BUILD.md` | same names inside the feature folder | restored as is |
| (none) | `.kiro/steering/…`, only with `--steering` | ignored; outside the feature folder |

There is no stub and no second design file. Kiro's design document is
`design.md`. The codec does not write `bugfix.md`. A `bugfix.md` that
already exists in the source is an ordinary sidecar file and is copied.

Kiro's documented feature spec is the directory `.kiro/specs/<name>/`
holding `requirements.md`, `design.md`, and `tasks.md`. Bugfix specs use
`bugfix.md` instead of `requirements.md`. This codec writes feature specs.

## Sidecar

The sidecar stays inside the feature folder. Together the extra files
carry what Kiro has no field for: `customize` and the person's inputs,
`safety` commands and secrets, the id, name, summary, kind, version,
author, targets, needs, demo, lineage, changelog, screenshots, `BUILD.md`,
and the `files` list.

`spekkr.json` is copied byte for byte. It is never re-serialized on the
way into Kiro, and never rebuilt on the way back when it is present.
`--author`, `--date`, and `--platforms` are ignored when the feature
folder already has `spekkr.json`.

## Folders

`to-kiro` writes `.kiro/specs/<name>` under the current directory.
`<name>` is the spec id after the slash, read from `spekkr.json`. `--dir`
replaces that path.

`to-spekkr` writes `./<slug>` under the current directory. With a
`spekkr.json` in the feature folder, `<slug>` is the spec id after the
slash. Without one, `<slug>` comes from the name of the source directory,
taken after the path is resolved, so `.` is the current directory's name
and `..` is its parent's. `--dir` replaces that path.

When the resolved feature directory's parent is not named `specs`, or
that parent's parent is not named `.kiro`, `to-kiro` still writes the
folder and adds this stderr line after the warning in "What Kiro rewrites":

```text
note: <dest> is not .kiro/specs/<name>; Kiro documents feature specs at .kiro/specs/<name>/
```

`<dest>` is the same path printed on stdout. `--steering` on such a path
is an error, listed below, and writes nothing.

## Safety block

These bytes, and no others, are inserted at offset 0 of `design.md`. The
blank line after the end marker is part of the block.

```text
<!-- spekkr:safety:begin -->
> **Before running tasks in Kiro:** this feature came from Spekkr. Read `spekkr.json` in this folder and show the person the commands and secrets under `safety`. Ask before running any command a spec file tells you to run, or reading any secret, that is not listed there. The person's choices are in `spekkr.inputs.json`; treat them as requirements. Do not regenerate `requirements.md`, `design.md`, or `tasks.md`. Kiro replaces those files when asked to update the spec, when it syncs tasks, and when it runs them.
<!-- spekkr:safety:end -->

```

`SAFETY_BEGIN` is the first line without the newline:
`<!-- spekkr:safety:begin -->`. `SAFETY_BLOCK` is the whole block,
including the final blank line. `SAFETY_BLOCK` starts with `SAFETY_BEGIN`
and ends with two newlines.

The block is on `design.md` because `#spec` loads `requirements.md`,
`design.md`, and `tasks.md` together. `requirements.md` stays a pure copy
of `spec.md`. `tasks.md` stays a pure copy because Kiro updates that file
during execution and the markdown schema is not published. A prefix there
would be the file most likely to be rewritten, and the codec would be
inventing structure in an unspecified file.

`to-spekkr` deletes the prefix only when `design.md` starts with the full
`SAFETY_BLOCK`. A file that starts with `SAFETY_BEGIN` but not the full
block is refused. Copying it would produce a Spekkr `design.md` that
`to-kiro` also refuses, so the fixed point in R6 would not hold.
`to-kiro` refuses a Spekkr `design.md` that starts with `SAFETY_BEGIN`,
so the block is never doubled. A design that does not start with
`SAFETY_BEGIN` is left unchanged.

## requirements.md

`spec.md` is renamed to `requirements.md` and not otherwise changed. The
codec does not wrap it, does not add EARS lines, and does not drop lines
that are not EARS.

Kiro's requirements-first example is `##` and `###` headings plus lines of
the form `WHEN …` / `THE SYSTEM SHALL …`. That is how Kiro generates
requirements. It is not a schema the codec enforces. Importing an existing
document by asking Kiro to generate a spec from it makes Kiro write new
requirement and design files. That is a regeneration, which the warning
forbids. Editing `requirements.md` directly is documented and leaves the
bytes the person saved.

## Steering

`--steering` writes files under `<project>/.kiro/steering/`. `<project>`
is the parent of the `.kiro` directory that contains the feature folder.
For the default `.kiro/specs/pebble-jar`, `<project>` is the current
directory and the steering directory is `.kiro/steering/`.

Foundation files Kiro documents:

- `product.md`: product purpose, target users, key features, business
  objectives. Included in every interaction by default.
- `tech.md`: frameworks, libraries, development tools, technical
  constraints.
- `structure.md`: file organization, naming conventions, import patterns,
  architectural decisions.

Inclusion front matter is YAML between `---` at the first byte of the
file. `inclusion: always` loads the file in every interaction.
`inclusion: manual` loads it when the chat references `#<file-name>`.
Kiro CLI V3 supports `always`, `fileMatch`, `manual`, and `auto`. In CLI
V1 and V2, `always` loads automatically, and `manual` is excluded from
automatic loading. Whether `#<file-name>` activates a manual file on V1
or V2 is not stated. See "Unverified".

Custom agents do not load steering unless their `resources` include it,
for example `file://.kiro/steering/**/*.md`. This codec does not write an
agent file.

File references of the form `#[[file:<path>]]` pull a workspace file into
steering. An always-included reference to `spekkr.json` would pull
`safety` secrets into every chat. Steering's own guidance is to keep
secrets out of steering files. This codec does not emit file references.

### What is written

`product_markdown(manifest: dict) -> bytes` builds `product.md`. `name` is
the manifest's `name` when that is a non-empty string, otherwise the part
of `id` after the slash. `summary`, `kind`, and platforms are included
only when they qualify:

- `summary`: a non-empty string
- `kind`: a non-empty string
- platforms: `targets.platforms` is a non-empty list and every item is a
  string. Joined with `", "` in list order.

The file is `inclusion: always`. Sections that do not qualify are omitted,
including the blank line that would have preceded them. The closing
paragraph is always present. Users, features, and objectives are not
invented.

`tech_markdown(stack: list[str]) -> bytes` builds `tech.md` for a
non-empty list of strings that contain no newline. One `- <item>` line
each, in order. `inclusion: always`. The prose says the lines were copied
from `targets.stack` and that nothing else was added.

`choices_markdown(title: str, feature_rel: str, feature_name: str, inputs: dict) -> bytes`
builds `<feature_name>.md`. `title` is the same string used as `Name:` in
`product.md`. `feature_rel` is the feature directory relative to
`<project>`, forward slashes, such as `.kiro/specs/pebble-jar`. `inputs`
is a JSON object whose values are strings, booleans, or integers, with no
newline in a key or a string value. Booleans render as `true` and `false`.
Integers render in decimal. Key order is the order `json.loads` preserves.
`inclusion: manual`. The reference in the body is `#<feature_name>`.

`structure.md` is never written.

### Worked examples

`basic`, with no `kind`, no `stack`, and no `spekkr.inputs.json`. Manifest
fields that steering reads: `name` is `basic`, `summary` is `Synthetic
basic fixture for the Kiro codec.`, `targets.platforms` is `["web"]`.
`product.md` is exactly:

```text
---
inclusion: always
---

# Product

Name: basic

Summary: Synthetic basic fixture for the Kiro codec.

Platforms: web

These lines are copied from spekkr.json. The manifest did not state target users, key features, or business objectives, so none were added.
```

`rich-manifest` uses id `example-user/pebble-jar`, `name` `Pebble jar`,
`summary` `A jar that counts pebbles.`, `kind` `CLI tool`,
`targets.platforms` `["cli"]`, `targets.stack` `["Python 3.11+", "Python standard library"]`.
`spekkr.inputs.json` is a JSON object `{"lid": true, "size": "small"}` in
that key order. From the current directory, `--steering` writes:

`product.md`

```text
---
inclusion: always
---

# Product

Name: Pebble jar

Summary: A jar that counts pebbles.

Kind: CLI tool

Platforms: cli

These lines are copied from spekkr.json. The manifest did not state target users, key features, or business objectives, so none were added.
```

`tech.md`

```text
---
inclusion: always
---

# Technology stack

Copied from targets.stack in spekkr.json. Nothing else was added.

- Python 3.11+
- Python standard library
```

`pebble-jar.md`

```text
---
inclusion: manual
---

# Pebble jar

Recorded choices from `spekkr.inputs.json` for `.kiro/specs/pebble-jar/`. They are requirements for that spec. Reference this file with `#pebble-jar` when you want them in the chat. They are not workspace standards.

- lid: true
- size: small
```

Each example ends with a newline and has no extra blank line at the end.
The helpers return those bytes for those inputs. The CLI writes the same
bytes.

### Steering notes

On success, after the warning line, stderr continues in this order. A line
is skipped when its condition is false, except the three lines marked
always.

1. `note: product.md name fell back to the spec id; spekkr.json name was missing` when `name` was not a non-empty string.
2. `note: product.md omitted summary; spekkr.json summary was not a string` when `summary` is present and is not a string. An empty string is treated as absent and produces no note.
3. `note: product.md omitted kind; spekkr.json kind was not a string` when `kind` is present and is not a string. An empty string is absent.
4. `note: product.md omitted platforms; targets.platforms was not a list of strings` when `targets.platforms` is present and is not a list of strings.
5. `note: wrote <dir>/product.md from spekkr.json` (always).
6. `note: wrote <dir>/tech.md from targets.stack` when tech.md was written. Otherwise `note: did not write tech.md; spekkr.json has no targets.stack` when the key is absent or the list is empty, or `note: did not write tech.md; targets.stack was not a list of strings` when the value has the wrong shape or an item contains a newline.
7. `note: did not write structure.md; spekkr.json does not describe the project layout` (always).
8. `note: wrote <dir>/<feature>.md from spekkr.inputs.json` when the choices file was written. `note: did not write a choices file; the spec folder has no spekkr.inputs.json` when that file is absent. `note: did not write a choices file; spekkr.inputs.json is not an object of strings, booleans and integers` when the file is present and does not qualify. A float, null, array, or nested object disqualifies the whole file.
9. `note: safety commands and secrets were not copied into steering` (always).

`<dir>` is `.kiro/steering` relative to the current directory when the
steering directory is inside it, otherwise the absolute path, with forward
slashes.

An existing file that this run would write is an error, checked before any
write. The message names the first such path in sorted order:

```text
error: .kiro/steering/product.md already exists; --steering will not overwrite it
```

The feature name `product`, `tech`, or `structure` would make the choices
file collide with a foundation name:

```text
error: feature name 'product' would overwrite a foundation steering file; rename the feature or skip --steering
```

That error is raised when a choices file would be written under that name.
It is checked before any write.

`--steering` when the feature folder is not `.kiro/specs/<name>`:

```text
error: feature folder is not .kiro/specs/<name>; --steering has nowhere documented to write
```

### Hooks

Hook files are `.kiro/hooks/<name>.json` with `"version": "v1"` and a
`hooks` array. Triggers include `PreTaskExecution` and `PostTaskExecution`.
A Spekkr manifest has no trigger, matcher, or action. This codec writes no
hook. It does not add a hook to protect the spec files, because that
behavior is not in the manifest.

The IDE can create `product.md`, `tech.md`, and `structure.md` from
Generate Steering Docs. Whether that button overwrites existing files is
not stated. The README tells the person not to run it over steering this
codec wrote.

## What Kiro rewrites

Checked 20 November 2026. Details and gaps are in "Sources" and
"Unverified".

Documented updates:

- Creating a feature spec generates `requirements.md`, `design.md`, and
  `tasks.md`. Requirements-first, design-first, and Quick Spec all produce
  those three files. Quick Spec does it in one pass, with no approval
  between phases.
- Asking Kiro to update requirements or design revises those files. Sync
  Files on `tasks.md` adds tasks or marks tasks complete.
- Task execution updates tasks as in progress or completed. Run all Tasks
  runs incomplete tasks that are marked required, using a dependency graph
  built from `tasks.md`.
- `#spec` and `#spec:<name>` include `requirements.md`, `design.md`, and
  `tasks.md` in the chat. `<name>` is the directory name under
  `.kiro/specs/`.

The docs do not describe a step that rewrites `spekkr.json`,
`spekkr.inputs.json`, `BUILD.md`, or any other sidecar file. They also do
not promise those files will be left in place. The warning stands either
way.

No spec index file, and no `spec.json`, appears in the pages checked. The
codec does not write one. The directory name is the spec name those pages
use.

The first stderr line of every successful `to-kiro`, with or without
`--steering`, is exactly:

```text
note: do not let Kiro regenerate requirements.md, design.md or tasks.md; updating the spec, Sync Files and task execution replace those files. Other files in the feature folder are not part of the spec Kiro documents.
```

`to-spekkr` does not print that line. A filled-in manifest prints its own
notes, below.

## Filled-in manifest

When the feature folder has no `spekkr.json`, the script writes one. The
text it summarizes is `requirements.md`, which is saved as `spec.md`. Key
order is `spekkr`, `id`, `name`, `summary`, `version`, `author`,
`targets`, `customize`, `files`, `needs`, `demo`, `safety`, `lineage`,
`changelog`. Indent is two spaces. Non-ASCII is written as UTF-8 rather
than escaped. Line endings are `\n`. The file ends with a newline. Empty
objects are `{}`.

| Field | Value |
| --- | --- |
| `id` | `<author>/<slug>`. Slug: lowercase the folder name, remove one leading run of digits followed by a hyphen, turn every other character that is not an ASCII letter, digit, or hyphen into a hyphen, then strip hyphens at the ends. A slug that is not a valid id part is an error. |
| `author.id`, `author.name` | the `--author` string. It is a Spekkr username: it starts with a lowercase letter or digit, and the rest is lowercase letters, digits, and hyphens. |
| `name` | text after `# Feature Specification:` in `requirements.md`; else the first `# ` heading; else the slug. A `##` heading is not a title. |
| `summary` | the first plain paragraph after that title. Headings, lists, quotes, tables, and fences are skipped. Whitespace collapses to single spaces. Longer than 140 characters, it is cut at the last space that keeps it within 140, or at 140 when the first 140 characters contain no space. With no paragraph, the name. |
| `version` | `0.1.0` |
| `changelog` | one entry, version `0.1.0`, note `Converted from Kiro.`, date from `--date` or `1970-01-01`. The date is a real calendar date, leap days included. |
| `targets.platforms` | `--platforms` split on commas and trimmed, default `["web"]`. Each value is one of `web`, `mobile`, `desktop`, `backend`, `cli`, listed once. |
| `files` | `spec.md`, `design.md`, then `tasks.md` if that file exists in the feature folder, then every other output file sorted by relative path, each as `{"path": ...}`. `requirements.md` is not listed; it became `spec.md`. |
| `customize`, `safety`, `needs`, `demo`, `lineage` | empty objects |

A plain paragraph line is non-empty and does not start, after stripping,
with `#`, `>`, `|`, `` ``` ``, `- `, `* `, or `+ `, and is not
`<digits>. `.

Stderr then carries these `note:` lines, in this order, each prefixed with
`note: `:

- `filled in spekkr.json for <author>/<slug> because the feature folder has no spekkr.json`
- `summary: <summary> (review it before publishing)`
- `summary was cut to 140 characters at a word boundary` when it was cut
- `requirements.md is not UTF-8; the name and summary fell back` when the file is not UTF-8. The name and summary are then the slug.
- `name fell back to the folder slug <slug>` when the file is UTF-8 and has no usable `# ` title
- `author.name is <author>, the same as author.id`
- `version is 0.1.0; customize and safety are empty`
- `changelog date is 1970-01-01 because --date was not given` when `--date` was omitted

## Reading and writing

The source is walked with `os.walk(..., onerror=...)`, directories and
files in sorted order. A directory that cannot be listed raises, so it is
never silently skipped. A symlink, or anything that is not a regular file
or directory, is refused. Empty directories are kept.

The output is written to a temporary sibling folder named
`.<name>.spekkr-tmp-<pid>` and renamed into place. The temporary folder is
removed if anything fails. An output folder that exists and is empty is
replaced. An output folder that exists and holds an entry is refused.
All checks, including steering conflicts, run before the first write.

`to-kiro` requires `spekkr.json`, `spec.md`, and `design.md`. `tasks.md`
is optional. `to-spekkr` requires `requirements.md` and `design.md`.

A spec id is `username/name`, one slash, each part a valid username as
defined for `--author`.

## Errors

Each error is one stderr line starting with `error: `, exit 1, nothing on
stdout, and no output folder. Steering files are included in "no output".

| Situation | Message after `error: ` |
| --- | --- |
| Spekkr folder has `requirements.md` | `this Spekkr spec already has requirements.md; to-kiro will not overwrite it` |
| Spekkr `design.md` starts with the begin marker | `design.md already starts with <!-- spekkr:safety:begin -->; to-kiro will not add the safety block again` |
| Feature folder has `spec.md` | `feature folder already has spec.md; to-spekkr will not overwrite it` |
| Feature `design.md` starts with the begin marker but not the full block | `design.md starts with <!-- spekkr:safety:begin --> but is not the safety block; to-spekkr will not convert it` |
| No `spekkr.json` and no `--author` | `--author is required when the feature folder has no spekkr.json` |
| A directory or file cannot be read | `cannot read <path>: <reason>` |
| Spekkr folder has no `spekkr.json` | `no spekkr.json in the Spekkr spec folder` |
| Spekkr folder has no `spec.md` | `Spekkr spec has no spec.md to convert into requirements.md` |
| Spekkr folder has no `design.md` | `Spekkr spec has no design.md` |
| Feature folder has no `requirements.md` | `feature folder has no requirements.md to convert into spec.md` |
| Feature folder has no `design.md` | `feature folder has no design.md` |
| `spekkr.json` is not a JSON object | `spekkr.json is not UTF-8 JSON: ...` or `spekkr.json must be a JSON object` |
| `spekkr.json` has a bad id | `spekkr.json id must look like username/name, got ...` |
| Bad `--author` | `--author must be a Spekkr username of lowercase letters, digits and hyphens, got '<value>'` |
| Bad `--date` | `--date must be a calendar date like 2026-01-01, got '<value>'` |
| Bad `--platforms` | a line naming the flag, the value, and the allowed list `web, mobile, desktop, backend, cli` |
| Folder name gives no valid slug | `folder name '<name>' does not make a Spekkr id` |
| Source is not a folder | `not a folder: <path>` |
| A symlink or special file | `refusing to follow a symlink: <path>` or `not a regular file: <path>` |
| Output exists and is not empty | `output folder <path> already exists and is not empty` |
| Output is inside the input | `output folder <dest> is inside the input folder <source>; pass --dir outside it` |
| `--steering` and the feature path is not `.kiro/specs/<name>` | `feature folder is not .kiro/specs/<name>; --steering has nowhere documented to write` |
| Steering file already exists | `<path> already exists; --steering will not overwrite it` |
| Choices file would be named `product`, `tech`, or `structure` | `feature name '<name>' would overwrite a foundation steering file; rename the feature or skip --steering` |

The collision fixtures' `error.txt` files are the first, second, and third
messages, each as a full stderr line ending in a newline.

## Checker

`tests/check.py` runs a codec as a subprocess and imports `SAFETY_BLOCK`,
`SAFETY_BEGIN`, `product_markdown`, `tech_markdown`, and
`choices_markdown`. The optional argument is another codec with the same
commands and the same helpers.

Fixtures are synthetic, committed under `tests/fixtures/`. Each case has a
one-line `README`. The checker fails if any required case directory is
missing.

Spekkr cases (`tests/fixtures/spekkr/<case>/`): `basic`, `requirements`,
`crlf`, `no-final-newline`, `unicode`, `extra-files`, `large-file`,
`odd-manifest`, `with-build`, `inputs-present`, `inputs-absent`,
`no-tasks`, `rich-manifest`, `collision-requirements`,
`collision-safety-marker`.

`source/` is converted with `to-kiro` and back with `to-spekkr`. The round
trip equals `source/`. The feature folder equals `expected/`. `design.md`
in the feature folder starts with `SAFETY_BLOCK` and the remainder equals
the source `design.md`. `requirements.md` equals the source `spec.md`.
`to-kiro` stderr is exactly the warning line. `to-spekkr` stderr is empty.
A case with `error.txt` fails with that stderr and writes nothing.

`basic` uses the steering fields in the worked example, including id
`example-user/basic`. `rich-manifest` uses id `example-user/pebble-jar`
and the worked-example fields. `inputs-absent` has a non-empty `customize`
and no `spekkr.inputs.json`. `with-build` has a `BUILD.md`. `large-file`
has a file over 60 KB. `extra-files` has a PNG under `shots/` and a nested
text file. `requirements` has `### R1.` and `**Accept when:**` lines.

Hand-written cases (`tests/fixtures/handwritten/<case>/`): `plain`,
`ears`, `long-summary`, `no-heading`, `no-tasks`, `numbered`, `odd-name`,
`unicode-title`, `with-docs`, `prefixed-design`, `collision-spec`.

The source is placed under the name in `folder-name`, or the case name.
Conversion uses `--author example-user --date 2026-01-01`. The checker
compares the fixed point, the stability of `to-spekkr`, and the goldens
`expected-spekkr/` and `expected-fixed/`. Source `requirements.md` equals
Spekkr `spec.md`. Source `design.md` equals Spekkr `design.md` after
removing `SAFETY_BLOCK` when the source starts with that block.
`prefixed-design` starts with the full block. `ears` has `##` headings,
`WHEN` / `THE SYSTEM SHALL` lines, and no `# ` heading, and its manifest
name is the slug. `plain` keeps an FR line and a `- [ ]` task.
`collision-spec` contains both `requirements.md` and `spec.md`.

Flag checks:

- Default `to-kiro` writes `.kiro/specs/basic` and no `.kiro/steering`.
- `--dir .kiro/specs/003-basic` writes that folder. stderr includes the
  warning and does not include the "not .kiro/specs" note.
- `--dir features/basic` writes the folder, stderr includes the "not
  .kiro/specs" note, and `--steering` with that `--dir` is the steering
  path error and leaves no folder.
- `--steering` on `basic` writes the `basic` `product.md` example and the
  notes for a missing stack, a missing structure file, a missing inputs
  file, and safety. It writes no `tech.md`, no choices file, no
  `structure.md`, and no `.kiro/hooks`.
- `--steering` on `rich-manifest` writes the three worked examples. The
  helpers return those same bytes.
- `--steering` when `.kiro/steering/product.md` already exists writes
  nothing.
- A feature named `product` that has a qualifying inputs file hits the
  foundation-name error and writes nothing.
- `inputs-absent` with `--steering` does not write a choices file. The
  note says the inputs file is absent. `customize` is not copied.
- Default `to-spekkr` of `003-example` writes `./example`.
- Omitting `--date` writes `1970-01-01` and the default-date note.
- `--platforms cli, backend` writes `["cli", "backend"]`.
- `.` and `..` use the directory name, as in R6.
- An unreadable directory aborts with `error: cannot read ` and writes
  nothing. Skipped when the checker is root.
- A `design.md` that starts with `SAFETY_BEGIN` but not `SAFETY_BLOCK` makes
  `to-spekkr` exit non-zero, print `error: design.md starts with <!-- spekkr:safety:begin --> but is not the safety block; to-spekkr will not convert it`, and write nothing. That input is outside the R6 fixed point.
- `product_markdown` on a manifest with no `summary` omits the Summary
  line.
- The repository README contains `SAFETY_BLOCK` when the checker is the
  one in this repository, not when it is pointed at another codec.

Every hand-written fixture's golden `spekkr.json` is sent to Spekkr's
`check_spec` and must pass.

The success line is `Kiro codec checks passed (tests/fixtures).`

## Sources

Pages read on 20 November 2026. "Updated" is the date printed on the page
when it had one.

| Fact used above | Page |
| --- | --- |
| A spec is `requirements.md` or `bugfix.md`, plus `design.md` and `tasks.md`. Mobile shows the three markdown files. Task execution updates tasks as in progress or completed and runs independent tasks in waves. | [Specs](https://kiro.dev/docs/specs/), updated 12 November 2026 |
| Specs are project scope `.kiro/specs/`. Steering is `.kiro/steering/`. Hooks are `.kiro/hooks/`. | [Configuration](https://kiro.dev/docs/configuration/) |
| Feature specs are requirements-first or design-first. Requirements use EARS: `WHEN` / `THE SYSTEM SHALL`. `design.md` is the technical design. | [Feature specs](https://kiro.dev/docs/specs/feature-specs/), updated 4 August 2026 |
| Generated requirements use `##` / `###` headings and EARS lines. Tasks are discrete, with outcomes, dependencies, and optional or required status. The markdown of `tasks.md` is not shown. | [Requirements-first](https://kiro.dev/docs/specs/feature-specs/requirements-first/) |
| Design-first generates `design.md`, then requirements, then the same kind of tasks. | [Design-first](https://kiro.dev/docs/specs/feature-specs/tech-design-first/) |
| Quick Spec writes the same three files under `.kiro/specs/` with no approval between phases. Asking Kiro to refine requirements, then Sync Files, regenerates tasks. | [Quick spec](https://kiro.dev/docs/specs/quick-spec/) |
| Iteration asks Kiro to revise `design.md` or regenerate requirements. Sync Files creates tasks or marks them complete. Run all Tasks runs incomplete required tasks and builds a dependency graph. `#spec` and `#spec:<name>` load the three files. The tree `.kiro/specs/user-authentication/` is the documented layout. Asking Kiro to generate a spec from an existing file writes new requirement and design docs. | [Best practices](https://kiro.dev/docs/specs/best-practices/), updated 25 September 2026 |
| Workspace steering is `.kiro/steering/`. Foundation files are `product.md`, `tech.md`, and `structure.md`, included by default. Generate Steering Docs creates those three in the IDE. Front matter sets `inclusion` to `always`, `fileMatch`, `manual`, or `auto`. Manual files are referenced as `#<file-name>`. CLI V3 implements all four modes. V1 and V2 load `always` and exclude `manual` from automatic loading. Custom agents need `resources`. `#[[file:<path>]]` includes a workspace file. Secrets do not belong in steering. | [Steering](https://kiro.dev/docs/steering/) |
| A hook file is `.kiro/hooks/<name>.json`, `"version": "v1"`, with a `hooks` array, a PascalCase trigger, and a command or agent action. | [Hooks](https://kiro.dev/docs/hooks/), updated 12 November 2026 |
| `PreTaskExecution` runs before a spec task. `PostTaskExecution` runs after. | [Hook triggers](https://kiro.dev/docs/hooks/types/) |

## Unverified

The codec's behavior on each gap is already fixed above. These are the
points the pages do not settle.

1. `tasks.md` has no published markdown schema. The docs name outcomes,
   dependencies, required and optional tasks, and status updates. They do
   not show checkboxes, ids, or a status token. The codec copies the file.
   After Run all Tasks, Sync Files, or a task run, a byte-for-byte round
   trip of `tasks.md` will not hold, because those actions update the file.
2. The dependency-graph rules used for parallel tasks are not published.
3. Nothing in the docs says Kiro deletes unknown files in a spec folder.
   Nothing says it preserves them. Sidecar survival is not a guarantee.
4. Nothing in the docs says Generate Steering Docs overwrites an existing
   `product.md` or `tech.md`. Nothing says it keeps them. The README tells
   the person not to run that action over these files.
5. Nothing in the docs says a `requirements.md` that is not EARS is
   rejected, and nothing says task execution requires EARS. Direct edits
   are documented. The codec does not convert to EARS.
6. No page checked describes a `spec.json` or other registry. That absence
   is not proof the product has none. The codec writes no registry file.
7. Whether a directory dropped into `.kiro/specs/` by another tool appears
   in the specs list without a Kiro session creating it is not a documented
   step. The pages identify a feature by that path and by `#spec:<name>`.
8. Whether `#<file-name>` loads a `manual` steering file on CLI V1 or V2
   is not stated. V3 does. The file is still written.
9. The docs do not say that opening a converted spec, with no further
   request, rewrites it. They do say that update requests, Sync Files,
   Quick Spec, and task execution change the three files.
