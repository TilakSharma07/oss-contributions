"""Quantify the impact of nf-core/tools' silent EDAM-load failure.

nf_core/modules/modules_utils.py::load_edam() returns an EMPTY dict when the
EDAM download fails (RequestException -> log.warning -> return edam_formats).
nf_core/modules/lint/__init__.py::_add_edam_ontologies() then still runs, and for
every file-typed channel element without an 'ontologies' key it executes

    elif "type" in section and section["type"] == "file":
        section["ontologies"] = []

so `nf-core modules lint --fix` writes an explicit empty list wherever the map is
empty -- indistinguishable in the committed YAML from "this file type genuinely has
no EDAM format".

This script separates the two cases over the real module set:
  * pattern extension IS in the EDAM map  -> the empty list is WRONG (recoverable)
  * pattern extension is NOT in the map   -> not attributable to the bug

Caches meta.yml locally so re-runs are offline.
"""
import json, re, pathlib, urllib.request, concurrent.futures as cf

RAW = "https://raw.githubusercontent.com/nf-core/modules/master"
CACHE = pathlib.Path("meta_cache"); CACHE.mkdir(exist_ok=True)
MODULES_KEY = "https://github.com/nf-core/modules.git"


def names():
    s = set()
    for f in ("mj_rnaseq.json", "mj_sarek.json"):
        s |= set(json.load(open(f))["repos"][MODULES_KEY]["modules"]["nf-core"])
    return sorted(s)


def get(name):
    p = CACHE / (name.replace("/", "__") + ".yml")
    if not p.exists():
        try:
            with urllib.request.urlopen(f"{RAW}/modules/nf-core/{name}/meta.yml", timeout=30) as r:
                p.write_bytes(r.read())
        except Exception:
            return None
    return p.read_text(encoding="utf-8", errors="replace")


def extensions_from_pattern(pattern):
    """Replicate _add_edam_ontologies' extension extraction (lint/__init__.py)."""
    out = []
    if re.search(r"{", pattern):
        for ext in re.split(r",|{|}", pattern):
            if ext:
                out.append(ext)
    elif re.search(r"\.\w+$", pattern):
        out.append(pattern.split(".")[-1])
    return out


def elements(node):
    if isinstance(node, dict):
        if "type" in node and "description" in node:
            yield node
        for v in node.values():
            yield from elements(v)
    elif isinstance(node, list):
        for v in node:
            yield from elements(v)


def main():
    import yaml
    edam = json.load(open("edam_map.json"))
    ns = names()
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        texts = dict(zip(ns, ex.map(get, ns)))

    recoverable, unmapped_ext, no_pattern, filled = [], {}, 0, 0
    for name, txt in texts.items():
        if not txt:
            continue
        try:
            m = yaml.safe_load(txt)
        except Exception:
            continue
        if not isinstance(m, dict):
            continue
        for e in elements(m.get("input")):
            pass
        for e in list(elements(m.get("input"))) + list(elements(m.get("output"))):
            if str(e.get("type", "")).lower() != "file":
                continue
            onto = e.get("ontologies")
            if onto:                      # non-empty list -> already populated
                filled += 1
                continue
            pat = e.get("pattern")
            if not pat:
                no_pattern += 1
                continue
            exts = extensions_from_pattern(str(pat))
            hit = [x for x in exts if x in edam]
            if hit:
                recoverable.append({"module": name, "pattern": str(pat),
                                    "extensions": hit,
                                    "edam": [edam[x][0] for x in hit]})
            else:
                for x in exts:
                    unmapped_ext[x] = unmapped_ext.get(x, 0) + 1

    json.dump(recoverable, open("recoverable_ontologies.json", "w"), indent=1)
    json.dump(sorted(unmapped_ext.items(), key=lambda kv: -kv[1]),
              open("unmapped_extensions.json", "w"), indent=1)

    tot = filled + len(recoverable) + no_pattern + sum(unmapped_ext.values())
    print(f"  file channel elements examined: {tot}")
    print(f"    already populated ............ {filled}")
    print(f"    empty BUT extension in EDAM .. {len(recoverable)}   <- wrong, caused by empty map")
    print(f"    empty, extension not in EDAM . {sum(unmapped_ext.values())}")
    print(f"    empty, no pattern field ...... {no_pattern}")
    print(f"  distinct unmapped extensions: {len(unmapped_ext)}")
    print("  top unmapped:", [f"{k}({v})" for k, v in
                              sorted(unmapped_ext.items(), key=lambda kv: -kv[1])[:12]])


if __name__ == "__main__":
    main()
