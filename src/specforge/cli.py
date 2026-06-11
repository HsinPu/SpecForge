from __future__ import annotations

import argparse
from pathlib import Path

from specforge import __version__
from specforge.gaps import detect_gaps
from specforge.persistence import load_fact_bundle
from specforge.scanner import scan_project
from specforge.trace import build_trace_claims
from specforge.writers import write_fact_bundle, write_spec_bundle

DEFAULT_WORK_DIR = ".specforge"
DEFAULT_SPEC_OUT = "specforge-output"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="specforge",
        description="Evidence-first codebase-to-spec generator",
    )
    parser.add_argument("--version", action="version", version=f"specforge {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a SpecForge bundle for the current project",
    )
    init_parser.add_argument(
        "project",
        nargs="?",
        default=".",
        help="Project directory to scan. Defaults to the current directory.",
    )
    init_parser.add_argument(
        "--work-dir",
        default=DEFAULT_WORK_DIR,
        help="Intermediate fact bundle directory. Defaults to .specforge under the project.",
    )
    init_parser.add_argument(
        "--out",
        default=DEFAULT_SPEC_OUT,
        help="Output spec bundle directory. Defaults to specforge-output under the project.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing SpecForge bundle instead of stopping.",
    )
    init_parser.set_defaults(func=_init_command)

    update_parser = subparsers.add_parser(
        "update",
        help="Refresh the SpecForge bundle for the current project",
    )
    update_parser.add_argument(
        "project",
        nargs="?",
        default=".",
        help="Project directory to scan. Defaults to the current directory.",
    )
    update_parser.add_argument(
        "--work-dir",
        default=DEFAULT_WORK_DIR,
        help="Intermediate fact bundle directory. Defaults to .specforge under the project.",
    )
    update_parser.add_argument(
        "--out",
        default=DEFAULT_SPEC_OUT,
        help="Output spec bundle directory. Defaults to specforge-output under the project.",
    )
    update_parser.set_defaults(func=_update_command)

    scan_parser = subparsers.add_parser("scan", help="Scan a project and write fact artifacts")
    scan_parser.add_argument("project", help="Project directory to scan")
    scan_parser.add_argument("--out", default=DEFAULT_WORK_DIR, help="Output fact bundle directory")
    scan_parser.set_defaults(func=_scan_command)

    render_parser = subparsers.add_parser(
        "render",
        help="Render a SpecForge spec bundle from a fact bundle",
    )
    render_parser.add_argument("facts", help="Fact bundle directory from `specforge scan`")
    render_parser.add_argument("--out", default=DEFAULT_SPEC_OUT, help="Output spec bundle directory")
    render_parser.set_defaults(func=_render_command)

    forge_parser = subparsers.add_parser(
        "forge",
        help="Scan a project and render a SpecForge spec bundle",
    )
    forge_parser.add_argument("project", help="Project directory to scan")
    forge_parser.add_argument("--work-dir", default=DEFAULT_WORK_DIR, help="Intermediate fact bundle directory")
    forge_parser.add_argument("--out", default=DEFAULT_SPEC_OUT, help="Output spec bundle directory")
    forge_parser.set_defaults(func=_forge_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


def _init_command(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve()
    work_dir = _project_output_path(project, args.work_dir)
    spec_out = _project_output_path(project, args.out)
    _ensure_init_targets_available(work_dir, spec_out, force=args.force)
    _forge_project(project, work_dir, spec_out)
    print(f"Initialized SpecForge bundle for {project}")


def _update_command(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve()
    work_dir = _project_output_path(project, args.work_dir)
    spec_out = _project_output_path(project, args.out)
    _forge_project(project, work_dir, spec_out)
    print(f"Updated SpecForge bundle for {project}")


def _scan_command(args: argparse.Namespace) -> None:
    facts = scan_project(args.project)
    claims = build_trace_claims(facts)
    gaps = detect_gaps(facts)
    write_fact_bundle(facts, claims, gaps, args.out)
    print(f"Wrote scan artifacts to {Path(args.out).resolve()}")


def _render_command(args: argparse.Namespace) -> None:
    facts, claims, gaps = load_fact_bundle(args.facts)
    write_spec_bundle(facts, claims, gaps, args.out)
    print(f"Wrote SpecForge spec bundle to {Path(args.out).resolve()}")


def _forge_command(args: argparse.Namespace) -> None:
    _forge_project(args.project, args.work_dir, args.out)


def _forge_project(project: str | Path, work_dir: str | Path, spec_out: str | Path) -> None:
    facts = scan_project(project)
    claims = build_trace_claims(facts)
    gaps = detect_gaps(facts)
    write_fact_bundle(facts, claims, gaps, work_dir)
    write_spec_bundle(facts, claims, gaps, spec_out)
    print(f"Wrote scan artifacts to {Path(work_dir).resolve()}")
    print(f"Wrote SpecForge spec bundle to {Path(spec_out).resolve()}")


def _project_output_path(project: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project / path


def _ensure_init_targets_available(work_dir: Path, spec_out: Path, *, force: bool) -> None:
    if force:
        return

    existing = [path for path in (work_dir, spec_out) if path.exists()]
    if not existing:
        return

    paths = "\n".join(f"- {path.resolve()}" for path in existing)
    raise SystemExit(
        "SpecForge output already exists:\n"
        f"{paths}\n\n"
        "Run `specforge update` to refresh it, or `specforge init --force` to overwrite."
    )
