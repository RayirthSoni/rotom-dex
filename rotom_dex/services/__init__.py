"""Playthrough-aware domain services built on the repositories and calculators.

Services take plain Python values and a `PlaythroughContext`, and return the same envelope the read
endpoints use. They import no web framework, so the CLI, the HTTP layer and a future assistant call
exactly the same functions.
"""
