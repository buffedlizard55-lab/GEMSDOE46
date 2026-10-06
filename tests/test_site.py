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


def test_homepage_puts_the_screened_download_first() -> None:
    """Active download precedes the validation evidence; format validation is not promotion."""
    import json
    home = (SITE / "index.html").read_text(encoding="utf-8")
    assert home.index('id="submission-download"') < home.index('id="validation"')
    receipt = json.loads((ROOT / "registry/h47.json").read_text())
    emission = receipt["emission"]
    name = Path(emission["zeros"]["path"]).name
    assert name in home
    assert (SITE / "downloads" / "h47" / name).is_file()
    audit = emission["zeros"]["audit"]
    assert audit["passes"] is True
    assert audit["positive_px"] == emission["emitted_px"] == 37654
    assert audit["out_of_range_px"] == 0
    # the page must state the measured verdict rather than imply a score
    assert "HOLD" in home and "do not submit" in home.lower()
    assert receipt["screen"]["verdict"] == "HOLD_DO_NOT_SUBMIT"
    assert receipt["screen"]["full"]["delta_vs_C"] < 0


def test_r10_receipt_is_archived_unchanged() -> None:
    """The failed R10 arm stays on disk with its own receipt (published negative result)."""
    import json
    receipt = json.loads((ROOT / "registry/r10.json").read_text())
    assert (SITE / "r10" / receipt["file"]).is_file()
    assert json.loads((SITE / "r10" / "receipt.json").read_text())["file"] == receipt["file"]
    assert not receipt["gate_passed"]
    assert receipt["audit"]["positive"] == 37654
