# bounded-structured-inspection

## Difficulty explanation

The task requires selecting the relevant facts from a multi-application enterprise snapshot while respecting retry, authorization, or approval boundaries where applicable.

## Environment and software requirements

The agent and verifier use the same digest-pinned Python 3.12 slim image with networking disabled. Harbor 0.22.0 and Docker provide isolated execution.

## Ground-truth provenance

Correctness comes from the checked-in fictional world fixture locked by SHA-256, independently of the answer recorded in the source trace.

## Solution explanation

The reference solution writes the minimal structured answer supported by the relevant records in the frozen snapshot.

## Verification explanation

The separate verifier parses the declared answer artifact and compares its objective fields and values with the task's verifier-owned expected output. Missing, malformed, incomplete, and incorrect artifacts fail.

## Relevant experience

This draft applies failure patterns observed in Hermes PA-style traces and the fixture contract in this repository. A human maintainer must review this section and the generalized task before publication readiness can be claimed.
