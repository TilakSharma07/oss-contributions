# Tests for the GTN:004 PMID regex, shipped vs. proposed.
# Run: ruby test_check_pmids.rb
#
# The shipped pattern in bin/lint.rb::check_pmids carries a doubled slash, so it never
# matches a real PubMed link. These cases are drawn from links that actually occur in
# the tutorial corpus (see pmid_findings.json).

SHIPPED = %r{(\[[^\]]*\]\(https?://www.ncbi.nlm.nih.gov/pubmed//[0-9]*\))}
PROPOSED = %r{(\[[^\]]*\]\(https?://(?:www\.ncbi\.nlm\.nih\.gov/pubmed|pubmed\.ncbi\.nlm\.nih\.gov)/[0-9]+/?\))}

SHOULD_MATCH = [
  'see [the paper](https://www.ncbi.nlm.nih.gov/pubmed/24678044)',
  'see [Smith et al.](http://www.ncbi.nlm.nih.gov/pubmed/12345678)',
  'see [the paper](https://pubmed.ncbi.nlm.nih.gov/24678044/)',
  'see [the paper](https://pubmed.ncbi.nlm.nih.gov/24678044)',
  'inline [OpenMS](https://www.ncbi.nlm.nih.gov/pubmed/27575624) reference',
]

SHOULD_NOT_MATCH = [
  'a [DOI link](https://doi.org/10.1093/bioinformatics/btu170)',           # check_dois handles this
  'the [PubMed search page](https://www.ncbi.nlm.nih.gov/pubmed/)',        # no identifier
  'a [BLAST link](https://blast.ncbi.nlm.nih.gov/Blast.cgi)',
  'bare url https://www.ncbi.nlm.nih.gov/pubmed/24678044 without link text',
  'a [cite shortcode]({% cite Smith2020 %})',
]

fails = 0

def report(label, ok)
  puts format('  [%s] %s', ok ? 'PASS' : 'FAIL', label)
  ok
end

puts '  shipped regex against links that SHOULD be flagged:'
SHOULD_MATCH.each do |c|
  hit = !(c =~ SHIPPED).nil?
  # documenting the defect: the shipped pattern is expected to miss every one
  fails += 1 unless report("shipped misses  #{c[0, 58]}", hit == false)
end

puts '  proposed regex against links that SHOULD be flagged:'
SHOULD_MATCH.each do |c|
  fails += 1 unless report("proposed matches #{c[0, 58]}", !(c =~ PROPOSED).nil?)
end

puts '  proposed regex against text that should NOT be flagged:'
SHOULD_NOT_MATCH.each do |c|
  fails += 1 unless report("proposed ignores #{c[0, 58]}", (c =~ PROPOSED).nil?)
end

puts '  captured group is the whole markdown link (the emitter slices on it):'
m = SHOULD_MATCH[0].match(PROPOSED)
fails += 1 unless report('capture == [the paper](...)',
                         m && m[1] == '[the paper](https://www.ncbi.nlm.nih.gov/pubmed/24678044)')

puts(fails.zero? ? "\n  all checks passed" : "\n  #{fails} failing check(s)")
exit(fails.zero? ? 0 : 1)
