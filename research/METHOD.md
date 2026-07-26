# 研究方法

## 為什麼用 skill 當研究材料

一個人自願把某件工作寫成 skill 並公開，代表三件事同時成立：
(a) 那件工作對他夠痛、(b) 他真的在用 AI 做那件事、(c) 他認為值得讓別人也這樣做。

這是**揭露性偏好（revealed preference）**資料 —— 比問卷（受訪者會美化）、
新聞報導（挑戲劇性個案）、廠商白皮書（有銷售動機）都更接近真實使用行為。

## 管線

```
bin/harvest_corpus.py   分層抽樣蒐集公開 SKILL.md → corpus/skills-YYYY-MM-DD.jsonl
bin/classify.sh         切批次派給 agy 分類（domain/profession/task/target/maturity/pain）
bin/aggregate.py        算統計與交叉表 → corpus/aggregate.json
index/prompt_insight.txt  依聚合結果產出研究報告
```

## 取樣中立性

**不預設職業類別去搜**（那只會撈到自己的假設），改用中立軸分層：
以 SKILL.md 檔案大小切 9 個級距，各自翻頁抽樣，讓領域分佈自己長出來。
每個 repo 最多取 6 個 skill，避免單一大型 skill 集散地灌爆分佈。

## 本次樣本

| 項目 | 數字 |
|---|---|
| GitHub 上可搜尋的 SKILL.md 總數 | 246,584 |
| 實際抓取 | 5,627 檔 / 4,537 repo |
| 成功解析並分類 | 5,397 |
| 疑似含 prompt injection | 87（1.61%） |

## 已知限制

見報告的〈方法與限制〉一節。最重要的三點：
1. 只看得到公開到 GitHub 的，系統性低估法務、醫療、金融、IC 設計的真實採用率。
2. star 數屬於 repo 不屬於 skill，高星樣本只代表「大型專案也開始附 skill」。
3. 分類由 LLM 標註，邊界案例有誤差。

## 稽核

報告中的量化宣稱由 Claude 逐一回查 `corpus/aggregate.json`。
本次抓到並修正的問題：一處俄文亂碼、以及 star 歸屬未說明清楚（已補進限制章節）。
