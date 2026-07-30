# Mac Agent Worklog — refresh canonical corpus and finish Wiki ingest

## 2026-07-28 Windows handoff — separate EDA/IC and investing research zones

- `PROVEN`: `docs/eda-ic/` and `docs/investing/` are now separate owner-facing zones with
  day/week/month/quarter period-keyed pages, full current skill dossiers, explicit canaries,
  evidence requirements, kill criteria and adoption boundaries.
- `PROVEN`: the ASIC candidate catalog was rebuilt against the current 42,242-row master;
  catalog/master SHA-256 now matches.  The secondary ASIC taxonomy still has zero golden rows
  and remains `BLOCKED`, so it is routing evidence only.
- `PROVEN`: the old dashboard EDA list no longer uses broad hardware keyword matches.  It now
  requires owner-scoped ASIC/generic + direct/supporting routing and excludes FPGA, embedded,
  PCB, analog/RF and non-WiFi wireless-specific material at display time.
- `PROVEN`: all 13 current EDA sources have static review dossiers; runtime proof remains
  `NOT_RUN`.  The finance zone now contains eight pinned source reviews: A=2, B=1, C=2, D=3.
  D-grade trading/position/credential paths are excluded.
- `PROVEN`: the daily pipeline now rebuilds the ASIC catalog before recommendations, builds both
  zones after the timescale dispatcher, and requires `domain_zones=PASS` in pipeline health.
- `PROVEN`: 89 unit tests, privacy scan, HTML structural/local-link audit and `git diff --check`
  passed on Windows.
- `UNKNOWN`: unattended launchd recovery remains unproven.  The current health marker correctly
  says `execution_context=manual_recovery`; only a real scheduled 08:30 run may change this to
  `launchd`.

Canonical Mac next action after pull:

```bash
git pull --ff-only
./bin/install_launchd.sh
./bin/check_launchd.sh
python3 -m unittest discover -s tests -v
python3 bin/check_privacy.py
```

Do not manually rewrite the health marker to `launchd`.  After the next real scheduled run,
require live Pages readback of `/pipeline_health.json`, `/eda-ic/` and `/investing/`.

## 2026-07-28 final Windows handoff — reader-safe articles and current snapshot

- `PROVEN`: canonical corpus is now 42,242 unique rows, with 6,577 seed labels and
  35,665 local-model labels. Master SHA-256 is
  `3a2d07c6965d92c167a932ea1323b9bc9f77b921416afdc90a2363f1528133f6`.
- `PROVEN`: rolling Release `corpus-latest` was replaced and read back with asset digest
  `sha256:b3f856d160bf816b6fb3fe1fd3b3887fee46f40a7778fe67d5303720caddbd01`.
- `PROVEN`: stored day, week, month and quarter prose was rewritten as reader-facing
  Traditional Chinese mini-editorials. The dispatcher now reschedules any old prose that fails
  the current jargon/readability validator; the public page hides unsafe legacy prose until repair.
- `PROVEN`: local dashboard visually renders the opinion text first and keeps numeric evidence in
  a collapsed section. Zero-sample periods no longer print internal fields, evidence IDs or rows of zeroes.
- `UNKNOWN`: no Windows run proves the canonical Mac has `scikit-learn`, has reloaded the LaunchAgent,
  or will produce the 2026-07-29 scheduled `execution_context=launchd` marker.

Canonical Mac next action after this commit reaches `main`:

```bash
git pull --ff-only
python3 -m pip install -r requirements-ml.txt
./bin/install_launchd.sh
./bin/check_launchd.sh
launchctl kickstart -k "gui/$UID/com.hsin.skills-radar"
```

The immediate kickstart is only a canary. The unattended schedule is proven only after a real
08:30 run publishes a matching live Pages health marker with `execution_context=launchd`.

## 2026-07-28 root cause — launchd could not resolve `gh`

- `PROVEN`: the scheduled 08:30 collector crashed in `harvest_delta.py` with
  `FileNotFoundError: 'gh'`.
- `PROVEN`: the old shell runner ignored that exit status, converted the crash into
  「今日無新增 skill」, and continued toward a false local PASS.
- `PROVEN`: the repaired runner now checks both `command -v gh` and `gh auth status`, then uses
  `update_corpus.py` to persist a read-back manifest. Collector, classify, merge, train,
  editorial, privacy, or health failure stops publish.
- `PROVEN`: the daily research AI output is now one evidence-bounded Traditional Chinese
  editorial. `research/insights/` is archive-only, avoiding a second daily AI call.
- `UNKNOWN`: launchd recovery is not proven until the canonical Mac reloads the plist and a
  scheduled run publishes `execution_context=launchd` for live Pages readback.
- `PROVEN`: a recovery spike of 1,012 public rows exceeded the per-batch Claude budget on
  Windows. The daily runner now caps LLM seed labelling at 180 rows; larger deltas use the
  existing local classifier and retain field-confidence gates. This is model labelling, not
  new LLM seed evidence.

Mac reload and canary:

```bash
git pull --ff-only
command -v gh
gh auth status
./bin/install_launchd.sh
./bin/check_launchd.sh
launchctl kickstart -k "gui/$UID/com.hsin.skills-radar"
```

After the canary, require today's `data/corpus_update_manifest.json` to be `SUCCESS`, require
both `research/editorials/YYYY-MM-DD.md` and `docs/editorials/YYYY-MM-DD.html`, then read back
live Pages. A manual canary can recover data but does not prove the next 08:30 schedule fired.

## RESOLVED on 2026-07-28 — use the new recoverable baseline

The old 610-row Mac LLM output was not recoverable from Git or Release, and remote `main`
never received it. Windows therefore created a new bounded, auditable relabel baseline instead
of pretending to reconstruct the missing labels.

- `PROVEN`: 640 public rows were sampled evenly across `targeted-eda2` / `targeted-wifi`
  and eight topic tiers; every `repo+path` and output index is unique.
- `PROVEN`: strict merge accepted all 640 valid LLM labels, then the local classifier retrained.
- `PROVEN`: canonical counts are now `rows=41230`, `seed=6577`, `model=34653`.
- `PROVEN`: master SHA-256 is
  `6086cfe264b26a69955234000d532d1a842fbadf2db0d0cb0da7d4d4424c54cd`.
- `PROVEN`: rolling Release tag `corpus-latest` has asset SHA-256
  `6727d6ced0055ab13ea15c444873274c5331b20283a06f2fcb44c0273510fb00`.
- `PROVEN`: day `2026-07-27`, week `2026-W30`, month `2026-06`, and quarter
  `2026-Q2` are all `AI_GENERATED`; local health is `PASS` with `master_freshness=CURRENT`.

Mac next action:

```bash
git pull --ff-only
gh release download corpus-latest --pattern master.jsonl.gz --dir corpus --clobber
gzip -dc corpus/master.jsonl.gz > corpus/master.jsonl
python3 bin/timescale_summaries.py --date "$(date +%F)" --plan-only
```

Do **not** republish or merge the older `6547/34683` master over this baseline.  First verify
the exact master hash and counts above.  `bin/run_daily.sh` now publishes `corpus-latest` on
every successful run and keeps the Monday dated archive separately, so tracked reports and
the downloadable corpus cannot silently drift again.

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

---

# 2026-07-28 audit — scheduled update missed; cadence dispatcher handoff

## Proven remote state

- Remote `main` and Pages were still at `a37462c` during the 2026-07-28 audit.
- Pages returned HTTP 200 but contained no `2026-07-28` report and still showed `PREVIEW_STALE_CORPUS`.
- Windows master remains stale: seed/model `5937/35293`; model report expects `6547/34683`.
- Therefore the existence of launchd is not proof that the 2026-07-28 run or publish succeeded.

## New cadence contract

The daily 08:30 launchd job is now a dispatcher. It updates only closed periods and retries missing
`period_id` values without recomputing successful periods:

- day: previous complete day;
- week: previous complete Monday-Sunday week;
- month: previous complete calendar month;
- quarter: previous complete calendar quarter.

On 2026-07-28 the initial due set is `2026-07-27`, `2026-W30`, `2026-06`, and `2026-Q2`.

## Required Mac recovery and proof

```bash
git pull --ff-only
# Restore/verify the canonical 6547-seed / 34683-model master first.
python3 bin/timescale_summaries.py --date 2026-07-28 --plan-only
python3 -m unittest discover -s tests -v
bash -n bin/daily_research.sh bin/run_daily.sh
~/skills-radar/bin/run_daily.sh
```

Required readback after the run:

1. `data/pipeline_health.json` and `docs/pipeline_health.json` must report the current date and `PASS`
   (or an explicitly explained `PARTIAL`), with `master_freshness=CURRENT`.
2. `data/timescale_summaries.json` must contain validated records for every due period above.
3. Remote `main` must advance, then Pages `/pipeline_health.json` and the dashboard must be read back.
4. `AI_GENERATED` proves validated summary structure only; it does not prove skill correctness, EDA signoff,
   actual deployment, or investment outcome.
5. The GitHub 09:30 freshness watchdog must turn green only after the current health marker is pushed;
   the watchdog detects failure but cannot replace the Mac canonical run.

---

# 2026-07-28 follow-up — make the automatic schedule auditable

The dispatcher logic and today's four summaries are proven, but the installed LaunchAgent was not
captured in Git.  Pull the follow-up commit, then install/reload the versioned contract on the
canonical Mac:

```bash
git pull --ff-only
./bin/install_launchd.sh
./bin/check_launchd.sh
```

The installed job must be `com.hsin.skills-radar`, daily at 08:30 with `TZ=Asia/Taipei`.  The next
scheduled health marker should expose `schedule_contract.execution_context=launchd`.  A manual run
may recover current data, but it is not proof that launchd fired.  The 09:30 GitHub watchdog now
downloads live Pages and requires it to equal the checked-out `docs/pipeline_health.json`; checking
remote Git alone is no longer accepted as publish proof.  Starting with report date `2026-07-29`,
the watchdog also fails unless `schedule_contract.execution_context` is exactly `launchd`.

---

# 2026-07-29 Windows recovery — cumulative corpus delta and AI harness research desk

## Proven local recovery

- The canonical master was updated and locally classified at `42,407` rows: `6,577` seed rows and
  `35,830` model rows. The `165` rows first seen on 2026-07-29 are all `label_source=model`; no new
  LLM seed evidence is claimed.
- `harvest_delta.load_seen()` now treats `master.jsonl` as the sole authority whenever it exists.
  A stale `seen.tsv` can no longer permanently hide a path absent from master.
- `delta-YYYY-MM-DD.jsonl` is cumulative across same-date recovery runs. The corpus manifest keeps
  `daily_baseline`, date-level `new_rows`, and invocation-level `run_new_rows` separate.
- The recovery scan found 64 currently searchable paths absent from master, but none returned usable
  content through the fetch/parse gate. They were not inserted or marked complete and remain retryable.
- Windows JSON producers for aggregate, opportunity and injection scan now write UTF-8 atomically.
- The AI Application / Agent Harness / Automation zone contains eight pinned reviews, a daily
  observation tape, four research horizons, three ASIC-front-end niche hypotheses and a reader-facing
  editorial. Agent-Reach remains WATCH; no cookie, private-session, auto-login or anti-bot path ran.
- Local gates: 103 unit tests PASS, privacy PASS, Wiki lint PASS, pipeline health PASS.

## Mac owner action and proof boundary

1. Pull the pushed commit with `git pull --ff-only`.
2. Do not rewrite or discard the preserved 2026-07-29 daily baseline or cumulative delta.
3. Let the next real scheduled job run under the installed LaunchAgent, then read back
   `docs/pipeline_health.json` from live Pages.
4. Only a marker created by that job may report `execution_context=launchd`. This Windows recovery
   must remain `manual_recovery`; local PASS and Pages publication do not prove the Mac scheduler fired.

---

# 2026-07-30 Windows follow-up — 130-source AI deployment desk and field brief

## Proven local change

- `data/expert_watchlist.json` now contains 130 unique canonical handles across six exact tracks:
  frontier AI 25, AI research/builders 25, AI deployment/internal engineering 30, aerospace 20,
  quantum 15, and technology business 15.
- The 30-person deployment track prioritizes internal engineers, CTOs, technical founders, and core
  maintainers across eval/observability, inference/compiler runtime, retrieval/agent data, distributed
  training, secure deployment, and real-time systems. Each primary site returned HTTP 200 on 2026-07-30.
- The AI zone now renders an `AI Deployment Field Brief` contract with daily flash, weekly method memo,
  and monthly stack thesis. Six watchlist tracks are collapsed by default and show layer distribution
  before the reader expands individual sources.
- Local gates: 104 unit tests PASS, privacy PASS, Wiki lint PASS, JSON total/track/unique-handle checks PASS,
  and generated HTML static structure readback PASS.

## Evidence boundary and Mac next action

- Public-profile discovery is not technical proof and the watchlist is not proof that any X account was
  followed. Promote claims only from code, paper, official documentation, release artifacts, or a
  reproducible experiment.
- No live deployment brief was fabricated from profile descriptions. The contract remains
  `CONTRACT_READY_NO_LIVE_ISSUE` until an append-only observation contains a real implementation delta.
- The 2026-07-30 local build is honestly `PARTIAL` because `data/ai_automation_history.json` still ends on
  2026-07-29. Pull this change, run the real scheduled intake, and require Pages readback before calling
  the current issue published or the LaunchAgent healthy.
