"""Point-in-time historical validation of the forecasting system.

Two stages that deliberately do not share a process:

    python -m validation.predict     # freezes predictions, sees no future
    python -m validation.model       # the same, for the neural forecaster
    python -m validation.score       # reveals outcomes, scores what was frozen

`predict` writes `validation/out/predictions.json` and never reads it back.
`score` reads it and never writes it. That split is what enforces "never
regenerate a historical prediction after seeing its outcome" structurally,
rather than by intention.
"""
