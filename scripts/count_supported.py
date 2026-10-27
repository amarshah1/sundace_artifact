#!/usr/bin/env python3
"""
Recompute the paper's "Sundance supports 91.3% of the held-out Verus, 93.0% of the Dafny and 97.1% of the F*
queries" (intro and Sec. 8) from the folder counts of the downloaded benchmark sets:

    supported / (supported + nonlinear + bitvector + strings)

  held-out Verus: sundance_heldout_benchmarks/{UFDTLIA,nonlinear,bitvector,strings}/<project>/*.smt2
  Dafny / F*:     dafny_fstar_benchmarks/{UFLIA,nonlinear,bitvector,strings}/<project>/*.smt2
                  (Dafny = d_* projects, F* = fs_* projects)

--lists DIR counts the release's .list files instead (UFLIA-<project>.list, nonlinear.list, bitvector.list,
strings.list), so the Dafny/F* numbers can be checked without extracting the 79 GB.

Scope (as in the paper's numbers): the held-out totals leave out the vest and rlsf projects, which were set aside
before the set was built, and Mariposa's Serval project (s_komodo_clean) is not part of the Dafny/F* sets.
The original Verus set (verus_benchmarks: UFDTLIA vs UFDTNIA/UFBVDTLIA/UFBVDTNIA) is printed for reference
only; the paper does not report it.
"""
import argparse
import os
from collections import Counter
from pathlib import Path

PAPER = {"Verus held-out": 91.3, "Dafny": 93.0, "F*": 97.1}
CATS = ["supported", "nonlinear", "bitvector", "strings"]


def count_tree(root: Path, folder_for_cat, group_of):
    """Counter[(group, category)] of *.smt2 files (symlinks followed)."""
    c = Counter()
    for cat, sub in folder_for_cat.items():
        for d in sub:
            base = root / d
            if not base.is_dir():
                continue
            for dp, _, fs in os.walk(str(base), followlinks=True):
                rel = Path(dp).relative_to(base)
                project = rel.parts[0] if rel.parts else ""
                n = sum(1 for f in fs if f.endswith(".smt2"))
                if n:
                    c[(group_of(project), cat)] += n
    return c


def count_lists(lists: Path):
    c = Counter()
    for lf in sorted(lists.glob("*.list")):
        stem = lf.stem
        cat = "supported" if stem.startswith("UFLIA-") else stem
        for line in lf.read_text().split():
            parts = Path(line).parts  # e.g. no_bv/d_fvbkv/x.smt2, bv_unknown/d_komodo/y.smt2
            project = parts[1] if len(parts) > 2 else ""
            c[(dafny_fstar(project), cat)] += 1
    return c


def dafny_fstar(project):
    return "Dafny" if project.startswith("d_") else "F*" if project.startswith("fs_") else "other:" + project


def row(name, c, group):
    n = {cat: c[(group, cat)] for cat in CATS}
    total = sum(n.values())
    pct = 100.0 * n["supported"] / total if total else 0.0
    paper = PAPER.get(name)
    check = "" if paper is None else ("  (paper: %.1f%% %s)" % (paper, "OK" if round(pct, 1) == paper else "MISMATCH"))
    print(f"{name:<16} {n['supported']:>9,} {n['nonlinear']:>9,} {n['bitvector']:>9,} {n['strings']:>8,} "
          f"{total:>9,} {pct:>7.1f}%{check}")
    return paper is None or round(pct, 1) == paper


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bench-root", default=os.environ.get("BENCH_ROOT", "./benchmarks"))
    ap.add_argument("--lists", default=None, help="count Dafny/F* from the release .list files in DIR")
    a = ap.parse_args()
    root = Path(a.bench_root)
    print(f"{'set':<16} {'supported':>9} {'nonlinear':>9} {'bitvector':>9} {'strings':>8} {'total':>9} {'share':>8}")
    ok = True
    ho = count_tree(root / "sundance_heldout_benchmarks",
                    {"supported": ["UFDTLIA"], "nonlinear": ["nonlinear"], "bitvector": ["bitvector"],
                     "strings": ["strings"]}, lambda p: "heldout")
    if ho:
        ok &= row("Verus held-out", ho, "heldout")
    if a.lists:
        df = count_lists(Path(a.lists))
    else:
        df = count_tree(root / "dafny_fstar_benchmarks",
                        {"supported": ["UFLIA"], "nonlinear": ["nonlinear"], "bitvector": ["bitvector"],
                         "strings": ["strings"]}, dafny_fstar)
    if df:
        ok &= row("Dafny", df, "Dafny")
        ok &= row("F*", df, "F*")
    vo = count_tree(root / "verus_benchmarks",
                    {"supported": ["UFDTLIA/20241211-verus"], "nonlinear": ["UFDTNIA"],
                     "bitvector": ["UFBVDTLIA", "UFBVDTNIA"]}, lambda p: "orig")
    if vo:
        print("reference only (not in the paper):")
        row("Verus original", vo, "orig")
    if not (ho or df):
        raise SystemExit(f"no benchmark folders found under {root}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
