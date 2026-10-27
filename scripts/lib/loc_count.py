import json, sys, subprocess, os
# usage: count.py LABEL ROOT EXTS [EXCLUDED_RELPATH_PREFIX ...]   (exts comma-separated; prefix '!' = include-only)
label, root, exts, *rest = sys.argv[1:]
exts = tuple('.' + e for e in exts.split(','))
excl = [r for r in rest if not r.startswith('+')]
only = [r[1:] for r in rest if r.startswith('+')]
files = []
for dp, dn, fn in os.walk(root):
    for f in fn:
        rel = os.path.relpath(os.path.join(dp, f), root)
        if not f.endswith(exts): continue
        if any(rel == e or rel.startswith(e.rstrip('/') + '/') for e in excl): continue
        if only and not any(rel == e or rel.startswith(e.rstrip('/') + '/') for e in only): continue
        files.append(os.path.join(dp, f))
code = cm = bl = 0
if files:
    d = json.loads(subprocess.run(['tokei', '-o', 'json', '--no-ignore', *files], capture_output=True, text=True).stdout)
    langs = {'.rs': ['Rust'], '.ml': ['OCaml']}.get(exts[0], ['C++', 'C Header', 'C++ Header', 'C'])
    for l in langs:
        if l in d: code += d[l]['code']; cm += d[l]['comments']; bl += d[l]['blanks']
print(f"{label:<44} files={len(files):>5}  code={code:>8}  comments={cm:>7}  blanks={bl:>7}")
