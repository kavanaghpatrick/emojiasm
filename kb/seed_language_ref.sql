-- Language Reference findings for EmojiASM developers
-- Stack effect notation (Forth-style): ( before -- after )
--   n = any number (int or float)
--   i = integer specifically
--   s = string
--   v = any value
--   0|1 = boolean result (integer 0 or 1)
--   Stack top is rightmost in both before and after

-- ── OPCODE REFERENCE ──────────────────────────────────────────────────────

INSERT INTO findings(skill_id, topic, claim, evidence, source_title, source_type, confidence, tags) VALUES

-- Stack ops
(9, 'opcode-ref', '📥 PUSH val  ( -- val )  Push a literal value onto the stack',
 'val can be: integer (42, -7), hex (0xFF), binary (0b1010), float (3.14), or string ("hello" or ''hi'' or «hi»). No values consumed.',
 'emojiasm/opcodes.py', 'codebase', 'verified', 'opcode,stack,push'),

(9, 'opcode-ref', '📤 POP  ( v -- )  Discard the top of stack',
 'Pops and discards one value. Raises VMError on underflow (empty stack).',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,stack,pop'),

(9, 'opcode-ref', '📋 DUP  ( v -- v v )  Duplicate the top of stack',
 'Pushes a second copy of the top value. Original remains. Useful before operations that consume their operands.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,stack,dup'),

(9, 'opcode-ref', '🔀 SWAP  ( a b -- b a )  Swap the top two stack values',
 'b (top) and a (second) are swapped. Raises VMError if fewer than 2 values on stack.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,stack,swap'),

(9, 'opcode-ref', '🫴 OVER  ( a b -- a b a )  Copy the second value to the top',
 'a (second from top) is copied to top. Stack grows by one. Common in comparison loops.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,stack,over'),

(9, 'opcode-ref', '🔄 ROT  ( a b c -- b c a )  Rotate the top three values',
 'Third item (a) is brought to top; b and c shift down one. Requires at least 3 values on stack.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,stack,rot'),

-- Arithmetic
(9, 'opcode-ref', '➕ ADD  ( a b -- a+b )  Add top two values, or concatenate if either is a string',
 'If both are numbers: pushes a+b. If either is a string: converts both to str and concatenates. Order: a is pushed first (deeper), b is top.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,arithmetic,strings,polymorphic'),

(9, 'opcode-ref', '➖ SUB  ( a b -- a-b )  Subtract: deeper minus top',
 'Pops b (top) and a (second), pushes a-b. Numeric only. Example: 📥 10  📥 3  ➖  → stack: [7]',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,arithmetic'),

(9, 'opcode-ref', '✖️ MUL  ( a b -- a*b )  Multiply top two values  [also: ✖]',
 'Pops b and a, pushes a*b. Both emoji variants work (variation selector). Numeric only.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,arithmetic,variation-selector'),

(9, 'opcode-ref', '➗ DIV  ( a b -- a//b or a/b )  Divide: integer floor if both ints, float otherwise',
 'If both a and b are int: pushes a//b (floor division). If either is float: pushes a/b. Raises VMError on division by zero.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,arithmetic,types'),

(9, 'opcode-ref', '🔢 MOD  ( a b -- a%b )  Modulo: remainder of a divided by b',
 'Pops b (top) and a (second), pushes a % b. Both operands treated as integers. Raises VMError on mod by zero.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,arithmetic'),

-- Comparison and logic
(9, 'opcode-ref', '🟰 CMP_EQ  ( a b -- 0|1 )  Push 1 if a == b, else 0',
 'Works on numbers and strings. Example: 📥 5  📥 5  🟰  → stack: [1]. Consumes both operands.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,comparison'),

(9, 'opcode-ref', '📏 CMP_LT  ( a b -- 0|1 )  Push 1 if a < b (deeper < top), else 0',
 'Example: 📥 3  📥 7  📏  → stack: [1]  because 3 < 7. Consumes both operands.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,comparison'),

(9, 'opcode-ref', '📐 CMP_GT  ( a b -- 0|1 )  Push 1 if a > b (deeper > top), else 0',
 'Example: 📥 10  📥 3  📐  → stack: [1]  because 10 > 3. Consumes both operands.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,comparison'),

(9, 'opcode-ref', '🤝 AND  ( a b -- 0|1 )  Logical AND: 1 if both truthy, else 0',
 'Python truthiness rules apply: 0 and "" are falsy. Consumes both operands.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,logic'),

(9, 'opcode-ref', '🤙 OR  ( a b -- 0|1 )  Logical OR: 1 if either truthy, else 0',
 'Python truthiness rules. Consumes both operands.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,logic'),

(9, 'opcode-ref', '🚫 NOT  ( a -- 0|1 )  Logical NOT: 1 if a is falsy, else 0',
 'Example: 📥 0  🚫  → stack: [1]. Example: 📥 5  🚫  → stack: [0].',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,logic'),

-- Control flow
(9, 'opcode-ref', '👉 JMP label  ( -- )  Unconditional jump to label in current function',
 'label must be defined with 🏷️ in the same function. Labels are function-scoped; cannot jump across function boundaries.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,control-flow,labels'),

(9, 'opcode-ref', '🤔 JZ label  ( cond -- )  Jump to label if cond == 0, else fall through. Consumes cond.',
 'Pops cond. If cond == 0: jump to label. Otherwise: next instruction. The condition value is always consumed — use 📋 DUP first to keep it.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,control-flow,gotcha'),

(9, 'opcode-ref', '😤 JNZ label  ( cond -- )  Jump to label if cond != 0, else fall through. Consumes cond.',
 'Pops cond. If cond != 0: jump to label. Otherwise: next instruction. The condition value is always consumed.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,control-flow,gotcha'),

(9, 'opcode-ref', '📞 CALL func  ( -- )  Call a named function. Return address is saved automatically.',
 'Pushes (current_func, return_ip) onto the call stack. Execution continues inside func. Stack is shared across calls — pass arguments on the stack.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,control-flow,functions'),

(9, 'opcode-ref', '📲 RET  ( -- )  Return from current function to the call site',
 'Execution resumes at the instruction after the 📞 CALL. Leave return values on the stack before 📲.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,control-flow,functions'),

(9, 'opcode-ref', '🛑 HALT  ( -- )  Stop program execution immediately',
 'Program terminates. Any values left on the stack are discarded. Every function must reach HALT or RET to avoid falling off the end.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,control-flow'),

(9, 'opcode-ref', '💤 NOP  ( -- )  No operation. Does nothing.',
 'Useful as a placeholder or for alignment. Costs one execution step.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,control-flow'),

-- I/O
(9, 'opcode-ref', '📢 PRINT  ( v -- )  Print top of stack to stdout without a newline. Consumes v.',
 'Converts v to str. Numbers print without trailing .0 for integers. Use 💬 PRINTS to push a string first: 💬 "hello"  📢',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,io'),

(9, 'opcode-ref', '🖨️ PRINTLN  ( v -- )  Print top of stack with a trailing newline. Consumes v.  [also: 🖨]',
 'Equivalent to PRINT followed by a newline. Both emoji variants work.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,io,variation-selector'),

(9, 'opcode-ref', '💬 PRINTS "text"  ( -- s )  Push a string literal onto the stack',
 'PRINTS is asymmetric with PRINT/PRINTLN: it PUSHES, they POP. Use: 💬 "hello"  📢  to print hello. Escape sequences: \n \t \\.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,io,strings,gotcha'),

(9, 'opcode-ref', '🎤 INPUT  ( -- s )  Read one line from stdin and push as string',
 'Trailing newline is stripped. On EOF: pushes empty string "". Use 🔟 INPUT_NUM for numeric input.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,io'),

(9, 'opcode-ref', '🔟 INPUT_NUM  ( -- n )  Read one line from stdin and push as number',
 'Parses input as float (int-like values compare equal to integers). On bad input or EOF: silently pushes 0. Known limitation — no error signal.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,io,gotcha'),

-- Memory
(9, 'opcode-ref', '💾 STORE cell  ( v -- )  Pop top of stack and store in named memory cell',
 'cell is any emoji used as an address (e.g. 💾 🅰️). Cell is created on first write; any value type accepted. Global scope — visible across all functions.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,memory'),

(9, 'opcode-ref', '📂 LOAD cell  ( -- v )  Push the value of a named memory cell onto the stack',
 'Raises VMError if cell has never been written with 💾 STORE. Memory is global: a cell written in one function is readable in all others.',
 'emojiasm/vm.py', 'codebase', 'verified', 'opcode,memory,gotcha'),

-- ── PATTERNS / IDIOMS ─────────────────────────────────────────────────────

(9, 'pattern', 'While loop: initialise counter, mark loop start with 🏷️, compute exit condition, use 😤 to break, jump back with 👉',
 '📥 0  💾 🔢          💭 i = 0
🏷️ 🔁               💭 loop:
  📂 🔢  📥 N  🟰   💭 i == N?
  😤 🏁             💭 exit if true
  [body]
  📂 🔢  📥 1  ➕  💾 🔢   💭 i++
  👉 🔁             💭 repeat
🏷️ 🏁               💭 end',
 'examples/fibonacci.emoji', 'codebase', 'verified', 'pattern,loops,control-flow'),

(9, 'pattern', 'Countdown loop: push N, decrement until zero using 📋 DUP + 🤔 JZ',
 '📥 10              💭 count = 10
🏷️ 🔁
  📋               💭 DUP: keep count for check
  🤔 🏁            💭 exit when count == 0
  [body uses top-of-stack count here]
  📥 1  ➖         💭 decrement count
  👉 🔁
🏷️ 🏁
  📤               💭 discard final 0',
 'emojiasm patterns', 'other', 'verified', 'pattern,loops,stack'),

(9, 'pattern', 'If-then (single branch): compute condition, use 🤔 JZ to skip the body',
 '💭 if condition then body
[push condition]
🤔 🏁        💭 skip if condition == 0 (false)
[then-body]
🏷️ 🏁',
 'emojiasm patterns', 'other', 'verified', 'pattern,conditionals,control-flow'),

(9, 'pattern', 'If-then-else: use 🤔 to jump to else branch, 👉 to skip over it',
 '[push condition]
🤔 🔀        💭 jump to else if false
[then-body]
👉 🏁        💭 skip else
🏷️ 🔀        💭 else:
[else-body]
🏷️ 🏁',
 'emojiasm patterns', 'other', 'verified', 'pattern,conditionals,control-flow'),

(9, 'pattern', 'Function with argument and return value: caller pushes arg before 📞, callee uses 📋/💾 to access it, leaves result on stack before 📲',
 '💭 Caller:
📥 5  📞 🔲  🖨️  🛑

💭 Square function: ( n -- n*n )
📜 🔲
  📋          💭 DUP: keep n for second multiply
  ✖️           💭 n * n
  📲          💭 return result on stack',
 'examples/functions.emoji', 'codebase', 'verified', 'pattern,functions,stack'),

(9, 'pattern', 'Swap two memory cells without a temp variable: use the stack itself as temp storage',
 '📂 🅰️     💭 push A
📂 🅱️     💭 push B  → stack: [A, B]
💾 🅰️     💭 store B into A
💾 🅱️     💭 store A into B
💭 A and B are now swapped',
 'emojiasm patterns', 'other', 'verified', 'pattern,memory,stack'),

(9, 'pattern', 'String formatting: use 💬 PRINTS to push string parts then ➕ ADD to concatenate',
 '💬 "Result: "
📂 🔢           💭 push a number
➕              💭 concat: "Result: " + number
📢              💭 print without newline

💭 Numbers auto-convert to string when concatenated via ADD.',
 'emojiasm patterns', 'other', 'verified', 'pattern,strings,io'),

(9, 'pattern', 'Guard clause: check precondition at function entry and RET early if invalid',
 '📜 🔲           💭 safe-divide: ( a b -- a/b ) or exits on b==0
  📋            💭 DUP b
  🤔 🚪         💭 if b==0, jump to guard exit
  ➗            💭 safe to divide
  📲
🏷️ 🚪
  📤            💭 discard b
  📤            💭 discard a
  📲            💭 return with empty result',
 'emojiasm patterns', 'other', 'verified', 'pattern,functions,error-handling'),

-- ── GOTCHAS ───────────────────────────────────────────────────────────────

(9, 'gotcha', '🤔 JZ and 😤 JNZ always consume the condition value — use 📋 DUP first if you need it after the jump',
 'Common mistake: compute a condition, jump on it, then try to use the result again. Fix: 📋 DUP before the comparison. vm.py Op.JZ: val = self._pop() — always pops.',
 'emojiasm/vm.py', 'codebase', 'verified', 'gotcha,control-flow,beginners'),

(9, 'gotcha', 'Labels are function-scoped — 👉 JMP cannot jump to a label defined in a different 📜 function',
 'Function.labels is a per-Function dict. The VM resolves labels within _exec_function using func.labels only. Cross-function jumps require 📞 CALL.',
 'emojiasm/parser.py', 'codebase', 'verified', 'gotcha,labels,scope'),

(9, 'gotcha', '📂 LOAD on an uninitialised cell raises a runtime VMError — always 💾 STORE before 📂 LOAD',
 'vm.py Op.LOAD: if arg not in self.memory: raise VMError(f"Memory address not initialized"). There is no default value; unlike most languages there is no implicit 0.',
 'emojiasm/vm.py', 'codebase', 'verified', 'gotcha,memory,beginners'),

(9, 'gotcha', '💬 PRINTS pushes a string; 📢 PRINT and 🖨️ PRINTLN pop and print — they are asymmetric',
 'Common confusion: 💬 "hello"  💬 "world" pushes two strings. Then 📢 prints "world" and leaves "hello" on the stack. PRINTS is a stack PUSH, not a print.',
 'emojiasm/vm.py', 'codebase', 'verified', 'gotcha,io,strings,beginners'),

(9, 'gotcha', 'Memory cells are globally scoped — a 💾 STORE in one function overwrites the same cell in all functions',
 'self.memory is a single dict on the VM instance shared across all function calls. There is no stack frame or lexical scoping for named cells.',
 'emojiasm/vm.py', 'codebase', 'verified', 'gotcha,memory,scope'),

(9, 'gotcha', 'Some emoji have invisible variation selectors (U+FE0F): ✖️ and ✖ both work, but copy-paste from different sources may give either form',
 'opcodes.py maps both "✖️" and "✖" to Op.MUL. If a program fails with "Unknown instruction" for what looks like ✖, the clipboard may have dropped the variation selector. Both 🖨️ and 🖨 work for PRINTLN.',
 'emojiasm/opcodes.py', 'codebase', 'verified', 'gotcha,unicode,variation-selector'),

(9, 'gotcha', '🔟 INPUT_NUM silently pushes 0 on bad input — there is no error signal for non-numeric user input',
 'vm.py: except (EOFError, ValueError): self._push(0). A user typing "abc" when a number is expected will silently get 0 with no feedback. Workaround: use 🎤 INPUT and validate the string manually.',
 'emojiasm/vm.py', 'codebase', 'verified', 'gotcha,io,error-handling'),

(9, 'gotcha', 'The default 1M step limit will terminate long-running programs with a VMError — use --max-steps to raise it',
 'VM.max_steps = 1_000_000. A program doing 100k iterations with 13 ops/iter uses ~1.3M steps and will be cut off. Run: emojiasm --max-steps 10000000 file.emoji',
 'emojiasm/vm.py', 'codebase', 'verified', 'gotcha,limits,performance'),

-- ── TYPE SYSTEM ───────────────────────────────────────────────────────────

(9, 'type-system', 'EmojiASM has three runtime types: integer (Python int), float (Python float), and string (Python str)',
 'The VM is a thin wrapper over Python objects. Type is determined at push time and propagated through operations. There is no static type checking.',
 'emojiasm/vm.py', 'codebase', 'verified', 'types,type-system'),

(9, 'type-system', '📥 PUSH infers type from the literal: integers for whole numbers, float for decimals, string for quoted text',
 'parser.py _parse_arg for Op.PUSH: tries int(), then float(), then string extraction. 📥 42 → int, 📥 3.14 → float, 📥 "hi" → str. Hex and binary literals always produce int.',
 'emojiasm/parser.py', 'codebase', 'verified', 'types,push,parsing'),

(9, 'type-system', '➕ ADD is the only polymorphic opcode: it concatenates strings if either operand is a string',
 'vm.py: if isinstance(a, str) or isinstance(b, str): push str(a)+str(b). This means 📥 1  💬 "x"  ➕ → "1x" (number auto-converted to string).',
 'emojiasm/vm.py', 'codebase', 'verified', 'types,strings,arithmetic,polymorphic'),

(9, 'type-system', '➗ DIV uses floor division for int/int, float division when either operand is float',
 'vm.py: if isinstance(a,int) and isinstance(b,int): push a//b. Example: 📥 7  📥 2  ➗ → 3 (not 3.5). Use 📥 7.0 to force float division.',
 'emojiasm/vm.py', 'codebase', 'verified', 'types,arithmetic,division'),

(9, 'type-system', 'Comparison operators (🟰 📏 📐) work on both numbers and strings using Python comparison semantics',
 'Python compares strings lexicographically. 📥 "b"  📥 "a"  📐  → 1 because "b" > "a". Comparing int to string will raise TypeError at runtime.',
 'emojiasm/vm.py', 'codebase', 'verified', 'types,comparison,strings'),

-- ── DEBUGGING ─────────────────────────────────────────────────────────────

(9, 'debugging', 'Run with -d / --debug to print every instruction with stack state to stderr',
 'Output format: 🔍 [function:ip] source_line  stack=[last 5 items]. Only the 5 deepest stack items are shown. Goes to stderr so it does not mix with program stdout.',
 'emojiasm/vm.py', 'codebase', 'verified', 'debugging,tooling'),

(9, 'debugging', 'Use --disasm to see the parsed program as re-emitted source without running it',
 'emojiasm --disasm file.emoji — useful for verifying that the parser understood the source correctly, especially after copy-paste emoji issues.',
 'emojiasm/__main__.py', 'codebase', 'verified', 'debugging,tooling,disasm'),

(9, 'debugging', 'Use --emit-c with --compile to inspect the generated C before compiling',
 'emojiasm --emit-c file.emoji — prints the full C source. Useful for understanding what the AOT compiler generates and diagnosing unexpected output.',
 'emojiasm/__main__.py', 'codebase', 'verified', 'debugging,compiler,tooling');
