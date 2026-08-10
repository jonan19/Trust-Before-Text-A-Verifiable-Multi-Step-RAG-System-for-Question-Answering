# CLAUDE.md

# Trust Before Text

This is a research project implementing a deterministic Retrieval-Augmented Generation (RAG) pipeline focused on minimizing hallucinations through evidence validation before LLM synthesis.

## Core Philosophy

- Retrieval maximizes recall.
- Validation determines whether evidence is trustworthy.
- The LLM is only responsible for synthesizing validated evidence.
- Prefer deterministic logic over LLM-based decision making.
- Explainability is more important than cleverness.
- Preserve architectural separation of responsibilities.

## Pipeline

User Query
→ Preprocessing
→ Query Classification
→ Query Decomposition
→ Hybrid Retrieval
→ Validation Pipeline
→ Decision Engine
→ LLM Synthesis
→ Final Response

## Development Principles

- Make one architectural change at a time.
- Keep changes as small and localized as possible.
- Do not refactor unrelated code.
- Preserve existing public APIs unless explicitly requested.
- Do not rename files, classes, or functions without justification.
- Avoid introducing unnecessary dependencies.
- Prefer improving existing components over rewriting them.

## Before Writing Code

Unless explicitly asked to implement immediately:

1. Analyze the existing implementation.
2. Explain which files need modification.
3. Explain the impact of the proposed change.
4. Identify possible regressions.
5. Present an implementation plan.
6. Wait for approval before writing code.

## When Implementing

- Modify only the files required.
- Keep diffs minimal.
- Preserve backward compatibility where possible.
- Add comments only when they improve understanding.
- Do not change formatting across unrelated files.

## After Implementation

Always provide:

- Summary of changes.
- Why the changes were made.
- Any assumptions.
- Possible edge cases.
- Any recommended follow-up work.

## Project Goal

Every architectural decision should improve one or more of:

- factual correctness
- evidence traceability
- validation reliability
- modularity
- maintainability

Do not optimize for code elegance if it weakens determinism or explainability.