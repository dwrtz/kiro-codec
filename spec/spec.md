# Kiro codec

## What this builds

A converter that turns a Spekkr spec folder into a
[Kiro](https://kiro.dev/docs/specs/) feature folder and back, with no loss
in either direction. It is one Python 3.11+ file, standard library only,
with the subcommands `to-kiro` and `to-spekkr`, plus an agent skill that
says when to run it.

The conversion runs on the person's machine. Spekkr's `pull_spec`,
`check_spec` and `publish_spec` keep reading and writing Spekkr folders.
The codec sits between them and a Kiro project.

This version is the spec. It does not contain a reference script, fixtures,
or a skill. `tasks.md` is the order for building those. `design.md` holds
the bytes, the steering rules, the error strings, the Kiro citations, and
the behavior the Kiro docs leave unspecified.

Kiro facts below were checked on 20 November 2026 against the pages listed
in `design.md`. Where a page does not specify a format, the codec copies
bytes and says so. It does not invent a `tasks.md` schema, a spec index, or
a hook.

`customize` is empty. This spec has no settings, options, or swaps.

### R1. Feature folder

`to-kiro` reads a Spekkr folder and writes a Kiro feature folder. The
default path is `.kiro/specs/<name>` under the current directory, where
`<name>` is the part of the spec id after the slash. `--dir` chooses
another path. The script prints the folder it wrote on stdout. The input
folder is not modified.

Kiro's feature specs live at `.kiro/specs/<name>/`
([specs](https://kiro.dev/docs/specs/),
[best practices](https://kiro.dev/docs/specs/best-practices/),
[configuration](https://kiro.dev/docs/configuration/)). The three files
Kiro documents there are `requirements.md`, `design.md`, and `tasks.md`.

**Accept when:** `to-kiro` of `tests/fixtures/spekkr/basic/source` with no
`--dir`, run from an empty directory, writes `.kiro/specs/basic/` equal to
that case's `expected/` and does not write `.kiro/steering/` or
`.kiro/hooks/`.

### R2. Byte-for-byte sidecar

`tasks.md` and every file other than `spec.md` and `design.md` keep their
relative paths and their bytes. `spekkr.json` is copied, never
re-serialized. `spekkr.inputs.json` and `BUILD.md` are copied when present
and omitted when absent. Those files, plus anything else in the Spekkr
folder (`reference/`, `shots/`, and the rest), are the sidecar. They sit
inside `.kiro/specs/<name>/`, next to the three spec files, so a mention of
`spekkr.inputs.json` still resolves.

Kiro's documented spec is those three files. The sidecar is how the codec
keeps the manifest, the recorded choices, and `BUILD.md`, which Kiro has
no field for.

**Accept when:** `to-spekkr(to-kiro(x))` is byte-identical to `x`, and the
feature folder equals the case's `expected/` folder, for every Spekkr
fixture under `tests/fixtures/spekkr/` that has no `error.txt`.

### R3. Safety block

`design.md` is copied with the safety block from `design.md` of this spec
at offset 0. The block is always the same bytes, including one blank line
after `<!-- spekkr:safety:end -->`. `to-spekkr` removes exactly those bytes
when `design.md` starts with them. A `design.md` that does not start with
`<!-- spekkr:safety:begin -->` is left untouched. One that starts with the
begin marker but not the full block is an error, on both commands.

The block tells the agent to show the person the commands and secrets
under `safety`, to treat `spekkr.inputs.json` as requirements, and not to
regenerate `requirements.md`, `design.md`, or `tasks.md`.

**Accept when:** for every Spekkr fixture, the feature `design.md` starts
with that block and the bytes after it equal the fixture's `design.md`,
and the reverse conversion restores `design.md` byte for byte.

### R4. requirements.md

`spec.md` is written as `requirements.md`, byte for byte. The codec does
not rewrite it into EARS notation. There is no stub file: Kiro's design
file is already `design.md`, so the design keeps that name. A Spekkr folder
that already contains `requirements.md` is refused, because that file would
be overwritten by the renamed `spec.md`.

**Accept when:** every successful `to-kiro` writes `requirements.md` equal
to the source `spec.md`. The `requirements` fixture keeps its `### R1.`
headings and `**Accept when:**` lines. The `collision-requirements` fixture
exits non-zero and writes nothing.

### R5. Steering

`--steering` writes workspace steering under `.kiro/steering/` of the Kiro
project. It is optional. Without the flag, no steering file is written.

Steering is outside the feature folder and is not part of the round trip.
`to-spekkr` does not read it.

The mapping is only what the manifest actually contains:

- `product.md` gets the manifest `name`, `summary`, `kind` when that is a
  non-empty string, and `targets.platforms` when that is a non-empty list
  of strings. It does not invent target users, key features, or business
  objectives.
- `tech.md` is written only when `targets.stack` is a non-empty list of
  strings. The list is copied. Nothing else is added.
- `structure.md` is not written. The manifest `files` list is the spec's
  own files, not the project's layout.
- A choices file `<feature>.md` with `inclusion: manual` is written only
  when `spekkr.inputs.json` is a JSON object of strings, booleans, and
  integers. `customize` defaults are not treated as recorded choices.
- Commands and secrets under `safety` are not copied into steering.
- No file under `.kiro/hooks/` is written.

The flag refuses when the feature folder is not `.kiro/specs/<name>/`, and
refuses to overwrite an existing steering file. Exact bytes, front matter,
and notes are in `design.md`.

**Accept when:** `to-kiro` of the `basic` fixture with no `--steering`
leaves `.kiro/steering/` absent. The same command with `--steering` writes
the `product.md` example in `design.md` and does not write `tech.md`,
`structure.md`, a choices file, or a hook. `to-kiro --steering` of
`rich-manifest` writes the three steering examples in `design.md` and no
`structure.md`. When `.kiro/steering/product.md` already exists and the
feature destination does not, `--steering` exits non-zero and does not
create the feature folder. `to-spekkr(to-kiro(rich-manifest))` does not
depend on the steering files and still matches the source.

### R6. Hand-written fixed point

`to-spekkr` of a feature folder that has no `spekkr.json` fills a manifest
the way `design.md` describes. `--author` is required. `--date` defaults to
`1970-01-01`, never the current day. `--platforms` defaults to `web`. The
same input and the same flags always produce the same bytes.

The slug comes from the name of the directory the source path refers to,
after the path is resolved, so `.` and `..` give that directory's own name.
The default output folder is `./<slug>`.

A hand-written `requirements.md` becomes `spec.md` byte for byte. A
hand-written `design.md` that does not start with
`<!-- spekkr:safety:begin -->` becomes Spekkr `design.md` byte for byte.
One that starts with the full block loses exactly that block. One that
starts with the begin marker but not the full block is refused, and this
requirement does not apply to it.

**Accept when:** for every hand-written fixture under
`tests/fixtures/handwritten/` that has no `error.txt`, with
`--author example-user --date 2026-01-01`:

- `to-kiro(to-spekkr(k))` equals `expected-fixed/` and is byte-identical to
  `to-kiro(to-spekkr(to-kiro(to-spekkr(k))))`;
- `to-spekkr(k)` equals `expected-spekkr/` and is byte-identical to
  `to-spekkr` of that fixed point;
- `requirements.md` round-trips through `spec.md` byte for byte;
- `design.md` in the Spekkr folder is the source `design.md` with the
  safety block removed when the source starts with it.

The source folder is named by the case's `folder-name` file when it has
one. Run from inside the `numbered` fixture placed as `003-example`,
`to-spekkr . --dir ../from-dot` writes `expected-spekkr/`, and
`to-spekkr ..` from an empty child folder writes the id
`example-user/example`. With no `--dir`, the same folder converts to
`./example`.

### R7. Filled-in manifest

The filled-in `spekkr.json` uses the key order, indent, and field rules in
`design.md`. `author.id` and `author.name` are both `--author`. The summary
is the first plain paragraph after the title in `requirements.md`, cut to
140 characters at a word boundary. `files` lists `spec.md`, `design.md`,
`tasks.md` when present, then every other file sorted by path. `customize`
and `safety` are empty. Notes on stderr include the summary, so the person
can fix it before publishing. The file passes `check_spec`.

Kiro's published requirements example uses `##` sections and no `# ` title
([requirements-first](https://kiro.dev/docs/specs/feature-specs/requirements-first/)).
The codec does not promote a `##` heading to the manifest name. With no
`# ` heading, the name is the folder slug. The `ears` fixture is that shape.

**Accept when:** every hand-written fixture's golden `spekkr.json` passes
`check_spec`, the `ears` manifest name is the folder slug, the
`long-summary` summary is at most 140 characters and ends on the word
`pebble`, omitting `--date` writes `1970-01-01` and says so on stderr, and
`--platforms "cli, backend"` writes `["cli", "backend"]`.

### R8. Collisions

`to-kiro` refuses a Spekkr spec that already has `requirements.md`, and a
`design.md` that starts with `<!-- spekkr:safety:begin -->`. `to-spekkr`
refuses a feature folder that already has `spec.md`. It also refuses a
`design.md` that starts with `<!-- spekkr:safety:begin -->` but is not the
full safety block. Each failure is a non-zero exit, one `error:` line on
stderr, and no output folder.

**Accept when:** `collision-requirements`, `collision-safety-marker`, and
`collision-spec` exit non-zero, their stderr equals the case's `error.txt`,
and they leave no output folder. A feature `design.md` that starts with the
begin marker but not the full block fails `to-spekkr` with the error in
`design.md` and leaves no output folder.

### R9. No reformatting

Requirement ids, "Accept when" lines, EARS lines, FR/SC lines, and task
text are copied as written. The codec does not renumber them, does not
convert prose into EARS, and does not add or remove checkboxes.

Kiro's docs describe `tasks.md` as discrete tasks with outcomes,
dependencies, and required or optional status. They do not publish the
markdown schema. Copying bytes is the conservative choice. `design.md`
records that gap.

**Accept when:** the `requirements` fixture keeps its headings and
**Accept when** lines, the `ears` fixture keeps its `WHEN` / `THE SYSTEM
SHALL` lines unchanged, and the `plain` fixture keeps its FR/SC lines and
its `- [ ]` task.

### R10. Edge bytes

CRLF line endings, a missing trailing newline, non-ASCII UTF-8, binary
files, and a file over 60 KB are copied as bytes. A manifest with unusual
spacing is copied as bytes.

**Accept when:** the `crlf`, `no-final-newline`, `unicode`, `extra-files`,
`large-file`, and `odd-manifest` fixtures round-trip byte for byte,
including `spekkr.json` and the PNG files under `shots/`.

### R11. All or nothing

A conversion either writes the whole output folder or writes nothing. A
directory in the source that cannot be listed, or a file that cannot be
read, stops the command with `error: cannot read <path>: <reason>` before
anything is written. It is never skipped. Symlinks and other non-regular
files are refused. An output folder that already holds files, or one inside
the input folder, is refused. The tree is written to a temporary sibling
folder and renamed into place. `--steering` checks for existing steering
files before that write, and a conflict writes neither the feature folder
nor a steering file.

**Accept when:** `to-kiro` of a copy of the `basic` fixture with an added
`reference/` directory that cannot be listed exits non-zero, prints a
stderr line starting with `error: cannot read `, prints nothing on stdout,
and leaves no output folder. The checker skips this case when it runs as
root, because root can list any directory.

### R12. Warning

Every successful `to-kiro` prints one `note:` line on stderr telling the
person not to let Kiro regenerate `requirements.md`, `design.md`, or
`tasks.md`. The same warning is inside the safety block, which Kiro loads
when a chat includes the spec.

What the docs say Kiro will rewrite, and what they do not mention, is
listed in `design.md`. The repository README quotes the safety block and
states that warning in the same words.

**Accept when:** every successful `to-kiro` in the checker writes that note
as its first stderr line, and the repository `README.md` contains the
safety block bytes.

### R13. Agent skill

`skills/kiro-codec/SKILL.md` tells an agent when and how to run the codec:
pulling a Spekkr spec into `.kiro/specs/<name>/`, when to pass
`--steering`, turning a Kiro feature into a Spekkr spec for `check_spec`
and `publish_spec`, and checking a self-built codec. It tells the agent to
show the person the stderr notes, to keep requirement text and task text as
written, and not to ask Kiro to regenerate the three converted files or to
run Generate Steering Docs over files this codec wrote.

**Accept when:** the skill has `name` and `description` front matter, and
the `to-kiro` command it gives, run on
`tests/fixtures/spekkr/basic/source` from an empty directory, writes
`.kiro/specs/basic/`.

### R14. Checker and CI

`tests/check.py` runs the round trip, the hand-written fixed point, the
collision cases, the steering examples, and the flag checks in `design.md`.
GitHub Actions runs it on Python 3.11 and 3.12.

**Accept when:** `python3 tests/check.py` exits 0 on both versions, and a
missing required fixture directory fails the checker.
