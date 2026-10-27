#!/usr/bin/env python3
"""
Recompute the paper's "Sundance supports 91.3% of the held-out Verus, 93.0% of the Dafny and 97.1% of the F*
queries" (intro and Sec. 8):

    supported / (supported + nonlinear + bitvector + strings)

The counts come from the file lists in /artifact/manifests/support_counts: the .smt2 files of the held-out Verus
repo (sundance_heldout_benchmarks @ 4828b94: UFDTLIA/, nonlinear/, bitvector/) and of the Dafny/F* release
(dafny_fstar_benchmarks v1.0: UFLIA/, nonlinear/, bitvector/, strings/). Only the supported folders (UFDTLIA/,
UFLIA/) are downloaded and run; the other folders are counted here and used nowhere else.
"""
import argparse
from collections import Counter
from pathlib import Path

LISTS = Path(__file__).resolve().parent.parent / "manifests" / "support_counts"
PAPER = {"Verus held-out": 91.3, "Dafny": 93.0, "F*": 97.1}
FOLDER = {"UFDTLIA": "supported", "UFLIA": "supported", "nonlinear": "nonlinear", "bitvector": "bitvector",
          "strings": "strings"}
CATS = ["supported", "nonlinear", "bitvector", "strings"]


def count(list_file, group_of):
    """Counter[(group, category)] from lines like UFLIA/d_fvbkv/x.smt2."""
    c = Counter()
    for line in list_file.read_text().split():
        parts = line.split("/")
        c[(group_of(parts[1]), FOLDER[parts[0]])] += 1
    return c


def row(name, c, group):
    n = {cat: c[(group, cat)] for cat in CATS}
    total = sum(n.values())
    pct = 100.0 * n["supported"] / total
    ok = round(pct, 1) == PAPER[name]
    print(f"{name:<16} {n['supported']:>9,} {n['nonlinear']:>9,} {n['bitvector']:>9,} {n['strings']:>8,} "
          f"{total:>9,} {pct:>7.1f}%  (paper: {PAPER[name]:.1f}% {'OK' if ok else 'MISMATCH'})")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lists", default=str(LISTS), help="directory with verus_heldout.txt and dafny_fstar.txt")
    a = ap.parse_args()
    lists = Path(a.lists)
    print(f"{'set':<16} {'supported':>9} {'nonlinear':>9} {'bitvector':>9} {'strings':>8} {'total':>9} {'share':>8}")
    ho = count(lists / "verus_heldout.txt", lambda p: "heldout")
    df = count(lists / "dafny_fstar.txt", lambda p: "Dafny" if p.startswith("d_") else "F*")
    ok = row("Verus held-out", ho, "heldout") & row("Dafny", df, "Dafny") & row("F*", df, "F*")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
