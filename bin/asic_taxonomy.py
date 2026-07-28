#!/usr/bin/env python3
"""Deterministic secondary taxonomy for WiFi baseband ASIC / RTL skills.

This module is deliberately *not* a domain classifier.  Callers must first pass
the existing ``hardware-eda`` label and confidence gate.  Regex is only used to
split an already-confirmed hardware row into owner-specific subcategories.

The taxonomy is provisional until a new-distribution LLM sample is labelled and
validated.  It is useful for candidate routing, never as ASIC sign-off evidence.
"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable

from corpus_policy import label_is_eligible


HARDWARE_TARGETS = {
    "asic", "fpga", "embedded", "board-pcb", "analog-rf", "physical",
    "mixed", "generic",
}
ASIC_STAGES = {
    "spec-architecture", "algorithm-to-architecture", "fixed-point",
    "microarchitecture", "rtl-design", "lint-cdc-rdc", "formal-assertion",
    "simulation-debug", "uvm-verification", "synthesis-lec-eco",
    "integration-handoff", "dft", "physical",
}
WIFI_AREAS = {
    "phy-baseband", "ofdm", "mimo-beamforming", "synchronization-cfo",
    "channel-estimation-equalization", "demapper-coding",
    "fixed-point-architecture", "mac", "rf",
}
OWNER_FITS = {"direct", "supporting", "adjacent", "exclude"}


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


ASIC = _rx(
    r"\b(asic|standard\s*cell|tape[ -]?out|design\s*compiler|primetime|formality|"
    r"spyglass|genus|tempus|conformal|power\s*compiler)\b"
)
FPGA = _rx(
    r"\b(fpga|vivado|quartus|vitis|xilinx|altera|intel\s+fpga|lattice|ecp5|"
    r"nextpnr|openfpgaloader|bitstream|\bxdc\b|\bbram\b|\bila\b|\bvio\b)\b"
)
FPGA_SPECIFIC = _rx(
    r"(?:^|[/\\])fpga(?:[/\\]|$)|\b(vivado|quartus|vitis|xilinx|altera|"
    r"intel\s+fpga|lattice|ecp5|nextpnr|openfpgaloader|bitstream|\bxdc\b|"
    r"\bbram\b|\bila\b|\bvio\b)\b"
)
EMBEDDED = _rx(
    r"\b(embedded|firmware|microcontroller|\bmcu\b|esp32|esp-idf|stm32|arduino|"
    r"freertos|zephyr|bare[ -]?metal|device\s*tree|openocd|\bgdb\b|jtag\s*debug)\b"
)
BOARD_PCB = _rx(
    r"\b(pcb|kicad|altium|schematic|gerber|board\s+(bring[ -]?up|design)|bom|"
    r"footprint|jlcpcb|solder)\b"
)
ANALOG_RF = _rx(
    r"\b(analog|mixed[ -]?signal|rf\s*(front[ -]?end|design|circuit)|antenna|"
    r"s[ -]?parameter|spice|lna|low\s+noise\s+amplifier|pll\s+circuit|adc\s+layout|"
    r"dac\s+layout|serdes|ibis[ -]?ami)\b"
)
PHYSICAL = _rx(
    r"\b(openroad|openlane|innovus|icc2?|place\s*(?:and|&)\s*route|pnr|"
    r"floorplan|physical\s+(?:design|verification)|\bdrc\b|\blvs\b|pdk|"
    r"clock\s*tree\s*synthesis|routing\s+congestion)\b"
)
GENERIC_DIGITAL = _rx(
    r"\b(rtl|systemverilog|verilog|uvm|sva|testbench|synthesis|netlist|"
    r"clock\s+domain\s+crossing|reset\s+domain\s+crossing|formal\s+verification|"
    r"vcs|verdi|xcelium|questa|fsdb|waveform|logic\s+design)\b"
)


STAGE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("spec-architecture", _rx(
        r"\b(requirements?|specification|design\s+intent|architecture|interface\s+contract|"
        r"behavior(?:al)?\s+spec|cycle[ -]?accurate)\b"
    )),
    ("algorithm-to-architecture", _rx(
        r"\b(algorithm\s+to\s+(?:hardware|rtl)|reference\s+model|golden\s+model|"
        r"hardware\s+architecture|matlab|simulink|throughput\s+budget|latency\s+budget)\b"
    )),
    ("fixed-point", _rx(
        r"\b(fixed[ -]?point|quantiz(?:e|ation)|word[ -]?length|bit[ -]?true|"
        r"finite\s+precision|saturation|rounding\s+mode)\b"
    )),
    ("microarchitecture", _rx(
        r"\b(microarchitecture|pipeline|datapath|control\s+path|fsm|arbit(?:er|ration)|"
        r"latency|throughput|ready[ /-]?valid|clock\s+gating)\b"
    )),
    ("rtl-design", _rx(
        r"\b(rtl|systemverilog|verilog|synthesizable|always_ff|always_comb|"
        r"module\s+(?:design|generation)|logic\s+design)\b"
    )),
    ("lint-cdc-rdc", _rx(
        r"\b(rtl\s+lint|lint(?:ing)?|clock\s+domain\s+crossing|\bcdc\b|"
        r"reset\s+domain\s+crossing|\brdc\b|synchronizer|metastability|waiver)\b"
    )),
    ("formal-assertion", _rx(
        r"\b(formal\s+(?:verification|property)|model\s+checking|sva|assertions?|"
        r"property\s+checking|equivalence|\blec\b|prove|proof)\b"
    )),
    ("simulation-debug", _rx(
        r"\b(simulat(?:e|ion|or)|regression|waveform|fsdb|\bvcd\b|vcs|verdi|"
        r"xcelium|questa|modelsim|verilator|debug|driver[/ ]load)\b"
    )),
    ("uvm-verification", _rx(
        r"\b(uvm|functional\s+coverage|code\s+coverage|constrained[ -]?random|"
        r"scoreboard|sequence(?:r)?|verification\s+plan|coverage\s+closure)\b"
    )),
    ("synthesis-lec-eco", _rx(
        r"\b(logic\s+synthesis|rtl\s+synthesis|synthesis|design\s+compiler|genus|"
        r"formality|conformal|logical\s+equivalence|equivalence\s+checking|\blec\b|"
        r"front[ -]?end\s+eco|rtl\s+eco|engineering\s+change\s+order|\bqor\b)\b"
    )),
    ("integration-handoff", _rx(
        r"\b(soc\s+integration|ip\s+integration|top[ -]?level\s+integration|ip[ -]?xact|"
        r"systemrdl|register\s+map|\bcsr\b|handoff|release\s+checklist|rtl\s+freeze)\b"
    )),
    ("dft", _rx(r"\b(dft|design\s+for\s+test|scan\s+chain|atpg|mbist|fault\s+coverage)\b")),
    ("physical", PHYSICAL),
)


WIFI_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("phy-baseband", _rx(
        r"\b(802\.11(?:a|n|ac|ax|be)?|wi[ -]?fi|wlan|wireless\s+lan|"
        r"phy\s+baseband|baseband\s+(?:phy|processor|signal))\b"
    )),
    ("ofdm", _rx(r"\b(ofdm|ofdma|cyclic\s+prefix|ofdm\s+(?:fft|ifft)|subcarrier)\b")),
    ("mimo-beamforming", _rx(r"\b(mimo|mu[ -]?mimo|beamform|spatial\s+stream|precod)\b")),
    ("synchronization-cfo", _rx(
        r"\b(carrier\s+frequency\s+offset|\bcfo\b|symbol\s+synchroni[sz]|"
        r"preamble\s+detect|packet\s+detect)\b"
    )),
    ("channel-estimation-equalization", _rx(
        r"\b(channel\s+estim|channel\s+equaliz|pilot\s+(?:tone|tracking)|phase\s+tracking|"
        r"frequency\s+domain\s+equal)\b"
    )),
    ("demapper-coding", _rx(
        r"\b(demapp|constellation|ldpc|viterbi|forward\s+error\s+correct|interleav|"
        r"descrambl|scrambl|qam|bpsk|qpsk)\b"
    )),
    ("fixed-point-architecture", _rx(
        r"\b(fixed[ -]?point|word[ -]?length|bit[ -]?true|quantiz(?:e|ation)|"
        r"hardware\s+architecture)\b"
    )),
    ("mac", _rx(
        r"\b(802\.11\s+mac|wlan\s+mac|wi[ -]?fi\s+mac|ppdu|a[ -]?mpdu|a[ -]?msdu|"
        r"csma[/ -]?ca|block\s+ack|target\s+wake\s+time|\btwt\b)\b"
    )),
    ("rf", _rx(
        r"\b(rf\s*(?:front[ -]?end|circuit|design)|antenna|s[ -]?parameter|lna|"
        r"power\s+amplifier|spectrum\s+analy[sz]er|vector\s+network\s+analy[sz]er)\b"
    )),
)


DIRECT_STAGES = {
    "spec-architecture", "algorithm-to-architecture", "fixed-point",
    "microarchitecture", "rtl-design", "lint-cdc-rdc", "formal-assertion",
    "simulation-debug", "uvm-verification", "synthesis-lec-eco",
    "integration-handoff",
}


def row_blob(row: dict) -> str:
    """Return bounded text used for secondary classification."""
    # Search terms and topic tiers are sampling provenance, not content evidence.
    # Including them would let a noisy query assign a false secondary label.
    parts: list[str] = [
        str(row.get("name") or ""),
        str(row.get("description") or ""),
        str(row.get("body_head") or "")[:2000],
        str(row.get("path") or ""),
    ]
    return " ".join(parts)


def is_hardware_candidate(row: dict) -> bool:
    """Apply the upstream domain/confidence gate before any regex split."""
    return row.get("domain") == "hardware-eda" and label_is_eligible(row, "domain")


def _hits(pattern: re.Pattern[str], text: str, limit: int = 6) -> list[str]:
    seen: list[str] = []
    for match in pattern.finditer(text):
        value = " ".join(match.group(0).lower().split())
        if value not in seen:
            seen.append(value)
        if len(seen) >= limit:
            break
    return seen


def classify_hardware_target(text: str) -> tuple[str, dict[str, list[str]]]:
    evidence = {
        "asic": _hits(ASIC, text),
        "fpga": _hits(FPGA, text),
        "embedded": _hits(EMBEDDED, text),
        "board-pcb": _hits(BOARD_PCB, text),
        "analog-rf": _hits(ANALOG_RF, text),
        "physical": _hits(PHYSICAL, text),
        "generic": _hits(GENERIC_DIGITAL, text),
    }
    if evidence["asic"] and evidence["fpga"]:
        target = "mixed"
    elif evidence["fpga"]:
        target = "fpga"
    elif evidence["embedded"]:
        target = "embedded"
    elif evidence["board-pcb"]:
        target = "board-pcb"
    elif evidence["analog-rf"]:
        target = "analog-rf"
    elif evidence["physical"] and not evidence["asic"]:
        target = "physical"
    elif evidence["asic"]:
        target = "asic"
    else:
        target = "generic"
    return target, {k: v for k, v in evidence.items() if v}


def _categories(text: str, patterns: Iterable[tuple[str, re.Pattern[str]]]) -> tuple[list[str], dict[str, list[str]]]:
    labels: list[str] = []
    evidence: dict[str, list[str]] = {}
    for label, pattern in patterns:
        hits = _hits(pattern, text)
        if hits:
            labels.append(label)
            evidence[label] = hits
    return labels, evidence


def classify_owner_fit(target: str, stages: list[str], wifi_areas: list[str], text: str) -> tuple[str, str]:
    non_rf_wifi = [area for area in wifi_areas if area != "rf"]
    if target in {"fpga", "embedded", "board-pcb", "analog-rf"}:
        return "exclude", f"hardware_target={target} 不在 WiFi ASIC RTL scope"
    if target == "mixed" and FPGA_SPECIFIC.search(text):
        return "exclude", "含明確 FPGA tool/device/bitstream flow"
    if wifi_areas == ["rf"]:
        return "exclude", "僅 RF/antenna scope，非數位 baseband"
    if target == "asic" and DIRECT_STAGES.intersection(stages):
        if non_rf_wifi:
            return "direct", "ASIC front-end 與 WiFi baseband 交集"
        return "direct", "ASIC RTL/front-end EDA 直接適用"
    if target in {"generic", "mixed"} and DIRECT_STAGES.intersection(stages):
        return "supporting", "通用數位 RTL/EDA 程序，可抽取後改編"
    if non_rf_wifi and DIRECT_STAGES.intersection(stages):
        return "supporting", "WiFi/baseband 內容可支援架構或驗證"
    if target == "physical" or "physical" in stages or "dft" in stages:
        return "adjacent", "屬 ASIC 後段/DFT 鄰接流程，非目前 RTL 主軸"
    return "adjacent", "硬體相關但缺少可直接映射到 ASIC RTL 的證據"


def _score_and_grade(row: dict, target: str, stages: list[str], wifi_areas: list[str], owner_fit: str) -> tuple[int, str]:
    score = {"direct": 70, "supporting": 48, "adjacent": 22, "exclude": 0}[owner_fit]
    if target == "asic":
        score += 10
    if [x for x in wifi_areas if x != "rf"]:
        score += 15
    score += min(10, 2 * len(DIRECT_STAGES.intersection(stages)))
    if target == "mixed":
        score -= 5
    if row.get("injection_suspect"):
        score -= 20
    score = max(0, min(100, score))
    if owner_fit == "exclude":
        grade = "D"
    elif owner_fit == "direct" and score >= 80:
        grade = "A"
    elif owner_fit in {"direct", "supporting"} and score >= 50:
        grade = "B"
    else:
        grade = "C"
    return score, grade


def classify_row(row: dict) -> dict:
    if not is_hardware_candidate(row):
        raise ValueError("secondary taxonomy requires eligible hardware-eda row")
    if row.get("asic_label_source") == "llm":
        target = row.get("hardware_target")
        stages = row.get("asic_stages")
        wifi_areas = row.get("wifi_areas")
        owner_fit = row.get("owner_fit")
        if target not in HARDWARE_TARGETS or owner_fit not in OWNER_FITS \
                or not isinstance(stages, list) or not set(stages).issubset(ASIC_STAGES) \
                or not isinstance(wifi_areas, list) or not set(wifi_areas).issubset(WIFI_AREAS):
            raise ValueError("invalid llm secondary taxonomy fields")
        score, grade = _score_and_grade(row, target, stages, wifi_areas, owner_fit)
        return {
            "hardware_target": target,
            "asic_stages": stages,
            "wifi_areas": wifi_areas,
            "owner_fit": owner_fit,
            "owner_fit_reason": "嚴格驗證後的 LLM golden label",
            "fit_score": score,
            "provisional_grade": grade,
            "target_evidence": {"llm": row.get("asic_label_evidence") or []},
            "stage_evidence": {},
            "wifi_evidence": {},
            "taxonomy_basis": "llm-golden-v1",
        }
    text = row_blob(row)
    target, target_evidence = classify_hardware_target(text)
    stages, stage_evidence = _categories(text, STAGE_PATTERNS)
    wifi_areas, wifi_evidence = _categories(text, WIFI_PATTERNS)
    # Fixed-point is cross-domain. Treat it as a WiFi area only when this skill
    # also contains independent WiFi/baseband algorithm evidence.
    if "fixed-point-architecture" in wifi_areas and not any(
        area not in {"fixed-point-architecture", "rf"} for area in wifi_areas
    ):
        wifi_areas.remove("fixed-point-architecture")
        wifi_evidence.pop("fixed-point-architecture", None)
    owner_fit, fit_reason = classify_owner_fit(target, stages, wifi_areas, text)
    score, grade = _score_and_grade(row, target, stages, wifi_areas, owner_fit)

    return {
        "hardware_target": target,
        "asic_stages": stages,
        "wifi_areas": wifi_areas,
        "owner_fit": owner_fit,
        "owner_fit_reason": fit_reason,
        "fit_score": score,
        "provisional_grade": grade,
        "target_evidence": target_evidence,
        "stage_evidence": stage_evidence,
        "wifi_evidence": wifi_evidence,
        "taxonomy_basis": "deterministic-secondary-v1",
    }


def content_signature(row: dict) -> str:
    """Stable duplicate key without retaining third-party body text."""
    normalized = re.sub(
        r"\s+", " ", f"{row.get('name') or ''}\n{row.get('description') or ''}".strip().lower()
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
