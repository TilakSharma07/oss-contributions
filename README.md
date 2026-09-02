# Upstream contributions: nf-core/tools and Galaxy training-material

Two defects found by auditing the tooling that annotates bioinformatics workflow
metadata, each with a measurement over the real corpus, a proposed fix, and a test
suite. Both were found by reading the tools' own source and then quantifying the
consequence — not by running the linters and reading their output, which is exactly
what neither defect produces.

| | nf-core/tools | Galaxy training-material |
|---|---|---|
| Component | `modules_utils.py::load_edam()` | `bin/lint.rb::check_pmids` |
| Symptom | `ontologies: []` written where a term exists | GTN:004 never fires |
| Corpus measured | 1,893 channel elements, 184 modules | 547 tutorials, 35 topics |
| Affected | 513 elements recoverable | 50 links missed, 23 tutorials |
| Tests | 12 passing (pytest) | 16 passing (ruby) |

## 1. nf-core/tools — EDAM ontology map covers 67 of 728 format concepts

`load_edam()` builds its extension map from EDAM.tsv column 14, "File extension".
EDAM 1.25 fills that column for **61 of 728** `format_*` concepts, so BAM
(`format_2572`), FASTA (`format_1929`), VCF (`format_3016`), BED (`format_3003`) and
CRAM (`format_3462`) are absent — the formats nf-core modules mostly emit.

Separately, when the ontology download fails the function returns `{}` and the
caller cannot tell that apart from a successful load. `nf-core modules lint --fix`
then writes `ontologies: []` onto every file-typed channel element, which in
committed YAML reads as "EDAM has no term for this format" — a claim the tool is not
in a position to make when it never loaded the ontology.

Measured over the 184 modules used by `nf-core/rnaseq` and `nf-core/sarek`:

* 249 of 1,893 file channel elements already carry an ontology
* 1,538 carry none; the top extensions are
  `*.` (370), `bam` (108), `fasta` (64), `tbi` (63), `txt` (57)
* keying additionally on preferred labels and single-token exact synonyms takes the
  map from **67 to 798 keys** and makes **513** of those elements
  annotatable
* tokens claimed by more than one format concept are dropped rather than guessed

`reproduce_bug.py` verifies both behaviours against nf-core/tools 4.1.0. For the
caller branch it extracts the `_add_edam_ontologies` closure's own source from the
installed package with `ast` and executes that, so the function under test is
upstream's own code rather than a re-implementation.

```
nf-core-tools/
  ISSUE.md                    the report as filed
  load_edam_proposed.py       proposed replacement, returns (mapping, ok)
  test_load_edam.py           12 tests: both claims + reviewer properties
  reproduce_bug.py            reproduction against the installed package
  audit_ontologies.py         corpus measurement
  edam_recovery.py            coverage-widening measurement
  data/                       raw findings
```

## 2. Galaxy training-material — GTN:004's regex has a doubled slash

`check_pmids` matches `.../pubmed//[0-9]*` — two slashes — while the documenting
comment on the line directly above shows the real URL with one. Real PubMed links
never match, so the check has never fired. Its companion `check_dois` is unaffected.

Across the 547 `tutorial.md` files reachable from the topic API (689 discovered
across all 35 topics; the rest are slides-only or renamed):

| | count |
|---|---|
| links the shipped regex matches | **0** |
| `.../pubmed/<id>` links present | 47 |
| links on the modern `pubmed.ncbi.nlm.nih.gov` host | 3 |
| tutorials with at least one missed link | 23 |

Most affected: `proteomics/protein-id-oms` (11), `proteomics/metaproteomics` (5), `proteomics/protein-id-sg-ps` (4), `proteomics/labelfree-vs-labelled` (3).

The patch drops the duplicated slash, requires at least one digit, allows the
trailing slash PubMed emits, and adds the modern host the check predates.
`test_check_pmids.rb` pins the behaviour in both directions: the shipped pattern
misses all five real-world link forms, the proposed one matches all five, and it
ignores DOI links, the identifier-less PubMed search page, non-PubMed NCBI links,
bare URLs without link text, and existing `{% cite %}` shortcodes.

```
galaxy-training-material/
  ISSUE.md                    the report as filed
  check_pmids.patch           the fix, applies with git apply
  test_check_pmids.rb         16 assertions, ruby
  measure_pmid.py             corpus measurement
  data/pmid_findings.json     per-tutorial counts
```

## Reproducing

```bash
# nf-core (needs nf-core==4.1.0 and EDAM.tsv in the working directory)
python -m venv .venv && .venv/bin/pip install nf-core==4.1.0 pytest
curl -sSLO https://raw.githubusercontent.com/edamontology/edamontology/main/releases/EDAM_1.25.tsv
mv EDAM_1.25.tsv EDAM.tsv
.venv/bin/python reproduce_bug.py
.venv/bin/python -m pytest test_load_edam.py -q

# galaxy
ruby test_check_pmids.rb
python measure_pmid.py          # re-fetches the corpus
```

## Scope left open deliberately

* **81 modules** have `tools[].identifier` empty in `meta.yml`, which the bio.tools
  registry would populate. Those are listed in `nf-core-tools/data/empty_identifiers.json`
  and deliberately left unfilled: the registry was unreachable during the audit, and
  writing identifiers without verifying them against it would put unverified metadata
  upstream.
* `*.` (370 occurrences — a wildcard carrying no extension) and index-file suffixes
  (`tbi`, `fai`, `crai`, `csi`) remain unmapped. Whether an index file should carry the
  format of the file it indexes is a design question for the maintainers, not a bug.
