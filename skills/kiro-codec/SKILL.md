---
name: kiro-codec
description: Convert a Spekkr spec folder to a Kiro feature folder and back, byte for byte. Use when pulling a Spekkr spec into .kiro/specs, turning a Kiro feature into a Spekkr spec, or checking a self-built Kiro codec.
---

# Kiro codec

`kiro_codec.py` turns a Spekkr spec folder into a Kiro feature folder, and the feature folder back into a Spekkr spec folder. The conversion is byte for byte. Python 3.11 or newer is enough. The standard library is the only dependency.

Run it from the repository root, or pass absolute paths. The script prints the folder it wrote. Notes go to stderr. Show those notes to the person. A problem is one `error:` line and a non-zero exit, and the input folder is left as it was.

## Spekkr folder to a Kiro feature

From an empty directory, this command writes `.kiro/specs/basic/` and does not write `.kiro/steering/`:

```sh
python3 kiro_codec.py to-kiro tests/fixtures/spekkr/basic/source
```

Use the same command with the Spekkr folder you pulled. The default destination is `.kiro/specs/<name>/`, where `<name>` is the part of the spec id after the slash. `--dir` writes somewhere else.

```sh
python3 kiro_codec.py to-kiro path/to/spekkr-folder --dir .kiro/specs/<name>
```

`spec.md` becomes `requirements.md`. `design.md` gains the safety block at the start. Every other file is copied, including `tasks.md`, `spekkr.json`, `spekkr.inputs.json`, and `BUILD.md`.

Keep requirement text and task text as written. Do not renumber requirements, do not turn prose into EARS, and do not add or remove checkboxes.

Do not ask Kiro to regenerate `requirements.md`, `design.md`, or `tasks.md`. Updating the spec, Sync Files, and task execution replace those files. Other files in the feature folder are not part of the spec Kiro documents.

## Steering

Pass `--steering` only when the person wants workspace steering and the feature folder is `.kiro/specs/<name>/`. The files are written to `.kiro/steering/`, outside the feature folder. They are not part of the round trip.

```sh
python3 kiro_codec.py to-kiro path/to/spekkr-folder --dir .kiro/specs/<name> --steering
```

The command refuses to overwrite an existing steering file. If it refuses, leave the existing file alone. Do not ask Kiro to run Generate Steering Docs over `product.md` or `tech.md` this codec wrote. The docs do not say whether that action overwrites those files.

## Kiro feature to a Spekkr folder

```sh
python3 kiro_codec.py to-spekkr path/to/feature-folder --dir path/to/spekkr-folder --author <username> --date YYYY-MM-DD
```

`--author` is required when the feature folder has no `spekkr.json`. `--date` defaults to `1970-01-01`, never the current day. `--platforms` defaults to `web`.

When the script fills in `spekkr.json`, stderr includes the summary. Show it to the person and let them fix it before publishing. Then, if they ask, send that manifest to Spekkr's `check_spec`. Publish only when they ask.

`requirements.md` becomes `spec.md`. A `design.md` that starts with the full safety block loses that block and nothing else. A `design.md` that starts with the begin marker but is not the full block is refused.

## Check a codec you built

```sh
python3 tests/check.py
python3 tests/check.py path/to/your_codec.py
```

The second command runs this repository's fixtures against another script with the same commands and the same helpers.
