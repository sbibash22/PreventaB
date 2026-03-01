import json, os
import joblib
import numpy as np
from django.conf import settings

def load_features_list():
    path = settings.ML_FEATURES_PATH
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return ["cpu","ram","disk","critical_count_1h","error_count_1h","warning_count_1h"]

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
        [("cpu", cpu),("ram", ram),("disk", disk),
         ("critical_count_1h", crit),("error_count_1h", err),("warning_count_1h", warn)],
        key=lambda x: x[1],
        reverse=True
    )[:3]
    return score, level, {"top_features":[{"name":n,"value":v} for n,v in top], "summary":f"Risk is driven mainly by {', '.join([t[0] for t in top])}."}

def predict_risk(features: dict):
    model_path = settings.ML_MODEL_PATH
    feat_names = load_features_list()

    if not os.path.exists(model_path):
        return heuristic_risk(features)

    model = joblib.load(model_path)
    x = np.array([[features.get(f,0) for f in feat_names]], dtype=float)

    if hasattr(model, "predict_proba"):
        proba = float(model.predict_proba(x)[0][1])
    else:
        proba = float(model.predict(x)[0])

    if proba >= 0.7: level = "HIGH"
    elif proba >= 0.4: level = "MEDIUM"
    else: level = "LOW"

    explanation = {
        "summary":"ML inference used (model.joblib). For SHAP plots run the notebook.",
        "top_features":[{"name":f,"value":float(features.get(f,0))} for f in feat_names[:6]]
    }
    return proba, level, explanation
