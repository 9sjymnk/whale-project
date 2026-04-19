# analyzer/train_model.py
import os
import pickle
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

FEATURE_COLS = [
    "buy_ratio", "buy_count_ratio", "price_change_pct",
    "trade_count", "total_volume", "whale_amount",
    "whale_side_bid", "hour", "price_volatility",
]
TARGETS = ["label_1m", "label_5m", "label_30m"]


def _train_one(df: pd.DataFrame, target: str) -> tuple:
    """단일 타임프레임에 대해 3모델 학습 후 최고 모델 반환"""
    X = df[FEATURE_COLS].values
    y = df[target].values.astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if len(set(y)) > 1 else None
    )

    scaler       = StandardScaler()
    X_train_sc   = scaler.fit_transform(X_train)
    X_test_sc    = scaler.transform(X_test)

    candidates = {
        "XGBoost": (
            XGBClassifier(
                n_estimators=100, max_depth=4, learning_rate=0.1,
                random_state=42, verbosity=0, eval_metric="logloss",
            ),
            X_train, X_test, None,
        ),
        "RandomForest": (
            RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42),
            X_train, X_test, None,
        ),
        "LogisticRegression": (
            LogisticRegression(max_iter=1000, random_state=42),
            X_train_sc, X_test_sc, scaler,
        ),
    }

    tf = target.replace("label_", "")
    print(f"\n  [{tf} 예측]")
    print(f"  {'모델':<22} {'Accuracy':>10} {'Precision':>10} {'Recall':>10}")
    print(f"  {'-'*56}")

    best_model, best_scaler, best_name, best_acc = None, None, "", 0.0

    for name, (model, X_tr, X_te, sc) in candidates.items():
        model.fit(X_tr, y_train)
        y_pred = model.predict(X_te)

        acc  = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec  = recall_score(y_test, y_pred, zero_division=0)
        print(f"  {name:<22} {acc*100:>9.1f}% {prec*100:>9.1f}% {rec*100:>9.1f}%")

        if acc > best_acc:
            best_acc, best_model, best_scaler, best_name = acc, model, sc, name

    print(f"  → 최적: {best_name} (Accuracy {best_acc*100:.1f}%)")
    return best_model, best_scaler, best_name, best_acc


if __name__ == "__main__":
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'features.csv')
    df = pd.read_csv(data_path)
    print(f"학습 데이터 로드: {len(df)}행")

    df = df.dropna(subset=FEATURE_COLS + TARGETS)
    print(f"전처리 후: {len(df)}행")

    if len(df) < 20:
        print("⚠️  데이터 부족: 고래 거래 20건 이상 필요합니다. feature_engineering.py 먼저 실행하세요.")
        raise SystemExit(1)

    bundle = {"features": FEATURE_COLS}

    for target in TARGETS:
        tf = target.replace("label_", "")
        model, sc, name, acc = _train_one(df, target)
        bundle[tf] = {"model": model, "scaler": sc, "name": name, "accuracy": round(acc * 100, 1)}

    model_dir  = os.path.join(os.path.dirname(__file__), '..', 'models')
    model_path = os.path.join(model_dir, 'model.pkl')
    os.makedirs(model_dir, exist_ok=True)
    with open(model_path, "wb") as f:
        pickle.dump(bundle, f)

    print(f"\n✅ 모델 저장 완료: models/model.pkl")
