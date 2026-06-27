"""preload.py — loaded ONCE when each worker process starts.

All model artifacts are loaded here into module globals.
The hot path (predict_batch) never touches disk.

Key design:
 - We reuse the DS team's feature_engineering() but patch its internal
   OHE / data_dict loads to use our already-loaded objects.
 - We call the DS-provided second_process helpers then run our preloaded models.
 - This exactly mirrors predict_frame() but without any pickle.load on the hot path.
"""

import json
import os
import pickle
import sys
import numpy as np
import pandas as pd
from pathlib import Path

# ── locate repo ───────────────────────────────────────────────────────────────
# VM layout:
#   /opt/app/
#     repo/          ← DS handover (predict.py, src/, models/, data/)
#     service/       ← this file (worker/preload.py)
#       worker/
#         preload.py  ← HERE
WORKER_DIR  = Path(__file__).parent.resolve()   # .../service/worker/
SERVICE_DIR = WORKER_DIR.parent                  # .../service/
APP_DIR     = SERVICE_DIR.parent                 # .../   (project root)
REPO_DIR    = APP_DIR / "repo"

sys.path.insert(0, str(REPO_DIR))

# ── import DS modules ─────────────────────────────────────────────────────────
from src import config
from src.features import feature_engineering
from src.models.catboost_cls import cat_cls_seconde_process
from src.models.lgbm_reg import lgb_reg_seconde_process
from src.models.merge import merge_fun

MODEL_DIR = config.MODEL_DIR  # Path object from config

# ── load all artifacts once ───────────────────────────────────────────────────
print(f"[preload] loading models from {MODEL_DIR}", flush=True)

# 1. One-hot encoder
with open(MODEL_DIR / "one_hot_encoder.pkl", "rb") as f:
    _OHE = pickle.load(f)

# 2. CatBoost fold models + saved category lists
with open(MODEL_DIR / "categories_cat_cls.pkl", "rb") as f:
    _CAT_CATEGORIES = pickle.load(f)

_CAT_MODELS = []
for i in range(config.N_FOLDS):
    with open(MODEL_DIR / f"catboost_cls_fold{i}.pkl", "rb") as f:
        _CAT_MODELS.append(pickle.load(f)["model"])

# 3. LightGBM fold models + saved category lists
with open(MODEL_DIR / "categories_lgb_reg.pkl", "rb") as f:
    _LGB_CATEGORIES = pickle.load(f)

_LGB_MODELS = []
for i in range(config.N_FOLDS):
    with open(MODEL_DIR / f"lightgbm_reg_fold{i}.pkl", "rb") as f:
        _LGB_MODELS.append(pickle.load(f)["model"])

# 4. Merge params
with open(MODEL_DIR / "merge_params.json") as f:
    _MERGE_PARAMS = json.load(f)

# 5. Data dictionary (needed by feature_engineering)
_DATA_DICT_DF = pd.read_csv(config.DATA_DICT)

print(f"[preload] {len(_CAT_MODELS)} CatBoost + {len(_LGB_MODELS)} LightGBM models loaded", flush=True)

# ── patch feature_engineering to use our preloaded objects ───────────────────
# The DS features.py loads OHE and data_dict from disk inside feature_engineering().
# We patch those module-level references so every call uses our cached copies.
import src.features as _feat_mod

# Patch whichever names features.py uses internally.
# Common patterns: _ohe, ohe, _OHE, encoder, ONE_HOT_ENCODER
for _attr in ("_ohe", "ohe", "_OHE", "encoder", "ONE_HOT_ENCODER", "_one_hot_encoder"):
    if hasattr(_feat_mod, _attr):
        setattr(_feat_mod, _attr, _OHE)

for _attr in ("_data_dict", "data_dict", "_DATA_DICT", "DATA_DICT", "_dd"):
    if hasattr(_feat_mod, _attr):
        setattr(_feat_mod, _attr, _DATA_DICT_DF)

# ── fast inference helpers ────────────────────────────────────────────────────

def _cls_predict(data: dict) -> np.ndarray:
    """CatBoost ensemble — no disk I/O."""
    data, _ = cat_cls_seconde_process(data)
    X = data["X"]
    # Align categories to training distribution
    for col in X.columns:
        if X[col].dtype.name == "category":
            X[col] = X[col].cat.set_categories(
                _CAT_CATEGORIES.get(col, X[col].cat.categories)
            )
    # Fill NaN categoricals with sentinel "-1"
    for col in X.columns:
        s = X[col]
        if s.dtype.name == "category" and s.isna().any():
            if "-1" not in s.cat.categories:
                s = s.cat.add_categories(["-1"])
            X[col] = s.fillna("-1")

    output = np.zeros(len(X))
    for model in _CAT_MODELS:
        output += model.predict_proba(X)[:, 1] / config.N_FOLDS
    return output


def _reg_predict(data: dict) -> np.ndarray:
    """LightGBM ensemble — no disk I/O."""
    data, _ = lgb_reg_seconde_process(data)
    X = data["X"]
    # Align categories
    for col in X.columns:
        if X[col].dtype.name == "category":
            X[col] = X[col].cat.set_categories(
                _LGB_CATEGORIES.get(col, X[col].cat.categories)
            )
    # The regressor expects 'efs' column (always 1 at inference)
    X["efs"] = 1
    X["efs"] = X["efs"].astype("category").cat.set_categories([0, 1])

    output = np.zeros(len(X))
    for model in _LGB_MODELS:
        output += model.predict(X) / config.N_FOLDS
    return output


def _merge(y_reg: np.ndarray, y_cls: np.ndarray) -> np.ndarray:
    return np.mean(
        [merge_fun(y_reg, y_cls, **p) for p in _MERGE_PARAMS],
        axis=0,
    )


def predict_batch(df: pd.DataFrame) -> np.ndarray:
    """Full pipeline: feature engineering → ensemble → merge → risk score.
    Mirrors predict_frame() exactly, without any disk I/O.
    """
    data = feature_engineering(df, train=False)
    y_cls = _cls_predict(data)
    y_reg = _reg_predict(data)
    merged = _merge(y_reg, y_cls)
    return 1.0 - merged
