# `file_extension` is populated for 61 of 612 format concepts (10.0%), and downstream tooling reads only that property

## Context

nf-core's `nf-core modules lint --fix` annotates workflow channel elements with EDAM
terms. It builds its extension map from the `file_extension` column of `EDAM.tsv`:

```python
if fields[0].split("/")[-1].startswith("format") and fields[14]:
    ...
```

Across EDAM 1.25 that column is populated for **61 of 612** non-obsolete
`format_*` concepts. BAM, FASTA, VCF, BED, CRAM, SAM and GTF all have concepts and
none of them carries an extension, so the tool never reaches them and writes an
empty annotation instead.

I am not proposing that tooling should read only one property — I have a patch
upstream that also keys on labels and synonyms. But the property exists, it is the
obvious thing for a consumer to read, and it is empty for 90% of the concepts it
would apply to.

## Evidence for the specific values below

Rather than assert extensions from my own knowledge, I took them from what nf-core
module authors independently wrote by hand. Across the 184 modules used by
`nf-core/rnaseq` and `nf-core/sarek` there are 184 channel elements that pair
**exactly one** file extension with **exactly one** EDAM term (elements with
multi-extension globs are excluded — they cannot attribute a term to an extension).

The method validates against EDAM itself: for the 8 extensions where EDAM already
records a value — `tsv`, `tab`, `yml`, `yaml`, `json`, `r`, `gz`, `zip`, `csv` — the
authors' consensus agrees with EDAM's own curation in every case (94-100%). On that
basis, the extensions below have unanimous author consensus and no recorded value:

| extension | concept | label | independent annotations agreeing |
|---|---|---|---|
| `bed` | [`format_3003`](http://edamontology.org/format_3003) | BED | 6/6 |
| `bam` | [`format_2572`](http://edamontology.org/format_2572) | BAM | 5/5 |
| `fasta` | [`format_1929`](http://edamontology.org/format_1929) | FASTA | 5/5 |
| `bcf` | [`format_3020`](http://edamontology.org/format_3020) | BCF | 4/4 |
| `txt` | [`format_2330`](http://edamontology.org/format_2330) | Textual format | 3/3 |
| `gtf` | [`format_2306`](http://edamontology.org/format_2306) | GTF | 2/2 |

Suggested values in the existing pipe-separated style, e.g. `fq|fastq` on
`format_1930`:

```
format_3003  BED             bed
format_2572  BAM             bam
format_1929  FASTA           fasta|fa|fna|fas
format_3020  BCF             bcf
format_2330  Textual format  txt
format_2306  GTF             gtf
```

`fasta` is listed with its common aliases because the corpus contains all four;
please trim if EDAM prefers one canonical extension per concept.

## Where authors disagreed, and why that points back here

Three extensions show authors splitting across different terms. In each case the
split tracks a gap in EDAM rather than author carelessness.

**No concept for a FASTA index.** `.fai` appears on 51 channel elements.
48 are unannotated and the 3 that are annotated use 3 different terms —
`format_3327` (BAI, which is the *BAM* index), `data_3210` (Genome index, a data
concept not a format), and `format_3326` (Data index format, the parent). In
`nf-core/modules@master`, `freebayes/meta.yml` reads:

```yaml
    - fasta_fai:
        type: file
        description: reference fasta file index
        pattern: "*.{fa,fasta}.fai"
        ontologies:
          - edam: http://edamontology.org/format_3327 # FASTA index
```

The comment says FASTA index; the term is the BAM index. The author knew what they
meant and there was no concept to express it. A `samtools faidx` index is a distinct
format — a plain-text five-column table, not the BAI binary layout.

**No concept for a CRAM index.** `.crai` appears on 33 elements; the 5 annotated
ones all reach for `format_3327` (BAI) as the nearest available term.

**Two concepts for the tabix index, neither with an extension.** `.tbi` appears on
74 elements and **not one** is annotated, which is what happens when the choice is
unclear:

* `format_3616` "tabix" — *TAB-delimited genome position file index format*,
  parents `format_2333`, `format_3547`
* `format_3700` "Tabix index file format" — *Index file format used by the samtools
  package to index TAB-delimited genome position files*, parents `format_3326`,
  `format_2333`

Both non-obsolete, both describing the same artefact, with different parents. A
consumer cannot pick between them, and the 74 unannotated elements are the
observable consequence.

Also unrepresented: `.csi` (23 elements, 21 unannotated) and `.dict` (sequence
dictionary, 18 elements, all unannotated).

## What would help

1. Populate `file_extension` for the six concepts in the table — a mechanical change
   with corroborating evidence attached.
2. Decide between `format_3616` and `format_3700`, deprecate one in favour of the
   other, and record `tbi` on the survivor.
3. Consider concepts for the FASTA index (`.fai`), CRAM index (`.crai`), CSI index
   (`.csi`) and sequence dictionary (`.dict`), all children of `format_3326`. These
   are ubiquitous in genomics workflows and currently have nowhere to point.

I am happy to open a PR against `EDAM_dev.owl` for item 1, and to file the
mis-annotation upstream at nf-core once (2) and (3) give it somewhere to point.

## Reproducing

```bash
curl -sSLO https://raw.githubusercontent.com/edamontology/edamontology/main/releases/EDAM_1.25.tsv
python edam_extension_coverage.py EDAM_1.25.tsv   # the counts in this issue
```
