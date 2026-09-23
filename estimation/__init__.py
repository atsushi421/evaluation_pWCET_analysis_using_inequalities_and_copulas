"""Estimation pipeline: unit-level pWCET bounds composed over the timing schema.

Implements the ten estimators of the evaluation (E2-1/E2-2): the end-to-end
methods E2E-CHB, E2E-MEMIK, E2E-CANTELLI, E2E-EVT-PoT, E2E-EVT-BM and the
decomposed methods CHB-COP, CHB-IND, CHB-COMONO, MEMIK-COP, EVT-COP, all from
the same IPoint traces and the same training windows. Entry point:
``tools/chb_cop_from_schema.py``.
"""
