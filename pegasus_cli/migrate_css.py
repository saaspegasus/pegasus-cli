"""Migrate pg- CSS classes to native Tailwind/DaisyUI equivalents."""
import os
import re
from pathlib import Path

import click

DEFAULT_CSS_FILE = "assets/styles/pegasus/tailwind.css"
DEFAULT_SEARCH_DIRS = ("templates", "assets/javascript", "apps", "frontend")
EXTENSIONS = {".html", ".jsx", ".js", ".vue", ".ts", ".tsx", ".py"}
SKIP_DIRS = {"node_modules"}

PG_CLASS_PATTERN = re.compile(
    r"\.(pg-[a-z0-9-]+)\s*\{\s*\n\s*@apply\s+([^;]+);?\s*\n\}",
)
ANY_PG_CLASS_PATTERN = re.compile(r"\b(pg-[a-z0-9-]+)\b")
DEFINED_PG_CLASS_PATTERN = re.compile(r"^\.(pg-[a-z0-9-]+)(?![a-z0-9-])", re.MULTILINE)


def parse_tailwind_css(path: Path) -> dict[str, str]:
    """Parse .pg-foo { @apply bar baz; } patterns from tailwind.css."""
    classes = {}
    content = path.read_text()
    for match in PG_CLASS_PATTERN.finditer(content):
        name = match.group(1)
        apply_classes = match.group(2).strip().rstrip(";")
        classes[name] = apply_classes
    return classes


def find_defined_classes(path: Path) -> set[str]:
    """Return every pg- class defined in tailwind.css, including complex ones."""
    return set(DEFINED_PG_CLASS_PATTERN.findall(path.read_text()))


def _echo_class_counts(unmigrated_by_class: dict[str, list[Path]], names: list[str]):
    for name in names:
        files = unmigrated_by_class[name]
        click.echo(f"  {name} ({len(files)} file{'s' if len(files) != 1 else ''})")


def iter_files(search_dir: Path):
    """Yield all files under search_dir, without descending into SKIP_DIRS."""
    for root, dirnames, filenames in os.walk(search_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            yield Path(root) / filename


def build_pattern(css_class_map: dict[str, str]) -> re.Pattern:
    """Build regex that matches pg- class names, longest first."""
    names = sorted(css_class_map.keys(), key=len, reverse=True)
    return re.compile(r"(" + "|".join(re.escape(n) for n in names) + r")(?![a-z0-9-])")


def migrate_file(
    filepath: Path,
    pattern: re.Pattern,
    css_class_map: dict[str, str],
    dry_run: bool = False,
) -> tuple[list[tuple[str, str]], set[str]]:
    """Replace pg- classes in a single file.

    Returns (replacements made, set of pg- class names found but not in the mapping).
    """
    content = filepath.read_text()
    replacements = []

    def replace_match(match):
        old = match.group(1)
        new = css_class_map[old]
        replacements.append((old, new))
        return new + match.group(0)[len(old) :]

    new_content = pattern.sub(replace_match, content)

    unmigrated = {
        name
        for name in ANY_PG_CLASS_PATTERN.findall(new_content)
        if name not in css_class_map
    }

    if replacements and not dry_run:
        filepath.write_text(new_content)

    return replacements, unmigrated


@click.command(name="migrate-css")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would change without modifying files",
)
@click.option(
    "--css-file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=DEFAULT_CSS_FILE,
    show_default=True,
    help="Path to the Pegasus tailwind.css file containing pg- class definitions",
)
@click.option(
    "--search-dir",
    "search_dirs",
    type=click.Path(file_okay=False, path_type=Path),
    multiple=True,
    help=(
        "Directory to search for files to migrate. Can be passed multiple times. "
        f"Defaults to: {', '.join(DEFAULT_SEARCH_DIRS)}"
    ),
)
def migrate_css(dry_run: bool, css_file: Path, search_dirs: tuple[Path, ...]):
    """Migrate pg- CSS classes to native Tailwind/DaisyUI equivalents.

    Replaces legacy pg- prefixed CSS classes with their native Tailwind/DaisyUI
    equivalents in templates and JavaScript files.

    The class mappings are read from your project's tailwind.css so they always
    match the version of Pegasus your project was built with.

    Run from your project root.
    """
    if not css_file.exists():
        raise click.ClickException(
            f"{css_file} not found. Run from your project root or pass --css-file."
        )

    css_class_map = parse_tailwind_css(css_file)
    if not css_class_map:
        raise click.ClickException(f"No pg- class mappings found in {css_file}.")

    click.echo(f"Loaded {len(css_class_map)} class mappings from {css_file}\n")

    pattern = build_pattern(css_class_map)
    dirs = search_dirs or tuple(Path(d) for d in DEFAULT_SEARCH_DIRS)
    total_files = 0
    total_replacements = 0
    unmigrated_by_class: dict[str, list[Path]] = {}

    for search_dir in dirs:
        if not search_dir.is_dir():
            continue
        for filepath in iter_files(search_dir):
            if not filepath.is_file() or filepath.suffix not in EXTENSIONS:
                continue
            # Skip CSS/style directories
            parts = set(filepath.parts)
            if "styles" in parts or "css" in parts:
                continue
            replacements, unmigrated = migrate_file(
                filepath, pattern, css_class_map, dry_run=dry_run
            )
            if replacements:
                total_files += 1
                total_replacements += len(replacements)
                prefix = "[dry run] " if dry_run else ""
                click.echo(f"  {prefix}{filepath} ({len(replacements)} replacements)")
                for old, new in replacements:
                    click.echo(f"    {old} -> {new}")
            for name in unmigrated:
                unmigrated_by_class.setdefault(name, []).append(filepath)

    if total_replacements:
        action = "Would update" if dry_run else "Updated"
        click.echo(
            f"\n{action} {total_replacements} class references in {total_files} files"
        )
    else:
        click.echo("No pg- CSS classes found to migrate.")

    if unmigrated_by_class:
        defined = find_defined_classes(css_file)
        complex_classes = sorted(n for n in unmigrated_by_class if n in defined)
        undefined_classes = sorted(n for n in unmigrated_by_class if n not in defined)
        if complex_classes:
            click.echo(
                f"\nFound {len(complex_classes)} pg- class(es) defined in {css_file} "
                "with more than a single @apply. These must be migrated by hand "
                "(see their definitions):"
            )
            _echo_class_counts(unmigrated_by_class, complex_classes)
        if undefined_classes:
            click.echo(
                f"\nFound {len(undefined_classes)} pg- class(es) with no definition "
                f"in {css_file}. These classes cannot yet be migrated:"
            )
            _echo_class_counts(unmigrated_by_class, undefined_classes)
