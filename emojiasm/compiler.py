"""AOT compiler: EmojiASM Program -> C source -> native binary."""

import os
import subprocess
import tempfile
from .parser import Program, Function, Instruction
from .opcodes import Op


def _hex(s: str) -> str:
    """Emoji string -> safe C identifier fragment."""
    return s.encode("utf-8").hex()


def _fn(name: str) -> str:
    return f"fn_{_hex(name)}"


def _lbl(func_hex: str, label: str) -> str:
    return f"lbl_{func_hex}_{_hex(label)}"


# ── C preambles ────────────────────────────────────────────────────────────

_PREAMBLE_NUMERIC = """\
#include <stdio.h>
#include <stdlib.h>

/* EmojiASM AOT compiled output (numeric-only fast path) */

#define STACK_MAX 4096
static double _stk[STACK_MAX];
static int _sp = 0;

#define PUSH_N(v) (_stk[_sp++]=(double)(v))
#define POP()     (_stk[--_sp])
#define PEEK()    (_stk[_sp-1])

static void _print_val(double v) {
    long long n = (long long)v;
    if ((double)n == v) printf("%lld", n); else printf("%g", v);
}
"""

_PREAMBLE_MIXED = """\
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* EmojiASM AOT compiled output */

/* Arena allocator — EmojiASM programs are short-lived, freed at exit */
static char _arena[1048576];
static int _arena_pos = 0;
static char *_arena_alloc(int sz) {
    if (_arena_pos + sz > (int)sizeof(_arena)) {
        fprintf(stderr, "arena exhausted\\n"); exit(1);
    }
    char *p = _arena + _arena_pos;
    _arena_pos += sz;
    return p;
}

typedef struct { int is_str; union { double num; const char *str; }; } Val;

#define STACK_MAX 4096
static Val _stk[STACK_MAX];
static int _sp = 0;

#define PUSH_N(v) (_stk[_sp].is_str=0, _stk[_sp++].num=(double)(v))
#define PUSH_S(v) (_stk[_sp].is_str=1, _stk[_sp++].str=(v))
#define POP()     (_stk[--_sp])
#define PEEK()    (_stk[_sp-1])

static void _print_val(Val v) {
    if (v.is_str) { printf("%s", v.str); return; }
    long long n = (long long)v.num;
    if ((double)n == v.num) printf("%lld", n); else printf("%g", v.num);
}
"""


def _uses_strings(program: Program) -> bool:
    for func in program.functions.values():
        for inst in func.instructions:
            if inst.op in (Op.PRINTS, Op.INPUT):
                return True
    return False


# ── Instruction emitter ────────────────────────────────────────────────────

def _emit_inst(inst: Instruction, lines: list, fhex: str, mem: dict, numeric_only: bool = True) -> None:
    op, arg = inst.op, inst.arg
    A = lines.append  # shorthand

    if op == Op.PUSH:
        if isinstance(arg, str) and not numeric_only:
            esc = arg.replace("\\","\\\\").replace('"','\\"').replace("\n","\\n").replace("\t","\\t")
            A(f'    PUSH_S("{esc}");')
        else:
            A(f'    PUSH_N({arg!r});')

    elif op == Op.POP:
        A('    POP();')

    elif op == Op.ADD:
        if numeric_only:
            A('    { double b=POP(),a=POP(); PUSH_N(a+b); }')
        else:
            A('    { Val b=POP(),a=POP();')
            A('      if (!a.is_str && !b.is_str) { PUSH_N(a.num+b.num); }')
            A('      else { char *s=_arena_alloc(512);')
            A('        if(a.is_str&&b.is_str) snprintf(s,512,"%s%s",a.str,b.str);')
            A('        else if(a.is_str){long long n=(long long)b.num;if((double)n==b.num)snprintf(s,512,"%s%lld",a.str,n);else snprintf(s,512,"%s%g",a.str,b.num);}')
            A('        else{long long n=(long long)a.num;if((double)n==a.num)snprintf(s,512,"%lld%s",n,b.str);else snprintf(s,512,"%g%s",a.num,b.str);}')
            A('        PUSH_S(s); } }')

    elif op == Op.SUB:
        if numeric_only:
            A('    { double b=POP(),a=POP(); PUSH_N(a-b); }')
        else:
            A('    { Val b=POP(),a=POP(); PUSH_N(a.num-b.num); }')

    elif op == Op.MUL:
        if numeric_only:
            A('    { double b=POP(),a=POP(); PUSH_N(a*b); }')
        else:
            A('    { Val b=POP(),a=POP(); PUSH_N(a.num*b.num); }')

    elif op == Op.DIV:
        if numeric_only:
            A('    { double b=POP(),a=POP();')
            A('      if(b==0){fprintf(stderr,"division by zero\\n");exit(1);}')
            A('      long long ai=(long long)a,bi=(long long)b;')
            A('      if((double)ai==a&&(double)bi==b) PUSH_N(ai/bi); else PUSH_N(a/b); }')
        else:
            A('    { Val b=POP(),a=POP();')
            A('      if(b.num==0){fprintf(stderr,"division by zero\\n");exit(1);}')
            A('      long long ai=(long long)a.num,bi=(long long)b.num;')
            A('      if((double)ai==a.num&&(double)bi==b.num) PUSH_N(ai/bi);')
            A('      else PUSH_N(a.num/b.num); }')

    elif op == Op.MOD:
        if numeric_only:
            A('    { double b=POP(),a=POP();')
            A('      if(b==0){fprintf(stderr,"modulo by zero\\n");exit(1);}')
            A('      PUSH_N((long long)a%(long long)b); }')
        else:
            A('    { Val b=POP(),a=POP();')
            A('      if(b.num==0){fprintf(stderr,"modulo by zero\\n");exit(1);}')
            A('      PUSH_N((long long)a.num%(long long)b.num); }')

    elif op == Op.DUP:
        A('    { _stk[_sp]=PEEK(); _sp++; }')

    elif op == Op.SWAP:
        if numeric_only:
            A('    { double b=POP(),a=POP(); _stk[_sp++]=b; _stk[_sp++]=a; }')
        else:
            A('    { Val b=POP(),a=POP(); _stk[_sp++]=b; _stk[_sp++]=a; }')

    elif op == Op.OVER:
        A('    { _stk[_sp]=_stk[_sp-2]; _sp++; }')

    elif op == Op.ROT:
        if numeric_only:
            A('    { double c=POP(),b=POP(),a=POP(); _stk[_sp++]=b; _stk[_sp++]=c; _stk[_sp++]=a; }')
        else:
            A('    { Val c=POP(),b=POP(),a=POP(); _stk[_sp++]=b; _stk[_sp++]=c; _stk[_sp++]=a; }')

    elif op == Op.JMP:
        A(f'    goto {_lbl(fhex, arg)};')

    elif op == Op.JZ:
        vtype = "double" if numeric_only else "Val"
        field = "" if numeric_only else ".num"
        A(f'    {{ {vtype} t=POP(); if(t{field}==0) goto {_lbl(fhex, arg)}; }}')

    elif op == Op.JNZ:
        vtype = "double" if numeric_only else "Val"
        field = "" if numeric_only else ".num"
        A(f'    {{ {vtype} t=POP(); if(t{field}!=0) goto {_lbl(fhex, arg)}; }}')

    elif op == Op.CMP_EQ:
        if numeric_only:
            A('    { double b=POP(),a=POP(); PUSH_N(a==b?1.0:0.0); }')
        else:
            A('    { Val b=POP(),a=POP(); PUSH_N(a.num==b.num?1.0:0.0); }')

    elif op == Op.CMP_LT:
        if numeric_only:
            A('    { double b=POP(),a=POP(); PUSH_N(a<b?1.0:0.0); }')
        else:
            A('    { Val b=POP(),a=POP(); PUSH_N(a.num<b.num?1.0:0.0); }')

    elif op == Op.CMP_GT:
        if numeric_only:
            A('    { double b=POP(),a=POP(); PUSH_N(a>b?1.0:0.0); }')
        else:
            A('    { Val b=POP(),a=POP(); PUSH_N(a.num>b.num?1.0:0.0); }')

    elif op == Op.AND:
        if numeric_only:
            A('    { double b=POP(),a=POP(); PUSH_N((a&&b)?1.0:0.0); }')
        else:
            A('    { Val b=POP(),a=POP(); PUSH_N((a.num&&b.num)?1.0:0.0); }')

    elif op == Op.OR:
        if numeric_only:
            A('    { double b=POP(),a=POP(); PUSH_N((a||b)?1.0:0.0); }')
        else:
            A('    { Val b=POP(),a=POP(); PUSH_N((a.num||b.num)?1.0:0.0); }')

    elif op == Op.NOT:
        if numeric_only:
            A('    { double a=POP(); PUSH_N(a?0.0:1.0); }')
        else:
            A('    { Val a=POP(); PUSH_N(a.num?0.0:1.0); }')

    elif op == Op.STORE:
        A(f'    {mem[arg]} = POP();')

    elif op == Op.LOAD:
        A(f'    _stk[_sp++] = {mem[arg]};')

    elif op == Op.CALL:
        A(f'    {_fn(arg)}();')

    elif op == Op.RET:
        A('    return;')

    elif op == Op.PRINTS:
        esc = str(arg).replace("\\","\\\\").replace('"','\\"').replace("\n","\\n").replace("\t","\\t")
        A(f'    PUSH_S("{esc}");')

    elif op == Op.PRINT:
        vtype = "double" if numeric_only else "Val"
        A(f'    {{ {vtype} v=POP(); _print_val(v); }}')

    elif op == Op.PRINTLN:
        vtype = "double" if numeric_only else "Val"
        A(f'    {{ {vtype} v=POP(); _print_val(v); printf("\\n"); }}')

    elif op == Op.INPUT:
        A('    { char *buf=_arena_alloc(4096);')
        A('      if(!fgets(buf,4096,stdin)){buf[0]=0;}')
        A('      else{int l=strlen(buf);if(l>0&&buf[l-1]==\'\\n\')buf[l-1]=0;}')
        A('      PUSH_S(buf); }')

    elif op == Op.INPUT_NUM:
        A('    { double v=0; if(scanf("%lf",&v)!=1){fprintf(stderr,"Invalid numeric input\\n");exit(1);} PUSH_N(v); }')

    elif op == Op.HALT:
        A('    exit(0);')

    elif op == Op.NOP:
        pass  # nothing


# ── Main compiler entry point ───────────────────────────────────────────────

def compile_to_c(program: Program) -> str:
    """Return a complete C program equivalent to the EmojiASM Program."""
    numeric_only = not _uses_strings(program)
    lines = [_PREAMBLE_NUMERIC if numeric_only else _PREAMBLE_MIXED]

    # Collect all named memory cells across all functions
    mem: dict[str, str] = {}  # emoji -> c_name
    idx = 0
    for func in program.functions.values():
        for inst in func.instructions:
            if inst.op in (Op.STORE, Op.LOAD) and inst.arg not in mem:
                mem[inst.arg] = f"_mem{idx}"
                idx += 1

    mem_type = "double" if numeric_only else "Val"
    mem_init = "0.0" if numeric_only else "{0, {.num=0}}"
    for emoji, c_name in mem.items():
        lines.append(f'static {mem_type} {c_name} = {mem_init}; /* {emoji} */')
    if mem:
        lines.append('')

    # Forward declarations
    for name in program.functions:
        lines.append(f'static void {_fn(name)}(void);')
    lines.append('')

    # Function bodies
    for name, func in program.functions.items():
        fhex = _hex(name)
        lines.append(f'static void {_fn(name)}(void) {{')

        # Build reverse label map: ip -> [label, ...]
        ip_labels: dict[int, list[str]] = {}
        for lbl, ip in func.labels.items():
            ip_labels.setdefault(ip, []).append(lbl)

        for ip, inst in enumerate(func.instructions):
            for lbl in ip_labels.get(ip, []):
                lines.append(f'  {_lbl(fhex, lbl)}:;')
            _emit_inst(inst, lines, fhex, mem, numeric_only)

        lines.append('}')
        lines.append('')

    # main()
    lines.append('int main(void) {')
    lines.append(f'    {_fn(program.entry_point)}();')
    lines.append('    return 0;')
    lines.append('}')

    return '\n'.join(lines)


def compile_program(program: Program, opt_level: str = '-O2') -> str:
    """Compile to C then to a native binary. Returns path to the binary."""
    c_src = compile_to_c(program)

    fd, c_path = tempfile.mkstemp(suffix='.c')
    with os.fdopen(fd, 'w') as f:
        f.write(c_src)

    bin_path = c_path[:-2]  # strip .c
    result = subprocess.run(
        ['clang', opt_level, '-o', bin_path, c_path],
        capture_output=True, text=True,
    )
    os.unlink(c_path)

    if result.returncode != 0:
        raise RuntimeError(f'Compilation failed:\n{result.stderr}')

    return bin_path
