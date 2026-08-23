# Closure V2 Protocol Amendment

Closure V2 is a new protocol, not a correction to Closure V1. V1 remains
factually closed with P0 and P1 unavailable because 488 of 9,413 intended fit
rows lacked a complete autoregressive target sequence and V1 required every
fit row to succeed.

V2 predeclares complete-case family eligibility. Complete sequences contribute
to model loss; incomplete sequences remain visible in the full ledger with
their reasons and denominators. The family fit is allowed only when the locked
aggregate row and location thresholds pass. Primary P0 and P1 fits use an
identical key intersection.

This amendment also separates an already opened V1 holdout from a fresh
location surface. The former is post hoc. The latter is frozen after model
lock using input-only criteria and cannot be selected or repaired using target
values or target availability.

No scientific outcome is presumed. P1 may be superior, descriptively
favorable, inconclusive, inferior or unavailable. A failure or negative result
is retained without seed replacement or ad hoc hyperparameter change.
