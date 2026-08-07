"""Desktop / frozen entry: launch the Qt package IDE or forward CLI commands."""

from __future__ import annotations

from rich import print as rprint

from lappa import __version__
from lappa.config import ensure_dirs
from lappa.paths import is_frozen


def run_desktop() -> int:
    """Launch the Qt desktop IDE."""
    ensure_dirs()
    rprint(f"[bold]Lappa[/bold] v{__version__}  frozen={is_frozen()}")
    from lappa.gui.app import main as gui_main

    return gui_main()


def main(argv: list[str] | None = None) -> None:
    """
    CLI entry used by PyInstaller.

    - No args / `desktop` / `gui` -> open the Qt package IDE
    - Otherwise forward to Typer CLI (demo, ros2, package, ...)
    """
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("desktop", "gui", "start"):
        raise SystemExit(run_desktop())

    from lappa.cli import app

    sys.argv = [sys.argv[0], *args]
    app()


if __name__ == "__main__":
    main()
