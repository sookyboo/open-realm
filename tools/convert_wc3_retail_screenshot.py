#!/usr/bin/env python3
"""Convert the newest Warcraft III Wine Print Screen TGA to an RGB PNG."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile

try:
    from PIL import Image
except ImportError as error:  # pragma: no cover - environment diagnostic
    Image = None  # type: ignore[assignment,misc]
    PIL_IMPORT_ERROR = error
else:
    PIL_IMPORT_ERROR = None


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "screenshots" / "tmp"


class ConversionError(Exception):
    """A screenshot could not be safely converted and removed."""


def find_screenshot_dir(prefix: Path, wine_user: str | None) -> Path:
    users_dir = prefix / "drive_c" / "users"
    if not users_dir.is_dir():
        raise ConversionError(f"Wine users directory not found: {users_dir}")

    if wine_user:
        candidates = [users_dir / wine_user / "Documents/Warcraft III/ScreenShots"]
    else:
        candidates = sorted(users_dir.glob("*/Documents/Warcraft III/ScreenShots"))

    existing = [path for path in candidates if path.is_dir()]
    if not existing:
        suffix = f" for Wine user {wine_user!r}" if wine_user else ""
        raise ConversionError(f"Warcraft III ScreenShots directory not found{suffix} under {users_dir}")
    if len(existing) > 1:
        raise ConversionError(
            "multiple Warcraft III screenshot directories found; select one with --wine-user: "
            + ", ".join(str(path) for path in existing)
        )
    return existing[0]


def convert_latest(prefix: Path, wine_user: str | None, output_dir: Path) -> Path:
    if Image is None:
        raise ConversionError(
            "Pillow is required. Run this tool with a Python environment that has Pillow installed."
        ) from PIL_IMPORT_ERROR

    screenshot_dir = find_screenshot_dir(prefix, wine_user)
    candidates = list(screenshot_dir.glob("*.tga")) + list(screenshot_dir.glob("*.TGA"))
    if not candidates:
        raise ConversionError(f"No TGA screenshots found in {screenshot_dir}")
    source = max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{source.stem}.png"
    if output.exists():
        raise ConversionError(f"Output already exists; leaving source TGA untouched: {output}")

    temp_path: Path | None = None
    try:
        with Image.open(source) as image:
            image.load()
            expected_size = image.size
            rgb = image.convert("RGB")

        with tempfile.NamedTemporaryFile(
            prefix=f".{source.stem}.", suffix=".tmp.png", dir=output_dir, delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)
        current_umask = os.umask(0)
        os.umask(current_umask)
        os.chmod(temp_path, 0o666 & ~current_umask)
        rgb.save(temp_path, format="PNG", optimize=True)

        with Image.open(temp_path) as image:
            image.verify()
        with Image.open(temp_path) as image:
            if image.format != "PNG" or image.mode != "RGB" or image.size != expected_size:
                raise ConversionError(
                    f"PNG verification mismatch: format={image.format}, mode={image.mode}, size={image.size}"
                )

        # Create the final name without replacing an existing image.
        try:
            os.link(temp_path, output)
        except FileExistsError as error:
            raise ConversionError(f"Output appeared during conversion; source TGA retained: {output}") from error
        temp_path.unlink()
        temp_path = None

        try:
            source.unlink()
        except OSError as error:
            output.unlink(missing_ok=True)
            raise ConversionError(f"Could not delete source TGA {source}: {error}") from error

        return output
    except ConversionError:
        raise
    except Exception as error:
        raise ConversionError(f"Could not convert {source}: {error}") from error
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_prefix = os.environ.get("WINEPREFIX", str(Path.home() / ".wine-war3"))
    parser.add_argument(
        "--wine-prefix", type=Path, default=Path(default_prefix).expanduser(),
        help="Wine prefix to search (default: WINEPREFIX or ~/.wine-war3)",
    )
    parser.add_argument(
        "--wine-user", help="Wine profile name when the prefix contains multiple users",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"PNG destination (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args(argv)

    try:
        output = convert_latest(
            args.wine_prefix.expanduser().resolve(),
            args.wine_user,
            args.output_dir.expanduser().resolve(),
        )
    except ConversionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    with Image.open(output) as image:
        print(f"Converted and deleted source TGA: {output.stem}.tga")
        print(f"PNG: {output} ({image.mode}, {image.width}x{image.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
