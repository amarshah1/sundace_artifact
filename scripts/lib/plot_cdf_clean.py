#!/usr/bin/env python3
"""
Clean per-set cactus plots (queries solved as unsat vs per-query wall time), one figure per set:
Verus, Verus held-out, Dafny, F*. Series: Sundance (proofs), z3 + tool options, z3 + tool options
(proofs), and the better of the two cvc5 proof configs for that set.

Queries are restricted to the run's file lists (--manifests, default: <root>/manifests), and the 1,187
anvil/splinterdb-smt-* copies of splinterdb/* are dropped (--keep-duplicates to keep them).

--sundance CFG plots the 5-line comparison (Sundance, Z3, Z3 proofs, cvc5 proofs, Alt-Ergo) with the
given Sundance config as the Sundance line, legend inside the plot (default out: plots/clean_<CFG>).

Usage: plot_cdf_clean.py [--root RUN_DIR] [--manifests DIR] [--out DIR] [--keep-duplicates]
                         [--sundance-only | --sundance-238fix | --sundance CFG]
--modularity-ablation (alias --sundance-238fix) plots the modularity ablation: Default, Semper, MiniSat and
Z3 arithmetic; out: plots/modularity_ablation.
"""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import matplotlib.transforms as mtransforms
from matplotlib.lines import Line2D

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
MAGENTA, GREEN, VIOLET = "#e87ba4", "#008300", "#6250d6"
INK, INK_2, INK_3, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#ffffff"
DASH = (0, (4, 2))
# Empty corner of each plot (checked by eye on the second run)
LEGEND_LOC = {"verus": "lower right", "verus_heldout": "lower right", "dafny": "upper left", "fstar": "upper left",
              "verus_combined": "lower right", "dafny_fstar": "upper left"}
MAX_TIME = 60.0  # an unsat answer after 60 s of wall time counts as unsolved

SETS = [  # (key, title, results dir, file prefix)
    ("verus", "Verus", "verus", None),
    ("verus_heldout", "Verus (held-out)", "verus_heldout", None),
    ("dafny", "Dafny", "mariposa", "d_"),
    ("fstar", "F*", "mariposa", "fs_"),
]
# --combined: one figure per verifier (Verus = original + held-out, Mariposa = Dafny + F*)
COMBINED_SETS = [
    ("verus_combined", "Verus + held-out", [("verus", None), ("verus_heldout", None)]),
    ("dafny_fstar", "Dafny + F*", [("mariposa", "d_"), ("mariposa", "fs_")]),
]
CVC5_PROOF = {"cvc5-proof": "cvc5 (proofs)",
              "cvc5-nocbqi-strict-proof": "cvc5 (proofs)"}


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


def load(root, bench, prefix, keep, dedupe):
    out = {}
    def wanted(f):
        return (not prefix or f.startswith(prefix)) and not (dedupe and bench == "verus" and f.startswith("anvil/splinterdb-smt-"))
    # Denominator: the queries in the manifest (a config whose CSV lacks some of them counts those as unsolved)
    n_manifest = sum(1 for f in keep if wanted(f)) if keep is not None else None
    for cfg in ["sundance-proof", "sundance-semper-proof", "sundance-semper-unpatched-proof", "sundance-minisat",
                "sundance-internal-proof"] + ([SUNDANCE_CFG] if SUNDANCE_CFG else []) + list(II238) + [
                "z3-tool", "z3-tool-proof", "alt-ergo"] + list(CVC5_PROOF):
        path = results_csv(root, bench, cfg)
        if not path.exists():
            continue
        rows = []
        for r in csv.DictReader(open(path, newline="")):
            f = r["file"]
            if prefix and not f.startswith(prefix):
                continue
            if keep is not None and f not in keep:
                continue
            if dedupe and bench == "verus" and f.startswith("anvil/splinterdb-smt-"):
                continue
            rows.append(r)
        out[cfg] = (sorted(t for t in (float(r["time_seconds"]) for r in rows if r["result"] == "unsat")
                           if t <= MAX_TIME), n_manifest if n_manifest is not None else len(rows))
    return out


def series_for(data):
    """Legend order keeps yellow (Alt-Ergo) away from z3's orange (validated adjacent palette)."""
    s = [(SUNDANCE_CFG or "sundance-proof", "Sundance (proofs)", BLUE, "-"),
         ("z3-tool", "Z3", ORANGE, "-"),
         ("z3-tool-proof", "Z3 (proofs)", ORANGE, DASH)]
    cvc = [c for c in CVC5_PROOF if c in data]
    if cvc:
        best = max(cvc, key=lambda c: len(data[c][0]))
        s.append((best, CVC5_PROOF[best], AQUA, "-"))
    s.append(("alt-ergo", "Alt-Ergo", YELLOW, "-"))
    if SUNDANCE_CFG:
        return [x for x in s if x[0] in data]
    # Run 3: the other Sundance variants (palette slots 5-7, validated in this order)
    s += [("sundance-semper-proof", "Sundance semper (proofs)", MAGENTA, "-"),
          ("sundance-minisat", "Sundance MiniSat", GREEN, "-"),
          ("sundance-internal-proof", "Sundance internal arith (proofs)", VIOLET, "-")]
    return [x for x in s if x[0] in data]


SUNDANCE_ONLY = False
SUNDANCE_CFG = None
SUNDANCE_238FIX = False
II238 = ["sundance-default-proof", "sundance-egraph-semper-proof", "sundance-sat-minisat",
         "sundance-arith-z3-proof"]


def sundance_series(data):
    if SUNDANCE_238FIX:  # same four validated slots as the run-3 Sundance-only plots
        s = [("sundance-default-proof", "Default (proofs)", BLUE, "-"),
             ("sundance-egraph-semper-proof", "Semper (proofs)", MAGENTA, "-"),
             ("sundance-sat-minisat", "MiniSat", GREEN, "-"),
             ("sundance-arith-z3-proof", "Z3 arithmetic (proofs)", VIOLET, "-")]
        return [x for x in s if x[0] in data]
    semper = ("sundance-semper-proof", "Semper (proofs)") if "sundance-semper-proof" in data else \
        ("sundance-semper-unpatched-proof", "Semper (proofs)*")
    s = [("sundance-proof", "Default (proofs)", BLUE, "-"),
         (semper[0], semper[1], MAGENTA, "-"),
         ("sundance-minisat", "MiniSat", GREEN, "-"),
         ("sundance-internal-proof", "Internal arith (proofs)", VIOLET, "-")]
    return [x for x in s if x[0] in data]


def plot(key, title, data, out_dir):
    series = sundance_series(data) if SUNDANCE_ONLY else series_for(data)
    total = max(n for _, n in data.values())
    plt.rcParams.update({"font.size": 20, "axes.titlesize": 22})
    fig, ax = plt.subplots(figsize=(8.6, 5.8), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_3)
    ax.tick_params(colors=INK_2, labelsize=20, length=5, width=1.1)
    ax.grid(True, which="major", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)

    for z, (cfg, label, color, ls) in enumerate(series):
        times, n = data[cfg]
        xs = [0.01] + times
        ys = [0.0] + [100.0 * (i + 1) / n for i in range(len(times))]
        ax.step(xs, ys, where="post", color=color, linewidth=3.2, linestyle=ls, label=label,
                zorder=10 - z, solid_capstyle="round")

    ax.set_xscale("log")
    ax.set_xlim(0.01, MAX_TIME)
    ticks = [t for t in (0.01, 0.1, 1, 10) if t < MAX_TIME] + [MAX_TIME]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t:g}" for t in ticks])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(decimals=0))
    ax.set_xlabel("time (seconds)", color=INK_2, fontsize=23)
    ax.set_ylabel("queries solved", color=INK_2, fontsize=23)
    if SUNDANCE_CFG:
        leg = ax.legend(loc=LEGEND_LOC.get(key, "best"), frameon=True, fontsize=18, labelcolor=INK_2,
                        handlelength=1.8, handletextpad=0.6, labelspacing=0.3, borderpad=0.45,
                        borderaxespad=0.4, framealpha=0.92)
        leg.get_frame().set_edgecolor(GRID)
        leg.get_frame().set_linewidth(0.8)
    elif SUNDANCE_ONLY:
        ax.legend(loc=LEGEND_LOC.get(key, "best") if SUNDANCE_238FIX else "upper left", frameon=True, fontsize=17, labelcolor=INK_2,
                  handlelength=1.8, handletextpad=0.6, labelspacing=0.3, borderpad=0.45,
                  borderaxespad=0.4, framealpha=0.92).get_frame().set_edgecolor(GRID)
    else:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, frameon=False, fontsize=17,
                  labelcolor=INK_2, handlelength=1.8, handletextpad=0.6, labelspacing=0.35,
                  columnspacing=1.6)

    fig.tight_layout()
    for ext in ("png", "pdf"):
        name = (f"cdf_modularity_ablation_{key}" if SUNDANCE_238FIX else f"cdf_sundance_{key}") if SUNDANCE_ONLY \
            else f"cdf_clean_{key}"
        fig.savefig(out_dir / f"{name}.{ext}", dpi=400, bbox_inches="tight")
    plt.close(fig)
    return [(label, len(data[cfg][0]), data[cfg][1]) for cfg, label, _, _ in series]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--manifests", default=None, help="default: <root>/manifests")
    ap.add_argument("--out", default=None)
    ap.add_argument("--sundance-only", action="store_true", help="plot only the 4 Sundance variants")
    ap.add_argument("--sundance-238fix", "--modularity-ablation", action="store_true",
                    help="plot the #238 + fixes variants (default, semper, MiniSat) and z3incremental")
    ap.add_argument("--sundance", default=None, metavar="CFG",
                    help="5-line plot with this Sundance config as the Sundance line")
    ap.add_argument("--keep-duplicates", action="store_true")
    ap.add_argument("--combined", action="store_true", help="Verus + held-out and Dafny + F* figures instead of the 4 sets")
    a = ap.parse_args()
    global SUNDANCE_ONLY, SUNDANCE_CFG, SUNDANCE_238FIX, MAX_TIME
    SUNDANCE_238FIX = a.sundance_238fix
    SUNDANCE_ONLY = a.sundance_only or a.sundance_238fix
    SUNDANCE_CFG = a.sundance
    root = Path(a.root)
    try:  # the time axis follows the run's timeout (60 s in the paper)
        import json
        MAX_TIME = float(json.loads((root / "run_settings.json").read_text())["timeout"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if a.manifests is None:
        a.manifests = str(root / "manifests")
    out_dir = Path(a.out) if a.out else root / "plots" / (f"clean_{a.sundance}" if a.sundance else
                                                          "modularity_ablation" if a.sundance_238fix else "clean")
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"unsat within {MAX_TIME:.0f} s of wall time", "",
             "| set | series | unsat | queries |", "|---|---|---:|---:|"]
    def load_set(bench, prefix):
        mf = Path(a.manifests) / f"{bench}.txt" if a.manifests else None
        keep = set(mf.read_text().split()) if mf and mf.exists() else None
        return load(root, bench, prefix, keep, not a.keep_duplicates)

    def merge(parts):
        parts = [d for d in parts if d]
        if not parts:
            return {}
        cfgs = set.intersection(*(set(d) for d in parts))  # a series is drawn only if it ran on every part
        return {c: (sorted(t for d in parts for t in d[c][0]), sum(d[c][1] for d in parts)) for c in cfgs}

    groups = ([(key, title, merge([load_set(b, p) for b, p in parts])) for key, title, parts in COMBINED_SETS]
              if a.combined else [(key, title, load_set(bench, prefix)) for key, title, bench, prefix in SETS])
    for key, title, data in groups:
        if not data or not max(n for _, n in data.values()):
            continue
        for label, n, total in plot(key, title, data, out_dir):
            lines.append(f"| {title} | {label} | {n:,} | {total:,} |")
    (out_dir / (("summary_sundance" if SUNDANCE_ONLY else "summary") + ("_combined" if a.combined else "") + ".md")).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
