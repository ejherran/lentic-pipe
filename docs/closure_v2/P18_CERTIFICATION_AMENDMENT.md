# Closure V2 P18 certification amendment

## Status and scope

This additive amendment was authorized after the unmodified Phase 11 controls
reached a diagnostic stop. It does not modify Closure V1 evidence, tests,
locks, manifests, models, data, or scientific results.

Phase 11 certifies the Closure V2 execution, restoration, and software scope.
It does not certify the entire historical repository and it never certifies
model efficacy.

## Reason for the amendment

The literal global controls are not descendant-safe on the final Closure V2
commit:

- the full workspace suite contains historical Closure V1 tests that bind
  intermediate commits, source bytes, local Git configuration, or stage-local
  artifact absence;
- the historical curated public suite has a sealed E0-U local Git
  configuration binding and an optional PostgreSQL test;
- the global publication script scans immutable tracked history and rejects
  the Spanish Closure V2 protocol guide itself, together with frozen Closure
  V1 records that contain historical local-path evidence.

Those results remain mandatory diagnostics in the certification reports.
They are not deleted, skipped, rewritten, or reported as passing.

## Effective certification gate

The Closure V2 scope is certified only when all of the following pass:

1. every test under `tests/closure_v2`;
2. synthetic P0/P1 training, calibration, and evaluation smokes;
3. the three registered outcome-free API end-to-end tests;
4. `poetry run ty check`;
5. `poetry check --lock`;
6. installation of the registered Poetry dependency groups;
7. OpenAPI 3.1 model validation and unique operation identifiers;
8. exact directed DVC restoration from an empty cache and clean clone;
9. a publication scan limited to the additive P18 implementation and the
   eight generated certification outputs;
10. manifest-last, exclusive, deterministic publication.

The effective gate fails closed if a Closure V2 or synthetic test fails. The
global diagnostics are recorded separately and cannot be used as evidence of
Closure V2 efficacy.

## Publication semantics

The terminal report and manifest must state all three predicates explicitly:

- `closure_v2_scope_certified = true`;
- `global_repository_certified = false`;
- `efficacy_certified = false`.

No commit, push, or tag is part of the builder. The terminal tag remains a
user-controlled action after publication review.
