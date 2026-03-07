---
name: kb-research
description: "Research a topic related to EmojiASM, assemblers, VMs, or compiler design. Conducts web searches, extracts findings, and stores them in the knowledge base with citations."
argument-hint: "<skill> <topic>"
allowed-tools: [Bash, WebSearch, WebFetch, Read]
---

# EmojiASM KB Research Agent

Research a topic, extract structured findings, and store them in the knowledge base.

## Parse Arguments

Parse `$ARGUMENTS`:
- First token: **skill name** (vm, parser, compiler, opcodes, performance, assemblers, esoteric, tooling)
- Remaining: **topic description**

Example: `assemblers "how Lua VM dispatch works"`

## Research Protocol

### Phase 1: Setup

Check what's already known to avoid duplicates:
```bash
scripts/kb search "<topic>"
scripts/kb skill <skill>
```

Start an investigation session:
```bash
inv_id=$(scripts/kb investigation-start <skill> "<topic>")
```

### Phase 2: Research

Run 3–5 targeted web searches covering:
1. Primary technical documentation or source code
2. Benchmarks or performance characteristics
3. Design rationale or trade-offs
4. Comparison with alternative approaches

For each search: use WebSearch, then WebFetch the most relevant result for full content.

Track: queries_run count, sources consulted.

### Phase 3: Extract Findings

For each meaningful fact discovered, extract:
- **claim**: one clear, specific, falsifiable sentence
- **evidence**: the supporting detail, quote, or measurement
- **confidence**: verified (tested/authoritative), high, medium, low, or unverified

### Phase 4: Store Findings

Add each finding:
```bash
scripts/kb add <skill> "<topic>" "<claim>" "<evidence>" \
  --confidence <level> \
  --tags "<comma,separated,tags>" \
  --source-title "<source name>" \
  --source-url "<url>" \
  --type <blog_post|academic_paper|docs|benchmark|other>
```

For academic or citable sources, add a citation:
```bash
scripts/kb cite <finding-id> "<title>" --authors "<authors>" --year <year> --url "<url>" --venue "<venue>"
```

### Phase 5: Complete & Summarise

```bash
scripts/kb investigation-complete $inv_id <findings_added> <queries_run> "<one-line summary>"
```

Then provide a summary to the user:
- How many findings added
- Key insights discovered
- Sources consulted
- Gaps or follow-up questions remaining

## Skill Descriptions

- `vm` — Stack-based VM internals: dispatch, execution model, call stacks
- `parser` — Tokenization, AST, label resolution
- `compiler` — AOT codegen, optimisation passes, C/LLVM backends
- `opcodes` — Instruction set design and semantics
- `performance` — Benchmarks, throughput, profiling
- `assemblers` — How other assemblers/VMs work (LLVM, Wasm, JVM, CPython, Lua, Forth)
- `esoteric` — Esoteric language design patterns and case studies
- `tooling` — Editor support, REPL, debugger, LSP, packaging

## Quality Standards

- Each claim must be specific and verifiable — no vague generalisations
- Evidence must explain *why* the claim is true, not just restate it
- Flag uncertainty honestly with appropriate confidence level
- Do not store findings that duplicate what `scripts/kb search` already returns
