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


def test_r12_candidate_page_is_published_with_its_own_receipt() -> None:
    """R12 passed its own two-instrument gate; it stays fully published beside the active arm."""
    import json
    receipt = json.loads((ROOT / "registry/r12.json").read_text())
    page = (SITE / "r12" / "index.html").read_text(encoding="utf-8")
    assert (SITE / "r12" / receipt["file"]).is_file()
    assert receipt["file"] in page
    assert receipt["audit"]["sha256"] in page
    assert receipt["note"] in page
    assert all(receipt["audit"]["checks"].values())
    assert receipt["audit"]["positive"] == 37654
    # both preregistered instruments must be visible, and the status must match the receipt
    assert "stratified" in page.lower()
    assert ("Proxy gate PASSED" in page) is bool(receipt["gate_passed"])
    assert bool(receipt["gate_locked_blocks_200m"]) is bool(receipt["gate_locked_blocks_200m"])
    assert bool(receipt["gate_stratified_whole_domain"]) is (
        receipt["stratified_instrument"]["delta_vs_incumbent"] > 0)
    assert "no leaderboard score" in page.lower()


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


def test_r11_arms_receipt_is_archived_unchanged() -> None:
    """The parallel R11 arms (A/C/D) keep their receipt, their held TIF and their review."""
    import json
    receipt = json.loads((ROOT / "registry/r11.json").read_text())
    assert (SITE / "r11" / receipt["file"]).is_file()
    assert json.loads((SITE / "r11" / "receipt.json").read_text())["file"] == receipt["file"]
    assert "HOLD" in receipt["status"]
    assert (ROOT / "docs/research/r11-review.md").is_file()


def test_r11f_receipt_and_artefacts_are_archived() -> None:
    """The R11F fusion arm keeps its receipt, both TIFs and its review."""
    import json
    receipt = json.loads((ROOT / "registry/r11f.json").read_text())
    for key in ("candidate", "dfa_candidate"):
        blob = receipt[key]
        assert (SITE / "r11f" / blob["file"]).is_file()
    assert json.loads((SITE / "r11f" / "receipt.json").read_text())["candidate"]["file"] == \
        receipt["candidate"]["file"]
    assert (ROOT / "docs/research/r11f-review.md").is_file()
    assert (ROOT / "docs/research/session-r11f-plan.md").is_file()


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
