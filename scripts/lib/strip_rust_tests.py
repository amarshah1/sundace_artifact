"""Copy a Rust source tree to dst, removing every item annotated #[cfg(test)] (and #[test] fns)."""
import os, re, sys, shutil

ATTR = re.compile(r'^\s*#\[(cfg\(test\)|test)\]\s*$')

def item_end(src, i):
    """Given index i at the start of an item, return index just past its end (matching '}' or ';')."""
    depth, n = 0, len(src)
    while i < n:
        c = src[i]
        if src.startswith('//', i):
            i = src.find('\n', i); i = n if i < 0 else i
            continue
        if src.startswith('/*', i):
            d = 1; i += 2
            while i < n and d:
                if src.startswith('/*', i): d += 1; i += 2
                elif src.startswith('*/', i): d -= 1; i += 2
                else: i += 1
            continue
        m = re.match(r'b?r(#*)"', src[i:i+10])
        if m and (i == 0 or not (src[i-1].isalnum() or src[i-1] == '_')):
            close = '"' + m.group(1)
            i = src.find(close, i + len(m.group(0))) + len(close)
            continue
        if c == '"':
            i += 1
            while src[i] != '"':
                i += 2 if src[i] == '\\' else 1
            i += 1; continue
        if c == "'":
            m = re.match(r"'(\\.[^']*|[^\\'])'", src[i:i+12])
            if m: i += len(m.group(0)); continue
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return i + 1
        elif c == ';' and depth == 0: return i + 1
        i += 1
    raise ValueError("unterminated item")

def strip(text):
    removed = 0
    lines = text.splitlines(keepends=True)
    out, idx = [], 0
    offs = [0]
    for l in lines: offs.append(offs[-1] + len(l))
    li = 0
    while li < len(lines):
        if ATTR.match(lines[li]):
            end = item_end(text, offs[li + 1])
            # advance li to the line containing end-1
            j = li
            while offs[j + 1] < end: j += 1
            removed += j - li + 1
            li = j + 1
            continue
        out.append(lines[li]); li += 1
    return ''.join(out), removed

src, dst = sys.argv[1], sys.argv[2]
skip_dirs = set(sys.argv[3:])
total = 0
for root, dirs, files in os.walk(src):
    rel = os.path.relpath(root, src)
    dirs[:] = [d for d in dirs if os.path.normpath(os.path.join(rel, d)) not in skip_dirs]
    for f in files:
        if not f.endswith('.rs'): continue
        p = os.path.join(root, f); q = os.path.join(dst, rel, f)
        os.makedirs(os.path.dirname(q), exist_ok=True)
        new, r = strip(open(p).read())
        open(q, 'w').write(new)
        if r: print(f"{r:>6} lines stripped  {os.path.join(rel, f)}", file=sys.stderr)
        total += r
print(f"total physical lines stripped: {total}", file=sys.stderr)
