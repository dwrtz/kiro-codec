# Tasks

Work in this order. Finish each check before the next task. This folder is
the spec. It has no reference implementation. Build the codec in the project
root you were asked to build it in. In the kiro-codec repository, that root
is the parent of the `spec/` directory. Run the commands from that root.

1. **Codec.** Write one Python 3.11+ file, `kiro_codec.py`, with no
   dependencies beyond the standard library. The subcommands are `to-kiro`
   and `to-spekkr`. The flags are `--dir`, `--steering`, `--author`,
   `--date` and `--platforms`. Define `SAFETY_BLOCK` and `SAFETY_BEGIN` as
   the bytes in `design.md`, and the steering helpers that `design.md`
   names. Follow `spec.md` (R1-R12) and `design.md`. There is no design
   stub.

   **Accept when:** `python3 kiro_codec.py --help` exits 0 and lists both
   subcommands.

2. **Checker and fixtures.** Add `tests/check.py` and synthetic fixtures
   under `tests/fixtures/`, the cases `design.md` lists. A pebble jar and a
   lantern are enough. Do not copy a catalog spec. `tests/fixtures/**` is
   marked `-text` in `.gitattributes` so Git does not rewrite CRLF or a
   missing trailing newline. `.gitignore` ignores `__pycache__/` and
   `*.py[cod]`. A `Makefile` target `check` runs `python3 tests/check.py`.

   **Accept when:** `python3 tests/check.py` exits 0 and prints
   `Kiro codec checks passed (tests/fixtures).` For a codec of your own,
   `python3 tests/check.py path/to/your_codec.py` does the same.
   `python3 tests/check.py` also passes the golden `spekkr.json` files
   from the hand-written fixtures through Spekkr's `check_spec`.

3. **Skill, README, CI.** Add `skills/kiro-codec/SKILL.md` as an agent
   skill named `kiro-codec` (R13). Rewrite the repository `README.md` so it
   quotes `SAFETY_BLOCK`, cites the Kiro pages in `design.md`, and tells
   the person not to let Kiro regenerate the converted files (R12). Add
   `.github/workflows/ci.yml` that runs `python3 tests/check.py` on Python
   3.11 and 3.12 for pushes to `main` and for pull requests, with
   `contents: read` (R14).

   **Accept when:** the skill has `name` and `description` front matter.
   From an empty directory, the skill's `to-kiro` command on
   `tests/fixtures/spekkr/basic/source` writes `.kiro/specs/basic/` and
   does not write `.kiro/steering/`. The README contains the safety block
   bytes. The workflow file names both Python versions.
