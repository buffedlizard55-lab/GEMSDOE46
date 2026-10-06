from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs"
#: the receipt tag that drives the live pages (built by scripts/build_r12_site.py)
ACTIVE_TAG = "r12"


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
    """Active download precedes analysis; format validation is not scientific promotion."""
    import json
    home = (SITE / "index.html").read_text(encoding="utf-8")
    assert home.index('id="submission-download"') < home.index('id="validation"')
    receipt = json.loads((ROOT / f"registry/{ACTIVE_TAG}.json").read_text())
    assert receipt["file"] in home
    assert (SITE / ACTIVE_TAG / receipt["file"]).is_file()
    assert all(receipt["audit"]["checks"].values())
    assert receipt["audit"]["positive"] == 37654
    # the page must state the gate outcome truthfully whatever it was, plus its limits
    assert "no leaderboard score" in home.lower()
    assert receipt["note"] in home
    assert receipt["audit"]["sha256"] in home
    assert ("Proxy gate PASSED" in home) is bool(receipt["gate_passed"])
    assert ("do not submit" in home) is not bool(receipt["gate_passed"])


def test_executive_summary_explains_how_to_submit() -> None:
    """The submission guide must exist, name the file and cover the known range error."""
    import json
    page = (SITE / "executive-summary.html").read_text(encoding="utf-8")
    receipt = json.loads((ROOT / f"registry/{ACTIVE_TAG}.json").read_text())
    assert 'id="how-to-submit"' in page
    assert receipt["file"] in page
    assert receipt["note"] in page
    assert receipt["audit"]["sha256"] in page
    assert "Predicted values must be in range [0, 1]" in page
    assert "New submission" in page
    assert "https://www.drivendata.org/competitions/306/competition-doe-gems/" in page


def test_r10_receipt_is_archived_unchanged() -> None:
    """The failed R10 arm stays on disk with its own receipt (published negative result)."""
    import json
    receipt = json.loads((ROOT / "registry/r10.json").read_text())
    assert (SITE / "r10" / receipt["file"]).is_file()
    assert json.loads((SITE / "r10" / "receipt.json").read_text())["file"] == receipt["file"]
    assert not receipt["gate_passed"]
    assert receipt["audit"]["positive"] == 37654
    review = (ROOT / "docs/research/r10-review.md").read_text(encoding="utf-8")
    assert "HOLD" in review


def test_r11_receipt_is_archived_unchanged() -> None:
    """The R11 matched-filter arm stays on disk with its own receipt (published negative result)."""
    import json
    receipt = json.loads((ROOT / "registry/r11.json").read_text())
    assert (SITE / "r11" / receipt["file"]).is_file()
    assert json.loads((SITE / "r11" / "receipt.json").read_text())["file"] == receipt["file"]
    assert receipt["status"] == "HOLD_DO_NOT_SUBMIT"
    assert receipt["audit"]["positive"] == 37654


def test_h47_receipt_is_archived_unchanged() -> None:
    """The screened H47 arm stays on disk with its own receipt (published negative result)."""
    import json
    receipt = json.loads((ROOT / "registry/h47.json").read_text())
    emission = receipt["emission"]
    name = Path(emission["zeros"]["path"]).name
    assert (SITE / "downloads" / "h47" / name).is_file()
    audit = emission["zeros"]["audit"]
    assert audit["passes"] is True
    assert audit["positive_px"] == emission["emitted_px"] == 37654
    assert receipt["screen"]["verdict"] == "HOLD_DO_NOT_SUBMIT"
    assert receipt["screen"]["full"]["delta_vs_C"] < 0
