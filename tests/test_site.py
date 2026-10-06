from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs"


class PageAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.ids: list[str] = []
        self.external_blank_links: list[tuple[str, str]] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        if "href" in attributes:
            self.hrefs.append(attributes["href"])
            if attributes.get("target") == "_blank":
                self.external_blank_links.append((attributes["href"], attributes.get("rel", "")))
        if "id" in attributes:
            self.ids.append(attributes["id"])
        if tag == "script":
            self.scripts.append(attributes.get("src", "inline"))


def test_static_site_has_resolving_local_links_and_safe_external_targets() -> None:
    pages = sorted(SITE.glob("*.html"))
    assert len(pages) >= 6
    audits: dict[Path, PageAudit] = {}

    for page in pages:
        audit = PageAudit()
        audit.feed(page.read_text(encoding="utf-8"))
        assert len(audit.ids) == len(set(audit.ids)), f"duplicate IDs in {page.name}"
        assert not audit.scripts, f"unexpected JavaScript in static site: {page.name}"
        assert all(
            "noopener" in rel.split() and "noreferrer" in rel.split()
            for _, rel in audit.external_blank_links
        ), f"unsafe target=_blank link in {page.name}"
        audits[page] = audit

    for page, audit in audits.items():
        for href in audit.hrefs:
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc:
                continue
            target = (page.parent / parsed.path).resolve() if parsed.path else page
            if parsed.path.endswith("/"):
                target /= "index.html"
            assert target.is_file(), f"{page.name} has broken local link: {href}"
            if parsed.fragment and target.suffix == ".html":
                target_audit = audits.get(target)
                if target_audit is None:
                    target_audit = PageAudit()
                    target_audit.feed(target.read_text(encoding="utf-8"))
                assert parsed.fragment in target_audit.ids, (
                    f"{page.name} links to missing anchor: {href}"
                )


def test_homepage_puts_the_verified_download_first() -> None:
    """Active download precedes analysis; format validation is not scientific promotion.

    Reads the current receipt (`registry/r11f.json`) instead of a hard-coded experiment, so this
    asserts a *contract*: the downloadable file named in the receipt is on the page, exists on disk,
    passes its own format audit, and the status banner matches `gate_passed`.
    """
    import json
    home = (SITE / "index.html").read_text(encoding="utf-8")
    assert home.index('id="submission-download"') < home.index('id="gate"')
    receipt = json.loads((ROOT / "registry/r11f.json").read_text())
    candidate = receipt["candidate"]
    assert candidate["file"] in home
    assert (SITE / "r11f" / candidate["file"]).is_file()
    assert candidate["all_finite"] and candidate["in_range"] and candidate["nodata"] is None
    assert candidate["count"] == 1 and candidate["dtype"] == "float32"
    assert candidate["crs"] == "EPSG:32611" and candidate["shape"] == [3730, 3292]
    assert candidate["positive"] == receipt["emissions"]["r11f_fused"]["accepted"]
    if receipt["gate_passed"]:
        assert "Proxy gate passed" in home
    else:
        assert "do not submit" in home
