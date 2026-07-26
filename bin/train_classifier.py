#!/usr/bin/env python3
"""
train_classifier.py — 用 LLM 標好的種子樣本訓練本機分類器，再去標全量。零 token（訓練與推論都在本機）。

為什麼要這樣做：
語料要擴到十萬級時，用 LLM 逐筆分類在時間與成本上都不可行（5,400 筆就跑了一小時）。
但 LLM 已經標好的那幾千筆是很好的訓練資料。所以：
  LLM 當標註員（只標種子）→ 本機模型當放大器（標全量）→ LLM 只負責解讀結果。
新增樣本的邊際分類成本因此降為零。

誠實面對的限制：
- 模型只學得到 LLM 標註裡的模式，LLM 標錯的偏誤會被完整複製並放大。
- 每個欄位都會輸出交叉驗證準確率；準確率不夠的欄位不該拿來下結論。
- 預測結果會標上 `label_source: model` 與信心值，跟 LLM 標的分開存，不可混為一談。
"""
import json, os, sys
import numpy as np
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.calibration import CalibratedClassifierCV

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, "corpus", "master.jsonl")
FIELDS = ["domain", "task", "target", "maturity"]

rows = []
for line in open(MASTER, encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line:
        continue
    try:
        rows.append(json.loads(line))
    except Exception:
        pass

def text_of(r):
    return " ".join([
        (r.get("name") or ""),
        (r.get("description") or ""),
        (r.get("body_head") or "")[:500],
        " ".join(r.get("repo_topics") or []),
        " ".join(r.get("tools_hinted") or []),
        (r.get("path") or "").replace("/", " ").replace("-", " "),
    ])

# 種子＝LLM 標過、且不是模型標的
seed = [r for r in rows if r.get("domain") and r.get("label_source") != "model"]
# 模型標過但後來被 LLM 覆蓋的不算待標；其餘模型標的要重標（種子擴充後模型會更準）
todo = [r for r in rows if not r.get("domain") or r.get("label_source") == "model"]
print(f"種子樣本 {len(seed)} 筆｜待標 {len(todo)} 筆｜總計 {len(rows)} 筆")
if len(seed) < 200:
    print("種子太少，不訓練"); sys.exit(0)
if not todo:
    print("沒有待標樣本，只做交叉驗證")

X_seed = [text_of(r) for r in seed]
report = {"n_seed": len(seed), "n_predicted": 0, "fields": {}}
models = {}

for f in FIELDS:
    y = [r.get(f) or "unknown" for r in seed]
    keep = [i for i, v in enumerate(y) if Counter(y)[v] >= 8]   # 太稀有的類別無法交叉驗證
    Xs = [X_seed[i] for i in keep]; ys = [y[i] for i in keep]
    if len(set(ys)) < 2:
        continue
    pipe = make_pipeline(
        TfidfVectorizer(sublinear_tf=True, min_df=2, max_features=60000,
                        ngram_range=(1, 2), strip_accents="unicode"),
        LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced"),
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    acc = cross_val_score(pipe, Xs, ys, cv=cv, scoring="accuracy", n_jobs=-1)
    # 多數類基準：模型必須贏過「全部猜最常見的類別」才有意義
    base = Counter(ys).most_common(1)[0][1] / len(ys)
    pipe.fit(Xs, ys)
    models[f] = pipe
    report["fields"][f] = {
        "cv_accuracy": round(float(acc.mean()), 3),
        "cv_std": round(float(acc.std()), 3),
        "majority_baseline": round(base, 3),
        "lift_over_baseline": round(float(acc.mean()) - base, 3),
        "n_classes": len(set(ys)), "n_train": len(ys),
    }
    print(f"  {f:10s} 交叉驗證準確率 {acc.mean():.3f} ±{acc.std():.3f}"
          f"（多數類基準 {base:.3f}，提升 {acc.mean()-base:+.3f}）")

if todo:
    Xt = [text_of(r) for r in todo]
    preds = {}
    for f, m in models.items():
        proba = m.predict_proba(Xt)
        classes = m.classes_
        idx = proba.argmax(axis=1)
        preds[f] = [(classes[i], float(proba[k, i])) for k, i in enumerate(idx)]
    for k, r in enumerate(todo):
        for f in models:
            lab, conf = preds[f][k]
            r[f] = lab
            r[f + "_conf"] = round(conf, 3)
        r["label_source"] = "model"
    report["n_predicted"] = len(todo)
    with open(MASTER, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    conf = [r.get("domain_conf", 0) for r in todo]
    report["pred_conf"] = {
        "mean": round(float(np.mean(conf)), 3),
        "pct_above_0.6": round(100 * float(np.mean([c >= 0.6 for c in conf])), 1),
        "pct_above_0.8": round(100 * float(np.mean([c >= 0.8 for c in conf])), 1),
    }
    print(f"\n已預測 {len(todo)} 筆（domain 信心 ≥0.6 佔 {report['pred_conf']['pct_above_0.6']}%）")

json.dump(report, open(os.path.join(ROOT, "corpus", "model_report.json"), "w"),
          ensure_ascii=False, indent=1)
print(f"\n報告 → corpus/model_report.json")
