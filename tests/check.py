#!/usr/bin/env python3
"""Round-trip the Kiro codec and compare it with the golden fixtures.

From this repository:

    python3 tests/check.py
    python3 tests/check.py path/to/your_codec.py

The optional argument is a self-built codec. It has to accept the same
commands as kiro_codec.py, and the module has to define SAFETY_BLOCK,
SAFETY_BEGIN, product_markdown, tech_markdown, and choices_markdown.

Spekkr's check_spec needs a Spekkr session, which GitHub Actions does not
have. The checker validates each hand-written golden spekkr.json against
the manifest shape that tool accepts. A session can still send those files
to check_spec before anyone publishes.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

SPEKKR_CASES = (
    "basic",
    "requirements",
    "crlf",
    "no-final-newline",
    "unicode",
    "extra-files",
    "large-file",
    "odd-manifest",
    "with-build",
    "inputs-present",
    "inputs-absent",
    "no-tasks",
    "rich-manifest",
    "collision-requirements",
    "collision-safety-marker",
)
HAND_CASES = (
    "plain",
    "ears",
    "long-summary",
    "no-heading",
    "no-tasks",
    "numbered",
    "odd-name",
    "unicode-title",
    "with-docs",
    "prefixed-design",
    "collision-spec",
)
PLATFORMS = ("web", "mobile", "desktop", "backend", "cli")


def main() -> int:
    codec_path, fixtures, custom = locate()
    codec = load_codec(codec_path)
    failures: list[str] = []
    require_cases(fixtures, failures)
    check_spekkr(codec_path, codec, fixtures / "spekkr", failures)
    check_handwritten(codec_path, codec, fixtures / "handwritten", failures)
    check_flags(codec_path, codec, fixtures, failures)
    check_manifests(fixtures / "handwritten", failures)
    if not custom:
        check_documented(codec, failures)
    if failures:
        print(f"{len(failures)} Kiro codec check(s) failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print("Kiro codec checks passed (tests/fixtures).")
    return 0


def locate() -> tuple[Path, Path, bool]:
    """The codec, the fixtures, and whether the caller named another codec."""
    if len(sys.argv) > 2:
        raise SystemExit("usage: python3 tests/check.py [CODEC.py]")
    override = Path(sys.argv[1]) if len(sys.argv) == 2 else None
    codec = HERE.parent / "kiro_codec.py"
    fixtures = HERE / "fixtures"
    custom = override is not None
    if custom:
        codec = override
    # Flag checks run the script with a different cwd. A relative path would
    # then be looked up inside that temporary directory.
    codec = codec.resolve()
    if not codec.is_file():
        raise SystemExit(f"codec not found: {codec}")
    if not fixtures.is_dir():
        raise SystemExit(f"fixtures not found: {fixtures}")
    return codec, fixtures, custom


def load_codec(path: Path):
    spec = importlib.util.spec_from_file_location("kiro_codec_under_test", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in (
        "SAFETY_BLOCK",
        "SAFETY_BEGIN",
        "REGEN_NOTE",
        "product_markdown",
        "tech_markdown",
        "choices_markdown",
    ):
        if not hasattr(module, name):
            raise SystemExit(f"{path} does not define {name}")
    return module


def require_cases(fixtures: Path, failures: list[str]) -> None:
    for group, names in (("spekkr", SPEKKR_CASES), ("handwritten", HAND_CASES)):
        root = fixtures / group
        for name in names:
            case = root / name
            if not case.is_dir():
                failures.append(f"missing required fixture directory: {group}/{name}")
                continue
            readme = case / "README"
            if not readme.is_file():
                failures.append(f"{group}/{name}: README is missing")
            elif readme.read_text(encoding="utf-8").count("\n") != 1:
                failures.append(f"{group}/{name}: README is not one line")


def warning_line(codec) -> str:
    return f"note: {codec.REGEN_NOTE}"


def check_spekkr(codec_path: Path, codec, root: Path, failures: list[str]) -> None:
    if not root.is_dir():
        return
    for case in cases(root):
        label = f"spekkr/{case.name}"
        source = case / "source"
        if (case / "error.txt").is_file():
            expect_error(
                codec_path,
                ["to-kiro", str(source), "--dir", "out"],
                case,
                label,
                failures,
            )
            continue
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # A destination under .kiro/specs keeps stderr to the warning line.
            feature = tmp_path / ".kiro" / "specs" / "out"
            back = tmp_path / "back"
            forward = run(codec_path, ["to-kiro", str(source), "--dir", str(feature)])
            if not ok(forward, label, "to-kiro", failures):
                continue
            if forward.stderr != warning_line(codec) + "\n":
                failures.append(f"{label}: to-kiro stderr is {forward.stderr!r}")
            backward = run(codec_path, ["to-spekkr", str(feature), "--dir", str(back)])
            if not ok(backward, label, "to-spekkr", failures):
                continue
            if backward.stderr:
                failures.append(f"{label}: to-spekkr wrote to stderr: {backward.stderr!r}")
            differ(source, back, f"{label}: round trip", failures)
            differ(case / "expected", feature, f"{label}: golden feature folder", failures)
            assert_feature_bytes(codec, source, feature, label, failures)
            if case.name == "requirements":
                spec_text = (source / "spec.md").read_text(encoding="utf-8")
                copied = (feature / "requirements.md").read_text(encoding="utf-8")
                if "### R1." not in copied or "**Accept when:**" not in copied or copied != spec_text:
                    failures.append(f"{label}: requirement text was not copied as written")
            if case.name == "large-file":
                payload = source / "payload.txt"
                if not payload.is_file() or payload.stat().st_size <= 60 * 1024:
                    failures.append(f"{label}: payload.txt is not over 60 KB")
            if case.name == "extra-files":
                png = feature / "shots" / "pixel.png"
                if not png.is_file() or png.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                    failures.append(f"{label}: shots/pixel.png is not the source PNG")


def check_handwritten(codec_path: Path, codec, root: Path, failures: list[str]) -> None:
    if not root.is_dir():
        return
    flags = ["--author", "example-user", "--date", "2026-01-01"]
    for case in cases(root):
        label = f"handwritten/{case.name}"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = place(case, tmp_path / "placed")
            if (case / "error.txt").is_file():
                expect_error(
                    codec_path,
                    ["to-spekkr", str(source), "--dir", "out", *flags],
                    case,
                    label,
                    failures,
                )
                continue
            spekkr = tmp_path / "spekkr"
            fixed = tmp_path / ".kiro" / "specs" / "fixed"
            again_spekkr = tmp_path / "again-spekkr"
            again_fixed = tmp_path / ".kiro" / "specs" / "again-fixed"
            first = run(codec_path, ["to-spekkr", str(source), "--dir", str(spekkr), *flags])
            if not ok(first, label, "to-spekkr", failures):
                continue
            feature = run(codec_path, ["to-kiro", str(spekkr), "--dir", str(fixed)])
            if not ok(feature, label, "to-kiro", failures):
                continue
            if not feature.stderr.startswith(warning_line(codec) + "\n"):
                failures.append(f"{label}: to-kiro did not lead with the warning")
            second = run(codec_path, ["to-spekkr", str(fixed), "--dir", str(again_spekkr), *flags])
            if not ok(second, label, "to-spekkr again", failures):
                continue
            third = run(codec_path, ["to-kiro", str(again_spekkr), "--dir", str(again_fixed)])
            if not ok(third, label, "to-kiro again", failures):
                continue
            differ(fixed, again_fixed, f"{label}: fixed point", failures)
            differ(spekkr, again_spekkr, f"{label}: to-spekkr is stable", failures)
            differ(case / "expected-spekkr", spekkr, f"{label}: golden Spekkr folder", failures)
            differ(case / "expected-fixed", fixed, f"{label}: golden fixed point", failures)
            requirements = (source / "requirements.md").read_bytes()
            spec_bytes = (spekkr / "spec.md").read_bytes()
            if spec_bytes != requirements:
                failures.append(f"{label}: spec.md is not the original requirements.md")
            design = (source / "design.md").read_bytes()
            spekkr_design = (spekkr / "design.md").read_bytes()
            if design.startswith(codec.SAFETY_BLOCK):
                if spekkr_design != design[len(codec.SAFETY_BLOCK) :]:
                    failures.append(f"{label}: the safety block was not removed exactly once")
            elif spekkr_design != design:
                failures.append(f"{label}: design.md changed on the way to Spekkr")
            fixed_design = (fixed / "design.md").read_bytes()
            if not fixed_design.startswith(codec.SAFETY_BLOCK):
                failures.append(f"{label}: fixed design.md does not start with the safety block")
            elif fixed_design[len(codec.SAFETY_BLOCK) :] != spekkr_design:
                failures.append(f"{label}: stripping the safety block does not restore design.md")
            if case.name == "ears":
                text = requirements.decode("utf-8")
                manifest = json.loads((spekkr / "spekkr.json").read_text(encoding="utf-8"))
                slug = manifest["id"].split("/", 1)[1]
                if "WHEN" not in text or "THE SYSTEM SHALL" not in text:
                    failures.append(f"{label}: EARS lines were not kept")
                if any(line.startswith("# ") for line in text.splitlines()):
                    failures.append(f"{label}: an # heading was added")
                if manifest["name"] != slug:
                    failures.append(f"{label}: manifest name {manifest['name']!r} is not the slug {slug!r}")
            if case.name == "plain":
                text = requirements.decode("utf-8")
                task = (source / "tasks.md").read_text(encoding="utf-8")
                if "FR1:" not in text or "SC1:" not in text or "- [ ]" not in task:
                    failures.append(f"{label}: FR/SC lines or the checkbox task changed")
            if case.name == "long-summary":
                summary = json.loads((spekkr / "spekkr.json").read_text(encoding="utf-8"))["summary"]
                words = summary.split(" ")
                if len(summary) > 140 or not words or words[-1] != "pebble":
                    failures.append(
                        f"{label}: summary is {len(summary)} characters and ends {summary[-24:]!r}"
                    )
            if case.name == "prefixed-design" and not design.startswith(codec.SAFETY_BLOCK):
                failures.append(f"{label}: source design.md does not start with the full safety block")


def check_flags(codec_path: Path, codec, fixtures: Path, failures: list[str]) -> None:
    basic = fixtures / "spekkr" / "basic" / "source"
    rich = fixtures / "spekkr" / "rich-manifest" / "source"
    absent = fixtures / "spekkr" / "inputs-absent" / "source"
    numbered = fixtures / "handwritten" / "numbered"
    plain = fixtures / "handwritten" / "plain"
    if not basic.is_dir() or not rich.is_dir() or not numbered.is_dir() or not plain.is_dir():
        failures.append("flags: basic, rich-manifest, plain or numbered fixture is missing")
        return

    help_proc = run(codec_path, ["--help"])
    if help_proc.returncode != 0 or "to-kiro" not in help_proc.stdout or "to-spekkr" not in help_proc.stdout:
        failures.append("flags: --help did not list to-kiro and to-spekkr")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        default = run(codec_path, ["to-kiro", str(basic)], cwd=tmp_path)
        feature = tmp_path / ".kiro" / "specs" / "basic"
        if default.returncode != 0 or not feature.is_dir():
            failures.append(
                f"flags: default feature folder .kiro/specs/basic was not written ({default.stderr.strip()})"
            )
        else:
            differ(fixtures / "spekkr" / "basic" / "expected", feature, "flags: default dir", failures)
            if default.stderr != warning_line(codec) + "\n":
                failures.append(f"flags: default to-kiro stderr is {default.stderr!r}")
        if (tmp_path / ".kiro" / "steering").exists():
            failures.append("flags: to-kiro wrote .kiro/steering without --steering")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        numbered_dir = run(
            codec_path,
            ["to-kiro", str(basic), "--dir", ".kiro/specs/003-basic"],
            cwd=tmp_path,
        )
        if numbered_dir.returncode != 0:
            failures.append(f"flags: --dir .kiro/specs/003-basic failed ({numbered_dir.stderr.strip()})")
        else:
            if "not .kiro/specs" in numbered_dir.stderr:
                failures.append("flags: a .kiro/specs destination was reported as outside .kiro/specs")
            if not numbered_dir.stderr.startswith(warning_line(codec) + "\n"):
                failures.append("flags: --dir .kiro/specs/003-basic did not lead with the warning")
            if not (tmp_path / ".kiro" / "specs" / "003-basic").is_dir():
                failures.append("flags: --dir .kiro/specs/003-basic wrote nothing")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        outside = run(
            codec_path,
            ["to-kiro", str(basic), "--dir", "features/basic"],
            cwd=tmp_path,
        )
        if outside.returncode != 0:
            failures.append(f"flags: --dir features/basic failed ({outside.stderr.strip()})")
        else:
            if outside.stdout.strip() != "features/basic":
                failures.append(f"flags: stdout was {outside.stdout!r}")
            note = f"note: {outside.stdout.strip()} is not .kiro/specs/<name>"
            if note not in outside.stderr:
                failures.append(f"flags: missing path note in {outside.stderr!r}")
            if not outside.stderr.startswith(warning_line(codec) + "\n"):
                failures.append("flags: --dir features/basic did not lead with the warning")
        (tmp_path / "elsewhere").mkdir()
        steered = run(
            codec_path,
            ["to-kiro", str(basic), "--dir", "features/basic", "--steering"],
            cwd=tmp_path / "elsewhere",
        )
        if steered.returncode == 0:
            failures.append("flags: --steering outside .kiro/specs succeeded")
        elif "feature folder is not .kiro/specs/<name>" not in steered.stderr:
            failures.append(f"flags: --steering path error was {steered.stderr!r}")
        if (tmp_path / "elsewhere" / "features").exists():
            failures.append("flags: a refused --steering left a feature folder")

    check_steering_basic(codec_path, codec, basic, failures)
    check_steering_rich(codec_path, codec, rich, failures)
    check_steering_conflict(codec_path, basic, failures)
    check_foundation_name(codec_path, basic, failures)
    if absent.is_dir():
        check_inputs_absent(codec_path, absent, failures)
    check_default_spekkr(codec_path, numbered, failures)
    check_date_and_platforms(codec_path, plain, failures)
    check_relative_source(codec_path, numbered, failures)
    check_unreadable_source(codec_path, basic, failures)
    check_partial_marker(codec_path, codec, failures)
    check_empty_directory(codec_path, basic, failures)
    check_symlink(codec_path, basic, failures)
    check_product_without_summary(codec, failures)
    check_skill_command(codec_path, basic, failures)

    if not codec.SAFETY_BLOCK.startswith(codec.SAFETY_BEGIN):
        failures.append("flags: safety block does not start with its begin marker")
    if not codec.SAFETY_BLOCK.endswith(b"\n\n"):
        failures.append("flags: safety block does not end with a blank line")


def check_steering_basic(codec_path: Path, codec, basic: Path, failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proc = run(codec_path, ["to-kiro", str(basic), "--steering"], cwd=tmp_path)
        if proc.returncode != 0:
            failures.append(f"flags: --steering on basic failed ({proc.stderr.strip()})")
            return
        steering = tmp_path / ".kiro" / "steering"
        product = steering / "product.md"
        manifest = json.loads((basic / "spekkr.json").read_text(encoding="utf-8"))
        if not product.is_file() or product.read_bytes() != codec.product_markdown(manifest):
            failures.append("flags: basic product.md is not the worked example")
        names = sorted(path.name for path in steering.iterdir()) if steering.is_dir() else []
        if names != ["product.md"]:
            failures.append(f"flags: basic steering files are {names}")
        if (tmp_path / ".kiro" / "hooks").exists():
            failures.append("flags: --steering wrote .kiro/hooks")
        for needle in (
            "did not write tech.md; spekkr.json has no targets.stack",
            "did not write structure.md; spekkr.json does not describe the project layout",
            "did not write a choices file; the spec folder has no spekkr.inputs.json",
            "safety commands and secrets were not copied into steering",
            "wrote .kiro/steering/product.md from spekkr.json",
        ):
            if needle not in proc.stderr:
                failures.append(f"flags: basic steering stderr lacks {needle!r}")
        if not proc.stderr.startswith(warning_line(codec) + "\n"):
            failures.append("flags: steered to-kiro did not lead with the warning")


def check_steering_rich(codec_path: Path, codec, rich: Path, failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proc = run(codec_path, ["to-kiro", str(rich), "--steering"], cwd=tmp_path)
        if proc.returncode != 0:
            failures.append(f"flags: --steering on rich-manifest failed ({proc.stderr.strip()})")
            return
        steering = tmp_path / ".kiro" / "steering"
        manifest = json.loads((rich / "spekkr.json").read_text(encoding="utf-8"))
        inputs = json.loads((rich / "spekkr.inputs.json").read_text(encoding="utf-8"))
        product = codec.product_markdown(manifest)
        tech = codec.tech_markdown(manifest["targets"]["stack"])
        choices = codec.choices_markdown(
            "Pebble jar",
            ".kiro/specs/pebble-jar",
            "pebble-jar",
            inputs,
        )
        found = {
            "product.md": (steering / "product.md").read_bytes() if (steering / "product.md").is_file() else b"",
            "tech.md": (steering / "tech.md").read_bytes() if (steering / "tech.md").is_file() else b"",
            "pebble-jar.md": (steering / "pebble-jar.md").read_bytes() if (steering / "pebble-jar.md").is_file() else b"",
        }
        if found["product.md"] != product or found["tech.md"] != tech or found["pebble-jar.md"] != choices:
            failures.append("flags: rich-manifest steering bytes do not match the helpers")
        if (steering / "structure.md").exists():
            failures.append("flags: rich-manifest wrote structure.md")
        if (tmp_path / ".kiro" / "hooks").exists():
            failures.append("flags: rich-manifest --steering wrote a hook")
        for needle in (
            "wrote .kiro/steering/product.md from spekkr.json",
            "wrote .kiro/steering/tech.md from targets.stack",
            "wrote .kiro/steering/pebble-jar.md from spekkr.inputs.json",
            "did not write structure.md",
            "safety commands and secrets were not copied into steering",
        ):
            if needle not in proc.stderr:
                failures.append(f"flags: rich steering stderr lacks {needle!r}")


def check_steering_conflict(codec_path: Path, basic: Path, failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        steering = tmp_path / ".kiro" / "steering"
        steering.mkdir(parents=True)
        (steering / "product.md").write_text("keep\n", encoding="utf-8")
        proc = run(codec_path, ["to-kiro", str(basic), "--steering"], cwd=tmp_path)
        if proc.returncode == 0:
            failures.append("flags: --steering overwrote an existing product.md")
            return
        if proc.stderr != "error: .kiro/steering/product.md already exists; --steering will not overwrite it\n":
            failures.append(f"flags: existing steering stderr was {proc.stderr!r}")
        if proc.stdout:
            failures.append(f"flags: a steering conflict wrote to stdout: {proc.stdout!r}")
        if (tmp_path / ".kiro" / "specs" / "basic").exists():
            failures.append("flags: a steering conflict left a feature folder")
        if (steering / "product.md").read_text(encoding="utf-8") != "keep\n":
            failures.append("flags: a steering conflict changed product.md")


def check_foundation_name(codec_path: Path, basic: Path, failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source = tmp_path / "spec"
        shutil.copytree(basic, source)
        manifest = json.loads((source / "spekkr.json").read_text(encoding="utf-8"))
        manifest["id"] = "example-user/product"
        (source / "spekkr.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (source / "spekkr.inputs.json").write_text('{\n  "lid": true\n}\n', encoding="utf-8")
        work = tmp_path / "work"
        work.mkdir()
        proc = run(
            codec_path,
            ["to-kiro", str(source), "--dir", ".kiro/specs/product", "--steering"],
            cwd=work,
        )
        if proc.returncode == 0:
            failures.append("flags: a feature named product was allowed to write steering")
            return
        if "feature name 'product' would overwrite a foundation steering file" not in proc.stderr:
            failures.append(f"flags: foundation-name stderr was {proc.stderr!r}")
        if (work / ".kiro" / "specs" / "product").exists() or (work / ".kiro" / "steering").exists():
            failures.append("flags: the foundation-name error left files behind")


def check_inputs_absent(codec_path: Path, absent: Path, failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proc = run(codec_path, ["to-kiro", str(absent), "--steering"], cwd=tmp_path)
        if proc.returncode != 0:
            failures.append(f"flags: inputs-absent --steering failed ({proc.stderr.strip()})")
            return
        steering = tmp_path / ".kiro" / "steering"
        names = sorted(path.name for path in steering.iterdir())
        if names != ["product.md"]:
            failures.append(f"flags: inputs-absent steering files are {names}")
        if "did not write a choices file; the spec folder has no spekkr.inputs.json" not in proc.stderr:
            failures.append("flags: inputs-absent did not report the missing inputs file")
        product = (steering / "product.md").read_text(encoding="utf-8")
        if "cloth" in product or "wood" in product or "Lid material" in product:
            failures.append("flags: customize was copied into steering")


def check_default_spekkr(codec_path: Path, numbered: Path, failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source = place(numbered, tmp_path / "in")
        proc = run(
            codec_path,
            ["to-spekkr", str(source), "--author", "example-user", "--date", "2026-01-01"],
            cwd=tmp_path,
        )
        written = tmp_path / "example"
        if proc.returncode != 0 or not (written / "spekkr.json").is_file():
            failures.append(
                f"flags: default Spekkr folder ./example was not written ({proc.stderr.strip()})"
            )
            return
        differ(numbered / "expected-spekkr", written, "flags: numbered default dir", failures)


def check_date_and_platforms(codec_path: Path, plain: Path, failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source = place(plain, tmp_path / "in")
        undated = run(
            codec_path,
            ["to-spekkr", str(source), "--dir", str(tmp_path / "out"), "--author", "example-user"],
        )
        if undated.returncode != 0:
            failures.append(f"flags: default date failed ({undated.stderr.strip()})")
        else:
            manifest = (tmp_path / "out" / "spekkr.json").read_text(encoding="utf-8")
            if '"date": "1970-01-01"' not in manifest:
                failures.append("flags: omitting --date did not use 1970-01-01")
            if "changelog date is 1970-01-01 because --date was not given" not in undated.stderr:
                failures.append("flags: the default date was not reported on stderr")
            if "review it before publishing" not in undated.stderr:
                failures.append("flags: the filled-in summary was not reported on stderr")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source = place(plain, tmp_path / "in")
        chosen = run(
            codec_path,
            [
                "to-spekkr",
                str(source),
                "--dir",
                str(tmp_path / "out"),
                "--author",
                "example-user",
                "--date",
                "2026-01-01",
                "--platforms",
                "cli, backend",
            ],
        )
        if chosen.returncode != 0:
            failures.append(f"flags: --platforms failed ({chosen.stderr.strip()})")
            return
        manifest = json.loads((tmp_path / "out" / "spekkr.json").read_text(encoding="utf-8"))
        if manifest["targets"]["platforms"] != ["cli", "backend"]:
            failures.append(
                "flags: --platforms was not applied: " + json.dumps(manifest["targets"]["platforms"])
            )


def check_relative_source(codec_path: Path, numbered: Path, failures: list[str]) -> None:
    """`.` and `..` name the directory they refer to, not the path text."""
    flags = ["--author", "example-user", "--date", "2026-01-01"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source = place(numbered, tmp_path / "placed")
        dot = run(
            codec_path,
            ["to-spekkr", ".", "--dir", "../from-dot", *flags],
            cwd=source,
        )
        if not ok(dot, "flags", "to-spekkr .", failures):
            return
        differ(numbered / "expected-spekkr", source.parent / "from-dot", "flags: slug from .", failures)

        inside = source / "inside"
        inside.mkdir()
        parent = run(
            codec_path,
            ["to-spekkr", "..", "--dir", "../../from-parent", *flags],
            cwd=inside,
        )
        if not ok(parent, "flags", "to-spekkr ..", failures):
            return
        written = source.parent / "from-parent" / "spekkr.json"
        if not written.is_file():
            failures.append("flags: to-spekkr .. did not write spekkr.json")
        else:
            spec_id = json.loads(written.read_text(encoding="utf-8"))["id"]
            if spec_id != "example-user/example":
                failures.append(f"flags: slug from .. is {spec_id!r}")


def check_unreadable_source(codec_path: Path, basic: Path, failures: list[str]) -> None:
    """An unreadable subdirectory aborts the conversion and writes nothing."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source = tmp_path / "spec"
        shutil.copytree(basic, source)
        hidden = source / "reference"
        hidden.mkdir()
        (hidden / "note.md").write_text("hidden\n", encoding="utf-8")
        hidden.chmod(0)
        out = tmp_path / "out"
        try:
            proc = run(codec_path, ["to-kiro", str(source), "--dir", str(out)])
        finally:
            hidden.chmod(0o755)
        if proc.returncode == 0:
            failures.append("flags: an unreadable directory was converted")
            return
        if not proc.stderr.startswith("error: cannot read "):
            failures.append(f"flags: unreadable directory stderr was {proc.stderr!r}")
        if proc.stdout:
            failures.append(f"flags: an unreadable directory wrote to stdout: {proc.stdout!r}")
        if out.exists():
            failures.append("flags: an unreadable directory left an output folder")


def check_partial_marker(codec_path: Path, codec, failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source = tmp_path / "feature"
        source.mkdir()
        (source / "requirements.md").write_text("# Partial\n\nNot the block.\n", encoding="utf-8")
        (source / "design.md").write_bytes(codec.SAFETY_BEGIN + b"\nnot the block\n")
        out = tmp_path / "out"
        proc = run(
            codec_path,
            [
                "to-spekkr",
                str(source),
                "--dir",
                str(out),
                "--author",
                "example-user",
                "--date",
                "2026-01-01",
            ],
        )
        want = (
            "error: design.md starts with <!-- spekkr:safety:begin --> but is not "
            "the safety block; to-spekkr will not convert it\n"
        )
        if proc.returncode == 0:
            failures.append("flags: a partial safety marker was converted")
        elif proc.stderr != want:
            failures.append(f"flags: partial marker stderr was {proc.stderr!r}")
        if proc.stdout:
            failures.append(f"flags: a partial marker wrote to stdout: {proc.stdout!r}")
        if out.exists():
            failures.append("flags: a partial marker left an output folder")


def check_empty_directory(codec_path: Path, basic: Path, failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source = tmp_path / "spec"
        shutil.copytree(basic, source)
        (source / "reference" / "empty").mkdir(parents=True)
        feature = tmp_path / ".kiro" / "specs" / "out"
        back = tmp_path / "back"
        forward = run(codec_path, ["to-kiro", str(source), "--dir", str(feature)])
        if forward.returncode != 0:
            failures.append(f"flags: empty directory to-kiro failed ({forward.stderr.strip()})")
            return
        if not (feature / "reference" / "empty").is_dir():
            failures.append("flags: an empty directory was dropped on the way to Kiro")
        backward = run(codec_path, ["to-spekkr", str(feature), "--dir", str(back)])
        if backward.returncode != 0 or not (back / "reference" / "empty").is_dir():
            failures.append("flags: an empty directory was dropped on the way back")


def check_symlink(codec_path: Path, basic: Path, failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source = tmp_path / "spec"
        shutil.copytree(basic, source)
        (source / "alias.md").symlink_to(source / "spec.md")
        out = tmp_path / "out"
        proc = run(codec_path, ["to-kiro", str(source), "--dir", str(out)])
        if proc.returncode == 0:
            failures.append("flags: a symlink was followed")
            return
        if "refusing to follow a symlink:" not in proc.stderr:
            failures.append(f"flags: symlink stderr was {proc.stderr!r}")
        if out.exists():
            failures.append("flags: a symlink left an output folder")


def check_product_without_summary(codec, failures: list[str]) -> None:
    text = codec.product_markdown(
        {"id": "example-user/basic", "name": "basic", "targets": {"platforms": ["web"]}}
    ).decode("utf-8")
    if "\nSummary:" in text or text.startswith("Summary:"):
        failures.append("flags: product.md included Summary when the manifest had none")
    if "Name: basic\n" not in text:
        failures.append("flags: product.md dropped the name")


def check_skill_command(codec_path: Path, basic: Path, failures: list[str]) -> None:
    """The skill's to-kiro command, from an empty directory, writes the feature only."""
    skill = HERE.parent / "skills" / "kiro-codec" / "SKILL.md"
    if not skill.is_file():
        failures.append("flags: skills/kiro-codec/SKILL.md is missing")
        return
    text = skill.read_text(encoding="utf-8")
    if "python3 kiro_codec.py to-kiro tests/fixtures/spekkr/basic/source" not in text:
        failures.append("flags: the skill does not give the basic to-kiro command")
        return
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proc = run(codec_path, ["to-kiro", str(basic)], cwd=tmp_path)
        if proc.returncode != 0 or not (tmp_path / ".kiro" / "specs" / "basic").is_dir():
            failures.append(f"flags: the skill command did not write .kiro/specs/basic ({proc.stderr.strip()})")
        if (tmp_path / ".kiro" / "steering").exists():
            failures.append("flags: the skill command wrote .kiro/steering")


def check_manifests(root: Path, failures: list[str]) -> None:
    """Local stand-in for Spekkr check_spec. See the module docstring."""
    if not root.is_dir():
        return
    for case in cases(root):
        if (case / "error.txt").is_file():
            continue
        path = case / "expected-spekkr" / "spekkr.json"
        label = f"handwritten/{case.name}"
        if not path.is_file():
            failures.append(f"{label}: golden spekkr.json is missing")
            continue
        raw = path.read_bytes()
        if not raw.endswith(b"\n"):
            failures.append(f"{label}: spekkr.json has no trailing newline")
        try:
            manifest = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            failures.append(f"{label}: spekkr.json is not UTF-8 JSON: {error}")
            continue
        rendered = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        if rendered != raw:
            failures.append(f"{label}: spekkr.json is not the two-space form")
        problems = manifest_problems(manifest)
        for problem in problems:
            failures.append(f"{label}: manifest {problem}")


def manifest_problems(manifest: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(manifest, dict):
        return ["is not an object"]
    if manifest.get("spekkr") != 1:
        problems.append("spekkr is not 1")
    spec_id = manifest.get("id")
    if not isinstance(spec_id, str) or spec_id.count("/") != 1:
        problems.append(f"id is {spec_id!r}")
    else:
        user, _, name = spec_id.partition("/")
        if not user or not name:
            problems.append(f"id is {spec_id!r}")
    if not isinstance(manifest.get("name"), str) or not manifest["name"].strip():
        problems.append("name is empty")
    summary = manifest.get("summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 140:
        problems.append(f"summary is unusable ({summary!r})")
    if manifest.get("version") != "0.1.0":
        problems.append("version is not 0.1.0")
    author = manifest.get("author")
    if not isinstance(author, dict) or author.get("id") != "example-user" or author.get("name") != "example-user":
        problems.append(f"author is {author!r}")
    targets = manifest.get("targets")
    platforms = targets.get("platforms") if isinstance(targets, dict) else None
    if not isinstance(platforms, list) or not platforms or any(item not in PLATFORMS for item in platforms):
        problems.append(f"platforms are {platforms!r}")
    if manifest.get("customize") != {} or manifest.get("safety") != {}:
        problems.append("customize or safety was not empty")
    files = manifest.get("files")
    paths = [item.get("path") for item in files] if isinstance(files, list) else []
    if "spec.md" not in paths or "design.md" not in paths:
        problems.append(f"files are {paths!r}")
    changelog = manifest.get("changelog")
    if not isinstance(changelog, list) or not changelog:
        problems.append("changelog is empty")
    else:
        entry = changelog[0]
        note = entry.get("note") if isinstance(entry, dict) else None
        date = entry.get("date") if isinstance(entry, dict) else None
        if note != "Converted from Kiro.":
            problems.append(f"changelog note is {note!r}")
        if not isinstance(date, str) or len(date) != 10:
            problems.append(f"changelog date is {date!r}")
    return problems


def check_documented(codec, failures: list[str]) -> None:
    """README, skill, workflow, and the safety block in spec/design.md."""
    readme = HERE.parent / "README.md"
    if not readme.is_file():
        failures.append("docs: README.md is missing")
    else:
        text = readme.read_bytes()
        if codec.SAFETY_BLOCK not in text:
            failures.append("docs: README.md does not contain the safety block bytes")
        if codec.REGEN_NOTE.encode("utf-8") not in text:
            failures.append("docs: README.md does not state the regenerate warning")
    skill = HERE.parent / "skills" / "kiro-codec" / "SKILL.md"
    if not skill.is_file():
        failures.append("docs: skills/kiro-codec/SKILL.md is missing")
    else:
        head = skill.read_text(encoding="utf-8")
        if not head.startswith("---\n") or "name: kiro-codec\n" not in head.split("---", 2)[1]:
            failures.append("docs: the skill front matter has no name: kiro-codec")
        if "description:" not in head.split("---", 2)[1]:
            failures.append("docs: the skill front matter has no description")
    workflow = HERE.parent / ".github" / "workflows" / "ci.yml"
    if not workflow.is_file():
        failures.append("docs: .github/workflows/ci.yml is missing")
    else:
        body = workflow.read_text(encoding="utf-8")
        for needle in ("3.11", "3.12", "contents: read", "python3 tests/check.py"):
            if needle not in body:
                failures.append(f"docs: the workflow does not mention {needle}")
    design = HERE.parent / "spec" / "design.md"
    if design.is_file():
        fence = design.read_text(encoding="utf-8")
        marker = "```text\n"
        start = fence.find(marker + "<!-- spekkr:safety:begin -->")
        end = fence.find("\n```", start + len(marker)) if start >= 0 else -1
        if start < 0 or end < 0:
            failures.append("docs: spec/design.md has no safety block fence")
        else:
            block = fence[start + len(marker) : end].encode("utf-8") + b"\n"
            if block != codec.SAFETY_BLOCK:
                failures.append("docs: SAFETY_BLOCK does not match spec/design.md")


def cases(root: Path) -> list[Path]:
    return sorted(path for path in root.iterdir() if path.is_dir())


def place(case: Path, dest: Path) -> Path:
    """Copy source/ to a folder of the name the codec should see."""
    name = case.name
    marker = case / "folder-name"
    if marker.is_file():
        name = marker.read_text(encoding="utf-8").strip()
    dest.mkdir(parents=True)
    target = dest / name
    shutil.copytree(case / "source", target)
    return target


def run(
    codec: Path,
    args: list[str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(codec), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def ok(proc: subprocess.CompletedProcess[str], label: str, step: str, failures: list[str]) -> bool:
    if proc.returncode == 0:
        return True
    failures.append(f"{label}: {step} exited {proc.returncode}: {proc.stderr.strip()}")
    return False


def expect_error(
    codec: Path,
    args: list[str],
    case: Path,
    label: str,
    failures: list[str],
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rewritten: list[str] = []
        index = 0
        out = tmp_path / "out"
        while index < len(args):
            if args[index] == "--dir" and index + 1 < len(args) and not Path(args[index + 1]).is_absolute():
                rewritten.extend(["--dir", str(out)])
                index += 2
                continue
            rewritten.append(args[index])
            index += 1
        proc = run(codec, rewritten)
        want = (case / "error.txt").read_text(encoding="utf-8")
        if not want.endswith("\n"):
            want += "\n"
        if proc.returncode == 0:
            failures.append(f"{label}: expected a failure, but the command succeeded")
            return
        if proc.stderr != want:
            failures.append(f"{label}: stderr {proc.stderr!r}, want {want!r}")
        if proc.stdout:
            failures.append(f"{label}: a failure wrote to stdout: {proc.stdout!r}")
        if out.exists():
            failures.append(f"{label}: a failure left an output folder")


def assert_feature_bytes(codec, source: Path, feature: Path, label: str, failures: list[str]) -> None:
    design = (feature / "design.md").read_bytes()
    original = (source / "design.md").read_bytes()
    requirements = (feature / "requirements.md").read_bytes()
    spec = (source / "spec.md").read_bytes()
    if requirements != spec:
        failures.append(f"{label}: requirements.md is not spec.md")
    if not design.startswith(codec.SAFETY_BLOCK):
        failures.append(f"{label}: design.md does not start with the safety block")
    elif design[len(codec.SAFETY_BLOCK) :] != original:
        failures.append(f"{label}: removing the safety block does not restore design.md")


def differ(left: Path, right: Path, label: str, failures: list[str]) -> None:
    if not left.exists() or not right.exists():
        failures.append(f"{label}: missing {left} or {right}")
        return
    left_files, left_dirs = snapshot(left)
    right_files, right_dirs = snapshot(right)
    if left_files.keys() != right_files.keys() or left_dirs != right_dirs:
        missing = sorted((set(left_files) | left_dirs) - (set(right_files) | right_dirs))
        extra = sorted((set(right_files) | right_dirs) - (set(left_files) | left_dirs))
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("extra " + ", ".join(extra))
        failures.append(f"{label}: tree differs ({'; '.join(detail)})")
        return
    for rel, data in left_files.items():
        other = right_files[rel]
        if data != other:
            offset = next(
                (i for i, (a, b) in enumerate(zip(data, other)) if a != b),
                min(len(data), len(other)),
            )
            failures.append(
                f"{label}: {rel} differs at byte {offset} ({len(data)} bytes vs {len(other)} bytes)"
            )
            return


def snapshot(root: Path) -> tuple[dict[str, bytes], set[str]]:
    files: dict[str, bytes] = {}
    directories: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        for name in dirnames:
            rel = (current / name).relative_to(root).as_posix()
            directories.add(rel + "/")
        for name in filenames:
            path = current / name
            rel = path.relative_to(root).as_posix()
            files[rel] = path.read_bytes()
    return files, directories


if __name__ == "__main__":
    sys.exit(main())
