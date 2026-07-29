#!/usr/bin/env python3
"""Run deterministic checks against the static publication artifact."""

from __future__ import annotations

import json
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "site"
SOURCE_DIR = ROOT / "source-assets" / "website-graphics"
MAX_PLAY_STORE_BYTES = 1_000_000
PROMOTIONAL_TEXT = (
    "Reimagining play through fun, inclusive games that inspire learning, "
    "creativity, cognitive growth, and meaningful connection for every age."
)
PRODUCT_SLUGS = (
    "bomb-duel-arena",
    "mindful-adventures",
    "imagine-world",
    "curiosity-lab",
    "tales-unfolded",
)


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.class_counts: Counter[str] = Counter()
        self.ids: set[str] = set()
        self.references: list[tuple[str, str, str]] = []
        self.images: list[dict[str, str]] = []
        self.fragment_links: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = {name: value or "" for name, value in attrs}

        for class_name in attributes.get("class", "").split():
            self.class_counts[class_name] += 1

        element_id = attributes.get("id")
        if element_id:
            if element_id in self.ids:
                raise AssertionError(f"Duplicate HTML id: {element_id}")
            self.ids.add(element_id)

        if tag == "img":
            self.images.append(attributes)

        for attribute_name in ("href", "src"):
            reference = attributes.get(attribute_name)
            if reference:
                self.references.append((tag, attribute_name, reference))
                if reference.startswith("#"):
                    self.fragment_links.append(reference[1:])

        srcset = attributes.get("srcset")
        if srcset:
            for candidate in srcset.split(","):
                reference = candidate.strip().split()[0]
                self.references.append((tag, "srcset", reference))


def assert_required_files() -> None:
    required_files = (
        "index.html",
        "style.css",
        "site.js",
        "manifest.webmanifest",
        "robots.txt",
        "sitemap.xml",
        ".nojekyll",
        "assets/brand/logo-transparent.png",
        "assets/brand/favicon.ico",
        "assets/brand/favicon-32.png",
        "assets/brand/apple-touch-icon.png",
        "assets/artwork/social-preview.jpg",
        "assets/play-store/developer-icon.png",
        "assets/play-store/header-image.jpg",
    )

    for relative_path in required_files:
        path = SITE_DIR / relative_path
        if not path.is_file() or path.stat().st_size == 0:
            raise AssertionError(f"Required public file is missing or empty: {path}")

    for number in range(1, 9):
        for suffix in (".webp", "-960.webp"):
            path = SITE_DIR / "assets" / "artwork" / f"reimagined-studio-{number}{suffix}"
            if not path.is_file() or path.stat().st_size == 0:
                raise AssertionError(f"Required artwork derivative is missing: {path}")

    for source_name in ("logo.jpeg", *(f"reimagined-studio-{number}.jpeg" for number in range(1, 9))):
        path = SOURCE_DIR / source_name
        if not path.is_file() or path.stat().st_size == 0:
            raise AssertionError(f"Required source artwork is missing: {path}")


def assert_reference_exists(reference: str, source_file: Path) -> None:
    parsed = urlsplit(reference)
    if parsed.scheme in {"http", "https", "mailto", "data"} or reference.startswith("#"):
        return

    if reference.startswith("/"):
        raise AssertionError(f"Root-absolute reference breaks project Pages: {reference}")

    relative_path = unquote(parsed.path)
    target = (source_file.parent / relative_path).resolve()
    if SITE_DIR.resolve() not in target.parents and target != SITE_DIR.resolve():
        raise AssertionError(f"Reference escapes the publication boundary: {reference}")
    if not target.is_file():
        raise AssertionError(f"Broken local reference in {source_file.name}: {reference}")


def assert_html() -> None:
    index_path = SITE_DIR / "index.html"
    html = index_path.read_text(encoding="utf-8")
    parser = SiteParser()
    parser.feed(html)

    for _, _, reference in parser.references:
        assert_reference_exists(reference, index_path)

    for fragment in parser.fragment_links:
        if fragment and fragment not in parser.ids:
            raise AssertionError(f"Broken in-page link: #{fragment}")

    for image in parser.images:
        if "alt" not in image:
            raise AssertionError(f"Image is missing an alt attribute: {image.get('src')}")
        if not image.get("width") or not image.get("height"):
            raise AssertionError(
                f"Image is missing intrinsic dimensions: {image.get('src')}"
            )

    if parser.class_counts["benefit-grid"] != 1:
        raise AssertionError("Expected one semantic benefit list")
    if parser.class_counts["benefit-icon"] != 5:
        raise AssertionError("Expected five inline-SVG benefit icons")
    if parser.class_counts["product-card"] != 5:
        raise AssertionError("Expected five product cards")
    if html.count("<details>") != 5:
        raise AssertionError("Expected five native product disclosures")
    if html.count("<summary>") != 5:
        raise AssertionError("Expected five accessible product summaries")

    for number in (1, 2, 3, 4, 5, 7, 8):
        if f"reimagined-studio-{number}.webp" not in html:
            raise AssertionError(f"Artwork {number} is not used by the public page")

    for product_slug in PRODUCT_SLUGS:
        if f"assets/products/{product_slug}.webp" not in html:
            raise AssertionError(
                f"Product artwork derived from artwork 6 is not used: {product_slug}"
            )

    expected_text = (
        "For All Ages",
        "Build Skills",
        "Inspire Growth",
        "Positive Impact",
        "Better Together",
        "Bomb Duel Arena",
        "Mindful Adventures",
        "Imagine World",
        "Curiosity Lab",
        "Tales Unfolded",
        "awo.edutainment+info@gmail.com",
        "©",
    )
    for text in expected_text:
        if text not in html:
            raise AssertionError(f"Expected public content is missing: {text}")

    forbidden_references = (".agent/", ".idea/", "source-assets/", "../")
    for forbidden_reference in forbidden_references:
        if forbidden_reference in html:
            raise AssertionError(
                f"Repository-only path leaked into public HTML: {forbidden_reference}"
            )


def assert_manifest() -> None:
    manifest_path = SITE_DIR / "manifest.webmanifest"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("start_url") != "./" or manifest.get("scope") != "./":
        raise AssertionError("Manifest must use project-relative start_url and scope")

    for icon in manifest.get("icons", []):
        assert_reference_exists(icon["src"], manifest_path)


def assert_image(
    relative_path: str,
    expected_size: tuple[int, int],
    *,
    must_be_opaque: bool,
    max_bytes: int | None = None,
) -> None:
    path = SITE_DIR / relative_path
    with Image.open(path) as image:
        if image.size != expected_size:
            raise AssertionError(
                f"{relative_path} has size {image.size}, expected {expected_size}"
            )

        if must_be_opaque:
            if image.mode in {"RGBA", "LA"}:
                alpha = image.getchannel("A")
                if alpha.getextrema() != (255, 255):
                    raise AssertionError(f"{relative_path} must not be transparent")
            elif image.mode == "P" and "transparency" in image.info:
                raise AssertionError(f"{relative_path} must not be transparent")

    if max_bytes is not None and path.stat().st_size > max_bytes:
        raise AssertionError(
            f"{relative_path} is {path.stat().st_size} bytes; maximum is {max_bytes}"
        )


def assert_images() -> None:
    assert_image(
        "assets/play-store/developer-icon.png",
        (512, 512),
        must_be_opaque=True,
        max_bytes=MAX_PLAY_STORE_BYTES,
    )
    assert_image(
        "assets/play-store/header-image.jpg",
        (4096, 2304),
        must_be_opaque=True,
        max_bytes=MAX_PLAY_STORE_BYTES,
    )

    for slug in PRODUCT_SLUGS:
        assert_image(
            f"assets/products/{slug}.webp",
            (640, 700),
            must_be_opaque=True,
        )

    logo_path = SITE_DIR / "assets" / "brand" / "logo-transparent.png"
    with Image.open(logo_path) as logo:
        if logo.mode != "RGBA":
            raise AssertionError("Reusable logo must use RGBA")
        alpha_extrema = logo.getchannel("A").getextrema()
        if alpha_extrema != (0, 255):
            raise AssertionError(
                f"Reusable logo needs transparent and opaque pixels: {alpha_extrema}"
            )


def main() -> None:
    assert_required_files()
    assert_html()
    assert_manifest()
    assert_images()

    if len(PROMOTIONAL_TEXT) > 140:
        raise AssertionError(
            f"Promotional text is {len(PROMOTIONAL_TEXT)} characters; maximum is 140"
        )

    print("Static site verification passed")
    print(f"Promotional text length: {len(PROMOTIONAL_TEXT)}/140")
    print(
        "Play Store icon: "
        f"{(SITE_DIR / 'assets/play-store/developer-icon.png').stat().st_size} bytes"
    )
    print(
        "Play Store header: "
        f"{(SITE_DIR / 'assets/play-store/header-image.jpg').stat().st_size} bytes"
    )


if __name__ == "__main__":
    main()
