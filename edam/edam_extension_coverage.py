"""Reproduce the coverage counts in ISSUE_edam_extensions.md.

Usage:  python edam_extension_coverage.py EDAM_1.25.tsv

Reports how many non-obsolete format concepts carry a file_extension value, and
checks the specific concepts named in the issue. Columns are resolved by header
name rather than by index, so a column reordering upstream does not silently
change what is counted.
"""
import csv
import sys


NAMED = {
    "format_3003": "BED",
    "format_2572": "BAM",
    "format_1929": "FASTA",
    "format_3020": "BCF",
    "format_2330": "Textual format",
    "format_2306": "GTF",
    "format_3616": "tabix",
    "format_3700": "Tabix index file format",
    "format_3327": "BAI",
    "format_3326": "Data index format",
}


def load(path):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh, delimiter="\t"))
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    for required in ("Class ID", "Preferred Label", "File extension", "Obsolete"):
        if required not in idx:
            sys.exit(f"column {required!r} not found; header is {header[:6]}...")
    return rows[1:], idx


def main(path):
    rows, idx = load(path)
    cid, lbl, ext, obs = (idx["Class ID"], idx["Preferred Label"],
                          idx["File extension"], idx["Obsolete"])

    formats = [r for r in rows
               if r and r[cid].rsplit("/", 1)[-1].startswith("format")
               and (r[obs] or "").strip().lower() != "true"]
    populated = [r for r in formats if (r[ext] or "").strip()]

    print(f"non-obsolete format concepts : {len(formats)}")
    print(f"with a file_extension value  : {len(populated)} "
          f"({len(populated) / len(formats) * 100:.1f}%)")

    print("\nconcepts named in the issue:")
    by_acc = {r[cid].rsplit("/", 1)[-1]: r for r in formats}
    for acc, expected in NAMED.items():
        row = by_acc.get(acc)
        if row is None:
            print(f"  {acc:14s} NOT FOUND or obsolete")
            continue
        got = (row[ext] or "").strip()
        note = "" if row[lbl] == expected else f"  (label is {row[lbl]!r}, issue says {expected!r})"
        print(f"  {acc:14s} {row[lbl]:26s} file_extension={got or '(empty)'}{note}")

    print("\nexisting multi-value examples, for the format convention:")
    for row in populated:
        if "|" in row[ext]:
            print(f"  {row[cid].rsplit('/', 1)[-1]:14s} {row[lbl]:26s} {row[ext]}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
