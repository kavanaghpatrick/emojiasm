---
name: kb
description: "Query the EmojiASM knowledge base. Supports stats, search, skill browsing, topic lookup, finding detail, and markdown export. Run with no args for an overview."
argument-hint: "[subcommand] [args]"
allowed-tools: [Bash, Read]
---

# EmojiASM Knowledge Base

Query the project KB using the `scripts/kb` CLI. The DB stores verified findings about EmojiASM internals (vm, parser, compiler, opcodes) and research about assemblers, esoteric languages, and related tooling.

## Parse Arguments

Parse `$ARGUMENTS` for a subcommand and its arguments. Default to `stats` when empty.

## Subcommands

All delegate to `scripts/kb` in the project root.

### `stats` (default)
Show finding counts per skill domain.
```bash
scripts/kb stats
```

### `search <query>`
BM25 full-text search across all findings.
```bash
scripts/kb search "<query>" [--skill <name>] [--limit N]
```
Valid skills: `vm`, `parser`, `compiler`, `opcodes`, `performance`, `assemblers`, `esoteric`, `tooling`

### `skill [name]`
List all findings for a skill. Omit name to list available skills.
```bash
scripts/kb skill vm
scripts/kb skill parser
scripts/kb skill          # list all skill names
```

### `topic <name>`
Find findings matching a topic substring across all skills.
```bash
scripts/kb topic dispatch
scripts/kb topic "constant folding"
```

### `detail <id>`
Full detail for one finding including evidence, source, notes, and citations.
```bash
scripts/kb detail 12
```

### `unverified`
List findings that need review or validation.
```bash
scripts/kb unverified
```

### `export [skill]`
Export findings as formatted markdown. Optionally filter to one skill.
```bash
scripts/kb export
scripts/kb export performance
```

## Output Format

After running the KB command, present the results clearly. For `search` and `skill` results, if relevant findings are returned, summarise the key insights rather than just dumping the raw table. For `detail`, show the full structured output.
