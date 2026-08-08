"""V2 — alpha-driven predictive architecture.

Separate package from `validation/` on purpose. The V1 study's harness is
frozen (directive §0): nothing in here imports from it in a way that could
change its behaviour, and nothing in here writes to `app/cache`, whose exact
contents define the V1 universe.

Read `PREREGISTRATION.md` before `V2_REPORT.md`. The thresholds in the first
file were written down before the second file's numbers existed, which is the
only thing that makes them thresholds rather than descriptions.
"""
