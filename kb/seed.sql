-- Seed findings: known facts about EmojiASM from codebase analysis
-- All confidence=verified because they were read directly from source

-- ── VM ─────────────────────────────────────────────────────────────────────

INSERT INTO findings(skill_id, topic, claim, evidence, source_title, source_type, confidence, tags) VALUES
(1, 'dispatch', 'The VM dispatches opcodes via a 30-branch if/elif chain in _exec_function', 'vm.py lines 77-228 contain sequential if/elif branches for every Op enum value. Python evaluates these top-to-bottom on each instruction.', 'emojiasm/vm.py', 'codebase', 'verified', 'dispatch,performance,vm'),
(1, 'dispatch', 'CALL uses Python recursion: _exec_function calls itself for each CALL opcode', 'vm.py Op.CALL handler: self.call_stack.append(...); self._exec_function(arg). The Python call stack mirrors the EmojiASM call stack.', 'emojiasm/vm.py', 'codebase', 'verified', 'call,recursion,vm'),
(1, 'limits', 'Default max_steps is 1,000,000 — a safety guard against infinite loops', 'VM.__init__: self.max_steps = 1_000_000. Raises VMError("Execution limit exceeded") when exceeded.', 'emojiasm/vm.py', 'codebase', 'verified', 'limits,safety'),
(1, 'limits', 'Default max_stack is 4,096 entries; both limits are configurable', 'VM.__init__(stack_size=4096). The CLI exposes --max-steps; stack_size must be set programmatically.', 'emojiasm/vm.py', 'codebase', 'verified', 'limits,stack'),
(1, 'memory', 'Named memory cells are stored in a plain Python dict keyed by emoji strings', 'self.memory: dict[str, object] = {}. Any emoji can be a memory address; capacity is unbounded by the VM itself.', 'emojiasm/vm.py', 'codebase', 'verified', 'memory,addressing'),
(1, 'output', 'PRINT/PRINTLN write to both stdout and output_buffer; tests use output_buffer for capture', 'vm.py: self.output_buffer.append(out); print(out, end=""). output_buffer is returned by vm.run().', 'emojiasm/vm.py', 'codebase', 'verified', 'io,testing'),
(1, 'stack', 'ADD performs string concatenation when either operand is a str instance', 'vm.py Op.ADD: if isinstance(a, str) or isinstance(b, str): self._push(str(a)+str(b))', 'emojiasm/vm.py', 'codebase', 'verified', 'strings,stack,arithmetic'),
(1, 'stack', 'DIV uses integer floor division when both operands are int, float division otherwise', 'vm.py Op.DIV: if isinstance(a,int) and isinstance(b,int): self._push(a//b) else self._push(a/b)', 'emojiasm/vm.py', 'codebase', 'verified', 'arithmetic,types'),
(1, 'debug', 'Debug mode prints a 🔍 trace line to stderr for every instruction with the last 5 stack entries', 'vm.py: if self.debug: print(f"  🔍 [{func_name}:{ip}] {inst.source}  stack={stack_preview}", file=sys.stderr)', 'emojiasm/vm.py', 'codebase', 'verified', 'debug,tooling'),

-- ── Parser ─────────────────────────────────────────────────────────────────

(2, 'labels', 'Labels are resolved to instruction indices at parse time, not at runtime', 'parser.py Function.labels: dict[str,int] maps label emoji to instruction index. No runtime lookup needed.', 'emojiasm/parser.py', 'codebase', 'verified', 'labels,performance'),
(2, 'structure', 'Program is a dict of Functions; each Function has a list of Instructions and a labels dict', 'dataclasses: Program{functions:dict[str,Function], entry_point:str}; Function{name,instructions,labels}; Instruction{op,arg,line_num,source}', 'emojiasm/parser.py', 'codebase', 'verified', 'architecture,dataclasses'),
(2, 'entry-point', 'Default entry point is 🏠; if absent the first defined function becomes the entry point', 'parser.py: if "🏠" not in program.functions: program.entry_point = next(iter(program.functions))', 'emojiasm/parser.py', 'codebase', 'verified', 'entry-point,conventions'),
(2, 'opcode-matching', 'Opcodes are identified by string prefix matching against EMOJI_TO_OP; order matters for variation selectors', 'parser.py: iterates EMOJI_TO_OP.items() and checks line.startswith(emoji_candidate). ✖️ and ✖ are both mapped; order in dict determines priority.', 'emojiasm/parser.py', 'codebase', 'verified', 'parsing,emoji,variation-selectors'),
(2, 'string-literals', 'String literals support double-quote, single-quote, and «guillemet» delimiters with \n \t \\ escapes', 'parser.py _extract_string_literal: checks text[0] in double-quote, single-quote, or «. Handles escape sequences via escape_map dict.', 'emojiasm/parser.py', 'codebase', 'verified', 'strings,parsing'),
(2, 'auto-function', 'Instructions before any 📜 directive are implicitly placed in a 🏠 function', 'parser.py: if current_func is None: current_func = Function(name="🏠")', 'emojiasm/parser.py', 'codebase', 'verified', 'conventions,parsing'),

-- ── Compiler ───────────────────────────────────────────────────────────────

(3, 'numeric-path', 'The compiler detects numeric-only programs (no PRINTS/INPUT) and uses a plain double[] stack instead of a Val struct', 'compiler.py _uses_strings(): returns True if any Op.PRINTS or Op.INPUT found. Selects _PREAMBLE_NUMERIC vs _PREAMBLE_MIXED.', 'emojiasm/compiler.py', 'codebase', 'verified', 'optimization,types,codegen'),
(3, 'numeric-path', 'The numeric-only path uses double _stk[4096] — 8 bytes/entry vs 16 bytes for Val struct — halving stack memory pressure', 'Val struct: int is_str (4 bytes) + padding (4 bytes) + double/ptr (8 bytes) = 16 bytes. double = 8 bytes.', 'emojiasm/compiler.py', 'codebase', 'verified', 'memory,performance,codegen'),
(3, 'labels', 'Labels are emitted as C goto labels using UTF-8 hex encoding of the emoji name to ensure valid C identifiers', 'compiler.py _hex(s): s.encode("utf-8").hex(). Labels like 🔁 become lbl_<func_hex>_f09f8481', 'emojiasm/compiler.py', 'codebase', 'verified', 'codegen,labels'),
(3, 'memory', 'Named memory cells become static global C variables prefixed _mem0, _mem1, etc.', 'compile_to_c() collects all STORE/LOAD args, assigns sequential C names, emits static Val or double declarations.', 'emojiasm/compiler.py', 'codebase', 'verified', 'codegen,memory'),
(3, 'string-leak', 'The mixed-mode compiler leaks memory: string concatenation (ADD with strings) mallocs 512 bytes without free', 'compiler.py Op.ADD mixed path: A("char *s=malloc(512);"). No corresponding free is emitted.', 'emojiasm/compiler.py', 'codebase', 'verified', 'bugs,memory,strings'),

-- ── Opcodes ────────────────────────────────────────────────────────────────

(4, 'variation-selectors', 'Some opcodes have two emoji variants to handle Unicode variation selectors: ✖/✖️ (MUL), 🖨/🖨️ (PRINTLN), 🏷/🏷️ (LABEL)', 'opcodes.py EMOJI_TO_OP: "✖️": Op.MUL, "✖": Op.MUL — both mapped. Variation selector U+FE0F is a zero-width modifier.', 'emojiasm/opcodes.py', 'codebase', 'verified', 'emoji,unicode,compatibility'),
(4, 'args', 'Only 8 opcodes take an argument: PUSH, JMP, JZ, JNZ, CALL, STORE, LOAD, PRINTS', 'opcodes.py OPS_WITH_ARG = {Op.PUSH, Op.JMP, Op.JZ, Op.JNZ, Op.CALL, Op.STORE, Op.LOAD, Op.PRINTS}', 'emojiasm/opcodes.py', 'codebase', 'verified', 'opcodes,parsing'),
(4, 'count', 'The instruction set has 31 opcodes across 6 categories: stack(6), arithmetic(5), comparison/logic(6), control(7), io(5), memory(2)', 'opcodes.py Op IntEnum: PUSH POP DUP SWAP OVER ROT | ADD SUB MUL DIV MOD | CMP_EQ CMP_LT CMP_GT AND OR NOT | JMP JZ JNZ CALL RET HALT NOP | PRINT PRINTLN PRINTS INPUT INPUT_NUM | STORE LOAD', 'emojiasm/opcodes.py', 'codebase', 'verified', 'opcodes,architecture'),

-- ── Performance ─────────────────────────────────────────────────────────────

(5, 'throughput', 'The EmojiASM interpreter achieves ~1M instructions/sec on Apple Silicon (M-series)', 'Benchmark: sum(1..50000) = ~650k instructions in ~617ms median. 650000/0.617 ≈ 1.05M inst/sec.', 'benchmarks/run.py', 'benchmark', 'verified', 'performance,throughput'),
(5, 'overhead', 'EmojiASM interpreted is ~33x slower than equivalent raw Python while-loop code', 'Benchmark: VM only 617ms vs Python subprocess 18ms for same N=50000 sum. 617/18 ≈ 34x.', 'benchmarks/run.py', 'benchmark', 'verified', 'performance,overhead,python'),
(5, 'compiled-vs-c', 'AOT compiled EmojiASM (clang -O2, numeric path) matches or beats hand-written C with runtime N', 'Benchmark: EmojiASM→C -O2: 3.6ms vs C -O2 runtime-N: 3.8ms for sum(1..50000). Within measurement noise.', 'benchmarks/run.py', 'benchmark', 'verified', 'compiler,performance,c'),
(5, 'constant-fold', 'clang -O2 constant-folds the hardcoded-N reference C benchmark: no loop runs at runtime', 'Assembly analysis: sum_n.c compiled to two mov instructions (mov w8 #56872; movk w8 #19073 lsl #16 = 1250025000) then printf. Process startup dominates the 1.5ms.', 'benchmarks/sum_n_ref.s', 'benchmark', 'verified', 'c,optimization,clang'),
(5, 'startup', 'Python process startup + emojiasm import is negligible vs VM execution time (~0ms overhead)', 'Benchmark: subprocess 632ms ≈ VM-only 617ms. Startup+parse adds ~15ms which is ~2.4% of total.', 'benchmarks/run.py', 'benchmark', 'verified', 'performance,startup'),
(5, 'lua-comparison', 'Lua 5.4 is ~250x faster than the EmojiASM interpreter for tight numeric loops', 'Benchmark: Lua 2.4ms vs EmojiASM VM 617ms for sum(1..50000). Lua uses a register-based VM vs stack-based.', 'benchmarks/run.py', 'benchmark', 'verified', 'performance,lua,comparison');
