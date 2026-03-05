import json
from pathlib import Path

import joblib
import numpy as np
from django.conf import settings

_MODEL = None
_MODEL_MTIME = None


def _load_json(path: str, default):
    try:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def load_features_list():
    return _load_json(settings.ML_FEATURES_PATH, [
        "cpu", "ram", "disk",
        "critical_count_1h", "error_count_1h", "warning_count_1h"
    ])


def _get_model():
    global _MODEL, _MODEL_MTIME

    p = Path(settings.ML_MODEL_PATH)
    if not p.exists():
        _MODEL = None
        _MODEL_MTIME = None
        return None

    mtime = p.stat().st_mtime
    if _MODEL is not None and _MODEL_MTIME == mtime:
        return _MODEL

    try:
        _MODEL = joblib.load(str(p))
        _MODEL_MTIME = mtime
        return _MODEL
    except Exception:
        # If model can't load, fallback to heuristic (no crash)
        _MODEL = None
        _MODEL_MTIME = None
        return None


def heuristic_risk(features: dict):
    cpu, ram, disk = features["cpu"], features["ram"], features["disk"]
    crit, err, warn = features["critical_count_1h"], features["error_count_1h"], features["warning_count_1h"]

    score = 0.0
    score += min(cpu/100.0, 1.0) * 0.35
    score += min(ram/100.0, 1.0) * 0.30
    score += min(disk/100.0, 1.0) * 0.15
    score += min((crit*0.15 + err*0.08 + warn*0.03), 1.0) * 0.20
    score = float(max(0.0, min(score, 1.0)))

    if score >= 0.7: level = "HIGH"
    elif score >= 0.4: level = "MEDIUM"
    else: level = "LOW"

    top = sorted(
        [("cpu", cpu), ("ram", ram), ("disk", disk),
         ("critical_count_1h", crit), ("error_count_1h", err), ("warning_count_1h", warn)],
        key=lambda x: x[1],
        reverse=True
    )[:3]

    return score, level, {
        "model_used": False,
        "summary": f"Risk is driven mainly by {', '.join([t[0] for t in top])}.",
        "top_features": [{"name": n, "value": float(v)} for n, v in top],
    }


def predict_risk(features: dict):
    feat_names = load_features_list()
    model = _get_model()

    if model is None:
        return heuristic_risk(features)

    x = np.array([[features.get(f, 0) for f in feat_names]], dtype=float)

    try:
        if hasattr(model, "predict_proba"):
            proba = float(model.predict_proba(x)[0][1])
        else:
            proba = float(model.predict(x)[0])
    except Exception:
        return heuristic_risk(features)

    if proba >= 0.7: level = "HIGH"
    elif proba >= 0.4: level = "MEDIUM"
    else: level = "LOW"

    # Simple “local explanation” (value-based)
    top = sorted([(f, float(features.get(f, 0))) for f in feat_names], key=lambda t: t[1], reverse=True)[:3]

    return proba, level, {
        "model_used": True,
        "summary": "ML inference used (model.joblib).",
        "top_features": [{"name": n, "value": v} for n, v in top],
    }