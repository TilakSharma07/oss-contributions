"""Reproduce, against the installed nf-core/tools, the two behaviours reported upstream.

Run with the venv interpreter:  nfvenv/bin/python reproduce_bug.py

A. load_edam() returns {} on a network failure and the caller cannot tell.
   -> `nf-core modules lint --fix` then writes `ontologies: []` onto every file-typed
      channel element, which is indistinguishable in the committed YAML from
      "this format genuinely has no EDAM term".

B. Even when the download SUCCEEDS, the map is built from the "File extension"
   column alone, which EDAM 1.25 populates for 61 of 728 format concepts -- so
   BAM/FASTA/VCF/BED/CRAM are absent and get the same empty list.

Both are checked by calling the real functions, not by re-implementing them.
"""
import json, sys, types, pathlib

import nf_core
import nf_core.modules.modules_utils as mu

print(f"  nf-core {nf_core.__version__}")
FAIL = []


def check(label, got, expect):
    ok = got == expect
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: got {got!r}, expected {expect!r}")
    if not ok:
        FAIL.append(label)
    return ok


# ---------------------------------------------------------------- A
# Force the download to fail exactly as an offline/proxied run would, and point
# the cache at an empty dir so no previously cached TSV masks the failure.
import requests

tmp = pathlib.Path("repro_cache"); tmp.mkdir(exist_ok=True)
for stale in tmp.glob("EDAM.tsv"):
    stale.unlink()
orig_cache, orig_get = mu.NFCORE_CACHE_DIR, requests.get
mu.NFCORE_CACHE_DIR = str(tmp)


def boom(*a, **k):
    raise requests.exceptions.ConnectionError("simulated offline")


requests.get = boom
try:
    edam_offline = mu.load_edam()
finally:
    requests.get = orig_get

check("A1 load_edam() returns empty dict when the download fails",
      edam_offline, {})
check("A2 the failure is not signalled to the caller (no exception, no sentinel)",
      type(edam_offline).__name__, "dict")

# What _add_edam_ontologies does with that empty map, on a real element.
# `nf-core modules lint --fix` reaches this through ModuleLint.update_meta_yml_file(),
# which needs a `nextflow` binary and a clonable git remote -- neither available here.
# So instead of hand-replicating the branch, extract the closure's OWN source text from
# the installed package and exec it: the function under test is upstream's bytes.
import inspect, re as _re, textwrap
import ruamel.yaml                      # the closure references this
from nf_core.modules.lint import ModuleLint

import ast
_src = textwrap.dedent(inspect.getsource(ModuleLint.update_meta_yml_file))
_tree = ast.parse(_src)
_fn = next((n for n in ast.walk(_tree)
            if isinstance(n, ast.FunctionDef) and n.name == "_add_edam_ontologies"), None)
assert _fn is not None, "could not locate _add_edam_ontologies in the installed package"
# ast gives exact line bounds, so nothing after the closure is captured
_closure_src = textwrap.dedent(
    "\n".join(_src.splitlines()[_fn.lineno - 1:_fn.end_lineno]))
_ns = {"re": _re, "ruamel": ruamel, "log": mu.log, "nf_core": nf_core}
exec(compile(_closure_src, "nf_core/modules/lint/__init__.py (extracted)", "exec"), _ns)
_add_edam_ontologies = _ns["_add_edam_ontologies"]
print(f"  extracted upstream closure: {len(_closure_src.splitlines())} lines")

section = {"type": "file", "description": "Aligned reads", "pattern": "*.{bam}"}
_add_edam_ontologies(section, edam_offline, "output - bam")
check("A3 real closure + empty map writes an explicit empty ontologies list",
      section.get("ontologies"), [])

# ---------------------------------------------------------------- B
mu.NFCORE_CACHE_DIR = orig_cache
tsv = pathlib.Path("EDAM.tsv").resolve()
cache2 = pathlib.Path("repro_cache2"); cache2.mkdir(exist_ok=True)
(cache2 / "EDAM.tsv").write_bytes(tsv.read_bytes())
mu.NFCORE_CACHE_DIR = str(cache2)
edam_online = mu.load_edam()
mu.NFCORE_CACHE_DIR = orig_cache

print(f"  load_edam() with a real EDAM.tsv: {len(edam_online)} extensions")
for ext in ["bam", "fasta", "vcf", "bed", "cram"]:
    check(f"B {ext!r} is absent from the map built by load_edam()",
          ext in edam_online, False)
check("B 'fastq' IS present (the column is populated for a minority of concepts)",
      "fastq" in edam_online, True)

# corroborate the 61/728 column-coverage figure through the same parse
import csv
rows = list(csv.reader(open(tsv, encoding="utf-8"), delimiter="\t"))
fmts = [r for r in rows[1:] if r and r[0].split("/")[-1].startswith("format")]
with_ext = [r for r in fmts if len(r) > 14 and r[14]]
print(f"  EDAM 1.25: {len(with_ext)}/{len(fmts)} format concepts carry a File extension value")

print(f"\n  {len(FAIL)} failing check(s)" if FAIL else "\n  all checks reproduced as described")
sys.exit(1 if FAIL else 0)
