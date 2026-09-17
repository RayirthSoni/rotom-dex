"""Grounded chat: the model chooses tools and explains their output; it never computes a fact.

This package sits beside `services/` rather than inside it. `services/` is guaranteed to touch no
network, and a provider adapter would break that guarantee. Everything here takes plain values and
imports no web framework, so the CLI, the API and the evaluation runner drive the same code.
"""
