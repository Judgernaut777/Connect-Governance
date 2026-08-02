"""The Connect governance plane: state resolution, persistence, and projections.

Everything in this package is *outside* the Decision Kernel. It resolves
governed state into explicit Kernel inputs, persists the resulting Decisions,
and renders explanations. It decides nothing.

The Kernel must never import from here — enforced by
``tests/test_kernel_isolation.py``.
"""
