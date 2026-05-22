#!/usr/bin/env python3
"""
Pinterest Wallpaper Downloader (v2)

A clean approach that delegates board extraction to gallery-dl, then keeps only
high-resolution images in ~/Desktop/wallpapers.

Dependencies:
    pip install gallery-dl Pillow
"""

import hashlib
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image

MIN_WIDTH = 1280
MIN_HEIGHT = 720
TARGET_ASPECT_RATIO = 16 / 9
ASPECT_RATIO_TOLERANCE = 0.15
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def prompt_board_url() -> str:
    print("Pinterest Wallpaper Downloader v2")
    print("=" * 40)
    print("Paste a Pinterest board URL.")
    print("Example: https://www.pinterest.com/user/board/\n")

    while True:
        url = input("Board URL: ").strip()
        if not url:
            print("Please enter a URL.")
            continue
        if not url.startswith("http"):
            url = f"https://{url}"
        if "pinterest.com" not in url:
            print("That does not look like a Pinterest URL. Try again.")
            continue
        return url


def resolve_gallery_dl_command() -> list[str] | None:
    exe = shutil.which("gallery-dl")
    if exe:
        return [exe]

    python_exe = shutil.which("python3") or shutil.which("python")
    if not python_exe:
        return None
    return [python_exe, "-m", "gallery_dl"]


def run_gallery_dl(board_url: str, temp_dir: Path) -> tuple[bool, str]:
    cmd_prefix = resolve_gallery_dl_command()
    if not cmd_prefix:
        return False, "Could not find gallery-dl or python executable."

    cmd = [
        *cmd_prefix,
        "-d",
        str(temp_dir),
        "--no-mtime",
        board_url,
    ]

    try:
        result = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception as exc:
        return False, f"Failed to launch gallery-dl: {exc}"

    output = (result.stdout or "").strip()
    if result.returncode != 0:
        return False, output or f"gallery-dl failed with exit code {result.returncode}"
    return True, output


def file_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def is_allowed_aspect_ratio(width: int, height: int) -> bool:
    ratio = width / height
    min_ratio = TARGET_ASPECT_RATIO * (1 - ASPECT_RATIO_TOLERANCE)
    max_ratio = TARGET_ASPECT_RATIO * (1 + ASPECT_RATIO_TOLERANCE)
    return min_ratio <= ratio <= max_ratio


def collect_image_candidates(
    temp_dir: Path,
) -> tuple[list[tuple[Path, int, int]], int, int, int]:
    """
    Return downloadable image candidates and skip counts:
    (candidates, skipped_non_image, skipped_small, skipped_aspect)
    """
    skipped_non_image = 0
    skipped_small = 0
    skipped_aspect = 0
    candidates: list[tuple[Path, int, int]] = []

    files = [p for p in temp_dir.rglob("*") if p.is_file()]
    files.sort()

    for path in files:
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            print(f"Skipping '{path.name}': Not an allowed image type.")
            skipped_non_image += 1
            continue
        try:
            with Image.open(path) as img:
                width, height = img.size
        except Exception as e:
            print(f"Skipping '{path.name}': Could not open or read image ({e}).")
            skipped_non_image += 1
            continue

        if width < MIN_WIDTH or height < MIN_HEIGHT:
            print(f"Skipping '{path.name}': Resolution {width}x{height} is below minimum {MIN_WIDTH}x{MIN_HEIGHT}.")
            skipped_small += 1
            continue

        if not is_allowed_aspect_ratio(width, height):
            print(f"Skipping '{path.name}': Aspect ratio {width/height:.2f} is outside 16:9 tolerance ({TARGET_ASPECT_RATIO * (1 - ASPECT_RATIO_TOLERANCE):.2f}-{TARGET_ASPECT_RATIO * (1 + ASPECT_RATIO_TOLERANCE):.2f}).")
            skipped_aspect += 1
            continue

        candidates.append((path, width, height))

    return candidates, skipped_non_image, skipped_small, skipped_aspect


def parse_selection(choice: str, total: int) -> list[int] | None:
    """Parse 1-based selection syntax like d, 1,3,5, 2-7, q."""
    choice = choice.strip().lower()
    if choice == "q":
        return []
    if choice == "d":
        return list(range(total))

    indices: list[int] = []
    try:
        parts = choice.replace(" ", "").split(",")
        for part in parts:
            if not part:
                continue
            if "-" in part:
                start_s, end_s = part.split("-", 1)
                start = int(start_s)
                end = int(end_s)
                if start < 1 or end < 1 or start > end or end > total:
                    return None
                indices.extend(range(start - 1, end))
            else:
                idx = int(part)
                if idx < 1 or idx > total:
                    return None
                indices.append(idx - 1)
    except ValueError:
        return None

    # Preserve order and remove duplicates.
    return list(dict.fromkeys(indices))


def choose_candidates(candidates: list[tuple[Path, int, int]]) -> list[tuple[Path, int, int]] | None:
    """Show candidate list and ask user what to download."""
    if not candidates:
        return []

    print(f"\nFound {len(candidates)} image candidate(s):")
    print("-" * 60)
    for i, (path, w, h) in enumerate(candidates, 1):
        print(f"  {i}. {w}x{h} - {path.name}")
    print("-" * 60)
    print("\nOptions:")
    print("  d      - Download all")
    print("  1,3,5  - Download specific numbers")
    print("  1-5    - Download a range")
    print("  q      - Quit")

    selection = input("\nSelect: ")
    parsed = parse_selection(selection, len(candidates))
    if parsed is None:
        print("Invalid selection. Exiting.")
        return None
    if not parsed:
        return []
    return [candidates[i] for i in parsed]


def keep_high_res_images(selected: list[tuple[Path, int, int]], output_dir: Path) -> int:
    downloaded = 0
    seen_hashes: set[str] = set()
    batch_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    for path, width, height in selected:
        digest = file_sha1(path)
        if digest in seen_hashes:
            print(f"Skipping duplicate '{path.name}'.")
            continue
        seen_hashes.add(digest)

        ext = path.suffix.lower()
        base_filename = f"{batch_stamp}_{downloaded + 1:03d}"
        destination = output_dir / f"{base_filename}{ext}"
        collision = 1
        while destination.exists():
            destination = output_dir / f"{base_filename}_{collision:02d}{ext}"
            collision += 1
        shutil.copy2(path, destination)
        print(f"Downloaded '{path.name}' to '{destination.name}'.")
        downloaded += 1

    return downloaded


def main() -> None:
    board_url = prompt_board_url()
    output_dir = Path.home() / "Desktop" / "wallpapers"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nDestination: {output_dir}")
    print(f"Minimum resolution: {MIN_WIDTH}x{MIN_HEIGHT}")
    print("Extracting board media with gallery-dl...\n")

    with tempfile.TemporaryDirectory(prefix="pinterest_v2_") as tmp:
        temp_dir = Path(tmp)
        ok, info = run_gallery_dl(board_url, temp_dir)
        if not ok:
            print("Failed to extract board media.")
            print("\nDetails:")
            print(info)
            print("\nInstall/verify dependencies in your venv:")
            print("  pip install gallery-dl Pillow")
            return

        candidates, skipped_non_image, skipped_small, skipped_aspect = collect_image_candidates(temp_dir)
        if not candidates:
            print("No downloadable image candidates found on this board.")
            print(f"Skipped (non-image/unsupported): {skipped_non_image}")
            print(f"Skipped (too small): {skipped_small}")
            print(f"Skipped (not near 16:9): {skipped_aspect}")
            return

        selected = choose_candidates(candidates)
        if selected is None:
            return
        if not selected:
            print("No images selected. Exiting.")
            return

        downloaded = keep_high_res_images(selected, output_dir)

    print("Done!")
    print(f"  Eligible images listed: {len(candidates)}")
    print(f"  Downloaded wallpapers: {downloaded}")
    print(f"  Skipped (too small): {skipped_small}")
    print(f"  Skipped (not near 16:9): {skipped_aspect}")
    print(f"  Skipped (non-image/unsupported): {skipped_non_image}")
    print(f"\nSaved to: {output_dir}")


if __name__ == "__main__":
    main()
