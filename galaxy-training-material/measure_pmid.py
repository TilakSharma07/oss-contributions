"""Measure how many GTN tutorials the GTN:004 PMID check silently misses.

galaxyproject/training-material bin/lint.rb::check_pmids matches

    %r{(\\[[^\\]]*\\]\\(https?://www.ncbi.nlm.nih.gov/pubmed//[0-9]*\\))}
                                                        ^^ two slashes

while the documenting comment on the line above it shows the real URL shape with one
slash (https://www.ncbi.nlm.nih.gov/pubmed/24678044). Real PubMed links therefore
never match and the check cannot fire.

This walks the tutorials reachable over raw.githubusercontent.com (the git remote and
codeload are unreachable from here) and counts, per file, links the SHIPPED regex
catches vs. links the INTENDED one-slash regex would catch, including the modern
pubmed.ncbi.nlm.nih.gov host the check predates.
"""
import concurrent.futures as cf
import json
import re
import urllib.error
import urllib.request

RAW = "https://raw.githubusercontent.com/galaxyproject/training-material/main"

GTN_API = "https://training.galaxyproject.org/training-material/api"

SHIPPED = re.compile(r"(\[[^\]]*\]\(https?://www\.ncbi\.nlm\.nih\.gov/pubmed//[0-9]*\))")
INTENDED = re.compile(r"(\[[^\]]*\]\(https?://www\.ncbi\.nlm\.nih\.gov/pubmed/[0-9]+/?\))")
MODERN = re.compile(r"(\[[^\]]*\]\(https?://pubmed\.ncbi\.nlm\.nih\.gov/[0-9]+/?\))")
# GTN:004's sibling, check_dois, for comparison: that one is not broken.
DOI = re.compile(r"(\[[^\]]*\]\(https?://doi\.org/[^)]*\))")


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None


def topic_tutorials(topic):
    """The GTN publishes a per-topic index; raw.githubusercontent cannot list dirs."""
    blob = get(f"{GTN_API}/topics/{topic}.json")
    if not blob:
        return []
    d = json.loads(blob)
    mats = d.get("materials", d) if isinstance(d, dict) else d
    out = []
    for m in (mats if isinstance(mats, list) else []):
        if isinstance(m, dict) and m.get("tutorial_name"):
            out.append(m["tutorial_name"])
    return sorted(set(out))


def main():
    topics = sorted(json.loads(get(f"{GTN_API}/topics.json")))
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        found = dict(zip(topics, ex.map(topic_tutorials, topics)))
    targets = [(t, s, f"{RAW}/topics/{t}/tutorials/{s}/tutorial.md")
               for t, slugs in found.items() for s in slugs]
    print(f"  tutorials discovered: {len(targets)} across "
          f"{sum(1 for v in found.values() if v)}/{len(topics)} topics")

    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        texts = list(ex.map(get, [u for _, _, u in targets]))

    rows, n_ok = [], 0
    for (topic, slug, _u), txt in zip(targets, texts):
        if not txt:
            continue
        n_ok += 1
        s, i, m, d = (len(SHIPPED.findall(txt)), len(INTENDED.findall(txt)),
                      len(MODERN.findall(txt)), len(DOI.findall(txt)))
        if i or m or s:
            rows.append({"topic": topic, "tutorial": slug, "shipped_matches": s,
                         "intended_matches": i, "modern_host_matches": m, "doi_links": d})

    tot_s = sum(r["shipped_matches"] for r in rows)
    tot_i = sum(r["intended_matches"] for r in rows)
    tot_m = sum(r["modern_host_matches"] for r in rows)
    print(f"  tutorials fetched: {n_ok}")
    print(f"  PMID links the SHIPPED regex matches:            {tot_s}")
    print(f"  PMID links a one-slash regex would match:        {tot_i}")
    print(f"  PMID links on the modern pubmed.ncbi host:       {tot_m}")
    print(f"  tutorials with at least one missed PMID link:    "
          f"{sum(1 for r in rows if r['intended_matches'] or r['modern_host_matches'])}")
    for r in sorted(rows, key=lambda r: -(r["intended_matches"] + r["modern_host_matches"]))[:8]:
        print(f"    {r['topic']}/{r['tutorial']}: legacy={r['intended_matches']} "
              f"modern={r['modern_host_matches']} shipped={r['shipped_matches']}")
    json.dump(rows, open("pmid_findings.json", "w"), indent=1)


if __name__ == "__main__":
    main()
