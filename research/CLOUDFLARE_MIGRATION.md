# 遷移到 Cloudflare 免費方案：可行性評估

**結論先講：整條管線遷不過去，但有三塊值得搬，而且其中一塊能順便解掉現在的 GitHub 檔案大小問題。**

## 一、本機管線的實測資源用量

| 步驟 | CPU 時間 | 說明 |
|---|---:|---|
| `train_classifier.py` | **710 秒** | TF-IDF + LogReg，5-fold CV × 4 欄位 + 3.5 萬筆推論（實測 user 597s + sys 113s） |
| `scan_injection.py` | 30.6 秒 | 4.1 萬筆 × 9 類正則 |
| `build_site.py` | 2.1 秒 | |
| `eda_deepdive.py` | 1.4 秒 | |
| `opportunity.py` | 0.9 秒 | |
| `harvest_targeted.py` | 牆鐘 80 分鐘 | 約 600+ 次 API 呼叫，受速率限制而非 CPU 限制 |

儲存：`corpus/master.jsonl` 75 MB，整個 `corpus/` 173 MB。

## 二、Cloudflare 免費方案的硬限制

查證自官方文件（2026-07）：

| 項目 | 免費方案 | 付費方案 |
|---|---|---|
| **Workers CPU 時間** | **10 ms／請求，10 ms／Cron** | 5 分鐘 |
| Workers 請求數 | 10 萬／日 | 無上限 |
| Subrequest（對外 fetch） | **50／請求** | 10,000／請求 |
| 記憶體 | 128 MB／isolate | 同 |
| Cron Triggers | **5 個／帳號** | 同 |
| Worker bundle | 3 MB（壓縮後） | 同 |
| R2 儲存 | **10 GB／月**，egress 完全免費 | $0.015/GB |
| R2 Class A / B 操作 | 100 萬 / 1000 萬 次／月 | |
| Pages 靜態託管 | 無限 | |

## 三、逐項對照：能不能搬

### ❌ 分類器訓練（`train_classifier.py`）— 不可能

710 秒 CPU vs 免費方案 10 ms。**差距 71,000 倍。** 就算升付費方案（5 分鐘 = 300 秒）也不夠。

而且更根本的問題：**Python Workers 仍在 beta，官方列舉的支援套件是 FastAPI / Langchain / Pydantic，
沒有 scikit-learn、numpy、scipy。** 這條路不是「慢」而是「跑不了」。

替代方案是用 Workers AI 的 embedding + Vectorize 取代 TF-IDF，但那是**換一套方法論**，
不是搬遷——準確率要重新驗證，而且目前 0.73 的 domain 準確率是靠 6,547 筆人工標註種子換來的。

### ❌ 分群（`cluster.py`）— 同上

MiniBatchKMeans 對 4 萬 × 8 萬維稀疏矩陣，同樣需要 numpy/scipy。

### ❌ LLM 標註與洞察撰寫（`agy`）— 需要換掉，不是搬遷

`agy` 是本機 CLI，走免費模型額度。搬到 Cloudflare 要改用 Workers AI 或外部 API：

- **Workers AI**：有免費 neuron 額度，但模型選擇與品質跟現在不同，prompt 要重調
- **外部 API**：Cloudflare 只是代跑，成本不變，還多一層

現在這步是**零現金成本**（走 agy 的免費額度）。搬過去只會讓成本上升。

### ⚠️ 採集（`harvest_*.py`）— 技術上可行，但很麻煩

好消息：Workers 的 10ms 限制是 **CPU 時間**，等待 GitHub API 回應不算 CPU。
壞消息：**50 subrequests／請求**。一次完整過取樣要 600+ 次 API 呼叫，得拆成 12+ 次調用。

要做的話需要：Cron 觸發 → Queue 分批 → 每批 ≤50 次 fetch → 寫入 R2。
可行，但**只為了省一台已經在跑的 Mac，不划算**。而且 GitHub 的 10 次/分鐘速率限制搬到哪都一樣，
牆鐘時間不會變快。

### ✅ 靜態網站託管 → Cloudflare Pages — 值得，成本 ~15 分鐘

目前用 GitHub Pages，運作正常。搬到 CF Pages 的實際好處有限（都免費、都自動部署），
除非你要用 CF 的邊緣快取、Web Analytics 或自訂網域。**不急，但很便宜。**

### ✅ 語料儲存 → R2 — **最值得搬的一塊**

現在的痛點：`master.jsonl` 75 MB，GitHub 已警告超過 50 MB 建議值，100 MB 會硬性失敗。
目前的處置是每週把壓縮快照發到 GitHub Release。

R2 免費額度 10 GB，**egress 完全免費**。75 MB 只佔 0.75%，即使每天存一份未壓縮快照
也能撐一年以上。而且：

- 不會塞爆 git 歷史
- 可以直接從 Worker 或本機讀取
- 沒有 GitHub Release 的 2 GB／檔上限與 API 額度顧慮

**成本：約 1 小時**（建 bucket、寫上傳/下載腳本、改 `publish_snapshot.sh`）。

### ✅ 輕量每日抓取（生態指標）→ Workers Cron — 可行，成本 ~2-3 小時

`bin/fetch.py` 只抓 5 個 repo 的 metadata + arXiv + HN，大約 20-30 次 API 呼叫，
CPU 幾乎為零。**這塊完全放得進免費 Workers Cron**（50 subrequests 夠用）。

好處是就算 Mac 關機、睡眠，生態指標仍會每天更新。但洞察報告仍需本機的 agy，
所以只有一半的每日產出會自動化。

## 四、建議的分工

```
Cloudflare（免費）              本機 Mac（現狀）
─────────────────              ─────────────────
R2      語料快照存放      ←──  每日 push 快照
Workers 輕量生態指標抓取   ──→  結果寫回 R2
Pages   靜態網站（選配）        harvest 大規模採集（受 GitHub 速率限制）
                                sklearn 訓練與分群（710s CPU）
                                agy 標註與洞察撰寫（零現金成本）
```

**理由**：Cloudflare 的價值在「不需要開機的輕量常駐工作」與「便宜的物件儲存」，
不在「重運算」。這條管線的重量級部分（ML 訓練、LLM 呼叫）恰好是免費 Workers 最不適合的。

## 五、成本總結

| 項目 | 現金 | 工時 | 效益 |
|---|---|---|---|
| R2 存語料 | $0（10 GB 內） | ~1 小時 | **高**——解掉 GitHub 檔案大小天花板 |
| Workers Cron 抓生態指標 | $0 | ~2-3 小時 | 中——Mac 離線時仍更新 |
| Pages 託管 | $0 | ~15 分鐘 | 低——GitHub Pages 已夠用 |
| 分類器搬到 Workers AI | $0-? | **數天** | **負**——要重驗準確率，方法論改變 |
| 採集搬到 Workers | $0 | ~1-2 天 | 低——速率限制不變，只省一台已在跑的機器 |

**建議只做 R2 那一項。** 它解決一個真實且會惡化的問題（git 檔案大小），
其餘的投入產出比都不好。

## 六、如果之後真的要搬 ML

不要試著把 scikit-learn 塞進 Workers。正確的路是：

1. Workers AI 產生 embedding（`@cf/baai/bge-*` 系列）
2. Vectorize 存向量、做相似度檢索
3. 分類改成「最近鄰投票」而非訓練線性模型

這是**換方法**而非搬遷，好處是零訓練成本，代價是要用現有的 6,547 筆人工標註
重新驗證準確率——低於現在的 0.73 就不該換。
