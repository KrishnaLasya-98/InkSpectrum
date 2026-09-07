"""InkSpectrum test suite.

Three tiers, matching the OpenMontage test architecture:
- contracts/ — BaseTool contract, registry, schema, config, checkpoint (no external I/O)
- qa/       — real-API integration tests (cost-capped, may skip without keys)
- eval/     — golden scenario replay harness for regression testing
"""
