# Artifact: Sundance: A Simple SMT Solver for Program Verification

A Docker image with Sundance (built from [yaspar-org/Sundance-SMT](https://github.com/yaspar-org/Sundance-SMT)),
the solvers it is compared against, and scripts that rerun the paper's evaluation.

## Quick start

```sh
git clone https://github.com/amarshah1/sundace_artifact.git && cd sundace_artifact
docker buildx build -t sundance-artifact .                    # ~10 min
mkdir -p benchmarks results
RUN="docker run --rm --user $(id -u):$(id -g) -e HOME=/tmp -e MPLCONFIGDIR=/tmp"
$RUN -v $PWD/benchmarks:/benchmarks sundance-artifact \
    fetch_benchmarks.sh --only verus --only heldout --only dafny_fstar --asset UFLIA-fs_vwasm.tar.xz /benchmarks
$RUN -v $PWD/benchmarks:/benchmarks:ro -v $PWD/results:/results sundance-artifact \
    smoke_test.sh 5 10                                        # 5 queries per set, 10 s timeout, ~5 min
```

The smoke test prints one summary line per (benchmark set, config); the results are in `results/smoke/`.
`--user` makes the output files yours instead of root's.

## Architectures

The image builds for `linux/amd64` (x86_64) and `linux/arm64` (e.g. Apple Silicon Macs, AWS Graviton).
`docker buildx build` builds for the machine it runs on. Sundance and Alt-Ergo are compiled from source; Z3 and
cvc5 are the official release builds for that architecture. The paper's numbers were measured on amd64.
On a Mac, give Docker Desktop enough CPUs and memory (Settings > Resources).

## Contents

| path in the image | what |
|---|---|
| `/opt/sundance/bin/sundance-smt` | Sundance, built from `SUNDANCE_COMMIT` (default: main `c175059`), features `local-z3,minisat`. Build info: `/opt/sundance/info/sundance-smt.txt` |
| `/opt/solvers/z3-5.3.0/z3` | Z3 5.3.0 |
| `/opt/solvers/cvc5-1.4.2/cvc5` | cvc5 1.4.2, static release |
| `/opt/solvers/alt-ergo-2.4.3-free/alt-ergo` | Alt-Ergo 2.4.3 (alt-ergo-free), built with opam on OCaml 5.2.1 |
| `/opt/z3-4.13.4` | libz3 4.13.4, linked into Sundance for `--arithmetic z3incremental` |
| `/artifact/scripts` | the scripts below |
| `/artifact/manifests/paper` | the file lists the paper ran on |

To build another Sundance commit: `docker buildx build --build-arg SUNDANCE_COMMIT=<commit> -t sundance-artifact .`

## Benchmarks

`fetch_benchmarks.sh /benchmarks` downloads all three sets (3 GB download, ~85 GB extracted):

| set | source | queries |
|---|---|---|
| Verus | [amarshah1/verus_benchmarks](https://github.com/amarshah1/verus_benchmarks) | 3,763 (the tables drop 1,187 duplicate `anvil/splinterdb-smt-*` queries) |
| Verus held-out | [amarshah1/sundance_heldout_benchmarks](https://github.com/amarshah1/sundance_heldout_benchmarks) | 4,086 |
| Dafny / F\* | [amarshah1/dafny_fstar_benchmarks](https://github.com/amarshah1/dafny_fstar_benchmarks) (release v1.0) | 11,674 Dafny + 3,195 F\* |

## Running the evaluations

```sh
docker run --rm -v $PWD/benchmarks:/benchmarks:ro -v $PWD/results:/results sundance-artifact <command>
```

| eval | command | time* |
|---|---|---|
| Solver comparison (RQ1/RQ2) | `run_all_solvers.sh --manifests /artifact/manifests/paper -j 150` | ~4.5 h |
| Sundance configurations (RQ3) | `run_sundance_configs.sh --manifests /artifact/manifests/paper -j 150` | ~3 h more |
| Tables and figures | `make_tables.sh`, `make_plots.sh` | seconds |
| Supported fraction (91.3% / 93.0% / 97.1%) | `count_supported.py` | seconds |
| Lines of code | `count_lines.sh --paper` (needs network) | ~2 min |

\* On a 192-thread machine at `-j 150`; expect about 150/N times longer at `-j N`. Add `--sample N` to run N
random queries per set. Results go to `/results/paper/results/<set>/<config>_results.csv`.

## Configurations

All Sundance configs use the same binary; `--infer-triggers` is added on Dafny/F\*. 60 s per query.

| config | command |
|---|---|
| `sundance-default-proof` | `sundance-smt --arithmetic internalincremental --stats FILE --proof=P --timeout=60` |
| `sundance-sat-minisat` | `sundance-smt --arithmetic internalincremental --sat-backend minisat --stats FILE --timeout=60` (no proofs) |
| `sundance-arith-z3-proof` | `sundance-smt --arithmetic z3incremental --stats FILE --proof=P --timeout=60` |
| `z3-tool`, `z3-tool-proof` | `z3 [proof=true] --st [Verus: options from the file's :source header] FILE -t:60000` |
| `cvc5-nocbqi-strict-proof` | `cvc5 [Dafny/F*: --incremental] --no-cbqi --user-pat=strict --produce-proofs --dump-proofs --proof-format-mode=cpc --proof-granularity=dsl-rewrite --stats FILE --tlimit-per=60000` |
| `alt-ergo` | `alt-ergo --timelimit=60 PREP`, where PREP is FILE rewritten by `prep_smtlib.py --legacy-ae` (untimed) so that Alt-Ergo 2.4.3 can parse it |

The Semper e-graph is not on Sundance main yet, so the Semper config is not included.

## Licenses

Sundance: Apache-2.0. Z3: MIT. cvc5: BSD-3. Alt-Ergo (alt-ergo-free): CeCILL-C. Benchmarks: CC BY 4.0.
