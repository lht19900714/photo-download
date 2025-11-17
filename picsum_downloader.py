"""Download random images from picsum.photos."""

from __future__ import annotations

import argparse
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional, Tuple

import requests

PICSUM_URL_TEMPLATE = "https://picsum.photos/{width}/{height}?random={token}"
DEFAULT_WIDTH = 200
DEFAULT_HEIGHT = 300
DEFAULT_COUNT = 50
DEFAULT_DELAY = 0.1  # polite delay between requests
DEFAULT_RETRIES = 3
DEFAULT_TIMEOUT = 30
DEFAULT_DEST = Path(__file__).resolve().parent / "test_photo"

CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download random images from https://picsum.photos/ to a local folder."
        )
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help="Number of random images to download (default: 50)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
        help="Image width in pixels (default: 200)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=DEFAULT_HEIGHT,
        help="Image height in pixels (default: 300)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help="Destination directory (default: ./test_photo)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help="Delay (seconds) between downloads to be gentle to the API (default: 0.1)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help="Number of retries per image on failure (default: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="HTTP timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def build_session(timeout: int) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "photo-download-bot/1.0 (+https://picsum.photos)",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=0)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.request = _wrap_with_timeout(session.request, timeout)
    return session


def _wrap_with_timeout(func, timeout: int):
    def wrapper(method, url, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return func(method, url, **kwargs)

    return wrapper


def guess_extension(content_type: Optional[str]) -> str:
    if not content_type:
        return "jpg"
    return CONTENT_TYPE_EXTENSIONS.get(content_type.lower(), "jpg")


def build_filename(index: int, ext: str) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    random_suffix = uuid.uuid4().hex[:8]
    return f"picsum_{timestamp}_{index:03d}_{random_suffix}.{ext}"


def download_single_image(
    session: requests.Session,
    width: int,
    height: int,
    dest_dir: Path,
    index: int,
    retries: int,
) -> Tuple[bool, Optional[Path]]:
    for attempt in range(1, retries + 1):
        try:
            token = uuid.uuid4().hex
            url = PICSUM_URL_TEMPLATE.format(width=width, height=height, token=token)
            logging.debug("Requesting %s", url)
            response = session.get(url, stream=True)
            response.raise_for_status()

            ext = guess_extension(response.headers.get("Content-Type"))
            filename = build_filename(index, ext)
            file_path = dest_dir / filename

            with open(file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)

            logging.info("[%02d] ✓ Saved %s", index, file_path.name)
            return True, file_path
        except Exception as exc:  # pylint: disable=broad-except
            logging.warning(
                "[%02d] Download failed (attempt %d/%d): %s",
                index,
                attempt,
                retries,
                exc,
            )
            if attempt == retries:
                logging.error("[%02d] Giving up after %d attempts", index, retries)
                return False, None
            time.sleep(1)

    return False, None


def download_random_images(
    count: int,
    width: int,
    height: int,
    dest_dir: Path,
    delay: float,
    retries: int,
    timeout: int,
) -> None:
    if count <= 0:
        raise ValueError("count must be positive")

    ensure_directory(dest_dir)
    session = build_session(timeout)

    logging.info(
        "Downloading %d random images of size %dx%d into %s",
        count,
        width,
        height,
        dest_dir,
    )

    success = 0
    for index in range(1, count + 1):
        ok, _ = download_single_image(session, width, height, dest_dir, index, retries)
        if ok:
            success += 1
        if delay > 0 and index != count:
            time.sleep(delay)

    logging.info("Completed: %d/%d images saved.", success, count)

    if success < count:
        raise SystemExit(1)


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)
    download_random_images(
        count=args.count,
        width=args.width,
        height=args.height,
        dest_dir=args.dest,
        delay=args.delay,
        retries=args.retries,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
