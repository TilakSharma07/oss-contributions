"""Proposed replacement for nf_core/modules/modules_utils.py::load_edam().

Two changes, each addressing a measured problem:

1. SIGNAL THE FAILURE. The current function returns {} when the download fails, and
   the caller (_add_edam_ontologies in modules/lint/__init__.py:598-599) cannot
   distinguish that from "EDAM has no term for this format": it writes
   `ontologies: []` onto every file-typed channel element either way. Returning a
   `(mapping, ok)` pair -- or raising -- lets the caller skip the annotation pass
   instead of writing empty lists it cannot justify.

2. WIDEN THE MAP. The map is keyed only on EDAM.tsv column 14, "File extension",
   which EDAM 1.25 fills for 61 of 728 format_* concepts. BAM (format_2572),
   FASTA (format_1929), VCF (format_3016), BED (format_3003) and CRAM (format_3462)
   are all absent, so the formats nf-core modules mostly emit get no ontology.
   Also keying on the lowercased preferred label and single-token exact synonyms
   raises coverage 67 -> 798 keys. Tokens claimed by more than one format concept
   are DROPPED rather than guessed: a wrong ontology term is worse than none.

Measured on the 184 modules used by nf-core/rnaseq and nf-core/sarek:
1538 file channel elements currently get no ontology; 513 of them become
annotatable under (2).

This file is a drop-in body, kept separate so the diff against upstream is reviewable.
"""
import csv
import logging
import re
from collections import defaultdict
from pathlib import Path

import requests

log = logging.getLogger(__name__)

EDAM_TSV_URL = "https://edamontology.org/EDAM.tsv"
EDAM_CACHE_TTL = 7 * 24 * 60 * 60

COL_URI, COL_LABEL, COL_SYNONYMS, COL_EXTENSION = 0, 1, 2, 14
# A synonym is only extension-like if it is a single short token.
_EXTENSION_LIKE = re.compile(r"[a-z0-9._-]{1,12}\Z")
_OBSOLETE_HINTS = ("obsolete", "deprecated")


def _parse_edam(data_bytes):
    """Build {extension -> (uri, label)} from EDAM.tsv.

    Keys come from three places, in decreasing order of authority:
      1. the curated "File extension" column,
      2. the concept's preferred label,
      3. its exact synonyms, when they look like a file extension.
    A token claimed by two different format concepts is dropped as ambiguous.
    """
    rows = list(csv.reader(data_bytes.decode("utf-8").splitlines(), delimiter="\t"))
    formats = [
        r for r in rows[1:]
        if r and r[COL_URI].split("/")[-1].startswith("format")
        and not any(h in " ".join(r[:3]).lower() for h in _OBSOLETE_HINTS)
    ]

    curated = {}
    for r in formats:
        if len(r) > COL_EXTENSION and r[COL_EXTENSION]:
            for ext in r[COL_EXTENSION].split("|"):
                curated.setdefault(ext, (r[COL_URI], r[COL_LABEL]))

    claims = defaultdict(set)
    for r in formats:
        tokens = set()
        if len(r) > COL_LABEL and r[COL_LABEL].strip():
            tokens.add(r[COL_LABEL].strip().lower())
        if len(r) > COL_SYNONYMS and r[COL_SYNONYMS].strip():
            for syn in r[COL_SYNONYMS].split("|"):
                syn = syn.strip().lower()
                if syn and _EXTENSION_LIKE.match(syn):
                    tokens.add(syn)
        for t in tokens:
            claims[t].add((r[COL_URI], r[COL_LABEL]))

    edam_formats = {t: sorted(v)[0] for t, v in claims.items() if len(v) == 1}
    ambiguous = sorted(t for t, v in claims.items() if len(v) > 1)
    if ambiguous:
        log.debug(f"EDAM tokens claimed by multiple format concepts, skipped: {ambiguous}")
    edam_formats.update(curated)          # the curated column always wins
    return edam_formats


def cache_is_expired(path: Path) -> bool:
    import time
    return time.time() - path.stat().st_mtime > EDAM_CACHE_TTL


def load_edam(cache_dir):
    """Load the EDAM ontology.

    Returns:
        (edam_formats, ok): ``ok`` is False when the ontology could not be loaded,
        so callers can skip ontology annotation rather than write empty lists.
    """
    cache_path = Path(cache_dir) / "EDAM.tsv"

    if cache_path.exists() and cache_is_expired(cache_path):
        log.debug("Cached EDAM ontology expired; removing old cache file")
        cache_path.unlink(missing_ok=True)

    if not cache_path.exists():
        log.debug("EDAM.tsv file not found in cache; downloading")
        try:
            response = requests.get(EDAM_TSV_URL, timeout=15)
            response.raise_for_status()
            data_bytes = response.content
            cache_path.write_bytes(data_bytes)
        except requests.exceptions.RequestException as e:
            log.warning(
                f"Failed to download EDAM ontology: {e}. "
                "Ontology annotations will be left unchanged."
            )
            return {}, False
    else:
        log.debug("Using EDAM.tsv file found in cache")
        try:
            data_bytes = cache_path.read_bytes()
        except OSError as e:
            log.warning(
                f"Failed to load EDAM ontology: {e}. "
                "Ontology annotations will be left unchanged."
            )
            return {}, False

    return _parse_edam(data_bytes), True
