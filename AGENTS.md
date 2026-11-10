# Repository working instructions

After making code changes, request an independent review from a separate agent before finishing, when agent delegation is available. Ask the reviewer to inspect the actual changes for correctness, regressions, security, and missing tests. Assess and address actionable findings, run appropriate checks, and report any unresolved findings and verification limits. If delegation is unavailable, say so and perform the review directly; do not claim an independent review occurred.

For data-release changes, check that candidate data cannot be published before validation, that released data remains compatible with the deployed dashboard, and that the last verified data remains recoverable after failed updates. Keep tests isolated from real project data and credentials.
