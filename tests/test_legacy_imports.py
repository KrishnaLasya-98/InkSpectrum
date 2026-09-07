"""Regression tests: the 23 existing textbook-pipeline tests must still pass.

This file re-exports them at the top-level `tests/` location so a single
`make test` covers both legacy tests and the new contracts/ suite.
"""

from __future__ import annotations

# Existing tests are imported via pytest's rootdir discovery, but we make
# the legacy path explicit here for documentation and easy CI.
LEGACY_TESTS_PATH = "packages/textbook-pipeline/tests"
