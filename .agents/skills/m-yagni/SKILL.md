---

name: m-yagni
description: >
   Use for every coding task that creates, modifies, fixes, refactors,
   reviews, or designs code. Enforces lean implementations, delayed
   abstraction, strategic boundaries, and refactorability.
-------------------------------------------------------

# M-YAGNI

Role Constraint: Write lean, production-grade code. Apply YAGNI while keeping current code cheap to refactor when requirements change.

[RULES]

1. Concrete First:

   - Write high-cohesion, isolated, replaceable modules.
   - FORBIDDEN: Premature abstractions, generic interfaces, speculative hooks, or unused extension points.

2. Rule of Three:

   - Duplicate logic across 1–2 use cases if simpler.
   - Abstract shared logic only when the same pattern appears >= 3 times.
   - Exception: real infrastructure boundaries are allowed immediately.

3. Strategic Boundaries:

   - Keep domain logic independent from DBs, APIs, frameworks, and external services using the smallest necessary boundary.
   - Implement ONLY what is required today. No unused adapters or future providers.

4. Tactical Simplicity:

   - Prefer flat control flow, early returns, simple functions, and explicit data flow.
   - FORBIDDEN: Design patterns or indirection without demonstrated need.

5. Verification Over Speculation:

   - Test current behavior, edge cases, and contracts so refactoring remains safe.
   - FORBIDDEN: Tests for hypothetical features, unused parameters, or dead branches.

6. Complexity Must Pay:
   - Every abstraction, layer, dependency, or configuration option must solve a current problem.
   - Prefer existing, well-tested dependencies already in the project over reimplementing non-trivial standard functionality.
   - Do not add a new dependency when a small, obvious implementation is safer and simpler.
   - When uncertain, choose the simpler implementation.
   