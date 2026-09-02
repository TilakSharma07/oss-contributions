# Galaxy training-material: GTN:004's PMID regex has a doubled slash, so the check has never fired

## Summary

`bin/lint.rb::check_pmids` matches:

```ruby
# https://www.ncbi.nlm.nih.gov/pubmed/24678044
find_matching_texts(contents,
                    %r{(\[[^\]]*\]\(https?://www.ncbi.nlm.nih.gov/pubmed//[0-9]*\))})
```

The pattern requires `pubmed//` — two slashes — while the documenting comment on the
line directly above shows the real URL shape with one. Real PubMed links never match,
so GTN:004 has never fired for a PMID link. Its companion `check_dois` is unaffected.

## Measurement

Across the **547** `tutorial.md` files reachable from the topic API
(689 discovered across all 35 topics; the rest are slides-only or renamed):

| | count |
|---|---|
| links the shipped regex matches | **0** |
| links `.../pubmed/<id>` — the shape the comment documents | 47 |
| links on the modern host `pubmed.ncbi.nlm.nih.gov/<id>/` | 3 |
| tutorials with at least one missed link | 23 |

Most affected: `proteomics/protein-id-oms` (11), `proteomics/metaproteomics` (5), `proteomics/protein-id-sg-ps` (4), `proteomics/labelfree-vs-labelled` (3), `transcriptomics/rna-seq-genes-to-pathways` (3).

## Proposed fix

`check_pmids.patch` drops the duplicated slash, requires at least one digit, allows
the trailing slash PubMed itself emits, and additionally matches the modern
`pubmed.ncbi.nlm.nih.gov` host the check predates.

`test_check_pmids.rb` (16 assertions, all passing on ruby 4.0.6) pins the behaviour:
the shipped pattern misses all five real-world link forms; the proposed one matches
all five; and it ignores DOI links (handled by `check_dois`), the identifier-less
PubMed search page, non-PubMed NCBI links, bare URLs without link text, and existing
`{% cite %}` shortcodes. One assertion checks that capture group 1 is the whole
markdown link, since `ReviewDogEmitter` slices on `selected.begin(0)`/`end(0)`.
