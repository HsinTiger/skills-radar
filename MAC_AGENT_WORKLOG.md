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
