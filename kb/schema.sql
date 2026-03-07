-- EmojiASM Knowledge Base Schema
-- Stores project architecture facts + assembler/VM/compiler research

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,       -- e.g. 'vm', 'parser', 'assemblers'
    title TEXT NOT NULL,             -- human-readable label
    description TEXT
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id INTEGER NOT NULL REFERENCES skills(id),
    topic TEXT NOT NULL,             -- sub-category within skill
    claim TEXT NOT NULL,             -- the actual finding/assertion (one sentence)
    evidence TEXT,                   -- supporting detail, code refs, measurements
    source_url TEXT,
    source_title TEXT,
    source_type TEXT CHECK(source_type IN (
        'codebase',         -- observed directly in source code
        'benchmark',        -- measured empirically
        'academic_paper',
        'blog_post',
        'docs',
        'empirical_test',
        'other'
    )) DEFAULT 'codebase',
    confidence TEXT CHECK(confidence IN (
        'verified',     -- confirmed by test/measurement or authoritative source
        'high',         -- strong evidence, multiple sources
        'medium',       -- single credible source, not independently verified
        'low',          -- speculative or inferred
        'unverified'    -- needs follow-up
    )) DEFAULT 'unverified',
    date_found TEXT DEFAULT (date('now')),
    tags TEXT,          -- comma-separated cross-cutting tags
    notes TEXT,
    session TEXT        -- which research session produced this
);

CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER REFERENCES findings(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    authors TEXT,
    year INTEGER,
    url TEXT,
    venue TEXT          -- e.g. 'PLDI 2019', 'arXiv', 'GitHub'
);

CREATE TABLE IF NOT EXISTS investigations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id INTEGER REFERENCES skills(id),
    topic TEXT NOT NULL,
    started_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    queries_run INTEGER DEFAULT 0,
    findings_added INTEGER DEFAULT 0,
    status TEXT CHECK(status IN ('running','completed','failed')) DEFAULT 'running',
    summary TEXT
);

-- Full-text search over findings
CREATE VIRTUAL TABLE IF NOT EXISTS findings_fts USING fts5(
    claim, evidence, tags, notes,
    content=findings,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS findings_ai AFTER INSERT ON findings BEGIN
    INSERT INTO findings_fts(rowid, claim, evidence, tags, notes)
    VALUES (new.id, new.claim, new.evidence, new.tags, new.notes);
END;

CREATE TRIGGER IF NOT EXISTS findings_ad AFTER DELETE ON findings BEGIN
    INSERT INTO findings_fts(findings_fts, rowid, claim, evidence, tags, notes)
    VALUES ('delete', old.id, old.claim, old.evidence, old.tags, old.notes);
END;

CREATE TRIGGER IF NOT EXISTS findings_au AFTER UPDATE ON findings BEGIN
    INSERT INTO findings_fts(findings_fts, rowid, claim, evidence, tags, notes)
    VALUES ('delete', old.id, old.claim, old.evidence, old.tags, old.notes);
    INSERT INTO findings_fts(rowid, claim, evidence, tags, notes)
    VALUES (new.id, new.claim, new.evidence, new.tags, new.notes);
END;

-- Seed skills
INSERT OR IGNORE INTO skills(id, name, title, description) VALUES
(1, 'vm',           'Virtual Machine',        'Stack-based VM internals: dispatch, execution, memory, call stack'),
(2, 'parser',       'Parser',                 'Tokenization, directive handling, label resolution, Program/Function/Instruction dataclasses'),
(3, 'compiler',     'AOT Compiler',           'EmojiASM → C codegen, numeric vs mixed path, clang integration'),
(4, 'opcodes',      'Instruction Set',        'Opcode semantics, emoji mappings, variation selectors, argument types'),
(5, 'performance',  'Performance',            'Benchmark results, throughput, comparisons, optimization techniques'),
(6, 'assemblers',   'Assembler Research',     'How other assemblers, VMs, and interpreters work (LLVM, Wasm, JVM, Forth, etc.)'),
(7, 'esoteric',     'Esoteric Languages',     'Esoteric/toy language design: Brainfuck, Forth, Befunge, Whitespace, etc.'),
(8, 'tooling',      'Tooling & Ecosystem',    'Editor support, REPL, debugger, LSP, packaging, CI/CD');
