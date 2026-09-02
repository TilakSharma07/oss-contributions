# nf-core/tools: EDAM ontology map covers 67 of 728 format concepts, and a failed download is indistinguishable from "no term exists"

## Summary

Two defects in `nf_core/modules/modules_utils.py::load_edam()` and its caller
`nf_core/modules/lint/__init__.py::_add_edam_ontologies()` cause
`nf-core modules lint --fix` to write `ontologies: []` onto channel elements
that do have an EDAM term.

**1. The map is built from one sparsely-populated column.**
`load_edam()` keys the extension map on EDAM.tsv column 14, "File extension":

```python
if fields[0].split("/")[-1].startswith("format") and fields[14]:
```

EDAM 1.25 populates that column for **61 of 728** `format_*` concepts. So BAM
(`format_2572`), FASTA (`format_1929`), VCF (`format_3016`), BED (`format_3003`)
and CRAM (`format_3462`) — the formats nf-core modules mostly emit — are absent
from the map, and every channel element carrying them gets an empty ontology list.

**2. A failed download is silently indistinguishable from an empty answer.**
On `RequestException`, `load_edam()` logs a warning and returns `{}`. The caller
cannot tell that apart from a successful load, so it still runs the annotation pass
and writes, for every file-typed element (`lint/__init__.py:598-599`):

```python
elif "type" in section and section["type"] == "file":
    section["ontologies"] = []
```

An explicit empty list in committed YAML reads as "EDAM has no term for this
format" — a claim the tool is not in a position to make when it never loaded the
ontology.

## Measurement

Over the 184 modules used by `nf-core/rnaseq` and `nf-core/sarek`
(1,893 file-typed channel elements):

| | count |
|---|---|
| ontologies already populated | 249 |
| empty, extension **is** in the current map (mis-annotated) | 3 |
| empty, extension not in the current map | 1,538 |
| empty, no `pattern` field | 103 |

Of those 1,538, the most frequent extensions are
`bam` (108), `fasta` (64), `txt` (57), `bai` (56), `cram` (49), `bed` (33), `vcf` (32).

Also keying the map on each concept's lowercased preferred label and its
single-token exact synonyms takes it from **67 to 798 keys**
and makes **513 of the 1,538** elements annotatable. Tokens claimed by
more than one format concept (7 shown in the analysis output) are dropped rather
than guessed — a wrong ontology term is worse than a missing one.

The remainder stays unmapped, led by `*.` (370 — a wildcard with no extension),
`tbi` (63), `fai` (42), `crai` (38), `csi` (21). Index-file suffixes look like a
separate question and are out of scope here.

## Reproduction

`reproduce_bug.py` runs against nf-core/tools 4.1.0 and checks both behaviours by
calling the real functions. For the caller branch it extracts the
`_add_edam_ontologies` closure's own source from the installed package via `ast`
and executes that, rather than re-implementing it — the function under test is
upstream's own bytes. Driving `ModuleLint.update_meta_yml_file()` end-to-end was
attempted first but needs a `nextflow` binary and a clonable git remote, neither
available in this sandbox.

```
$ nfvenv/bin/python reproduce_bug.py
  nf-core 4.1.0
  [PASS] A1 load_edam() returns empty dict when the download fails
  [PASS] A2 the failure is not signalled to the caller (no exception, no sentinel)
  extracted upstream closure: 42 lines
  [PASS] A3 real closure + empty map writes an explicit empty ontologies list
  load_edam() with a real EDAM.tsv: 67 extensions
  [PASS] B 'bam' is absent from the map built by load_edam()
  [PASS] B 'fasta' is absent    [PASS] B 'vcf' is absent
  [PASS] B 'bed' is absent      [PASS] B 'cram' is absent
  [PASS] B 'fastq' IS present
  EDAM 1.25: 61/728 format concepts carry a File extension value
```

## Proposed fix

`patch/load_edam_proposed.py` — returns `(mapping, ok)` so the caller can skip
annotation instead of writing empty lists, and widens the key set as measured. The
curated "File extension" column always wins on conflict; obsolete/deprecated
concepts are skipped. 12 tests in `test_patch.py` cover both claims plus the
properties a reviewer would want guarded: no ambiguous token is emitted, widening
never drops an existing key, the curated mapping is never overridden, a failed load
is distinguishable from a successful one, and every emitted URI appears verbatim in
EDAM.tsv.

## Note on a related finding

81 modules in the same set have `tools[].identifier` empty in `meta.yml`, which the
bio.tools registry would populate. I could not fill those: bio.tools resolves into a
private address range from this environment, and writing identifiers I could not
verify against the registry would be fabrication. The list is available if useful.
