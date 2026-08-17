# E0-U Phase 3 recovery attempt 2

This authority transition records the consumed second E0-U attempt and seals one final recovery execution. It does not reinterpret either earlier activation, access-log record, or stale guard.

The immutable publication chain is `R -> H1 -> P1 -> U1 -> H2 -> P2 -> U2 -> H3 -> P3 -> U3`. H3 is exactly 15 paths (11 modifications and 4 additions), P3 is exactly the seven `software_evidence_source_recovery_2` additions, and U3 is exactly `closure_e0_u_recovery_2_activation.json`.

The second attempt failed in `E4_trophic_evaluation` before component metrics or publication because the E1 prediction-column order differed from the exact E4 input contract. H3 validates this producer-to-consumer interface outcome-free before the third durable log append.

The only authorized execution command is stored byte-for-byte in `reports/closure_v1/00_protocol/locked_recovery_2_batch_command.txt`. It uses attempt ordinal 3 and the exclusive guard `tmp/closure_v1_e0_u_recovery_2/sealed_batch.guard`. The historical attempt-1 and attempt-2 guards remain untouched, whether present with their sealed identities or absent in a fresh clone.

The recovery remains unauthorized until H3, P3, and U3 are separately published and the strict loader validates their direct-parent topology, exact scopes, source bindings, two-line access-log prefix, both failure receipts, and live remote identity. Generation is no-clobber and rollback is limited to the inode created by the activation transaction.
