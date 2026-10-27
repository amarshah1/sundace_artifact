#!/usr/bin/env python3
"""
Driver for the paper's evaluation: runs (benchmark set x solver config) with run_solver.py. Same solver flags and per-benchmark-set
differences as the paper's run; Sundance is a single build whose configurations are flags.

Suites:
  solvers           RQ1/RQ2: Sundance (Default), Z3 (tool options), Z3 (tool options, proofs),
                    cvc5 --no-cbqi --user-pat=strict (proofs), Alt-Ergo
  sundance-configs  RQ3: Default, MiniSat, Z3 arithmetic (Semper: not on Sundance main yet)

Benchmark sets (under --bench-root, as created by fetch_benchmarks.sh):
  verus          verus_benchmarks/UFDTLIA/20241211-verus      (3,763 files; tables drop the 1,187 duplicates)
  verus_heldout  sundance_heldout_benchmarks/UFDTLIA          (4,086)
  mariposa       dafny_fstar_benchmarks/UFLIA                 (14,869: d_* = Dafny, fs_* = F*)

Output (--out): results/<bench>/<config>_results.{csv,txt}, proofs/<bench>/<config>/...,
manifests/<bench>.txt, logs/. A run whose results CSV exists is skipped (rerun = resume).
"""
import argparse
import os
import random
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVERS = Path(os.environ.get("SOLVERS_DIR", "/opt/solvers"))
SUNDANCE_BIN = Path(os.environ.get("SUNDANCE_BIN_DIR", "/opt/sundance/bin"))
Z3 = str(SOLVERS / "z3-5.3.0/z3")                         # Z3 5.3.0 (PyPI wheel binary)
CVC5 = str(SOLVERS / "cvc5-1.4.2/cvc5")                   # cvc5 1.4.2 static release
ALTERGO = str(SOLVERS / "alt-ergo-2.4.3-free/alt-ergo")   # alt-ergo-free 2.4.3, OCaml 5.2.1
PREP = str(HERE / "prep_smtlib.py")

CVC5_PROOF = "--produce-proofs --dump-proofs --proof-format-mode=cpc --proof-granularity=dsl-rewrite"
CVC5_STRICT = "--no-cbqi --user-pat=strict"

# Sundance configurations: one binary (built from github.com/yaspar-org/Sundance-SMT), modules picked by flags.
# (config name, flags, produces proofs, label). --infer-triggers is added on Dafny/F*.
SUNDANCE = SUNDANCE_BIN / "sundance-smt"
SUNDANCE_VARIANTS = {
    "sundance-default-proof": (["--arithmetic", "internalincremental"], True, "Sundance / Default (proofs)"),
    "sundance-sat-minisat":   (["--arithmetic", "internalincremental", "--sat-backend", "minisat"], False,
                               "MiniSat (no proofs: the MiniSat backend has no proof tracer)"),
    "sundance-arith-z3-proof": (["--arithmetic", "z3incremental"], True, "Z3 arithmetic (proofs)"),
    # Semper e-graph: not on Sundance main yet; add its config here once it is.
}
SUITES = {
    "solvers": ["sundance-default-proof", "z3-tool", "z3-tool-proof", "cvc5-nocbqi-strict-proof", "alt-ergo"],
    "sundance-configs": ["sundance-default-proof", "sundance-sat-minisat", "sundance-arith-z3-proof"],
}
BENCHES = {  # name -> (path under bench root, family)
    "verus": ("verus_benchmarks/UFDTLIA/20241211-verus", "verus"),
    "verus_heldout": ("sundance_heldout_benchmarks/UFDTLIA", "verus"),
    "mariposa": ("dafny_fstar_benchmarks/UFLIA", "mariposa"),
}


def config(name, family):
    """(run_solver.py args, produces proofs) for one config on one benchmark family."""
    if name in SUNDANCE_VARIANTS:
        flags, proofs, _ = SUNDANCE_VARIANTS[name]
        flags = (["--infer-triggers"] if family == "mariposa" else []) + flags   # Dafny/F* lack patterns
        args = ["--kind=sundance", f"--solver={SUNDANCE}"]
        if flags:
            args.append(f"--sundance-flags={' '.join(flags)}")
        return args, proofs
    if name == "cvc5-nocbqi-strict-proof":
        cvc5 = CVC5 if family == "verus" else f"{CVC5} --incremental"   # Boogie emits (push 1)
        return ["--kind=cvc5", f"--solver={cvc5} {CVC5_STRICT} {CVC5_PROOF}"], True
    if name in ("z3-tool", "z3-tool-proof"):
        # Verus: the verifier's options are recorded in each file's :source header; Dafny/F*: in-file set-options
        args = ["--kind=z3", f"--solver={Z3}"] + (["--z3-header-options"] if family == "verus" else [])
        if name == "z3-tool-proof":
            return args + ["--z3-proof-production"], True
        return args, False
    if name == "alt-ergo":
        return ["--kind=altergo", f"--solver={ALTERGO}", f"--prep-script={PREP}", "--prep-args=--legacy-ae"], False
    raise SystemExit(f"unknown config {name}")


def list_files(path: Path):
    out = []
    for r, _, files in os.walk(str(path)):
        for f in files:
            p = Path(r) / f
            if f.endswith(".smt2") and not any(x.startswith(".") for x in p.relative_to(path).parts):
                out.append(str(p.relative_to(path)))
    return sorted(out)


def sample(files, bench, n, seed):
    """n files per set (Mariposa: n Dafny + n F*), deterministic."""
    groups = {}
    for f in files:
        key = ("d_" if f.startswith("d_") else "fs_") if bench == "mariposa" else ""
        groups.setdefault(key, []).append(f)
    rng = random.Random(seed)
    return sorted(x for g in groups.values() for x in rng.sample(g, min(n, len(g))))


def log(fh, msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    fh.write(line + "\n")
    fh.flush()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", choices=sorted(SUITES), action="append",
                    help="config suite(s) to run (default: solvers)")
    ap.add_argument("--configs", nargs="*", help="run only these config names")
    ap.add_argument("--only", nargs="*", choices=sorted(BENCHES), help="benchmark sets (default: all)")
    ap.add_argument("--bench-root", default=os.environ.get("BENCH_ROOT", "/benchmarks"))
    ap.add_argument("--out", default=os.environ.get("RESULTS_ROOT", "/results") + "/paper")
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count(),
                    help="parallel queries (the paper ran up to 150 on a 192-thread machine)")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--manifests", default=None,
                    help="directory with <bench>.txt file lists (e.g. /artifact/manifests/paper); default: all files")
    ap.add_argument("--sample", type=int, default=0, help="run only N random files per set (smoke tests)")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    names = []
    for s in a.suite or ["solvers"]:
        names += [c for c in SUITES[s] if c not in names]
    if a.configs:
        names = [c for c in names if c in a.configs] or a.configs
    out = Path(a.out).resolve()
    for d in ("logs", "manifests", "results", "proofs", "scratch"):
        (out / d).mkdir(parents=True, exist_ok=True)
    benches = [b for b in BENCHES if not a.only or b in a.only]
    with open(out / "logs/driver.log", "a") as fh:
        log(fh, f"driver start: configs={names} benches={benches} jobs={a.jobs} timeout={a.timeout} out={out}")
        if any(n in SUNDANCE_VARIANTS for n in names) and not SUNDANCE.exists():
            log(fh, f"WARNING: {SUNDANCE} missing; the Sundance configs will be skipped")
        for bench in benches:
            path = Path(a.bench_root) / BENCHES[bench][0]
            mf = out / "manifests" / f"{bench}.txt"
            if not mf.exists():
                if not path.is_dir():
                    log(fh, f"WARNING: {path} missing; skipping {bench}")
                    continue
                files = (Path(a.manifests, f"{bench}.txt").read_text().split() if a.manifests
                         else list_files(path))
                if a.sample:
                    files = sample(files, bench, a.sample, a.seed)
                mf.write_text("".join(f + "\n" for f in files))
            log(fh, f"manifest {bench}: {len(mf.read_text().split())} files ({path})")
        if not any((out / "manifests" / f"{b}.txt").exists() for b in benches):
            log(fh, f"ERROR: no benchmark set found under {a.bench_root}; run fetch_benchmarks.sh {a.bench_root} first")
            sys.exit(1)
        for bench in benches:
            path, family = Path(a.bench_root) / BENCHES[bench][0], BENCHES[bench][1]
            mf = out / "manifests" / f"{bench}.txt"
            if not mf.exists():
                continue
            for name in names:
                if name in SUNDANCE_VARIANTS and not SUNDANCE.exists():
                    continue
                if name == "alt-ergo" and not Path(ALTERGO).exists():
                    log(fh, f"WARNING: {ALTERGO} missing; skipping alt-ergo")
                    continue
                res_dir = out / "results" / bench
                if (res_dir / f"{name}_results.csv").exists():
                    log(fh, f"skip {bench}/{name} (results exist)")
                    continue
                extra, proofs = config(name, family)
                cmd = [sys.executable, str(HERE / "run_solver.py"), str(path), "-j", str(a.jobs),
                       f"--timeout={a.timeout}", f"-o={res_dir}", f"--run-name={name}",
                       f"--files-from={mf}", f"--scratch-dir={out / 'scratch'}",
                       f"--grace={60 if proofs else 30}"] + extra
                if proofs:
                    cmd += [f"--proofs-dir={out / 'proofs' / bench}", "--compress-proofs"]
                log(fh, f"start {bench}/{name}: {' '.join(shlex.quote(c) for c in cmd)}")
                t0 = time.time()
                rc = subprocess.run(cmd, stdout=open(out / "logs" / f"{bench}_{name}.log", "w"),
                                    stderr=subprocess.STDOUT).returncode
                log(fh, f"end {bench}/{name}: rc={rc} wall={time.time() - t0:.0f}s")
        log(fh, "driver done")


if __name__ == "__main__":
    main()
