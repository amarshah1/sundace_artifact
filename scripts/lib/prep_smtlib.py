"""Rewrite a z3-dialect SMT-LIB query (Verus / Dafny-Boogie / F*) into standard
SMT-LIB 2.6 that Alt-Ergo (dolmen frontend) and SMTInterpol accept.

usage: prep_smtlib.py IN OUT [--keep-options] [--legacy-ae]

Rewrites (all semantics-preserving):
  1. insert (set-logic ALL) before the first non set-option/set-info command
  2. drop all (set-option ...) commands (z3-only tuning; both solvers ignore them anyway)
  3. z3 tester sugar is-C: (define-fun is-C ((x T)) Bool ((_ is C) x)) is emitted after
     the declare-datatypes of C (kept as a symbol so it may appear inside :pattern, where
     dolmen cannot parse (_ is C)); for parametric datatypes (is-C x) -> ((_ is C) x)
  4. symbols starting with '@' (reserved in SMT-LIB 2.6; F* emits @x0/@u0/@lb0)
     ->  P + '@...' for the first prefix P in at/AT/at_/... unused in the file
  7. z3 n-ary sugar (and x) -> x, (or x) -> x, (and) -> true, (or) -> false
  5. (let ...) inside :pattern terms is inlined (Boogie emits it; dolmen rejects it)
  6. :no-pattern <term> attributes are dropped (z3 extension)
  8. --legacy-ae (for alt-ergo-free 2.4.3 and its legacy psmt2 parser):
     - every term attribute except :pattern/:named (:qid, :skolemid, :weight, :lblpos, ...) is
       dropped, and a (! t) left without attributes becomes t
     - (set-info ...) commands are dropped (unknown keywords such as :boogie-vc-id are lexer errors)
     - (_ is C) is rewritten to is-C (defined as above), and for a single-constructor datatype
       (which 2.4.3 turns into a record and on which it rejects (_ is C)) is-C is defined as
       true, which is exact for such a type
     - |s| is unquoted when s is a simple symbol (2.4.3 treats |T@T| and T@T as different)
"""
import re, sys

src, dst = sys.argv[1], sys.argv[2]
keep_options = '--keep-options' in sys.argv[3:]
legacy = '--legacy-ae' in sys.argv[3:]

TOK = re.compile(r'\s+|;[^\n]*|\|[^|]*\||"(?:[^"]|"")*"|[()]|[^\s()|";]+')
toks = [m.group(0) for m in TOK.finditer(open(src).read())]

SIMPLE = re.compile(r'[A-Za-z~!@$%^&*_+=<>.?/-][A-Za-z0-9~!@$%^&*_+=<>.?/-]*$')
RESERVED = {'!', '_', 'as', 'let', 'exists', 'forall', 'match', 'par', 'BINARY', 'DECIMAL',
            'HEXADECIMAL', 'NUMERAL', 'STRING'}
if legacy:
    toks = [t[1:-1] if t[0] == '|' and SIMPLE.match(t[1:-1]) and t[1:-1] not in RESERVED else t
            for t in toks]
    # (_ is C) -> is-C
    t0, i = [], 0
    while i < len(toks):
        if toks[i] == '(':
            j, parts = i + 1, []
            while j < len(toks) and len(parts) < 4:
                if not toks[j][0].isspace():
                    parts.append(toks[j])
                j += 1
            if len(parts) == 4 and parts[0] == '_' and parts[1] == 'is' and parts[3] == ')':
                t0.append('is-' + parts[2]); i = j
                continue
        t0.append(toks[i]); i += 1
    toks = t0
n = len(toks)


def is_ws(t):
    return t[0].isspace() or t[0] == ';'


def match_end(ts, i):
    """index one past the s-expression starting at ts[i] (skips leading ws)."""
    while is_ws(ts[i]):
        i += 1
    if ts[i] != '(':
        return i + 1
    depth = 0
    while True:
        if ts[i] == '(':
            depth += 1
        elif ts[i] == ')':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1


def parse(ts):
    stack, cur = [], []
    for t in ts:
        if is_ws(t):
            continue
        if t == '(':
            stack.append(cur); cur = []
        elif t == ')':
            done = cur; cur = stack.pop(); cur.append(done)
        else:
            cur.append(t)
    return cur


def subst(e, env):
    if isinstance(e, str):
        return env.get(e, e)
    if len(e) == 3 and e[0] == 'let' and isinstance(e[1], list):
        new = dict(env)
        for b in e[1]:
            new[b[0]] = subst(b[1], env)          # parallel let: bind in outer env
        return subst(e[2], new)
    if e and e[0] in ('forall', 'exists') and isinstance(e[1], list):
        bound = {b[0] for b in e[1]}
        inner = {k: v for k, v in env.items() if k not in bound}
        return [e[0], e[1]] + [subst(x, inner) for x in e[2:]]
    return [subst(x, env) for x in e]


def show(e):
    return e if isinstance(e, str) else '(' + ' '.join(show(x) for x in e) + ')'


# constructor names (SMT-LIB 2.6 and old z3 `(declare-datatypes () ...)` syntax)
ctors = {}          # ctor -> datatype sort name, or None if the datatype is parametric
nctors = {}         # ctor -> number of constructors of its datatype
dt_end = {}         # token index of the end of a declare-datatypes -> its ctors
for i in range(n - 1):
    if toks[i] == '(' and toks[i + 1] == 'declare-datatypes':
        j = match_end(toks, i)
        e = parse(toks[i:j])[0]
        names = [d[0] if isinstance(d, list) else None for d in e[1]]
        here = []
        for k, dt in enumerate(e[-1]):
            sort = names[k] if k < len(names) else None
            if dt and dt[0] == 'par':
                body, sort = dt[2], None
            elif dt and isinstance(dt[0], str):   # old z3: (T (C ...) ...)
                body, sort = dt[1:], dt[0]
            else:
                body = dt
            for c in body:
                c = c[0] if isinstance(c, list) else c
                ctors[c] = sort
                nctors[c] = len(body)
                here.append(c)
        dt_end[j] = here

AT = next(p for p in ('at', 'AT', 'at_', 'AT_', 'at__', 'AT__')
          if not any(t.startswith(p + '@') for t in toks))

# pass 1: token-local rewrites (3, 4)
used = {t[3:] for t in toks if t.startswith('is-') and t[3:] in ctors}
t1 = []
for i, t in enumerate(toks):
    if i in dt_end:
        for c in dt_end[i]:
            if c in used and ctors[c] is not None:
                body = 'true' if legacy and nctors[c] == 1 else '((_ is %s) x)' % c
                t1.append('\n(define-fun is-%s ((x %s)) Bool %s)' % (c, ctors[c], body))
    if t.startswith('@'):
        t = AT + t
    elif t.startswith('is-') and t[3:] in ctors and ctors[t[3:]] is None and t1 and t1[-1] == '(':
        t1.extend(['(', '_', ' ', 'is', ' ', t[3:], ')'])
        continue
    t1.append(t)
if len(toks) in dt_end:
    sys.exit('prep: file ends with declare-datatypes')
toks, n = t1, len(t1)

# pass 2: structural rewrites (1, 2, 5, 6, 7, 8)
out = []
frames = []          # per open paren: [first element, #elements, out index of '(', out index of op]
i = 0
logic_done = False
while i < n:
    t = toks[i]
    if is_ws(t):
        out.append(t); i += 1
        continue
    if t != ')' and frames:
        f = frames[-1]
        f[1] += 1
        if f[1] == 1:
            f[0] = t; f[3] = len(out)
    if t == '(':
        if not frames:
            cmd = next(x for x in toks[i + 1:i + 4] if not is_ws(x))
            if (cmd == 'set-option' and not keep_options) or (cmd == 'set-info' and legacy):
                i = match_end(toks, i)
                continue
            if not logic_done and cmd not in ('set-option', 'set-info'):
                if cmd != 'set-logic':
                    out.append('(set-logic ALL)\n')
                logic_done = True
        frames.append([None, 0, len(out), None])
    elif t == ')':
        op, k, lp, opi = frames.pop()
        if op in ('and', 'or') and k <= 2:
            if k == 1:
                out[lp] = 'true' if op == 'and' else 'false'
                out[opi] = ''
            else:
                out[lp] = out[opi] = ''
            i += 1
            continue
        if op == '!' and k == 2:
            out[lp] = out[opi] = ''
            i += 1
            continue
    elif t == ':pattern':
        j = match_end(toks, i + 1)
        seg = toks[i + 1:j]
        if 'let' in seg:
            out.append(':pattern ' + show(subst(parse(seg)[0], {})))
        else:
            out.append(t); out.extend(seg)
        frames[-1][1] += 1
        i = j
        continue
    elif t == ':no-pattern':
        frames[-1][1] -= 1
        i = match_end(toks, i + 1)
        continue
    elif legacy and t[0] == ':' and t != ':named' and frames[-1][0] == '!':
        frames[-1][1] -= 1
        j = i + 1
        while j < n and is_ws(toks[j]):
            j += 1
        i = j if toks[j] == ')' or toks[j][0] == ':' else match_end(toks, j)
        continue
    out.append(t)
    i += 1

open(dst, 'w').write(''.join(out))
