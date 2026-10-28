# Artifact: Sundance: A Simple SMT Solver for Program Verification

A Docker image with Sundance (built from [yaspar-org/Sundance-SMT](https://github.com/yaspar-org/Sundance-SMT)),
the solvers it is compared against (Z3, cvc5, Alt-Ergo), and scripts that rerun the paper's evaluation and
rebuild its tables and figures.

## Prerequisites

- **Docker.** On macOS and Windows, use Docker Desktop. On Linux, you need Docker Engine with the `buildx` plugin, and your user in the `docker` group.
- **Disk:** about 10 GB for building the image (about 7 GB of it is Docker's build cache, which
  `docker builder prune` frees afterwards; the image itself is 0.7 GB); the quick start adds 35 MB. **The full evaluation needs about 100 GB**: 77 GB of
  benchmarks and about 15 GB of results (mostly proofs).
- **Memory:** a few GB per parallel query. A few queries need up to 10 GB, so on a laptop use `-j` of 4 or less.
- **Time:** building the image takes 10–20 minutes (Sundance and Alt-Ergo are compiled from source). **We ran the
  full evaluation with 150 queries in parallel** (on a machine with 192 hardware threads), where it takes about
  8.5 hours. With fewer cores it takes proportionally longer: about 150/N times as long at `-j N`, so several
  days on an 8-core machine.

## Quick start

```sh
git clone https://github.com/amarshah1/sundace_artifact.git    # or unzip the artifact's Zenodo archive
cd sundace_artifact
docker buildx build --load -t sundance-artifact .
# If you built the image under another name (VS Code's Docker extension, for example, suggests
# sundanceartifactexperiment), rename it so that run.sh finds it:
#   docker tag sundanceartifactexperiment sundance-artifact
./run.sh fetch_benchmarks.sh --sample 5 /benchmarks # 5 queries per set
./run.sh smoke_test.sh 5 10 4                     # those queries, 10 s timeout, 4 parallel jobs
./run.sh make_tables.sh /results/smoke_n5_t10     # tables from that run
./run.sh make_plots.sh /results/smoke_n5_t10      # figures from that run
```

What you should see:
- **Fetch:** about a minute: 5 random queries (fixed seed) from each of Verus, held-out Verus, Dafny and F\*, out
  of the paper's file lists. About 0.3 GB is downloaded (the Dafny and F\* queries are extracted from the two
  smallest release tarballs), and 35 MB stays on disk. It ends with `Dafny/F*: 10 sampled queries (OK)`.
- **Smoke test:** a few minutes, then one line per (benchmark set, config), for example `verus/z3-tool: unsat=5 total=5`.
  - `mariposa` is the Dafny/F\* set.
  - `unsat` means solved; `timeout` means no answer within the time limit.
  - `other` or `error` means the solver failed on that query. One Verus query (`verismo/tspec_e__array.smt2`), if sampled, does this for Sundance, cvc5 and Alt-Ergo, as in the paper.
  - Tables and plots go to `results/smoke_n5_t10/`.
- **Tables and figures:** `results/smoke_n5_t10/tables/solvers.txt` (the solver comparison, RQ1/RQ2) and
  `modularity_ablation.txt` (the Sundance configurations, RQ3), with the share of queries each config solved within
  1 s and 10 s (up to the run's timeout), by set and by project; the CDF plots are in `results/smoke_n5_t10/plots/`.
  (`smoke_test.sh` also makes them itself.) The same two commands work on any run's output folder.

## `run.sh`

`./run.sh COMMAND` runs `COMMAND` inside the image, as your own user, so the output files are yours:
- `./benchmarks` is mounted as `/benchmarks`. It is read-only, except for `fetch_benchmarks.sh`.
- `./results` is mounted as `/results`.
- `./run.sh` with no command opens a shell. Inside it you can run, for example:
  - `sundance-smt --arithmetic internalincremental FILE`
  - `z3 FILE`, `cvc5 FILE`, `alt-ergo FILE`
  - Dafny/F\* queries need `sundance-smt --infer-triggers`.
- To use other folders or another image, set `BENCH_DIR`, `RESULTS_DIR` or `SUNDANCE_IMAGE`.

Run `./run.sh` on your machine, not inside the container's shell: in the shell, run commands directly (for example
`smoke_test.sh 5 10 4`), and download benchmarks from outside (in the shell, `/benchmarks` is read-only). The
prompt inside the shell may read `I have no name!`. That is harmless.

## Benchmarks

`./run.sh fetch_benchmarks.sh /benchmarks` downloads all three sets: about 3 GB to download, about 77 GB on disk. Only the queries the evaluation runs are downloaded (the `UFDTLIA/` and `UFLIA/` folders). Each set is checked, by git commit for the Verus sets and by sha256 for the tarballs. Rerunning skips what is already there.

| set (`--only`) | source | queries |
|---|---|---|
| Verus (`verus`) | [amarshah1/verus_benchmarks](https://github.com/amarshah1/verus_benchmarks) | 3,763 (the tables drop 1,187 duplicate `anvil/splinterdb-smt-*` queries) |
| Verus held-out (`heldout`) | [amarshah1/sundance_heldout_benchmarks](https://github.com/amarshah1/sundance_heldout_benchmarks) | 4,086 |
| Dafny / F\* (`dafny_fstar`) | [amarshah1/dafny_fstar_benchmarks](https://github.com/amarshah1/dafny_fstar_benchmarks), release v1.0 | 11,674 Dafny + 3,195 F\* |

## Running the evaluations

**The full evaluation needs about 100 GB of disk and was run with 150 queries in parallel (about 8.5 hours); on a
machine with few cores it takes days.** Use `--sample N` to try a smaller version first.

| eval | command | time* |
|---|---|---|
| Download all benchmarks (do this first) | `./run.sh fetch_benchmarks.sh /benchmarks` (about 3 GB to download, 77 GB on disk) | ~15 min, depending on your connection |
| Solver comparison (RQ1/RQ2) | `./run.sh run_all_solvers.sh --manifests /artifact/manifests/paper -j N` | ~4.5 h |
| Sundance configurations (RQ3) | `./run.sh run_sundance_configs.sh --manifests /artifact/manifests/paper -j N` | ~4 h more |
| Tables and figures from your run | `./run.sh make_tables.sh RUN` and `./run.sh make_plots.sh RUN` (RUN: the run's output folder, default `/results/paper`) → `results/<run>/{tables,plots}/` | seconds |
| Supported fraction (91.3% / 93.0% / 97.1%) | `./run.sh count_supported.py` (counts the file lists of the benchmark repos, including the queries Sundance does not support, which are not downloaded) | seconds |
| Lines of code (13,612 / 519,367 / 358,294) | `./run.sh count_lines.sh --paper` (needs network; clones into `results/loc_count/`) | ~1 min |

\* At `-j 150` on the paper's 192-thread machine; expect about 150/N times longer at `-j N`. The 1 s and 10 s
columns depend on the machine and its load.

For comparison, the paper's numbers from its full run (% of queries solved within 60 s; the summary rows of
`tables/solvers.txt` and `tables/modularity_ablation.txt`):

| | Verus | Verus held-out | Dafny | F\* |
|---|---:|---:|---:|---:|
| Sundance (proofs) | 83.0 | 90.2 | 73.7 | 56.7 |
| Z3, tool options | 99.8 | 99.8 | 98.0 | 97.8 |
| Z3, tool options (proofs) | 91.8 | 97.7 | 66.5 | 97.7 |
| cvc5 (proofs) | 88.4 | 95.3 | 69.8 | 54.9 |
| Alt-Ergo | 79.8 | 82.8 | 70.4 | 59.3 |
| Sundance, Semper e-graph | 75.7 | 81.7 | 56.9 | 54.7 |
| Sundance, MiniSat | 79.2 | 86.1 | 70.4 | 49.5 |
| Sundance, Z3 arithmetic | 81.9 | 88.3 | 70.5 | 50.5 |

A small local run, start to finish (20 random queries per set, all solvers and Sundance configs; output in
`results/sample20_t60/`):

```sh
./run.sh run_all_solvers.sh --sample 20 -j 4
./run.sh run_sundance_configs.sh --sample 20 -j 4
./run.sh make_tables.sh /results/sample20_t60
./run.sh make_plots.sh /results/sample20_t60
```

Options of `run_all_solvers.sh` and `run_sundance_configs.sh` (see `--help`):

| option | meaning |
|---|---|
| `--only SET` | `verus`, `verus_heldout` (or `heldout`) or `mariposa` (or `dafny_fstar`); repeatable |
| `--configs NAME…` | only these configs (names below) |
| `--sample N` | N random queries per set (Dafny and F\* separately) |
| `--timeout S` | per-query time limit (default 60) |
| `-j N` | parallel queries (default: all CPUs available to the container) |
| `--manifests DIR` | the paper's file lists; files that are not downloaded are skipped with a warning |
| `--out DIR` | output folder (default `/results/paper` for the full paper run; other settings get their own folder, e.g. `/results/sample10_t60`) |

- **Checks:** before running, each config's command line is tried on a trivial query; a solver that fails it is reported and skipped.
- **Resuming:** rerunning a command (for example after Ctrl-C) resumes it. Finished runs are skipped, and an interrupted run continues from its last finished query. A run is redone if the solver binary changed.
- **Settings are fixed per output folder.** An output folder made with other settings (timeout, sample, file lists), or made before more of the listed files were downloaded, is refused. To start over, delete the folder or pick another `--out`. Tables of runs on a partial download say `PARTIAL`.
- **Failures:** if a solver does not start or a run fails, the command exits non-zero and says which run failed.
- **Output files:** results are in `results/<out>/results/<set>/<config>_results.csv`, one row per query.

## Configurations

Each Sundance config swaps one component of Default. The Semper e-graph is a compile-time feature, so it has its own
binary (`sundance-smt-semper`); the other configs are flags of `sundance-smt`. On Dafny/F\*, `--infer-triggers` is
added. 60 s per query.

| config | command |
|---|---|
| `sundance-default-proof` | `sundance-smt --arithmetic internalincremental --stats FILE --proof=P --timeout=60` |
| `sundance-egraph-semper-proof` | `sundance-smt-semper --arithmetic internalincremental --stats FILE --proof=P --timeout=60` |
| `sundance-sat-minisat` | `sundance-smt --arithmetic internalincremental --sat-backend minisat --stats FILE --timeout=60` (no proofs) |
| `sundance-arith-z3-proof` | `sundance-smt --arithmetic z3incremental --stats FILE --proof=P --timeout=60` |
| `z3-tool`, `z3-tool-proof` | `z3 [proof=true] --st [Verus: options from the file's :source header] FILE -t:60000` |
| `cvc5-nocbqi-strict-proof` | `cvc5 [Dafny/F*: --incremental] --no-cbqi --user-pat=strict --produce-proofs --dump-proofs --proof-format-mode=cpc --proof-granularity=dsl-rewrite --stats FILE --tlimit-per=60000` |
| `alt-ergo` | `alt-ergo --timelimit=60 PREP`. PREP is FILE rewritten by `prep_smtlib.py --legacy-ae` (untimed) so that Alt-Ergo 2.4.3 can parse it |

Semper is built from a separate branch of the Sundance repository (`semper-egraph-minimal`) because the Semper
e-graph integration is not yet in Sundance's main branch. Supporting Semper is a minor modification: the branch
is main plus the Semper adapter (a new module behind Sundance's e-graph interface, compiled
only with the `semper-egraph` feature) and about 80 lines of small changes elsewhere.

**Proof checking is not evaluated.** The paper checks Sundance's proofs with the proof checker Valido, which is not
open source yet; we are in the process of open-sourcing it. The proof configs still write their proofs, to
`results/<run>/proofs/`.

`sundance-smt --help` lists `z3incremental` as the default arithmetic, because this build links Z3. The configs always pass `--arithmetic` explicitly.

## Sundance and Alt-Ergo source

The image builds Sundance and Alt-Ergo from source snapshots shipped in `sources/` (with `SHA256SUMS`), so the
build does not depend on those projects' repositories. The two Sundance binaries come from
[yaspar-org/Sundance-SMT](https://github.com/yaspar-org/Sundance-SMT):

| binary | branch | commit |
|---|---|---|
| `sundance-smt` | `main` | [`c175059`](https://github.com/yaspar-org/Sundance-SMT/commit/c17505996a5405135d989334f45738903960bccf) (2026-10-26, "Make the internal, incremental arithmetic solver the default (#247)") |
| `sundance-smt-semper` | `semper-egraph-minimal` | [`5c15293`](https://github.com/yaspar-org/Sundance-SMT/commit/5c15293cd9404e319bdd149fde3c1c2ed13ed721) (2026-10-27, main `c175059` plus the Semper adapter) |

The snapshots are `sources/Sundance-SMT-c17505996a54.tar.gz` and `sources/Sundance-SMT-5c15293cd940.tar.gz`
(`git archive` of those commits, without history). Alt-Ergo is `sources/alt-ergo-2.4.3-free.tar.gz`, the
[2.4.3-free release](https://github.com/OCamlPro/alt-ergo/releases/tag/v2.4.3-free). Building another Sundance commit
(`--build-arg SUNDANCE_COMMIT=…`) clones it from GitHub instead.

## Contents of the image

| path | what |
|---|---|
| `/opt/sundance/bin/sundance-smt` | Sundance at `SUNDANCE_COMMIT` (default: main `c175059`). Features `local-z3,minisat`. Dependencies are pinned by `docker/Cargo.lock.<commit>`. Build info is in `/opt/sundance/info/` |
| `/opt/solvers/{z3-5.3.0,cvc5-1.4.2,alt-ergo-2.4.3-free}` | Z3 5.3.0, cvc5 1.4.2 (static), and Alt-Ergo 2.4.3 (alt-ergo-free, built with opam on OCaml 5.2.1), with their licenses |
| `/opt/sundance/bin/sundance-smt-semper` | Sundance with the Semper e-graph: branch `semper-egraph-minimal` (`5c15293`, main `c175059` plus the Semper adapter), features `local-z3,minisat,semper-egraph`, rustc 1.98.1. Dependencies pinned by `docker/Cargo.lock.5c15293cd940` |
| `/opt/z3-4.13.4` | libz3 4.13.4, linked into Sundance for `--arithmetic z3incremental` |
| `/artifact/scripts`, `/artifact/manifests` | the scripts, and the paper's file lists |

To build other Sundance commits, run `docker buildx build --load --build-arg SUNDANCE_COMMIT=<commit> --build-arg SUNDANCE_SEMPER_COMMIT=<commit> -t sundance-artifact .`. Without a matching `docker/Cargo.lock.<commit>`, its dependencies are resolved at build time.

## Architectures

The image builds for `linux/amd64` and `linux/arm64`, for example Apple Silicon Macs and AWS Graviton. It builds for the machine it runs on:
- Sundance and Alt-Ergo are compiled from source.
- Z3 and cvc5 are the official release builds for that architecture.

The paper's numbers were measured on amd64. On a Mac, give Docker Desktop at least 4 CPUs and 8 GB of memory (Settings > Resources).

## Licenses

| component | license |
|---|---|
| This artifact (scripts, Dockerfile, README) | Apache-2.0 (`LICENSE`) |
| Sundance | Apache-2.0 |
| Z3 | MIT |
| cvc5 | BSD-3 |
| Alt-Ergo (alt-ergo-free) | CeCILL-C |
| Benchmarks | CC BY 4.0 |

## Acknowledgments

This artifact was created with the help of Claude Opus 5.5.
