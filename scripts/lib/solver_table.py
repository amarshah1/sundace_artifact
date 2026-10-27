#!/usr/bin/env python3
"""
Text tables of queries solved (unsat within 1 s / 10 s / 60 s of wall time) per benchmark set and
subproject, for the series in the clean CDF plots. Same query filtering as plot_cdf_clean.py
(manifests, 1,187 duplicate anvil/splinterdb-smt-* Verus queries dropped), plus a Verus table on
all 3,763 files. Lines are prefixed with "% " so they can be pasted into LaTeX as comments.

--modularity-ablation tabulates the Sundance modularity ablation instead (Default, Semper if run, MiniSat,
Z3 arithmetic).

Usage: solver_table.py [--root RUN_DIR] [--sundance CFG | --modularity-ablation] [--out FILE]
"""
import argparse
import csv
from collections import OrderedDict
from pathlib import Path

THRESHOLDS = [1.0, 10.0, 60.0]
SETS = [("Verus", "verus", None), ("Verus held-out", "verus_heldout", None),
        ("Dafny", "mariposa", "d_"), ("F*", "mariposa", "fs_")]


def configs(sundance):
    return [(sundance, "Sundance (proofs)"),
            ("z3-tool", "Z3, tool options"),
            ("z3-tool-proof", "Z3, tool options (proofs)"),
            ("cvc5-nocbqi-strict-proof", "cvc5 --no-cbqi --user-pat=strict (proofs)"),
            ("alt-ergo", "Alt-Ergo")]


ABLATION = [("sundance-default-proof", "Default (proofs)"),
            ("sundance-egraph-semper-proof", "Semper (proofs)"),
            ("sundance-sat-minisat", "MiniSat"),
            ("sundance-arith-z3-proof", "Z3 arithmetic (proofs)")]
ABLATION_HEADER = [
    "Sundance modularity ablation: queries solved (unsat within 1 s / 10 s / 60 s of wall time)",
    "Same Sundance build, one component swapped by a flag; eDRAT proofs; --infer-triggers on Dafny/F*.",
    "  Default (proofs)        --arithmetic internalincremental, CaDiCaL, Sundance e-graph",
    "  Semper (proofs)         Semper e-graph (not on Sundance main yet; shown only if its results exist)",
    "  MiniSat                 Default with --sat-backend minisat (no proofs: the MiniSat backend has no proof tracer)",
    "  Z3 arithmetic (proofs)  Default with --arithmetic z3incremental (Z3's incremental arithmetic)",
]
# Names of the same configs in the paper's own run (final_experiments/2026-10-15_03-14-03), so these scripts also
# read that run's results directory.
PAPER_RUN_NAMES = {"sundance-default-proof": "sundance-internalincremental238fix-proof",
                   "sundance-sat-minisat": "sundance-internalincremental238fix-minisat",
                   "sundance-arith-z3-proof": "sundance-proof",
                   "sundance-egraph-semper-proof": "sundance-internalincremental238fix-semper-proof"}


def results_csv(root, bench, cfg):
    path = root / "results" / bench / f"{cfg}_results.csv"
    if not path.exists() and cfg in PAPER_RUN_NAMES:
        path = root / "results" / bench / f"{PAPER_RUN_NAMES[cfg]}_results.csv"
    return path


def subproject(bench, f):
    top = f.split("/")[0]
    if bench == "verus" and top == "anvil":
        return "Verus:anvil/" + f.split("/")[1].split("-")[0]
    return {"verus": "Verus:", "verus_heldout": "heldout:"}.get(bench, "Dafny:" if top.startswith("d_") else "F*:") + top


def load(root, bench, cfg):
    path = results_csv(root, bench, cfg)
    return {r["file"]: (r["result"], float(r["time_seconds"])) for r in csv.DictReader(open(path, newline=""))}


def cell(n, total):
    return f"{n:,}/{total:,} ({100.0 * n / total:.1f}%)"


def table(title, cols, rows, width=22):
    out = [title, "config".ljust(45) + "".join(c.rjust(width) for c in cols), "-" * (45 + width * len(cols))]
    for label, cells in rows:
        out.append(label.ljust(45) + "".join(c.rjust(width) for c in cells))
    return out + [""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--sundance", default="sundance-default-proof")
    ap.add_argument("--modularity-ablation", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = Path(a.root)
    cfgs = ABLATION if a.modularity_ablation else configs(a.sundance)
    manifests = {b: set((root / "manifests" / f"{b}.txt").read_text().split())
                 for b in ("verus", "verus_heldout", "mariposa") if (root / "manifests" / f"{b}.txt").exists()}
    if not manifests:
        raise SystemExit(f"no manifests in {root / 'manifests'}: run the evaluations first")
    global SETS
    SETS = [x for x in SETS if x[1] in manifests]
    missing = [c for c, _ in cfgs if not all(results_csv(root, b, c).exists() for b in manifests)]
    if missing:
        import sys
        print(f"note: no results on every set for {', '.join(missing)}; left out of the table", file=sys.stderr)
    cfgs = [x for x in cfgs if x[0] not in missing]
    res = {(b, c): load(root, b, c) for b in manifests for c, _ in cfgs}

    def files(bench, prefix, dedupe=True):
        return sorted(f for f in manifests[bench] if (not prefix or f.startswith(prefix))
                      and not (dedupe and bench == "verus" and f.startswith("anvil/splinterdb-smt-")))

    def solved(bench, cfg, fs, t):
        r = res[(bench, cfg)]
        return sum(1 for f in fs if f in r and r[f][0] == "unsat" and r[f][1] <= t)

    groups = OrderedDict()  # subproject -> (bench, files)
    for _, bench, prefix in SETS:
        for f in files(bench, prefix):
            groups.setdefault(subproject(bench, f), (bench, []))[1].append(f)
    set_files = [(name, bench, files(bench, prefix)) for name, bench, prefix in SETS]
    set_files = [x for x in set_files if x[2]]   # e.g. no Dafny files when only an F* tarball was fetched

    L = []
    if a.modularity_ablation:
        L += ABLATION_HEADER + [
            f"Run folder: {str(root.resolve()).replace(str(Path.home().resolve()), '~').replace('/local~', '~')}/",
            "60 s timeout; an unsat after the threshold counts as unsolved.",
            "Benchmarks: current lists (nonlinear queries excluded); the 1,187 duplicate anvil/splinterdb-smt-* Verus queries removed.",
            ""]
    else:
        L += ["Queries solved (unsat within 1 s / 10 s / 60 s of wall time)",
            f"Run folder: {str(root.resolve()).replace(str(Path.home().resolve()), '~').replace('/local~', '~')}/",
            "Sundance: --arithmetic internalincremental, CaDiCaL, eDRAT proofs, --infer-triggers on Dafny/F*.",
            "Z3 5.3.0, cvc5 1.4.2, Alt-Ergo 2.4.3 (free). 60 s timeout, unsat after the threshold counts as unsolved.",
            "Benchmarks: current lists (nonlinear queries excluded); the 1,187 duplicate anvil/splinterdb-smt-* Verus queries removed.",
            ""]
    # Compact percentage summary
    cols = [f"{n} {int(t)}s" for n, _, _ in set_files for t in THRESHOLDS]
    hdr = "config".ljust(45) + "".join(f"{n:>27}" for n, _, _ in set_files)
    sub = " " * 45 + "".join(f"{'1 s':>9}{'10 s':>9}{'60 s':>9}" for _ in set_files)
    L += ["Summary (% solved)", hdr, sub, "-" * (45 + 27 * len(set_files))]
    for c, label in cfgs:
        row = label.ljust(45)
        for _, bench, fs in set_files:
            row += "".join(f"{100.0 * solved(bench, c, fs, t) / len(fs):8.1f}%" for t in THRESHOLDS)
        L.append(row)
    L.append("")
    # Combined per verifier (Verus = original + held-out, Mariposa = Dafny + F*), as in plot_cdf_clean.py --combined
    combined = [(n, [(b, files(b, None)) for b in bs if b in manifests])
                for n, bs in (("Verus + held-out", ("verus", "verus_heldout")), ("Dafny + F*", ("mariposa",)))]
    combined = [(n, parts) for n, parts in combined if parts]
    L += table("Combined per verifier (unsat within 1 s / 10 s / 60 s)",
               [f"{n} {int(t)} s" for n, _ in combined for t in THRESHOLDS],
               [(label, [cell(sum(solved(b, c, fs, t) for b, fs in parts), sum(len(fs) for _, fs in parts))
                         for _, parts in combined for t in THRESHOLDS]) for c, label in cfgs], width=24)
    for t in reversed(THRESHOLDS):
        L += [f"===== Within {int(t)} s =====", ""]
        L += table("By benchmark set", [n for n, _, _ in set_files],
                   [(label, [cell(solved(b, c, fs, t), len(fs)) for _, b, fs in set_files]) for c, label in cfgs])
        names = list(groups)
        for i in range(0, len(names), 5):
            chunk = names[i:i + 5]
            L += table(f"By subproject ({i // 5 + 1})", chunk,
                       [(label, [cell(solved(groups[g][0], c, groups[g][1], t), len(groups[g][1])) for g in chunk])
                        for c, label in cfgs])
    allv = files("verus", None, dedupe=False) if "verus" in manifests else []
    L += [] if not allv else table(f"Verus original WITH the 1,187 duplicate SplinterDB copies (all {len(allv):,} files, as published)",
               [f"{int(t)} s" for t in THRESHOLDS],
               [(label, [cell(solved("verus", c, allv, t), len(allv)) for t in THRESHOLDS]) for c, label in cfgs])
    text = "\n".join(("% " + l) if l else "%" for l in L) + "\n"
    if a.out:
        Path(a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
