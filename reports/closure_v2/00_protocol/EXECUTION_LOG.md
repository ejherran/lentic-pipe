# Closure V2 Execution Log

## P00–P01 — Reentry and V1 immutability

- Result: PASS (unpublished).
- Branch: `closure-v2`.
- Base commit: `e8f22ed733de56b6616b4ab9f651eb41bd095bb6`.
- Closure V1 tag object: `d6c241f6b89d98d6206563739fab3b7b2f28020f`.
- Closure V1 peeled commit: `eb07598aa54a0944d1a87fe46d62415d0a4454aa`.
- V1 inventory records: 604.
- V1 inventory digest: `608fafe1fe738138dcaf75cfe5e458f376a9bb3e5696feff20ea2e3b76276b37`.
- Protected V1 changes: none.
- Parquet files opened: no.
- DVC commands executed: no.
- Outcome access: forbidden and not performed.
- Next gate: P02 protocol and schemas.

## P02–P03 — Protocol, schemas and protocol lock

- Result: PASS (`locked_unpublished`).
- Protocol components: 14.
- Component digest: `fd66f5813a2941454f9e4ee594ee9547b9c629dc280c6fbe3686ff6e11796a19`.
- Protocol lock: `4ca761c0bf72a889bb5674133b7edced5b0144b6e5b444365cfe99460f185081`, 4,289 bytes.
- Artifact inventory: `785988e7273a44e45966a1f497faf0d29c320f1e1a7ed4435cde525f5c419c4b`, 1,338 bytes.
- Fresh-primary route predeclared: `fresh_location` with post-2021 input-only subset.
- Prelock feasibility: 137 new WQP locations and 2,286 intent origins per horizon.
- Target values read: no.
- Target availability inspected: no.
- Fit authorized: no.
- Evaluation authorized: no.
- Tests: 15 passed; full `ty check` passed; `poetry check --lock` passed.
- Next gate: human review and manual publication of the protocol bundle; P04 remains blocked until then.
