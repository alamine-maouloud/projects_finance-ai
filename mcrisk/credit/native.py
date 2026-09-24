"""Bridge to the C++ thinning kernel (mcrisk._native), if it was built."""

from __future__ import annotations

import numpy as np

try:
    from .. import _native
except ImportError:  # extension not compiled
    _native = None


def available() -> bool:
    return _native is not None


def block_ids(model, pd_bucket_width: float = 0.7) -> np.ndarray:
    """Blocks of obligors with the same factor pattern and similar PD.

    Tighter blocks give a tighter bound p_max (fewer rejected candidates) but
    cost one bound evaluation each per scenario; ~0.7 in log-PD is a good
    compromise (PDs within a factor 2, asset correlations nearly equal).
    """
    p = model.portfolio
    pattern = np.unique(p.factor_weights != 0, axis=0, return_inverse=True)[1].ravel()
    bucket = np.floor(np.log(p.pd) / pd_bucket_width).astype(np.int64)
    key = pattern.astype(np.int64) * 10_000 + (bucket - bucket.min())
    return np.unique(key, return_inverse=True)[1].astype(np.int64).ravel()


def kernel(model):
    """Native kernel for a CreditModel (cached on the model)."""
    if _native is None:
        raise RuntimeError("native kernel not built: run `python setup.py build_ext --inplace`")
    if model.lgd_model != "fixed":
        raise ValueError("the native kernel supports fixed LGD only")
    k = getattr(model, "_native_kernel", None)
    if k is None:
        k = _native.CreditKernel(
            model.b_f, model.chol, model.threshold, model.idio, model.c,
            block_ids(model), model.nu if model.copula == "t" else 0.0,
        )
        model._native_kernel = k
    return k
