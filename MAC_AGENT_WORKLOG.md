# Mac Agent Worklog — refresh canonical corpus and finish Wiki ingest

## Owner intent

Windows agent will push the neutral-sample policy fix, freshness gate, cumulative Domain Wiki implementation,
tests, and a public data-integrity warning first. Mac remains the canonical runtime because its local
`corpus/master.jsonl` contains the newest LLM seeds and model predictions.

## Current evidence (2026-07-27 Asia/Taipei)

- `PROVEN`: remote `main` was still `a059315` before the Windows push.
- `PROVEN`: Release `corpus-20260727/master.jsonl.gz` was updated at `2026-07-27T01:36:29Z`.
- `PROVEN`: commit `a4066f2` with the final classifier outputs was created later, at about 01:47 UTC.
- `PROVEN`: Release master contains 5,937 non-model seeds and 35,293 model rows.
- `PROVEN`: tracked `corpus/model_report.json` expects 6,547 seeds and 34,683 model rows.
- `BLOCKED`: Windows must not rebuild production signal tables or Wiki pages from that stale Release asset.

## Mac agent actions

1. Pull the Windows agent commit; do not overwrite its changes.
2. Confirm the canonical local master aligns with the tracked report:

   ```bash
   python3 - <<'PY'
   import json
   rows = [json.loads(line) for line in open('corpus/master.jsonl') if line.strip()]
   seeds = sum(bool(r.get('domain')) and r.get('label_source') != 'model' for r in rows)
   models = sum(r.get('label_source') == 'model' for r in rows)
   print({'rows': len(rows), 'seeds': seeds, 'models': models})
   PY
   ```

   Expected: `rows=41230`, `seeds=6547`, `models=34683`.

3. Re-publish the Release asset from that canonical master:

   ```bash
   ./bin/publish_snapshot.sh
   ```

4. Run the corrected deterministic pipeline, then the Wiki ingest:

   ```bash
   python3 bin/opportunity.py
   python3 bin/eda_deepdive.py
   python3 bin/wiki_ingest.py --date 2026-07-27 --revision-note "neutral sample policy correction"
   python3 bin/build_site.py
   python3 bin/wiki_lint.py
   python3 bin/check_privacy.py
   python3 -m unittest discover -s tests -v
   ```

5. Commit generated signal tables, `data/wiki_history.json`, `research/wiki/`, and `docs/wiki/`; push.
6. Verify the GitHub Pages readback no longer contains `"n_total": 24944` or
   `"global_production_pct": 48.4`, and that `/skills-radar/wiki/` returns HTTP 200.

## Do not do

- Do not bypass `require_model_report_alignment`.
- Do not use any `targeted-*` row for population proportions.
- Do not copy raw third-party skill text into Wiki pages.

---

# Follow-up — WiFi baseband ASIC / RTL taxonomy

## Owner scope

- Direct: WiFi baseband ASIC specification, fixed-point, microarchitecture, RTL, lint/CDC/RDC,
  formal/SVA, VCS/Verdi simulation/debug, UVM, synthesis/STA/power and RTL integration.
- Exclude: FPGA/Vivado/Quartus/bitstream, MCU/firmware/embedded, board/PCB and analog/RF/antenna.

## Windows work already prepared

- Narrow `asic` and `wifi-asic` harvest topics in `bin/harvest_targeted.py`.
- Secondary taxonomy and catalog builder in `bin/asic_taxonomy.py` and
  `bin/build_asic_catalog.py`.
- Bounded golden-sample pipeline:
  `sample_domain_labels.py` -> existing `classify.sh` -> `train_classifier.py` ->
  `sample_asic_labels.py` -> `classify_asic.sh` -> `evaluate_asic_taxonomy.py`.
- Strict label merge rejects missing, duplicate or invalid enum/list output.
- Current Windows catalog is intentionally `PROVISIONAL_STALE_SNAPSHOT`; do not promote it.

## Mac execution order after canonical refresh

Run each write phase sequentially; do not let harvest, merge or training write master concurrently.

```bash
git pull --ff-only
python3 bin/harvest_targeted.py asic wifi-asic
python3 bin/sample_domain_labels.py --n 400
./bin/classify.sh corpus/domain-golden-sample.jsonl 40 4
python3 bin/merge_classified.py corpus/domain-golden-sample.jsonl
python3 bin/train_classifier.py
python3 bin/sample_asic_labels.py --n 240
./bin/classify_asic.sh corpus/asic-golden-sample.jsonl 30 2
python3 bin/evaluate_asic_taxonomy.py
python3 bin/build_asic_catalog.py
python3 -m unittest discover -s tests -v
python3 bin/check_privacy.py
```

Evaluation must remain `BLOCKED` unless there are at least 200 golden rows, scalar accuracy is at
least 0.75, and multi-label mean Jaccard is at least 0.65. Inspect the FPGA false-positive rows
before accepting even a numerical PASS. Re-publish the Release master only after
`model_report.json` aligns with the new seed/model counts and all gates pass.

## Required readback

1. Push the generated catalog, taxonomy report, model report, source-review report and tests.
2. Report exact master SHA-256, seed/model counts and Release asset digest.
3. Confirm no `owner_fit=direct` row is FPGA/embedded/board/PCB/analog-RF.
4. Do not call any public skill production-ready; source review and EDA runtime proof are separate.

---

# Follow-up — daily EDA_IC and finance-investing recommendations

Windows added a deterministic daily builder and connected it to `bin/daily_research.sh` before the
site build. It writes:

- `corpus/daily_skill_recommendations.json`
- `research/recommendations/YYYY-MM-DD.md`
- `docs/recommendations/index.html` and a dated HTML page

Mac action after the canonical master refresh:

```bash
git pull --ff-only
python3 bin/build_daily_recommendations.py --date "$(date +%F)"
python3 -m unittest discover -s tests -v
python3 bin/check_privacy.py
```

Required readback:

1. Report must be `READY_FOR_OWNER_REVIEW`, not `PREVIEW_STALE_CORPUS`.
2. EDA scope excludes FPGA, embedded, PCB and analog/RF; source review does not equal EDA runtime proof.
3. Finance is research-only. Any trading execution, broker/wallet credential or private-key path stays excluded.
4. `pilot` means isolated evaluation only; it is not installed, live, profitable or production-proven.
