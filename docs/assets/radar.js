/* Skills Radar — 共用前端。由 bin/build_site.py 複製到 docs/assets/radar.js。
   所有頁面共用同一份 data.json（不再把 118KB 資料內嵌進每個 HTML），
   依 <body data-page> 決定要 render 哪些區塊。 */
(function () {
  "use strict";

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var num = function (n) { return Number(n || 0).toLocaleString(); };
  var pad = function (n) { return String(n).padStart(2, "0"); };

  /* 內部欄位名不該出現在給人看的文章裡 */
  var READABLE = [
    [/archive_n/gi, "依專案建立日期歸入本期的樣本數"],
    [/discovered_previous_n/gi, "前一期雷達新發現數"],
    [/discovered_n/gi, "本期雷達新發現數"],
    [/repo_created(?:\s+cohort)?/gi, "依專案建立日期歸入本期的樣本"],
    [/first_seen/gi, "本系統首次觀察日期"],
    [/domain mix/gi, "領域分布"], [/task mix/gi, "任務分布"],
    [/maturity mix/gi, "成熟度分布"],
    [/production_document_proxy/gi, "文件自述已投入使用的指標"],
    [/agent_target_proxy/gi, "文件自述供 AI 助理使用的指標"],
    [/diversity entropy/gi, "領域分散程度"], [/entropy/gi, "領域分散程度"],
    [/hardware_eda_n/gi, "硬體與電子設計自動化樣本數"],
    [/finance_n/gi, "財經研究樣本數"], [/EDA_IC/g, "EDA／數位 IC"],
    [/AI_GENERATED/g, "已完成"], [/proxy/gi, "文件自述指標"], [/cohort/gi, "同一期樣本"]
  ];
  var readable = function (s) {
    var v = String(s == null ? "" : s);
    READABLE.forEach(function (p) { v = v.replace(p[0], p[1]); });
    return v.replace(/\s*\((?:E(?:10|[1-9])(?:\s*,\s*)?)+\)/g, "").trim();
  };
  var readerUnsafe = function (s) {
    return /(?:archive_n|discovered_n|repo_created|first_seen|domain mix|task mix|maturity mix|\bE(?:10|[1-9])\b|\b(?:confidence|taxonomy|validation|production|workflow|DevOps|signoff|golden|cohort|proxy|entropy)\b)/i
      .test(String(s == null ? "" : s));
  };

  var SCALE_ZH = { day: "日", week: "週", month: "月", quarter: "季" };
  var D = null;
  var mode = "month";

  /* ---------------- 共用小元件 ---------------- */

  function spark(arr) {
    var max = Math.max.apply(null, (arr || []).concat([1]));
    return '<div class="spark">' + (arr || []).map(function (v) {
      return '<i style="height:' + Math.max(2, Math.round(100 * v / max)) + '%"></i>';
    }).join("") + "</div>";
  }

  function healthChip(ph) {
    if (!ph) return '<span class="chip">NOT_RUN</span>';
    var cls = ph.status === "PASS" ? "pass" : ph.status === "BLOCKED" ? "fail" : "warn";
    return '<span class="chip ' + cls + '">' + esc(ph.status) + " · " + esc(ph.report_date) + "</span>";
  }

  function freshChip(generated) {
    var d = String(generated || "").slice(0, 10);
    var age = Math.floor((Date.now() - new Date(d + "T00:00:00Z").getTime()) / 86400000);
    if (!d || isNaN(age)) return '<span class="chip">資料日期未知</span>';
    var cls = age <= 1 ? "pass" : age <= 3 ? "warn" : "fail";
    var txt = age <= 0 ? "今日" : age === 1 ? "昨日" : age + " 天前";
    return '<span class="chip ' + cls + '">資料 ' + esc(d) + " · " + txt + "</span>";
  }

  /* ---------------- 排程 ---------------- */

  function nextRun() {
    var s = D.schedule || { hour: 8, minute: 30 };
    var now = new Date(), n = new Date(now);
    n.setHours(s.hour, s.minute, 0, 0);
    if (n <= now) n.setDate(n.getDate() + 1);
    return n;
  }
  function fmtDT(d) {
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
  }
  function untilText(d) {
    var ms = d - new Date(), h = Math.floor(ms / 3600000), m = Math.floor(ms % 3600000 / 60000);
    return h > 0 ? h + " 小時 " + m + " 分後" : m + " 分後";
  }
  function nextBoundary(kind) {
    var d = new Date(), x;
    if (kind === "week") { x = new Date(d); var dow = (x.getDay() + 6) % 7; x.setDate(x.getDate() + (7 - dow)); x.setHours(0, 0, 0, 0); return x; }
    if (kind === "month") return new Date(d.getFullYear(), d.getMonth() + 1, 1);
    if (kind === "quarter") { var nm = (Math.floor(d.getMonth() / 3) + 1) * 3; return new Date(d.getFullYear() + (nm >= 12 ? 1 : 0), nm % 12, 1); }
    x = new Date(d); x.setDate(x.getDate() + 1); x.setHours(0, 0, 0, 0); return x;
  }

  function renderSchedule() {
    var el = $("#next-update"); if (!el) return;
    var nr = nextRun(), b = nextBoundary(mode), ph = D.pipeline_health || {}, s = D.schedule || {};
    var label = SCALE_ZH[mode];
    var bLabel = mode === "day" ? "新的一天" : mode === "week" ? "新的一週（週一）"
      : mode === "month" ? "新的一月（1 號）" : "新的一季（季首月 1 號）";
    el.innerHTML =
      '<p><b>下次資料更新</b> <span class="m">' + fmtDT(nr) + "</span>（" + untilText(nr) + "）　·　" +
      "<b>下次" + label + "界變動</b> <span class=\"m\">" + fmtDT(b).slice(0, 10) + "</span>（" + bLabel + "）</p>" +
      "<p>排程 <code>" + esc(s.job || "com.hsin.skills-radar") + "</code> 每日 " +
      pad(s.hour == null ? 8 : s.hour) + ":" + pad(s.minute == null ? 30 : s.minute) +
      " 執行。日摘要更新前一日、週摘要於週一更新上一完整週、月摘要於月初更新上一完整月、季摘要於季初更新上一完整季；" +
      "離線後依 <code>period_id</code> 補跑缺期，不重算成功期。</p>" +
      "<p>最近 pipeline health：" + healthChip(ph) +
      "　執行來源 <code>" + esc((ph.schedule_contract || {}).execution_context || "unknown") + "</code>。" +
      "本機 PASS 不證明遠端發佈成功，需另做 Pages 回讀。</p>";
  }

  /* ---------------- 四尺度摘要 ---------------- */

  function renderSummary() {
    var el = $("#summary-card"); if (!el) return;
    var ts = D.timescale_summary || {};
    var rec = (ts.latest || {})[mode];
    var label = SCALE_ZH[mode];

    if (!rec || rec.status !== "AI_GENERATED") {
      el.innerHTML = '<div class="sumcard"><p class="kicker">' + label + '級週期觀察</p>' +
        "<h3>尚未產生經證據驗證的" + label + "級摘要</h3>" +
        '<div class="meta">排程存在不等於成功；需要完整資料、通過本機檢查，並完成遠端回讀。</div></div>';
      return;
    }
    var ai = rec.ai || {}, e = rec.evidence || {}, sample = e.E1_sample || {};
    var prose = [ai.headline, ai.executive_summary, ai.eda_ic_readout, ai.finance_readout, ai.contrarian_view]
      .concat(ai.structural_changes || [], ai.actions || [], ai.falsifiers || [], ai.caveats || []).join(" ");

    if (readerUnsafe(prose)) {
      el.innerHTML = '<div class="sumcard"><p class="kicker">' + label + '級週期觀察</p>' +
        "<h3>這篇舊摘要正在重寫</h3><p>它仍含有資料庫欄位或未解釋的英文術語，不適合直接閱讀，因此暫不顯示。" +
        "資料證據仍保留，下一次每日更新會依目前的繁中專欄規格重新產生。</p></div>";
      return;
    }
    if (Number(sample.archive_n || 0) === 0 && Number(sample.discovered_n || 0) === 0) {
      el.innerHTML = '<div class="sumcard"><p class="kicker">' + label + "級週期觀察 · " +
        esc(rec.period.start) + "～" + esc(rec.period.end) + "</p>" +
        "<h3>這一期資料不足，先不判讀趨勢</h3>" +
        "<p>依專案建立日期歸入這一期的樣本，以及本系統在這一期首次發現的樣本都不足。" +
        "這不代表生態沒有變化，只代表目前沒有可靠材料可以下結論。</p>" +
        '<div class="meta">判讀信心：低（資料不足）</div></div>';
      return;
    }

    var list = function (xs) {
      return "<ul>" + (xs || []).map(function (x) { return "<li>" + esc(readable(x)) + "</li>"; }).join("") + "</ul>";
    };
    var conf = { HIGH: "高", MEDIUM: "中", LOW: "低" }[ai.confidence] || "未標示";
    var confCls = ai.confidence === "HIGH" ? "pass" : ai.confidence === "LOW" ? "warn" : "on";
    var proxy = (e.E6_maturity || {}).production_document_proxy || {};
    var agent = (e.E6_maturity || {}).agent_target_proxy || {};
    var entropy = (e.E7_diversity || {}).domain_entropy || {};
    var shifts = (e.E3_domain_shifts || []).slice(0, 4);
    var delta = function (x) {
      return esc(x.label) + (x.delta_pp > 0 ? "增加" : x.delta_pp < 0 ? "減少" : "持平") + Math.abs(x.delta_pp) + " 個百分點";
    };

    var h = '<article class="sumcard"><p class="kicker">' + label + "級週期觀察 · " + esc(rec.period.period_id) + "</p>" +
      "<h3>" + esc(readable(ai.headline)) + "</h3>" +
      '<div class="meta">' + esc(rec.period.start) + "～" + esc(rec.period.end) +
      '　<span class="chip ' + confCls + '">判讀信心 ' + conf + "</span></div>" +
      '<p class="lede2">' + esc(readable(ai.executive_summary)) + "</p>" +
      "<h4>這一期，我怎麼看</h4>" + list(ai.structural_changes) +
      "<h4>對兩個主題的意義</h4>" +
      "<p><strong>電子設計自動化與數位晶片設計：</strong>" + esc(readable(ai.eda_ic_readout)) + "</p>" +
      "<p><strong>財經投資研究：</strong>" + esc(readable(ai.finance_readout)) + "</p>" +
      "<h4>另一種可能</h4><p>" + esc(readable(ai.contrarian_view)) + "</p>" +
      "<h4>接下來看什麼</h4>" + list(ai.actions) +
      "<details><summary>展開資料依據</summary>" +
      '<div class="evidence-grid">' +
      '<div class="evidence-card"><b>' + (sample.archive_n == null ? "—" : num(sample.archive_n)) + "</b><span>依專案建立日期歸入本期</span></div>" +
      '<div class="evidence-card"><b>' + (sample.discovered_n == null ? "—" : num(sample.discovered_n)) + "</b><span>本系統本期新發現</span></div>" +
      '<div class="evidence-card"><b>' + (proxy.pct == null ? "—" : proxy.pct + "%") + "</b><span>文件自述已投入使用</span></div>" +
      '<div class="evidence-card"><b>' + (agent.pct == null ? "—" : agent.pct + "%") + "</b><span>文件自述供 AI 助理使用</span></div>" +
      '<div class="evidence-card"><b>' + (entropy.normalized == null ? "—" : entropy.normalized) + "</b><span>領域分散程度</span></div>" +
      "</div>";
    if (shifts.length) h += "<p><strong>領域比重變化：</strong>" + shifts.map(delta).join("、") + "</p>";
    h += "<p><strong>哪些後續訊號會推翻本文：</strong></p>" + list(ai.falsifiers) +
      "<p><strong>資料限制：</strong></p>" + list(ai.caveats) + "</details></article>";
    el.innerHTML = h;
  }

  /* ---------------- 每日新發現 ---------------- */

  function renderDiscovery() {
    var el = $("#discovery-block"); if (!el) return;
    var d = D.discovery || {};
    if (!d.days || d.days.length < 2) {
      el.innerHTML = '<div class="note"><p><strong>每日新發現序列還不夠長。</strong>' +
        "「發現時鐘」（本系統首次觀察到某個 skill 的日期）只有在排程確實跑過的日子才有值，" +
        "目前只有 " + ((d.days || []).length) + " 天。這條線要累積幾週才有判讀價值。</p></div>";
      return;
    }
    var last = d.days.length - 1;
    el.innerHTML = '<div class="card"><div class="meta">每日新發現 · 最近 ' + d.days.length + " 個採集日</div>" +
      '<div style="display:flex;align-items:flex-end;gap:1rem;margin-top:.6rem">' +
      '<div style="flex:1;min-width:0">' + spark(d.totals) + "</div>" +
      '<div style="text-align:right"><b class="m" style="font-size:1.3rem">' + num(d.totals[last]) + "</b>" +
      '<div class="meta">' + esc(d.days[last]) + "</div></div></div>" +
      '<p class="lede" style="margin:.7rem 0 0">這條線用的是「發現時鐘」，跟上面依專案建立日期的「檔案時鐘」不同，兩者不可相加。</p></div>';
  }

  /* ---------------- 首頁 ---------------- */

  function renderHome() {
    var el;
    if ((el = $("#readout"))) {
      el.innerHTML =
        '<div><b class="m">' + num(D.n_total) + "</b><span>通過門檻的已分類 skill</span></div>" +
        '<div><b class="m">' + D.global_production_pct + "<small>%</small></b><span>文件自述已上線</span></div>" +
        '<div><b class="m">' + D.global_task_pct["驗證"] + "<small>%</small></b><span>verify 任務佔比</span></div>" +
        '<div><b class="m">' + D.eda.pct_of_corpus + "<small>%</small></b><span>硬體 / EDA 佔比</span></div>" +
        '<div><b class="m">' + (D.security ? D.security.pct_flagged : "—") + "<small>%</small></b><span>疑似惡意內容命中</span></div>";
    }
    if ((el = $("#statusline"))) {
      var ph = D.pipeline_health || {};
      var gates = ph.gates || {};
      var bad = Object.keys(gates).filter(function (k) {
        return ["PASS", "SUCCESS", "AI_GENERATED", "CURRENT", "ARCHIVE_ONLY"].indexOf(gates[k]) < 0;
      });
      el.innerHTML = freshChip(D.generated) + " " + healthChip(ph) +
        ' <span class="chip ' + (bad.length ? "warn" : "pass") + '">' +
        (bad.length ? bad.length + " 個 gate 未通過" : "全部 gate 通過") + "</span>" +
        (ph.corpus_update ? ' <span class="chip on">今日新增 ' + num(ph.corpus_update.new_rows) + " 筆</span>" : "");
    }
    if ((el = $("#editorial-latest"))) {
      var ed = D.editorial || {};
      el.innerHTML = ed.href ? '<a class="zonecard" href="' + esc(ed.href) + '">' +
        '<span class="k">最新每日觀點 · ' + esc(ed.date) + "</span>" +
        "<h3>" + esc(ed.title) + "</h3>" +
        "<p>有主張、反方觀點與可證偽條件的繁中專欄；數字與 EDA／財經判讀都受當日可查證資料約束。</p>" +
        '<span class="go">閱讀全文 →</span></a>' : "";
    }
    renderSummary();
    renderSchedule();
  }

  /* ---------------- 趨勢頁 ---------------- */

  function renderTrends() {
    var v = D[mode], el;
    var label = SCALE_ZH[mode];
    if ((el = $("#view-desc"))) {
      el.textContent = v
        ? "目前為" + label + "級視角，涵蓋最近 " + v.periods.length + " " + (mode === "day" ? "天" : label) +
          "（" + v.periods[0] + " 起）。" +
          (mode === "day" ? "日級粒度雜訊大，且最近 2–3 天因搜尋索引落差必定偏低，看趨勢不要看單日。" : "")
        : label + "級資料尚未由目前的語料重建。";
    }
    if ((el = $("#trend-range"))) el.textContent = v ? "近期 " + v.recent_label + "｜前期 " + v.older_label : "等待有效資料";
    if ((el = $("#trend-body"))) {
      el.innerHTML = v ? v.growth.map(function (g) {
        var up = g.delta > 0;
        return "<tr><td>" + esc(g.zh) + "</td>" +
          '<td class="num">' + g.recent + '<br><span class="lede">' + g.recent_share + "%</span></td>" +
          '<td class="num">' + g.older + '<br><span class="lede">' + g.older_share + "%</span></td>" +
          '<td class="num ' + (up ? "up" : "down") + '">' + (up ? "+" : "") + g.delta + "<small>pp</small></td>" +
          "<td>" + spark(v.stack[g.domain]) + "</td></tr>";
      }).join("") : "";
    }
    if ((el = $("#traction-body"))) {
      el.innerHTML = D.traction.map(function (t) {
        return "<tr><td>" + esc(t.zh) + '</td><td class="num">' + t.n + "</td>" +
          '<td class="num">' + t.production_pct + "%</td>" +
          '<td class="num ' + (t.vs_global_production > 0 ? "up" : "down") + '">' +
          (t.vs_global_production > 0 ? "+" : "") + t.vs_global_production + "</td>" +
          '<td class="num">' + t.agent_facing_pct + "%</td></tr>";
      }).join("");
    }
    if ((el = $("#unfinished-body"))) {
      el.innerHTML = D.unfinished.slice(0, 10).map(function (u) {
        return "<tr><td>" + esc(u.zh) + '</td><td class="num">' + u.workflow + "</td>" +
          '<td class="num">' + u.production + '</td><td class="num">' + u.completion_ratio + "</td>" +
          '<td><div class="bar"><i style="width:' + Math.round(u.completion_ratio * 100) + '%"></i></div></td></tr>';
      }).join("");
    }
    renderDiscovery();
    renderSchedule();
  }

  /* ---------------- 缺口頁 ---------------- */

  function renderNiches() {
    var key = mode === "quarter" ? "niche_quarter" : mode === "month" ? "niche_month" : "niche_week";
    var list = D[key] || [], el;
    if ((el = $("#niche-body"))) {
      el.innerHTML = list.slice(0, 9).map(function (nc) {
        var mom = nc.momentum;
        var badge = mom == null ? '<span class="chip">動能資料不足</span>'
          : mom > 0 ? '<span class="chip warn">需求在長 +' + mom + "pp</span>"
            : '<span class="chip">份額收縮 ' + mom + "pp</span>";
        return '<div class="card"><div class="meta">缺口比值 ' + nc.ratio + "×</div>" +
          "<h3>" + esc(nc.zh) + " 缺「" + esc(nc.task_zh) + "」能力</h3>" +
          '<p class="lede" style="margin-bottom:.6rem">該領域共 ' + nc.domain_n + " 件，這種任務實際只有 <b>" +
          nc.observed + "</b> 件，按全體分佈推算應有 <b>" + nc.expected + "</b> 件。</p>" +
          '<div class="bar" title="實際 / 期望"><i class="gap" style="width:' +
          Math.min(100, nc.ratio * 100) + '%"></i></div>' +
          '<p style="margin:.65rem 0 0">' + badge + "</p></div>";
      }).join("");
    }
    if ((el = $("#pros-body"))) {
      el.innerHTML = D.niche_pros.map(function (p) {
        return "<tr><td>" + esc(p.profession) + '</td><td class="num">' + p.n + "</td>" +
          '<td class="num">' + p.production + '</td><td class="lede">' + esc((p.pains || []).join("；")) + "</td></tr>";
      }).join("");
    }
    if ((el = $("#eda-gaps"))) {
      var g = D.eda_gaps || { tasks: [] };
      var maxr = Math.max.apply(null, g.tasks.map(function (t) { return t.ratio; }).concat([3]));
      el.innerHTML = '<div class="card"><div class="meta">硬體 / EDA 任務密度 vs 全體基準（' +
        g.n_hw + " 件；1.0× = 與全體一致）</div>" +
        '<div class="ratio baselined" style="margin-top:.8rem">' +
        g.tasks.slice().sort(function (a, b) { return b.ratio - a.ratio; }).map(function (t) {
          var cls = t.ratio >= 1.5 ? "over" : t.ratio <= 0.6 ? "gap" : "";
          return '<div class="rrow"><span class="rname">' + esc(t.zh) + "</span>" +
            '<span class="rtrack"><span class="rbar ' + cls + '" style="width:' +
            Math.min(100, 100 * t.ratio / maxr) + '%"></span></span>' +
            '<span class="rval">' + t.ratio.toFixed(2) + "×</span></div>";
        }).join("") + "</div></div>";
    }
    renderSchedule();
  }

  /* ---------------- 安全頁 ---------------- */

  function renderSecurity() {
    var s = D.security, el = $("#security-block"); if (!el) return;
    if (!s) { el.innerHTML = '<div class="note alarm"><p>尚未產生掃描結果。</p></div>'; return; }
    var cats = Object.keys(s.by_category || {}).map(function (k) { return [k, s.by_category[k]]; })
      .sort(function (a, b) { return b[1] - a[1]; });
    var maxc = cats.length ? cats[0][1] : 1;
    var doms = Object.keys(s.by_domain || {}).map(function (k) { return [k, s.by_domain[k]]; })
      .sort(function (a, b) { return b[1].pct - a[1].pct; }).slice(0, 10);

    el.innerHTML =
      '<div class="readout" style="margin-bottom:1.4rem">' +
      '<div><b class="m">' + num(s.n_scanned) + "</b><span>掃描樣本</span></div>" +
      '<div><b class="m">' + num(s.n_flagged) + "</b><span>命中</span></div>" +
      '<div><b class="m">' + s.pct_flagged + "<small>%</small></b><span>命中率</span></div>" +
      "</div>" +
      '<div class="cards two">' +
      '<div class="card"><div class="meta">依樣態</div><div class="ratio" style="margin-top:.8rem">' +
      cats.map(function (c) {
        return '<div class="rrow"><span class="rname" style="font-size:.84rem">' + esc(c[0]) + "</span>" +
          '<span class="rtrack"><span class="rbar gap" style="width:' + (100 * c[1] / maxc) + '%"></span></span>' +
          '<span class="rval">' + c[1] + "</span></div>";
      }).join("") + "</div></div>" +
      '<div class="card"><div class="meta">依領域命中率</div><div class="ratio" style="margin-top:.8rem">' +
      doms.map(function (d) {
        return '<div class="rrow"><span class="rname" style="font-size:.84rem">' + esc(d[0]) + "</span>" +
          '<span class="rtrack"><span class="rbar" style="width:' + Math.min(100, d[1].pct * 30) + '%"></span></span>' +
          '<span class="rval">' + d[1].pct + "%</span></div>";
      }).join("") + "</div></div></div>";
  }

  /* ---------------- 尺度切換 ---------------- */

  function bindScaleTabs(onChange) {
    var tabs = document.querySelectorAll(".scaletabs button[data-scale]");
    if (!tabs.length) return;
    var saved = null;
    try { saved = localStorage.getItem("radar.scale"); } catch (e) { /* private mode */ }
    if (saved && SCALE_ZH[saved]) mode = saved;
    Array.prototype.forEach.call(tabs, function (b) {
      b.addEventListener("click", function () {
        mode = b.dataset.scale;
        try { localStorage.setItem("radar.scale", mode); } catch (e) { /* ignore */ }
        sync(); onChange();
      });
    });
    function sync() {
      Array.prototype.forEach.call(tabs, function (b) {
        b.setAttribute("aria-pressed", String(b.dataset.scale === mode));
      });
    }
    sync();
  }

  /* ---------------- 啟動 ---------------- */

  var PAGES = {
    home: renderHome,
    trends: renderTrends,
    niches: renderNiches,
    security: renderSecurity,
    method: function () { renderSchedule(); }
  };

  function boot(data) {
    D = data;
    var page = document.body.dataset.page || "home";
    var render = PAGES[page] || renderHome;
    bindScaleTabs(render);
    render();
    var f = document.querySelector("#foot-gen");
    if (f) f.textContent = "產生時間 " + D.generated + "　·　樣本 " + num(D.n_total) + " 筆" +
      (D.eligibility ? "　·　採納門檻 model_conf ≥ " + D.eligibility.model_conf_min : "");
    Array.prototype.forEach.call(document.querySelectorAll(".loading"), function (n) { n.remove(); });
  }

  var src = document.body.dataset.src || "data.json";
  fetch(src, { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(boot)
    .catch(function (err) {
      var m = document.querySelector("main") || document.body;
      var d = document.createElement("div");
      d.className = "err";
      d.textContent = "資料載入失敗（" + err.message + "）。這個頁面需要透過 HTTP 開啟，直接用 file:// 打開會被瀏覽器擋下。";
      m.insertBefore(d, m.firstChild);
    });
})();
