#!/usr/bin/env python3
"""
Run one solver configuration on every .smt2 file of a benchmark folder, in parallel, and write
  <out-dir>/<run-name>_results.txt   per-file log + summary
  <out-dir>/<run-name>_results.csv   file,result,time_seconds,<stats...>   (input of the table/plot scripts)
  <proofs-dir>/<run-name>/<rel>.{edrat,proof}[.gz]   proofs of unsat results (proof configs only)

Artifact copy of the paper run's scripts/run_verus.py (final_experiments/2026-10-15_03-14-03). Kept
unchanged: the command lines, solver-internal timeouts + grace before the hard kill, z3 header options,
(get-proof) injection, Alt-Ergo preprocessing (untimed), verdict classification, stats parsing and the CSV
format. Removed (host-specific): MemAvailable / JVM admission control, perf profiling, cargo build, git-info
capture, SMTInterpol, rerun filters. Added: --files-from (run a file list, e.g. the paper's manifests).

Classification (as in the paper's run):
  - verdict = first stdout line that is exactly unsat / sat / unknown; sat counts as 'other';
  - killed at --timeout + --grace -> 'timeout'; 'unknown' at >= 95% of the timeout -> 'timeout'
    (Sundance: its own solve_time stat);
  - Alt-Ergo: no verdict line -> 'error' (it exits 0 on errors); 'timeout' line -> 'timeout'.
A query counts as solved only if result == unsat and time_seconds <= the threshold (60 s in the paper).
"""
import argparse
import csv
import gzip
import json
import multiprocessing as mp
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SET_OPTION_RE = re.compile(r'^\s*\(set-option\s[^\n]*\n?', re.M)
CHECK_SAT_RE = re.compile(r'^(\s*\(check-sat\)[^\n]*)$', re.M)
HEADER_OPTIONS_RE = re.compile(r'following options:(.*?)\|\)', re.S)
HEADER_OPTION_RE = re.compile(r'\(set-option :(\S+) ([^)]*)\)')
VERDICT_LINE_RE = re.compile(r'^[ \t]*(unsat|sat|unknown)[ \t\r]*$', re.M)
AE_VERDICT_RE = re.compile(r'^(unsat|sat|unknown|timeout)$', re.M)
AE_STEPS_RE = re.compile(r'\(([\d.]+)\)\s*\((\d+) steps\)')


def prepare_query(filepath: Path, strip_set_options: bool, inject_get_proof: bool,
                  scratch_dir: str) -> Tuple[Path, Optional[Path]]:
    """(path to give the solver, scratch file to delete afterwards or None); the benchmark is never touched."""
    if not strip_set_options and not inject_get_proof:
        return filepath, None
    text = filepath.read_text()
    if strip_set_options:
        text = SET_OPTION_RE.sub('', text)
    if inject_get_proof:
        text, n = CHECK_SAT_RE.subn(r'\1\n(get-proof)', text, count=1)
        if n == 0:
            text += "\n(get-proof)\n"
    scratch = Path(scratch_dir)
    scratch.mkdir(parents=True, exist_ok=True)
    tmp = scratch / f"{os.getpid()}_{time.monotonic_ns()}_{filepath.name}"
    tmp.write_text(text)
    return tmp, tmp


def header_z3_options(filepath: Path) -> List[str]:
    """z3 options recorded in a Verus query's :source header, as z3 CLI params k=v in header order."""
    with open(filepath, errors='replace') as f:
        head = f.read(8192)
    m = HEADER_OPTIONS_RE.search(head)
    if not m:
        return []
    return [f"{k}={v.strip()}" for k, v in HEADER_OPTION_RE.findall(m.group(1))]


def read_head_tail(path: Path, head_bytes: int = 1 << 16, tail_bytes: int = 1 << 16) -> str:
    size = path.stat().st_size
    with open(path, 'rb') as f:
        if size <= head_bytes + tail_bytes:
            return f.read().decode(errors='replace')
        head = f.read(head_bytes).decode(errors='replace')
        f.seek(size - tail_bytes)
        tail = f.read().decode(errors='replace')
    tail = tail.split("\n", 1)[1] if "\n" in tail else tail
    return head + "\n" + tail


def remove_if_exists(path: Path):
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def gzip_file(path: Path) -> Path:
    gz_path = path.with_name(path.name + ".gz")
    with open(path, 'rb') as src, gzip.open(gz_path, 'wb', compresslevel=6) as dst:
        shutil.copyfileobj(src, dst, 1 << 20)
    path.unlink()
    return gz_path


def run_solver_on_file(filepath: Path, solver: str, timeout: int, proof_file: Optional[str],
                       solver_kind: str, stdout_path: Optional[str], grace: int):
    """Run one query; returns (stdout, stderr, wall seconds, returncode or None if killed)."""
    start_time = time.time()
    try:
        command = shlex.split(solver) + [str(filepath)]
        if proof_file is not None:
            command.append(f"--proof={proof_file}")
        if solver_kind == "sundance":
            command.append(f"--timeout={timeout}")
        elif solver_kind == "z3":
            command.append(f"-t:{timeout * 1000}")
        elif solver_kind == "cvc5":
            command.append(f"--tlimit-per={timeout * 1000}")
        subprocess_timeout = timeout + grace
        if stdout_path is not None:
            with open(stdout_path, 'w') as out_f:
                try:
                    result = subprocess.run(command, stdout=out_f, stderr=subprocess.PIPE, text=True,
                                            timeout=subprocess_timeout)
                except subprocess.TimeoutExpired:
                    return "", "TIMEOUT", time.time() - start_time, None
            end_time = time.time()
            return read_head_tail(Path(stdout_path)), result.stderr, end_time - start_time, result.returncode
        result = subprocess.run(command, capture_output=True, text=True, timeout=subprocess_timeout)
        return result.stdout, result.stderr, time.time() - start_time, result.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", time.time() - start_time, None
    except Exception as e:
        return "", f"ERROR: {e}", time.time() - start_time, None


# --------------------------------------------------------------------------- Alt-Ergo
def prep_query(filepath: Path, out_path: Path, prep_script: str, prep_args: str) -> Tuple[bool, str]:
    """python3 prep_smtlib.py IN OUT [args] (untimed)."""
    cmd = [sys.executable, prep_script, str(filepath), str(out_path)] + shlex.split(prep_args or "")
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                           timeout=1200)
    except subprocess.TimeoutExpired:
        return False, "prep timeout"
    if p.returncode != 0 or not out_path.exists():
        lines = [l for l in (p.stderr or "").strip().splitlines() if l.strip()]
        return False, "prep rc=%d %s" % (p.returncode, lines[-1][:200] if lines else "")
    return True, ""


def run_monitored(cmd: List[str], out_path: Path, err_path: Path, limit: float):
    """Run cmd with stdout/stderr to files; SIGKILL at `limit` s. (killed, exit code, wall, max RSS MB)."""
    start = time.time()
    with open(str(out_path), 'w') as fo, open(str(err_path), 'w') as fe:
        p = subprocess.Popen(cmd, stdout=fo, stderr=fe)
    killed = False
    deadline = start + limit
    delay = 0.005
    while True:
        pid, status, ru = os.wait4(p.pid, os.WNOHANG)
        if pid:
            break
        if time.time() >= deadline:
            p.kill()
            pid, status, ru = os.wait4(p.pid, 0)
            killed = True
            break
        time.sleep(delay)
        delay = min(0.05, delay * 1.5)
    wall = time.time() - start
    rc = -os.WTERMSIG(status) if os.WIFSIGNALED(status) else os.WEXITSTATUS(status)
    return killed, rc, wall, ru.ru_maxrss // 1024


def _first_line(text: str, pattern: str) -> str:
    for line in text.splitlines():
        if re.search(pattern, line):
            return line.strip()[:200]
    return ""


def classify_altergo(stdout: str, stderr: str, wall: float, timeout: int) -> Tuple[str, str]:
    m = AE_VERDICT_RE.search(stdout)
    if not m:
        return 'error', (_first_line(stderr, r'rror|Fatal|xception') or _first_line(stdout, r'rror')
                         or "no verdict")
    v = m.group(1)
    if v == 'unsat':
        return 'unsat', ""
    if v == 'sat':
        return 'other', "sat"
    if v == 'timeout' or '(error "timeout")' in stdout or wall >= timeout * 0.95:
        return 'timeout', ""
    return 'unknown', ""


def process_altergo(filepath: Path, solver: str, timeout: int, opts: Dict[str, Any]):
    stats: Dict[str, Any] = {}
    scratch = Path(opts['scratch_dir'])
    scratch.mkdir(parents=True, exist_ok=True)
    tag = "%d_%d" % (os.getpid(), time.monotonic_ns())
    prepped = scratch / ("%s_%s" % (tag, filepath.name))
    out_path, err_path = scratch / (tag + ".out"), scratch / (tag + ".err")
    try:
        t0 = time.time()
        ok, why = prep_query(filepath, prepped, opts['prep_script'], opts.get('prep_args', ''))
        stats['prep_s'] = round(time.time() - t0, 2)
        if not ok:
            stats['detail'] = why
            return filepath, 'error', 0.0, "", "ERROR: " + why, stats
        cmd = shlex.split(solver) + ["--timelimit=%d" % timeout, str(prepped)]
        killed, rc, wall, maxrss = run_monitored(cmd, out_path, err_path, timeout + opts['grace'])
        stdout, stderr = read_head_tail(out_path), read_head_tail(err_path)
        stats['exit_code'] = rc
        stats['max_rss_mb'] = maxrss
        if killed:
            category, detail = 'timeout', "killed at %ds" % (timeout + opts['grace'])
        else:
            category, detail = classify_altergo(stdout, stderr, wall, timeout)
            m = AE_STEPS_RE.search(stderr)
            if m:
                stats['ae_time'] = float(m.group(1))
                stats['ae_steps'] = int(m.group(2))
        if detail:
            stats['detail'] = detail
        return filepath, category, wall, stdout, stderr, stats
    finally:
        for p in (prepped, err_path, out_path):
            remove_if_exists(p)


# --------------------------------------------------------------------------- stats + classification
def flatten_stats(obj: Any, prefix: str = "") -> Dict[str, Any]:
    flat = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            flat.update(flatten_stats(v, f"{prefix}.{k}" if prefix else k))
    elif not isinstance(obj, list):
        flat[prefix] = obj
    return flat


def extract_sundance_stats(text: str) -> Dict[str, Any]:
    """Trailing JSON block of sundance --stats (stderr), flattened; per_round fields as comma lists."""
    stripped = text.rstrip()
    if not stripped.endswith("}"):
        return {}
    depth, start = 0, -1
    for i in range(len(stripped) - 1, -1, -1):
        if stripped[i] == "}":
            depth += 1
        elif stripped[i] == "{":
            depth -= 1
            if depth == 0:
                start = i
                break
    if start < 0:
        return {}
    try:
        raw = json.loads(stripped[start:])
    except json.JSONDecodeError:
        return {}
    flat = flatten_stats(raw)
    per_round = raw.get("per_round")
    if per_round and isinstance(per_round, list):
        keys: Dict[str, List[Any]] = {}
        for r in per_round:
            for k, v in flatten_stats({k: v for k, v in r.items() if k != "round"}).items():
                keys.setdefault(k, []).append(v)
        for k, vals in keys.items():
            flat[f"per_round.{k}"] = ",".join(str(x) for x in vals)
    return flat


def extract_z3_stats(text: str) -> Dict[str, Any]:
    stripped = text.rstrip()
    if not stripped.endswith(")"):
        return {}
    depth, start = 0, -1
    for i in range(len(stripped) - 1, -1, -1):
        if stripped[i] == ")":
            depth += 1
        elif stripped[i] == "(":
            depth -= 1
            if depth == 0:
                start = i
                break
    if start < 0:
        return {}
    stats: Dict[str, Any] = {}
    for m in re.finditer(r':([a-zA-Z0-9_\-]+)\s+([\d.eE\-+]+)', stripped[start + 1:-1]):
        key, val = m.group(1), m.group(2)
        try:
            stats[key] = int(val)
        except ValueError:
            try:
                stats[key] = float(val)
            except ValueError:
                pass
    return stats


def _parse_number(s: str):
    m = re.match(r'^(-?[\d.]+(?:[eE][\-+]?\d+)?)(ms|s|us|ns)?$', s.strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        try:
            return float(m.group(1))
        except ValueError:
            return None


def extract_cvc5_stats(text: str) -> Dict[str, Any]:
    stats: Dict[str, Any] = {}
    for line in text.splitlines():
        if " = " not in line:
            continue
        key, _, val = line.partition(" = ")
        key, val = key.strip(), val.strip()
        if not key or not val:
            continue
        if val.startswith("{") and val.endswith("}"):
            for pair in val[1:-1].split(","):
                if ":" in pair:
                    sk, _, sv = pair.partition(":")
                    num = _parse_number(sv)
                    if num is not None:
                        stats[f"{key}.{sk.strip()}"] = num
        else:
            num = _parse_number(val)
            if num is not None:
                stats[key] = num
    return stats


def split_at_verdict(stdout: str) -> Tuple[str, str]:
    m = VERDICT_LINE_RE.search(stdout)
    return (stdout[:m.start()], stdout[m.end():]) if m else (stdout, "")


def categorize_result(stdout: str, stderr: str) -> str:
    for line in stdout.splitlines():
        s = line.strip()
        if s == "unsat":
            return 'unsat'
        if s == "sat":
            return 'other'
        if s == "unknown":
            return 'unknown'
    if 'TIMEOUT' in stderr:
        return 'timeout'
    if 'ERROR' in stderr:
        return 'error'
    return 'other'


# --------------------------------------------------------------------------- one job
def process_one(args):
    try:
        return _process_one(args)
    except Exception as e:  # e.g. disk full while writing a proof: record it, keep the other jobs running
        return args[0], 'error', 0.0, "", "", {'detail': f"runner exception: {type(e).__name__}: {e}"[:200],
                                               'runner_exception': 1}


def _process_one(args):
    filepath, base, solver, timeout, proofs_dir, solver_kind, opts = args
    if solver_kind == "altergo":
        return process_altergo(filepath, solver, timeout, opts)
    proof_file = stdout_path = proof_path = None
    if proofs_dir:
        suffix = ".edrat" if solver_kind == "sundance" else ".proof"
        proof_path = Path(proofs_dir) / filepath.relative_to(base).with_suffix(suffix)
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        if solver_kind == "sundance":
            proof_file = str(proof_path)
        else:  # z3/cvc5 print the proof on stdout
            stdout_path = str(proof_path)
    if opts.get('z3_header_options'):
        solver = " ".join([solver] + [shlex.quote(o) for o in header_z3_options(filepath)])
    query_path, scratch_file = prepare_query(filepath, opts.get('strip_set_options', False),
                                             opts.get('inject_get_proof', False), opts['scratch_dir'])
    try:
        stdout, stderr, time_taken, returncode = run_solver_on_file(
            query_path, solver, timeout, proof_file, solver_kind, stdout_path, opts['grace'])
    finally:
        if scratch_file is not None:
            remove_if_exists(scratch_file)
    category = categorize_result(stdout, stderr)
    stats: Dict[str, Any] = {}
    if solver_kind == "sundance":
        stats = extract_sundance_stats(stderr)
        if category == 'unknown' and stats.get('solve_time', 0) >= timeout * 0.95:
            category = 'timeout'
    else:
        if stderr != "TIMEOUT" and not (stderr and stderr.startswith("ERROR")):
            stats = extract_z3_stats(stdout) if solver_kind == "z3" else extract_cvc5_stats(stderr)
        if category == 'unknown' and time_taken >= timeout * 0.95:
            category = 'timeout'
    if returncode is not None:
        stats['exit_code'] = returncode
        if returncode < 0 and category != 'unsat':
            stats['detail'] = f"killed by signal {-returncode} (out of memory?)"
    pre_verdict, post_verdict = split_at_verdict(stdout)
    if solver_kind == "z3":
        # z3 5.3.0 reports an (error ...) for Verus's (declare-fun partial-order ...) and continues
        errs = [l.strip() for l in pre_verdict.splitlines() if l.lstrip().startswith("(error")]
        if errs:
            stats['input_errors'] = len(errs)
            stats['detail'] = errs[0][:200]
    if proof_path is not None:
        if category == 'unsat' and proof_path.exists():
            stats['proof_bytes'] = proof_path.stat().st_size
            if solver_kind == "z3":
                stats['proof_error'] = int("(error" in post_verdict)
            if opts.get('compress_proofs'):
                gzip_file(proof_path)
        else:
            remove_if_exists(proof_path)
    return filepath, category, time_taken, stdout, stderr, stats


def available_cpus() -> int:
    """CPUs this process may use: the affinity mask, further capped by a cgroup v2 CPU quota (docker --cpus)."""
    try:
        n = len(os.sched_getaffinity(0))
    except AttributeError:
        n = os.cpu_count() or 1
    try:  # cgroup v2
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if quota != "max":
            n = min(n, max(1, int(int(quota) / int(period))))
    except (OSError, ValueError):
        try:  # cgroup v1
            quota = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read_text())
            period = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read_text())
            if quota > 0 and period > 0:
                n = min(n, max(1, quota // period))
        except (OSError, ValueError):
            pass
    return max(1, n)


def file_sha256(path) -> str:
    import hashlib
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def list_files(folder: Path) -> List[Path]:
    out = []
    for root, _, files in os.walk(str(folder)):
        for f in sorted(files):
            p = Path(root) / f
            if f.endswith('.smt2') and not any(x.startswith('.') for x in p.parts):
                out.append(p)
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("-o", "--output-dir", required=True)
    ap.add_argument("--run-name", required=True)
    ap.add_argument("-j", "--jobs", type=int, default=available_cpus())
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--grace", type=int, default=30, help="seconds past --timeout before the hard kill")
    ap.add_argument("--solver", required=True, help="solver command (binary + fixed flags)")
    ap.add_argument("--kind", required=True, choices=["sundance", "z3", "cvc5", "altergo"])
    ap.add_argument("--sundance-flags", default="")
    ap.add_argument("--z3-header-options", action="store_true",
                    help="append the z3 options from each Verus query's :source header")
    ap.add_argument("--z3-proof-production", action="store_true",
                    help="z3 proof=true + (get-proof) after (check-sat) in a scratch copy")
    ap.add_argument("--proofs-dir", default=None, help="save proofs of unsat results under DIR/<run-name>/")
    ap.add_argument("--compress-proofs", action="store_true")
    ap.add_argument("--scratch-dir", default="/tmp/sundance-artifact-scratch")
    ap.add_argument("--prep-script", default=None)
    ap.add_argument("--prep-args", default="")
    ap.add_argument("--files-from", default=None, help="file with relative paths (one per line) to run")
    a = ap.parse_args()

    folder = Path(a.folder).resolve()
    solver = a.solver
    if a.kind == "sundance":
        solver = (solver + " " + a.sundance_flags).strip() + " --stats"
    elif a.kind == "z3":
        if a.z3_proof_production:
            solver += " proof=true"
        solver += " --st"
    elif a.kind == "cvc5":
        solver += " --stats"
    if a.kind == "altergo" and not a.prep_script:
        sys.exit("alt-ergo needs --prep-script")
    if a.files_from:
        files = [folder / l.strip() for l in Path(a.files_from).read_text().splitlines() if l.strip()]
        missing = [f for f in files if not f.exists()]
        if missing:
            sys.exit(f"{len(missing)} listed files missing, e.g. {missing[0]}")
    else:
        files = list_files(folder)
    opts = {'grace': a.grace, 'scratch_dir': a.scratch_dir, 'compress_proofs': a.compress_proofs,
            'z3_header_options': a.z3_header_options, 'inject_get_proof': a.z3_proof_production,
            'prep_script': a.prep_script, 'prep_args': a.prep_args}
    proofs = str(Path(a.proofs_dir) / a.run_name) if a.proofs_dir else None
    out_dir = Path(a.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    progress = out_dir / f"{a.run_name}_results.progress.jsonl"
    txt = open(out_dir / f"{a.run_name}_results.txt", "a" if progress.exists() else "w")

    def log(msg):
        txt.write(msg + "\n")
        txt.flush()
        print(msg, flush=True)

    log(f"Processing {len(files)} files in '{folder}' with {a.jobs} parallel processes")
    log(f"Solver: {solver}")
    log(f"Kind: {a.kind}  Timeout: {a.timeout}s  Grace: {a.grace}s  Proofs: {proofs}")
    for k, v in sorted(opts.items()):
        log(f"Option {k}: {v}")
    log("-" * 60)
    t0 = time.time()
    # Progress file: one JSON line per finished query, so an interrupted run resumes where it stopped.
    # Its first line records the settings; a progress file from other settings is discarded.
    settings = {"solver": solver, "solver_sha256": file_sha256(shlex.split(solver)[0]), "kind": a.kind,
                "timeout": a.timeout, "grace": a.grace, "files": len(files), "proofs": bool(proofs)}
    done: Dict[str, Tuple[str, float, Dict[str, Any]]] = {}
    if progress.exists():
        lines = progress.read_text().splitlines()
        try:
            if lines and json.loads(lines[0]) == settings:
                for line in lines[1:]:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue  # torn last line
                    done[r["file"]] = (r["result"], r["time"], r["stats"])
                log(f"Resuming: {len(done)} of {len(files)} queries already done (now with -j {a.jobs})")
            else:
                log("Discarding a progress file from a run with other settings (solver binary, flags or timeout)")
        except ValueError:
            pass
    if not done:
        progress.write_text(json.dumps(settings) + "\n")
    rows, counts = [], {}
    for f in files:
        rel = str(f.relative_to(folder))
        if rel in done:
            cat, t, stats = done[rel]
            rows.append((f, cat, t, stats))
            counts[cat] = counts.get(cat, 0) + 1
    jobs = [(f, folder, solver, a.timeout, proofs, a.kind, opts) for f in files
            if str(f.relative_to(folder)) not in done]
    killed = runner_errors = 0
    if progress.read_bytes()[-1:] not in (b"", b"\n"):
        with open(progress, "a") as pf:
            pf.write("\n")   # a torn last line from a kill: start the next record on its own line
    try:
      with open(progress, "a") as pf, mp.Pool(processes=max(1, a.jobs)) as pool:
        for i, (f, cat, t, _, _, stats) in enumerate(pool.imap_unordered(process_one, jobs), len(rows) + 1):
            rows.append((f, cat, t, stats))
            counts[cat] = counts.get(cat, 0) + 1
            killed += "killed by signal" in str(stats.get('detail', ''))
            if stats.get('runner_exception'):
                runner_errors += 1   # not saved: such queries are retried on the next run
            else:
                pf.write(json.dumps({"file": str(f.relative_to(folder)), "result": cat, "time": t,
                                     "stats": stats}) + "\n")
                pf.flush()
            extra = (" " + " ".join(f"{k}={v}" for k, v in stats.items()
                                    if not str(k).startswith("per_round"))) if stats else ""
            log(f"[{i}/{len(files)}] {f.relative_to(folder)} -> {cat.upper()} [{t:.2f}s]{extra[:400]}")
    except KeyboardInterrupt:
        log(f"\ninterrupted after {len(rows)} of {len(files)} queries; rerun the same command to resume")
        sys.exit(130)
    log(f"\nProcessing completed in {time.time() - t0:.2f} seconds")
    log("SUMMARY " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())) + f" total={len(files)}")
    if killed:
        log(f"WARNING: {killed} solver runs were killed by a signal before the timeout (out of memory?); "
            "they count as unsolved. Use fewer parallel jobs (-j) or a machine with more memory.")
    keys: List[str] = []
    for _, _, _, s in rows:
        for k in s:
            if k not in keys:
                keys.append(k)
    csv_path = out_dir / f"{a.run_name}_results.csv"
    tmp = csv_path.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(['file', 'result', 'time_seconds'] + keys)
        for f, cat, t, s in sorted(rows, key=lambda r: str(r[0])):
            w.writerow([str(f.relative_to(folder)), cat, f"{t:.2f}"] + [s.get(k, "") for k in keys])
    os.replace(tmp, csv_path)
    meta = out_dir / f"{a.run_name}_results.json"
    if runner_errors:  # not finished: the next run retries these queries
        remove_if_exists(meta)
        log(f"ERROR: {runner_errors} queries failed in the runner itself (see 'runner exception' above, e.g. a full "
            "disk); fix the cause and rerun to retry them")
        sys.exit(2)
    # Written last: the driver treats a run as finished only if this file matches the CSV.
    meta.write_text(json.dumps(dict(settings, rows=len(rows), counts=counts, killed_by_signal=killed,
                                    jobs=a.jobs, finished=time.time())) + "\n")
    remove_if_exists(progress)


if __name__ == "__main__":
    main()
