"""How much EDAM coverage is recoverable by also matching concept labels/synonyms.

nf_core/modules/modules_utils.py::load_edam() builds its extension -> EDAM URI map
from ONE column of EDAM.tsv:

    if fields[0].split("/")[-1].startswith("format") and fields[14]:   # "File extension"

EDAM 1.25 has 728 format_* concepts but populates that column for only 61 of them,
so the map misses BAM (format_2572), FASTA (format_1929), VCF (format_3016),
BED (format_3003), CRAM (format_3462) and similar - the formats nf-core modules
actually emit.

This measures the alternative: additionally key the map on each concept's preferred
label and its exact synonyms, lowercased. Ambiguous keys (two different format
concepts claiming the same token) are REPORTED, not silently resolved - a wrong
ontology term is worse than a missing one.
"""
import csv, json, re, collections

TSV = "EDAM.tsv"
LABEL, SYNS, EXT = 1, 2, 14
DEPRECATED_HINTS = ("obsolete", "deprecated")


def load_rows():
    return list(csv.reader(open(TSV, encoding="utf-8"), delimiter="\t"))


def build_maps(rows):
    hdr = rows[0]
    fmts = [r for r in rows[1:] if r and r[0].split("/")[-1].startswith("format")]

    # --- current behaviour: File extension column only ---
    cur = {}
    for r in fmts:
        if len(r) > EXT and r[EXT]:
            for ext in r[EXT].split("|"):
                cur.setdefault(ext, (r[0], r[LABEL]))

    # --- proposed: add lowercased preferred label + exact synonyms ---
    claims = collections.defaultdict(set)     # token -> {(uri, label)}
    for r in fmts:
        if any(h in " ".join(r[:3]).lower() for h in DEPRECATED_HINTS):
            continue
        toks = set()
        if len(r) > LABEL and r[LABEL].strip():
            toks.add(r[LABEL].strip().lower())
        if len(r) > SYNS and r[SYNS].strip():
            for s in r[SYNS].split("|"):
                s = s.strip().lower()
                # only single-token synonyms look like file extensions
                if s and re.fullmatch(r"[a-z0-9._-]{1,12}", s):
                    toks.add(s)
        for t in toks:
            claims[t].add((r[0], r[LABEL]))

    unambiguous = {t: sorted(v)[0] for t, v in claims.items() if len(v) == 1}
    ambiguous = {t: sorted(v) for t, v in claims.items() if len(v) > 1}

    proposed = dict(unambiguous)
    proposed.update(cur)          # the curated column always wins
    return hdr, fmts, cur, proposed, ambiguous


def main():
    rows = load_rows()
    hdr, fmts, cur, proposed, ambiguous = build_maps(rows)
    print(f"  EDAM format concepts: {len(fmts)}")
    print(f"  current map (File extension column only): {len(cur)} keys")
    print(f"  proposed map (+ label / exact synonyms):  {len(proposed)} keys "
          f"({len(ambiguous)} tokens rejected as ambiguous)")

    for w in ["bam", "fasta", "vcf", "bed", "cram", "bai", "fastq", "gtf", "tsv"]:
        c = "HIT " if w in cur else "miss"
        p = "HIT " if w in proposed else "miss"
        uri = proposed.get(w, ("-",))[0].split("/")[-1]
        print(f"    {w:7s} current={c} proposed={p} {uri}")

    # --- replay the real module audit against both maps ---
    recov = json.load(open("recoverable_ontologies.json"))
    unmapped = dict(json.load(open("unmapped_extensions.json")))
    now_mapped = {e: n for e, n in unmapped.items() if e.lower() in proposed}
    still = {e: n for e, n in unmapped.items() if e.lower() not in proposed}
    print(f"  module channel elements unmapped today: {sum(unmapped.values())}")
    print(f"    recovered by proposed map: {sum(now_mapped.values())} "
          f"({len(now_mapped)} distinct extensions)")
    print(f"    still unmapped:            {sum(still.values())} "
          f"({len(still)} distinct)")
    print("  top recovered:", [f"{k}({v})" for k, v in
                               sorted(now_mapped.items(), key=lambda kv: -kv[1])[:10]])
    print("  top still-unmapped:", [f"{k}({v})" for k, v in
                                    sorted(still.items(), key=lambda kv: -kv[1])[:10]])

    json.dump({"current_keys": len(cur), "proposed_keys": len(proposed),
               "ambiguous_rejected": {k: [list(x) for x in v] for k, v in list(ambiguous.items())[:40]},
               "recovered_elements": sum(now_mapped.values()),
               "recovered_extensions": now_mapped,
               "still_unmapped": still},
              open("edam_recovery.json", "w"), indent=1)


if __name__ == "__main__":
    main()
