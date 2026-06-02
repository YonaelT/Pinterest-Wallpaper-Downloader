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
) -> tuple[list[tuple[Path, int, int]], list[tuple[Path, int, int, str]], int]:
    """
    Scan all files and sort them into:
      - candidates: passed all filters
      - skipped_list: valid image format but failed resolution or aspect ratio,
                      each entry includes a reason string
      - skipped_non_image: count of files with unsupported formats (always excluded)

    Returns: (candidates, skipped_list, skipped_non_image)
    """
    skipped_non_image = 0
    candidates: list[tuple[Path, int, int]] = []
    skipped_list: list[tuple[Path, int, int, str]] = []

    files = [p for p in temp_dir.rglob("*") if p.is_file()]
    files.sort()

    for path in files:
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            skipped_non_image += 1
            continue

        try:
            with Image.open(path) as img:
                width, height = img.size
        except Exception:
            skipped_non_image += 1
            continue

        too_small = width < MIN_WIDTH or height < MIN_HEIGHT
        bad_ratio = not is_allowed_aspect_ratio(width, height)

        if too_small and bad_ratio:
            reason = f"too small ({width}x{height}) + aspect ratio {width/height:.2f}"
            skipped_list.append((path, width, height, reason))
        elif too_small:
            reason = f"too small ({width}x{height}, min {MIN_WIDTH}x{MIN_HEIGHT})"
            skipped_list.append((path, width, height, reason))
        elif bad_ratio:
            reason = f"aspect ratio {width/height:.2f} (outside 16:9 tolerance)"
            skipped_list.append((path, width, height, reason))
        else:
            candidates.append((path, width, height))

    return candidates, skipped_list, skipped_non_image


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

    return list(dict.fromkeys(indices))


def choose_candidates(
    candidates: list[tuple[Path, int, int]],
    label: str = "image candidate",
    note: str | None = None,
) -> list[tuple[Path, int, int]] | None:
    """Show a candidate list and ask the user what to download.
    Returns None if user quits entirely, empty list if they skip."""
    if not candidates:
        return []

    print(f"\nFound {len(candidates)} {label}(s):")
    if note:
        print(f"  Note: {note}")
    print("-" * 60)
    for i, (path, w, h) in enumerate(candidates, 1):
        print(f"  {i}. {w}x{h}  (ratio {w/h:.2f}) - {path.name}")
    print("-" * 60)
    print("\nOptions:")
    print("  d      - Download all")
    print("  1,3,5  - Download specific numbers")
    print("  1-5    - Download a range")
    print("  s      - Skip / download none")
    print("  q      - Quit entirely")

    while True:
        selection = input("\nSelect: ").strip().lower()
        if selection == "q":
            return None
        if selection in ("s", ""):
            return []
        parsed = parse_selection(selection, len(candidates))
        if parsed is None:
            print("Invalid selection. Try again.")
            continue
        return [candidates[i] for i in parsed]


def choose_skipped(
    skipped_list: list[tuple[Path, int, int, str]],
) -> list[tuple[Path, int, int]] | None:
    """Show all skipped images with their skip reason and let the user pick any.
    Returns None if user quits entirely, empty list if they skip."""
    if not skipped_list:
        return []

    print(f"\n{len(skipped_list)} image(s) were skipped during filtering:")
    print("-" * 60)
    for i, (path, w, h, reason) in enumerate(skipped_list, 1):
        print(f"  {i}. {w}x{h} - {path.name} Reason: {reason}")
    print("-" * 60)
    print("\nOptions:")
    print("  d      - Download all")
    print("  1,3,5  - Download specific numbers")
    print("  1-5    - Download a range")
    print("  s      - Skip / download none")
    print("  q      - Quit entirely")

    while True:
        selection = input("\nSelect: ").strip().lower()
        if selection == "q":
            return None
        if selection in ("s", ""):
            return []
        parsed = parse_selection(selection, len(skipped_list))
        if parsed is None:
            print("Invalid selection. Try again.")
            continue
        return [(skipped_list[i][0], skipped_list[i][1], skipped_list[i][2]) for i in parsed]


def keep_high_res_images(selected: list[tuple[Path, int, int]], output_dir: Path) -> int:
    downloaded = 0
    seen_hashes: set[str] = set()
    batch_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    for path, width, height in selected:
        digest = file_sha1(path)
        if digest in seen_hashes:
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

        candidates, skipped_list, skipped_non_image = collect_image_candidates(temp_dir)

        if not candidates and not skipped_list:
            print("No downloadable image candidates found on this board.")
            print(f"Skipped (unsupported format): {skipped_non_image}")
            return

        selected: list[tuple[Path, int, int]] = []

        # --- Step 1: main candidates ---
        if candidates:
            result = choose_candidates(candidates, label="image candidate")
            if result is None:
                return
            selected.extend(result)
        else:
            print("\nNo images passed the filters.")

        # --- Step 2: show ALL skipped images ---
        if skipped_list:
            result2 = choose_skipped(skipped_list)
            if result2 is None:
                return
            selected.extend(result2)

        if not selected:
            print("\nNo images selected. Exiting.")
            return

        downloaded = keep_high_res_images(selected, output_dir)

    print("\nDone!")
    print(f"  Passed filters        : {len(candidates)}")
    print(f"  Skipped (shown to you): {len(skipped_list)}")
    print(f"  Skipped (bad format)  : {skipped_non_image}")
    print(f"  Downloaded            : {downloaded}")
    print(f"\nSaved to: {output_dir}")


if __name__ == "__main__":
    main()
