"""Tests for the proposed load_edam(). Run: python -m pytest test_load_edam.py -q

Requires nf-core==4.1.0 (the version the finding was measured against) and EDAM.tsv
in this directory; see the repository README for the two fetch commands.

Checks the two claims made in the patch docstring, plus the properties a reviewer
would want guarded: no ambiguous term is ever emitted, the curated column wins on
conflict, and a failed load is distinguishable from a successful empty one.
"""
import pathlib
import sys

import pytest
import requests

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import load_edam_proposed as proposed          # noqa: E402

import nf_core.modules.modules_utils as upstream  # noqa: E402

TSV = pathlib.Path(__file__).parent / "EDAM.tsv"
pytestmark = pytest.mark.skipif(not TSV.exists(), reason="EDAM.tsv not fetched")


@pytest.fixture(scope="module")
def data():
    return TSV.read_bytes()


@pytest.fixture(scope="module")
def new_map(data):
    return proposed._parse_edam(data)


@pytest.fixture(scope="module")
def old_map(data, tmp_path_factory):
    d = tmp_path_factory.mktemp("upstream_cache")
    (d / "EDAM.tsv").write_bytes(data)
    orig, upstream.NFCORE_CACHE_DIR = upstream.NFCORE_CACHE_DIR, str(d)
    try:
        return upstream.load_edam()
    finally:
        upstream.NFCORE_CACHE_DIR = orig


# ---------------------------------------------------------------- claim 1
def test_failed_download_is_signalled(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("offline")
    monkeypatch.setattr(proposed.requests, "get", boom)
    mapping, ok = proposed.load_edam(tmp_path)
    assert mapping == {} and ok is False


def test_successful_load_is_signalled(tmp_path, data):
    (tmp_path / "EDAM.tsv").write_bytes(data)
    mapping, ok = proposed.load_edam(tmp_path)
    assert ok is True and len(mapping) > 100


def test_upstream_cannot_distinguish_the_two(old_map, tmp_path, monkeypatch):
    """The behaviour that motivates the change."""
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("offline")
    monkeypatch.setattr(upstream.requests, "get", boom)
    monkeypatch.setattr(upstream, "NFCORE_CACHE_DIR", str(tmp_path))
    assert upstream.load_edam() == {}          # same type and value as a real answer
    assert isinstance(old_map, dict)           # ... which is also a dict


# ---------------------------------------------------------------- claim 2
@pytest.mark.parametrize("ext,concept", [
    ("bam", "format_2572"), ("fasta", "format_1929"), ("vcf", "format_3016"),
    ("bed", "format_3003"), ("cram", "format_3462"),
])
def test_common_formats_now_resolve(new_map, old_map, ext, concept):
    assert ext not in old_map, f"{ext} unexpectedly present upstream; re-measure the claim"
    assert new_map[ext][0].endswith(concept)


def test_coverage_increases(new_map, old_map):
    assert len(old_map) < len(new_map)
    assert set(old_map) <= set(new_map), "widening must not drop an existing key"


def test_curated_column_wins_on_conflict(new_map, old_map):
    for ext, val in old_map.items():
        assert new_map[ext] == val, f"{ext}: curated mapping was overridden"


def test_ambiguous_tokens_are_not_emitted(data):
    """A token claimed by two format concepts must be absent, not guessed."""
    import csv, collections, re
    rows = list(csv.reader(data.decode("utf-8").splitlines(), delimiter="\t"))
    claims = collections.defaultdict(set)
    for r in rows[1:]:
        if not r or not r[0].split("/")[-1].startswith("format"):
            continue
        if any(h in " ".join(r[:3]).lower() for h in proposed._OBSOLETE_HINTS):
            continue
        toks = {r[1].strip().lower()} if len(r) > 1 and r[1].strip() else set()
        if len(r) > 2 and r[2].strip():
            toks |= {s.strip().lower() for s in r[2].split("|")
                     if proposed._EXTENSION_LIKE.match(s.strip().lower())}
        for t in toks:
            claims[t].add(r[0])
    ambiguous = {t for t, v in claims.items() if len(v) > 1}
    assert ambiguous, "expected some ambiguity in EDAM; test would be vacuous otherwise"
    mapping = proposed._parse_edam(data)
    curated = {e for r in rows[1:] if len(r) > 14 and r[14]
               and r[0].split("/")[-1].startswith("format") for e in r[14].split("|")}
    assert not (ambiguous - curated) & set(mapping), "an ambiguous token was emitted"


def test_no_uri_is_fabricated(new_map, data):
    """Every emitted URI must appear verbatim in EDAM.tsv."""
    text = data.decode("utf-8")
    for ext, (uri, _label) in new_map.items():
        assert uri in text, f"{ext} -> {uri} not found in the ontology"
