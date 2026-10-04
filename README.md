# Pinterest Wallpaper Downloader

A Python script that pulls images from a Pinterest board, keeps only the ones that make good wallpapers (at least 1920x1080, roughly 16:9), and saves them to your Documents folder.

## Features

- Downloads from any public Pinterest board URL
- Filters out images that are too small or the wrong aspect ratio
- Lists every skipped image with the reason, so you can rescue the ones you still want
- Interactive selection: download all, specific numbers, a range, or none
- Remembers pins it has already seen, so you can re-run the same board over and over
- Keeps a log (`downloaded.txt`) with the Pinterest pin URL for each image

## Requirements

- Python 3
- [Pillow](https://pypi.org/project/pillow/) (reads image dimensions)
- [gallery-dl](https://github.com/mikf/gallery-dl) (fetches the images from Pinterest)

## Installation

```bash
git clone https://github.com/YonaelT/pinterest-wallpaper-downloader.git
cd pinterest-wallpaper-downloader
python -m venv .venv
source .venv/bin/activate
pip install pillow gallery-dl
```

## Usage

```bash
python pinterest_wallpaper_downloader_v2.py
```

Paste a Pinterest board URL when prompted:

```
Pinterest Wallpaper Downloader v2
========================================
Paste a Pinterest board URL.
Example: https://www.pinterest.com/user/board/

Board URL:
```

The script extracts the board and shows the images that passed the filters (minimum 1920x1080):

```
Found 1 image candidate(s):
------------------------------------------------------------
  1. 1920x1080  (ratio 1.78) - pinterest_317714948739899817.jpg
------------------------------------------------------------

Options:
  d      - Download all
  1,3,5  - Download specific numbers
  1-5    - Download a range
  s      - Skip / download none
  q      - Quit entirely
```

Next it lists the images it skipped, each with a reason, and offers the same options so you can download any of them anyway:

```
26 image(s) were skipped during filtering:
------------------------------------------------------------
  1. 500x500 - pinterest_317714948739223953.png
       Reason: too small (500x500) + aspect ratio 1.00
  2. 512x320 - pinterest_317714948739223941.jpg
       Reason: too small (512x320, min 1920x1080)
  ...
```

When it finishes, you get a summary:

```
Done!
  Passed filters        : 1
  Skipped (shown to you): 26
  Skipped (bad format)  : 27
  Downloaded            : 1

Saved to  : /home/user/Documents/wallpapers
Log file  : /home/user/Documents/wallpapers/downloaded.txt
```

## Output

Everything goes to `~/Documents/wallpapers`:

- The downloaded images
- `downloaded.txt`, a log with the Pinterest pin URL for each image
- `gallery_dl_archive.sqlite`, gallery-dl's skip-list of pins it has already seen


## License

MIT. See [LICENSE](LICENSE).
