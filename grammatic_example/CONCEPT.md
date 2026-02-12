# Grammatic Concept

Grammatic is a **grammar workshop** for humans and agents.

It is not primarily a parser wrapper. Parsing support exists, but the core value is enabling fast, reliable cycles for **creating, modifying, validating, and testing tree-sitter grammars**.

---

## Core Idea

Use existing Unix tools as-is, coordinate them with `just`, and record outcomes in append-only JSONL logs.

- **Control plane:** `just`
- **Grammar engine:** `tree-sitter` CLI
- **Build toolchain:** `gcc` / `g++`
- **Validation + logging:** small Python scripts with Pydantic
- **Querying:** `jq`

Grammatic should stay shell-first, explicit, and deterministic.

---

## Workshop Loop (Primary Workflow)

The workshop loop is:

1. **Create / modify grammar** (`grammar.js`, scanner, corpus tests)
2. **Generate** parser artifacts
3. **Build** shared library
4. **Test** corpus behavior
5. **Diagnose** issues and iterate

This loop is the product.

Parsing individual files is a supporting tool for debugging and spot checks, not the main success criterion.

---

## Command Contract

The core interface is grammar-name based:

- `just generate <grammar>`
- `just build <grammar>`
- `just test-grammar <grammar>`
- `just doctor <grammar>`
- `just parse <grammar> <source>` (auxiliary)

Recipes should resolve paths internally from project root + grammar name.

---

## Artifact Contract

Build output is organized per grammar:

- `build/<grammar>/<grammar>.so`

This layout is canonical and should be used consistently across scripts, checks, and docs.

---

## Testing-First Philosophy

Testing is central, not optional:

- Corpus tests (`tree-sitter test`) are first-class
- `doctor` checks catch common setup/quality issues quickly
- Parse commands provide supplemental diagnostics

Primary indicator of grammar health: **test results + diagnostics**, not parse demos.

---

## Logging and Provenance

JSONL logs capture workshop events for reproducibility:

- Build events (including failures)
- Parse events (supporting telemetry)
- Agent metadata where available (session/run context)

The logging goal is practical traceability for iteration, not heavyweight observability.

---

## Scope Boundaries (MVP)

In scope:

- grammar workshop loop
- grammar-name command UX
- deterministic build layout
- test-first flows
- lightweight structured logs

Out of scope for now:

- complex API/version governance
- heavy orchestration frameworks
- platform abstraction beyond devenv-controlled Unix workflow
- replacing tree-sitter functionality with custom implementations

---

## Success Definition

Grammatic succeeds when humans and agents can quickly improve grammars with predictable feedback:

- edit grammar
- regenerate and rebuild
- run corpus tests
- diagnose failures
- repeat with clear provenance
