# Upstream contributions: nf-core/tools, Galaxy training-material, EDAM

Three findings from auditing the tooling that annotates bioinformatics workflow
metadata, each with a measurement over the real corpus and a proposed fix. All three
were found by reading the tools' own source and then quantifying the consequence —
not by running the linters and reading their output, which is exactly what none of
these defects produces.

The three are one causal chain. EDAM records a file extension for a tenth of its
format concepts; nf-core's linter reads only that property, so it annotates almost
nothing; and the Galaxy finding is the same shape of defect — a check that runs
clean because it can never fire, not because the corpus is clean.

| | nf-core/tools | Galaxy training-material | EDAM |
|---|---|---|---|
| Component | `modules_utils.py::load_edam()` | `bin/lint.rb::check_pmids` | `file_extension` property |
| Symptom | `ontologies: []` written where a term exists | GTN:004 never fires | 61 of 612 concepts populated |
| Corpus measured | 1,893 channel elements, 184 modules | 547 tutorials, 35 topics | 612 non-obsolete format concepts |
| Affected | 513 elements recoverable | 50 links missed, 23 tutorials | 219 of 231 index elements unannotated |
| Deliverable | patch + 12 tests (pytest) | patch + 16 tests (ruby) | 6 evidenced values + 3 concept gaps |

## 1. nf-core/tools — the EDAM extension map reaches 61 of 612 live format concepts

`load_edam()` builds its extension map from EDAM.tsv column 14, "File extension".
EDAM 1.25 fills that column for **61 of 612** non-obsolete `format_*` concepts
(728 including obsolete ones), so BAM
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

## 3. EDAM — file_extension is populated for 61 of 612 format concepts

Finding 1 traced back to its cause. The `file_extension` property that nf-core reads
is populated for **61** of the **612** non-obsolete `format_*` concepts in EDAM 1.25.
The tool is reading the right property; the property is empty.

The values proposed to EDAM are not asserted from knowledge — they are taken from
what nf-core module authors independently wrote by hand, restricted to the 184
channel elements pairing exactly one extension with exactly one term (multi-extension
globs cannot attribute a term to an extension, so they are excluded). The method
validates against EDAM itself: for the nine extensions EDAM already records, author
consensus agrees with EDAM's own curation in every case.

| extension | concept | label | annotations agreeing |
|---|---|---|---|
| `bed` | `format_3003` | BED | 6/6 |
| `bam` | `format_2572` | BAM | 5/5 |
| `fasta` | `format_1929` | FASTA | 5/5 |
| `bcf` | `format_3020` | BCF | 4/4 |
| `txt` | `format_2330` | Textual format | 3/3 |
| `gtf` | `format_2306` | GTF | 2/2 |

Where authors disagreed, the disagreement tracks a gap in the ontology rather than
carelessness. `.tbi` appears on 74 channel elements and **none** is annotated — EDAM
carries two non-obsolete concepts for the tabix index (`format_3616` and
`format_3700`) with different parents, and a consumer cannot choose. `.fai` appears
on 51 elements annotated three different ways, because there is no FASTA-index
concept at all; in `nf-core/modules@master`, `freebayes/meta.yml` labels one
`# FASTA index` while pointing at `format_3327`, which is the BAM index. `.crai`
(33), `.csi` (23) and `.dict` (18) have nowhere to point either.

```
edam/
  ISSUE.md                        the report as filed
  edam_extension_coverage.py      reproduces every count in the issue
  evidence_from_modules.py        extracts the evidence table from meta.yml files
  data/                           curated pairs, proposals, index summary
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

# edam
python edam_extension_coverage.py EDAM_1.25.tsv
python evidence_from_modules.py <dir-of-nf-core-meta.yml>
```

## Scope left open deliberately

* **81 modules** have `tools[].identifier` empty in `meta.yml`, which the bio.tools
  registry would populate. Those are listed in `nf-core-tools/data/empty_identifiers.json`
  and deliberately left unfilled: the registry was unreachable during the audit, and
  writing identifiers without verifying them against it would put unverified metadata
  upstream.
* `*.` (370 occurrences) is a wildcard carrying no extension at all. Nothing can map
  it; the pattern would have to change in the module for annotation to be possible.

Index-file suffixes were initially set aside here as "a design question for the
maintainers". That turned out to be wrong, and chasing it produced the EDAM finding
above: `.tbi`, `.fai`, `.crai`, `.csi` and `.dict` are unmapped because EDAM has no
concept for most of them and two competing concepts for the one it does cover. See
`edam/ISSUE.md`.

## Filed upstream

| finding | upstream issue |
|---|---|
| `load_edam()` maps 61 of 728 EDAM format concepts, and a failed download is indistinguishable from "no term exists" | [nf-core/tools#4468](https://github.com/nf-core/tools/issues/4468) |
| GTN:004's PMID regex has a doubled slash, so the check has never fired (0 of 47 links across 23 tutorials) | [galaxyproject/training-material#7092](https://github.com/galaxyproject/training-material/issues/7092) |
| `file_extension` is populated for 61 of 612 non-obsolete format concepts, and downstream tooling reads only that column | [edamontology/edamontology#958](https://github.com/edamontology/edamontology/issues/958) |
