"""Extract extension -> EDAM term evidence from nf-core module meta.yml files.

Usage:  python evidence_from_modules.py <dir-of-meta.yml>

Only elements that pair exactly one file extension with exactly one EDAM term are
counted; a multi-extension glob such as *.{bam,cram,sam} cannot attribute a term to
a particular extension, so those are excluded rather than guessed at. This is the
evidence table quoted in ISSUE_edam_extensions.md.
"""
import collections
import pathlib
import sys

try:
    from ruamel.yaml import YAML
    _y = YAML(typ="safe")
    def load(path): return _y.load(open(path))
except ImportError:
    import yaml
    def load(path): return yaml.safe_load(open(path))


def collect(root):
    single = collections.defaultdict(collections.Counter)
    excluded = 0

    def walk(node):
        nonlocal excluded
        if isinstance(node, dict):
            if node.get("type") == "file":
                pattern = node.get("pattern") or ""
                terms = [o.get("edam") for o in (node.get("ontologies") or [])
                         if isinstance(o, dict) and o.get("edam")]
                if terms and "." in pattern:
                    tail = pattern.rsplit(".", 1)[-1].strip("{} ")
                    exts = [e.strip().lower() for e in tail.split(",") if e.strip()]
                    if len(exts) == 1 and len(terms) == 1:
                        single[exts[0]][terms[0]] += 1
                    else:
                        excluded += 1
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for path in sorted(pathlib.Path(root).rglob("*.yml")):
        try:
            walk(load(path))
        except Exception:
            continue
    return single, excluded


def main(root):
    single, excluded = collect(root)
    total = sum(sum(c.values()) for c in single.values())
    print(f"unambiguous (1 extension, 1 term) annotations: {total}")
    print(f"multi-extension elements excluded            : {excluded}")
    print()
    print(f"{'ext':10s} {'n':>4s}  {'consensus':>9s}  term")
    for ext, counter in sorted(single.items(), key=lambda kv: -sum(kv[1].values())):
        n_total = sum(counter.values())
        if n_total < 2:
            continue
        uri, n = counter.most_common(1)[0]
        print(f"{ext:10s} {n_total:4d}  {n / n_total * 100:8.0f}%  {uri.rsplit('/', 1)[-1]}"
              + ("" if len(counter) == 1
                 else "   competing: " + ", ".join(u.rsplit("/", 1)[-1]
                                                   for u in counter if u != uri)))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
