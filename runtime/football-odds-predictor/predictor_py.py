from __future__ import annotations

import json
import math
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
CALIBRATION_PATH = ROOT_DIR / "calibration" / "latest.json"
OPENING_ONLY_CALIBRATION_PATH = ROOT_DIR / "calibration" / "opening_only.json"
HYBRID_CALIBRATION_PATH = ROOT_DIR / "calibration" / "hybrid.json"
CLOSING_ONLY_CALIBRATION_PATH = ROOT_DIR / "calibration" / "closing_only.json"
LIVE_MODE_SELECTION_PATH = ROOT_DIR / "calibration" / "live-mode-selection.json"

CLASS_ORDER = ["H", "D", "A"]
CALIBRATED_MODE_LABELS = {
    "opening_only": "初赔",
    "closing_only": "临场",
    "hybrid": "初赔+临场",
}
CALIBRATED_ENGINE_LABELS = {
    "opening_only": "初赔监督学习模型",
    "closing_only": "临场监督学习模型",
    "hybrid": "初赔+临场监督学习模型",
}
MODE_SELECTION_DECISION_TYPE_LABELS = {
    "single": "单选",
    "double": "双选",
    "abstain": "放弃",
}
MODE_SELECTION_DEFAULT_MIN_SAMPLE = 30

_CALIBRATED_MODELS: dict[str, dict | None] = {}
_LIVE_MODE_SELECTION: dict[tuple[str, str, str], dict] | None = None
_LIVE_MODE_SELECTION_META: dict | None = None

FIXED_COMPANIES = [
    "Bet365",
    "William Hill",
    "Bwin",
    "Interwetten",
    "Pinnacle",
    "BetVictor",
]

OUTCOME_LABELS = {
    "home": "主胜",
    "draw": "平局",
    "away": "客胜",
}
OUTCOME_MAP = {
    "H": "home",
    "D": "draw",
    "A": "away",
}

DECISION_TYPE_LABELS = {
    "single": "单选",
    "double": "双选",
    "abstain": "放弃",
}

PREDICTION_MODE_LABELS = {
    "primary": "按首选单结果输出",
    "keep_order": "保留原始双选顺序",
    "secondary_first": "双选改按次选优先顺序输出",
    "observe_leader": "进入观察池，展示第一倾向",
    "skip": "过滤，不给投注结果",
}

BETTING_DECISION_RULES = [
    {
        "id": "high_strong_home_strong_single",
        "confidence": "高",
        "structure": "高-强主",
        "base_types": ("single",),
        "top_gap_min": 0.50,
        "top_gap_max": None,
        "top_gap_label": "0.50以上",
        "action": "强单",
        "prediction_mode": "primary",
        "note": "高-强主在 0.50 以上命中率最高，可直接作为强单。",
        "sample_note": "样本 12 场，命中率 91.67%。",
    },
    {
        "id": "high_strong_away_strong_single",
        "confidence": "高",
        "structure": "高-强客",
        "base_types": ("single",),
        "top_gap_min": 0.50,
        "top_gap_max": None,
        "top_gap_label": "0.50以上",
        "action": "强单",
        "prediction_mode": "primary",
        "note": "高-强客和高-强主是对称结构，差值足够大时按强单处理。",
        "sample_note": "样本偏少，但已有样本全部命中。",
    },
    {
        "id": "high_strong_home_single",
        "confidence": "高",
        "structure": "高-强主",
        "base_types": ("single",),
        "top_gap_min": 0.20,
        "top_gap_max": 0.50,
        "top_gap_label": "0.20-0.50",
        "action": "普通单选",
        "prediction_mode": "primary",
        "note": "高-强主在 0.20 到 0.50 之间仍可保留单选，但不升格为强单。",
        "sample_note": "样本 39 场，命中率约 51%。",
    },
    {
        "id": "high_strong_away_single",
        "confidence": "高",
        "structure": "高-强客",
        "base_types": ("single",),
        "top_gap_min": 0.20,
        "top_gap_max": 0.50,
        "top_gap_label": "0.20-0.50",
        "action": "普通单选",
        "prediction_mode": "primary",
        "note": "高-强客在中高差值段先保留为普通单选，避免样本不足时过度放大。",
        "sample_note": "样本偏少，先按普通单选执行。",
    },
    {
        "id": "high_side_split_single",
        "confidence": "高",
        "structure": "高-分胜负",
        "base_types": ("single",),
        "top_gap_min": 0.20,
        "top_gap_max": 0.30,
        "top_gap_label": "0.20-0.30",
        "action": "普通单选",
        "prediction_mode": "primary",
        "note": "高-分胜负在 0.20 到 0.30 区间可以保留原始单选。",
        "sample_note": "样本 16 场，命中率 56.25%。",
    },
    {
        "id": "high_defend_draw_single",
        "confidence": "高",
        "structure": "高-防平",
        "base_types": ("single",),
        "top_gap_min": 0.10,
        "top_gap_max": None,
        "top_gap_label": "0.10以上",
        "action": "普通单选",
        "prediction_mode": "primary",
        "note": "高-防平如果模型已经收敛成单选，先保留为普通单选。",
        "sample_note": "样本不大，先保守纳入普通单选。",
    },
    {
        "id": "high_defend_draw_double",
        "confidence": "高",
        "structure": "高-防平",
        "base_types": ("double",),
        "top_gap_min": 0.10,
        "top_gap_max": None,
        "top_gap_label": "0.10以上",
        "action": "标准双选",
        "prediction_mode": "keep_order",
        "note": "高-防平如果模型给出双选，继续保留双选。",
        "sample_note": "样本很少，仅作为保守延续规则。",
    },
    {
        "id": "medium_bias_home_secondary_first",
        "confidence": "中",
        "structure": "中-偏主",
        "base_types": ("double",),
        "top_gap_min": 0.00,
        "top_gap_max": 0.10,
        "top_gap_label": "0-0.10",
        "action": "双选次选优先",
        "prediction_mode": "secondary_first",
        "note": "中-偏主在极低差值时首选偏弱，次选反而更值得优先看。",
        "sample_note": "样本 9 场，次选命中率 55.56%，高于首选 22.22%。",
    },
    {
        "id": "medium_bias_home_standard_double",
        "confidence": "中",
        "structure": "中-偏主",
        "base_types": ("double",),
        "top_gap_min": 0.10,
        "top_gap_max": 0.20,
        "top_gap_label": "0.10-0.20",
        "action": "标准双选",
        "prediction_mode": "keep_order",
        "note": "中-偏主在 0.10 到 0.20 区间继续保留双选，不压成单选。",
        "sample_note": "样本 42 场，覆盖率 73.81%。",
    },
    {
        "id": "medium_bias_home_primary_first",
        "confidence": "中",
        "structure": "中-偏主",
        "base_types": ("double",),
        "top_gap_min": 0.20,
        "top_gap_max": None,
        "top_gap_label": "0.20以上",
        "action": "双选首选优先",
        "prediction_mode": "keep_order",
        "note": "中-偏主在 0.20 以上时首选优势明显，按首选优先双选处理。",
        "sample_note": "样本 9 场，首选命中率 77.78%，覆盖率 100%。",
    },
    {
        "id": "medium_bias_draw_standard_double_low",
        "confidence": "中",
        "structure": "中-偏平",
        "base_types": ("double",),
        "top_gap_min": 0.00,
        "top_gap_max": 0.20,
        "top_gap_label": "0-0.20",
        "action": "标准双选",
        "prediction_mode": "keep_order",
        "note": "中-偏平在低差值区间更适合继续保留双选。",
        "sample_note": "低差值样本覆盖率稳定，但不适合改单关平局。",
    },
    {
        "id": "medium_bias_away_standard_double",
        "confidence": "中",
        "structure": "中-偏客",
        "base_types": ("double",),
        "top_gap_min": 0.10,
        "top_gap_max": 0.20,
        "top_gap_label": "0.10-0.20",
        "action": "标准双选",
        "prediction_mode": "keep_order",
        "note": "中-偏客在 0.10 到 0.20 区间先按谨慎双选处理。",
        "sample_note": "样本 11 场，覆盖率 63.64%。",
    },
    {
        "id": "medium_bias_away_primary_first",
        "confidence": "中",
        "structure": "中-偏客",
        "base_types": ("double",),
        "top_gap_min": 0.20,
        "top_gap_max": None,
        "top_gap_label": "0.20以上",
        "action": "双选首选优先",
        "prediction_mode": "keep_order",
        "note": "中-偏客在 0.20 以上时首选已经更可信，按首选优先双选处理。",
        "sample_note": "0.20-0.30 样本较少，但首选命中率已明显抬升。",
    },
    {
        "id": "cautious_tug_of_war_double",
        "confidence": "谨慎",
        "structure": "谨慎-主客胶着",
        "base_types": ("double",),
        "top_gap_min": 0.00,
        "top_gap_max": 0.10,
        "top_gap_label": "0-0.10",
        "action": "双选次选优先",
        "prediction_mode": "secondary_first",
        "note": "谨慎-主客胶着如果仍给双选，只保留双选且改按次选优先看。",
        "sample_note": "样本 7 场，次选命中率 57.14%，覆盖率 100%。",
    },
    {
        "id": "cautious_tug_of_war_abstain",
        "confidence": "谨慎",
        "structure": "谨慎-主客胶着",
        "base_types": ("abstain",),
        "top_gap_min": 0.00,
        "top_gap_max": None,
        "top_gap_label": "全部",
        "action": "过滤",
        "prediction_mode": "skip",
        "note": "谨慎-主客胶着且模型放弃时，直接过滤，不进入投注池。",
        "sample_note": "对应样本第一倾向不稳定，继续过滤更合适。",
    },
    {
        "id": "cautious_abstain_filter",
        "confidence": "谨慎",
        "structure": "谨慎-不建议单押",
        "base_types": ("abstain",),
        "top_gap_min": 0.00,
        "top_gap_max": 0.40,
        "top_gap_label": "0-0.40",
        "action": "过滤",
        "prediction_mode": "skip",
        "note": "谨慎-不建议单押在 0.40 以下统一过滤。",
        "sample_note": "低于 0.40 时第一倾向稳定性不足。",
    },
    {
        "id": "cautious_abstain_observe",
        "confidence": "谨慎",
        "structure": "谨慎-不建议单押",
        "base_types": ("abstain",),
        "top_gap_min": 0.40,
        "top_gap_max": None,
        "top_gap_label": "0.40以上",
        "action": "观察池",
        "prediction_mode": "observe_leader",
        "note": "谨慎-不建议单押在 0.40 以上只进入观察池，不直接出手。",
        "sample_note": "0.40 以上第一倾向明显增强，但仍属于谨慎层。",
    },
    {
        "id": "high_single_fallback",
        "confidence": "高",
        "structure": None,
        "base_types": ("single",),
        "top_gap_min": None,
        "top_gap_max": None,
        "top_gap_label": "全部",
        "action": "普通单选",
        "prediction_mode": "primary",
        "note": "高信任且已给出单选时，未命中特定格子就按普通单选兜底。",
        "sample_note": "兜底规则。",
    },
    {
        "id": "high_double_fallback",
        "confidence": "高",
        "structure": None,
        "base_types": ("double",),
        "top_gap_min": None,
        "top_gap_max": None,
        "top_gap_label": "全部",
        "action": "标准双选",
        "prediction_mode": "keep_order",
        "note": "高信任但未命中特定格子时，保留原始双选。",
        "sample_note": "兜底规则。",
    },
    {
        "id": "medium_single_fallback",
        "confidence": "中",
        "structure": None,
        "base_types": ("single",),
        "top_gap_min": None,
        "top_gap_max": None,
        "top_gap_label": "全部",
        "action": "普通单选",
        "prediction_mode": "primary",
        "note": "中信任如果模型已经收敛到单选，先按普通单选保留。",
        "sample_note": "兜底规则。",
    },
    {
        "id": "medium_double_fallback",
        "confidence": "中",
        "structure": None,
        "base_types": ("double",),
        "top_gap_min": None,
        "top_gap_max": None,
        "top_gap_label": "全部",
        "action": "标准双选",
        "prediction_mode": "keep_order",
        "note": "中信任未命中特定格子时，保留原始双选。",
        "sample_note": "兜底规则。",
    },
    {
        "id": "cautious_single_fallback",
        "confidence": "谨慎",
        "structure": None,
        "base_types": ("single",),
        "top_gap_min": None,
        "top_gap_max": None,
        "top_gap_label": "全部",
        "action": "观察池",
        "prediction_mode": "observe_leader",
        "note": "谨慎层即使被模型收敛成单选，也先进入观察池。",
        "sample_note": "兜底规则。",
    },
    {
        "id": "cautious_double_fallback",
        "confidence": "谨慎",
        "structure": None,
        "base_types": ("double",),
        "top_gap_min": None,
        "top_gap_max": None,
        "top_gap_label": "全部",
        "action": "标准双选",
        "prediction_mode": "keep_order",
        "note": "谨慎层未命中特定格子时，只保留标准双选。",
        "sample_note": "兜底规则。",
    },
    {
        "id": "cautious_abstain_fallback",
        "confidence": "谨慎",
        "structure": None,
        "base_types": ("abstain",),
        "top_gap_min": None,
        "top_gap_max": None,
        "top_gap_label": "全部",
        "action": "过滤",
        "prediction_mode": "skip",
        "note": "谨慎层只要模型放弃，默认不过滤成投注结果。",
        "sample_note": "兜底规则。",
    },
]

BETTING_DECISION_HISTORY = {
    "high_strong_home_strong_single": {
        "samples": 12,
        "metrics": ({"label": "单选命中率", "value": 0.9167},),
    },
    "high_strong_away_strong_single": {
        "samples": 4,
        "metrics": ({"label": "单选命中率", "value": 1.0},),
    },
    "high_strong_home_single": {
        "samples": 39,
        "metrics": ({"label": "单选命中率", "value": 20 / 39},),
    },
    "high_strong_away_single": {
        "samples": 4,
        "metrics": ({"label": "单选命中率", "value": 1.0},),
    },
    "high_side_split_single": {
        "samples": 16,
        "metrics": ({"label": "单选命中率", "value": 0.5625},),
    },
    "high_defend_draw_single": {
        "samples": 6,
        "metrics": ({"label": "单选命中率", "value": 0.8333},),
    },
    "high_defend_draw_double": {
        "samples": 1,
        "metrics": (
            {"label": "首选命中率", "value": 0.0},
            {"label": "次选命中率", "value": 1.0},
            {"label": "双选覆盖率", "value": 1.0},
        ),
    },
    "medium_bias_home_secondary_first": {
        "samples": 9,
        "metrics": (
            {"label": "首选命中率", "value": 0.2222},
            {"label": "次选命中率", "value": 0.5556},
            {"label": "双选覆盖率", "value": 0.7778},
        ),
    },
    "medium_bias_home_standard_double": {
        "samples": 42,
        "metrics": (
            {"label": "首选命中率", "value": 0.4524},
            {"label": "次选命中率", "value": 0.2857},
            {"label": "双选覆盖率", "value": 0.7381},
        ),
    },
    "medium_bias_home_primary_first": {
        "samples": 9,
        "metrics": (
            {"label": "首选命中率", "value": 0.7778},
            {"label": "次选命中率", "value": 0.2222},
            {"label": "双选覆盖率", "value": 1.0},
        ),
    },
    "medium_bias_draw_standard_double_low": {
        "samples": 45,
        "metrics": (
            {"label": "首选命中率", "value": 22 / 45},
            {"label": "次选命中率", "value": 10 / 45},
            {"label": "双选覆盖率", "value": 32 / 45},
        ),
    },
    "medium_bias_away_standard_double": {
        "samples": 11,
        "metrics": (
            {"label": "首选命中率", "value": 0.3636},
            {"label": "次选命中率", "value": 0.2727},
            {"label": "双选覆盖率", "value": 0.6364},
        ),
    },
    "medium_bias_away_primary_first": {
        "samples": 6,
        "metrics": (
            {"label": "首选命中率", "value": 0.6667},
            {"label": "次选命中率", "value": 0.0},
            {"label": "双选覆盖率", "value": 0.6667},
        ),
    },
    "cautious_tug_of_war_double": {
        "samples": 7,
        "metrics": (
            {"label": "首选命中率", "value": 0.4286},
            {"label": "次选命中率", "value": 0.5714},
            {"label": "双选覆盖率", "value": 1.0},
        ),
    },
    "cautious_tug_of_war_abstain": {
        "samples": 65,
        "metrics": (
            {"label": "第一倾向命中率", "value": 0.4308},
            {"label": "前二覆盖率", "value": 0.6769},
        ),
    },
    "cautious_abstain_filter": {
        "samples": 318,
        "metrics": (
            {"label": "第一倾向命中率", "value": 156 / 318},
            {"label": "前二覆盖率", "value": 254 / 318},
        ),
    },
    "cautious_abstain_observe": {
        "samples": 78,
        "metrics": (
            {"label": "第一倾向命中率", "value": 55 / 78},
            {"label": "前二覆盖率", "value": 72 / 78},
        ),
    },
    "high_single_fallback": {
        "samples": None,
        "metrics": (),
        "note": "无独立历史样本，按兜底规则执行。",
    },
    "high_double_fallback": {
        "samples": None,
        "metrics": (),
        "note": "无独立历史样本，按兜底规则执行。",
    },
    "medium_single_fallback": {
        "samples": None,
        "metrics": (),
        "note": "无独立历史样本，按兜底规则执行。",
    },
    "medium_double_fallback": {
        "samples": None,
        "metrics": (),
        "note": "无独立历史样本，按兜底规则执行。",
    },
    "cautious_single_fallback": {
        "samples": None,
        "metrics": (),
        "note": "无独立历史样本，按兜底规则执行。",
    },
    "cautious_double_fallback": {
        "samples": None,
        "metrics": (),
        "note": "无独立历史样本，按兜底规则执行。",
    },
    "cautious_abstain_fallback": {
        "samples": None,
        "metrics": (),
        "note": "无独立历史样本，按兜底规则执行。",
    },
}

FALLBACK_THRESHOLDS = {
    "drawMinimum": 0.283,
    "drawLeadSlack": 0.014,
    "drawSplitLeadSlack": 0.024,
    "drawHomeAwayGapMax": 0.048,
    "drawDispersionMax": 0.03,
    "strongSingleProbabilityMin": 0.459,
    "strongSingleGapMin": 0.099,
    "strongSingleVoteShareMin": 1.0,
    "strongSingleDrawMax": 0.298,
    "favoriteVoteShareMin": 0.67,
    "sideDrawDoubleMin": 0.281,
    "sideDrawDoubleGapMax": 0.055,
    "splitVoteShareMax": 0.67,
    "homeAwayDoubleGapMax": 0.05,
    "dispersionMin": 0.018,
}


def load_thresholds() -> dict:
    try:
        data = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
        return data.get("selectedThresholds") or FALLBACK_THRESHOLDS
    except Exception:
        return FALLBACK_THRESHOLDS


THRESHOLDS = load_thresholds()


def load_json_file(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def get_calibration_model_data(feature_mode: str) -> dict | None:
    cached = _CALIBRATED_MODELS.get(feature_mode)
    if cached is not None or feature_mode in _CALIBRATED_MODELS:
        return cached

    if feature_mode == "closing_only":
        payload = load_json_file(CLOSING_ONLY_CALIBRATION_PATH)
    elif feature_mode == "opening_only":
        payload = load_json_file(OPENING_ONLY_CALIBRATION_PATH)
    elif feature_mode == "hybrid":
        payload = load_json_file(HYBRID_CALIBRATION_PATH) or load_json_file(CALIBRATION_PATH)
    else:
        payload = None

    if not payload or "supervisedModel" not in payload:
        _CALIBRATED_MODELS[feature_mode] = None
        return None

    _CALIBRATED_MODELS[feature_mode] = payload
    return payload


def load_live_mode_selection() -> tuple[dict[tuple[str, str, str], dict], dict]:
    global _LIVE_MODE_SELECTION, _LIVE_MODE_SELECTION_META

    if _LIVE_MODE_SELECTION is not None and _LIVE_MODE_SELECTION_META is not None:
        return _LIVE_MODE_SELECTION, _LIVE_MODE_SELECTION_META

    payload = load_json_file(LIVE_MODE_SELECTION_PATH) or {}
    rows = payload.get("rows", [])
    selection_index: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        key = (
            row.get("structure", ""),
            row.get("topGapBucket", ""),
            row.get("decisionType", ""),
        )
        if all(key):
            selection_index[key] = row

    _LIVE_MODE_SELECTION = selection_index
    _LIVE_MODE_SELECTION_META = {
        "generatedAt": payload.get("generatedAt"),
        "minSample": payload.get("minSample", MODE_SELECTION_DEFAULT_MIN_SAMPLE),
        "source": payload.get("source"),
        "rows": rows,
    }
    return _LIVE_MODE_SELECTION, _LIVE_MODE_SELECTION_META


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def average(values: list[float]) -> float:
    return sum(values) / len(values)


def standard_deviation(values: list[float]) -> float:
    mean = average(values)
    variance = average([(value - mean) ** 2 for value in values])
    return math.sqrt(variance)


def normalize_probabilities(values: dict[str, float]) -> dict[str, float]:
    total = values["home"] + values["draw"] + values["away"]
    return {
        "home": values["home"] / total,
        "draw": values["draw"] / total,
        "away": values["away"] / total,
    }


def to_probability_row(home_odds: float, draw_odds: float, away_odds: float) -> dict[str, float]:
    return normalize_probabilities(
        {
            "home": 1.0 / home_odds,
            "draw": 1.0 / draw_odds,
            "away": 1.0 / away_odds,
        }
    )


def distance(left: dict[str, float], right: dict[str, float]) -> float:
    return math.sqrt(
        (left["home"] - right["home"]) ** 2
        + (left["draw"] - right["draw"]) ** 2
        + (left["away"] - right["away"]) ** 2
    )


def round_metric(value: float) -> float:
    return round(value, 4)


def softmax(values: list[float]) -> list[float]:
    max_value = max(values)
    exponents = [math.exp(value - max_value) for value in values]
    total = sum(exponents)
    return [value / total for value in exponents]


def build_market_summary(rows: list[dict]) -> dict:
    probability_rows = [to_probability_row(row["home"], row["draw"], row["away"]) for row in rows]
    lowest_votes = {"home": 0, "draw": 0, "away": 0}

    for row in rows:
        ordered = sorted(
            [
                {"key": "home", "odds": row["home"]},
                {"key": "draw", "odds": row["draw"]},
                {"key": "away", "odds": row["away"]},
            ],
            key=lambda item: item["odds"],
        )
        lowest_votes[ordered[0]["key"]] += 1

    mean_prob = {
        "home": average([row["home"] for row in probability_rows]),
        "draw": average([row["draw"] for row in probability_rows]),
        "away": average([row["away"] for row in probability_rows]),
    }
    std_prob = {
        "home": standard_deviation([row["home"] for row in probability_rows]),
        "draw": standard_deviation([row["draw"] for row in probability_rows]),
        "away": standard_deviation([row["away"] for row in probability_rows]),
    }
    range_prob = {
        "home": max(row["home"] for row in probability_rows) - min(row["home"] for row in probability_rows),
        "draw": max(row["draw"] for row in probability_rows) - min(row["draw"] for row in probability_rows),
        "away": max(row["away"] for row in probability_rows) - min(row["away"] for row in probability_rows),
    }

    distances = [distance(row, mean_prob) for row in probability_rows]
    mean_distance = average(distances)
    std_distance = standard_deviation(distances)
    outlier_cutoff = max(0.045, mean_distance + std_distance)
    outlier_share = len([value for value in distances if value > outlier_cutoff]) / len(rows)
    consensus = clamp(1 - mean_distance / 0.09, 0, 1)
    dispersion = average([std_prob["home"], std_prob["draw"], std_prob["away"]])

    ranked = sorted(
        [
            {"key": "home", "value": mean_prob["home"]},
            {"key": "draw", "value": mean_prob["draw"]},
            {"key": "away", "value": mean_prob["away"]},
        ],
        key=lambda item: item["value"],
        reverse=True,
    )
    top_prob = ranked[0]["value"]
    second_prob = ranked[1]["value"]
    top_gap = top_prob - second_prob
    home_away_gap = abs(mean_prob["home"] - mean_prob["away"])
    skew_signed = mean_prob["home"] - mean_prob["away"]
    draw_vs_side = mean_prob["draw"] - max(mean_prob["home"], mean_prob["away"])
    overround_mean = average([1 / row["home"] + 1 / row["draw"] + 1 / row["away"] for row in rows])

    return {
        "probabilityRows": probability_rows,
        "metrics": {
            "meanProb": mean_prob,
            "stdProb": std_prob,
            "rangeProb": range_prob,
            "consensus": consensus,
            "outlierShare": outlier_share,
            "dispersion": dispersion,
            "favoriteVoteShare": max(lowest_votes.values()) / len(rows),
            "homeVoteShare": lowest_votes["home"] / len(rows),
            "drawVoteShare": lowest_votes["draw"] / len(rows),
            "awayVoteShare": lowest_votes["away"] / len(rows),
            "topGap": top_gap,
            "homeAwayGap": home_away_gap,
            "topProb": top_prob,
            "secondProb": second_prob,
            "skewSigned": skew_signed,
            "drawVsSide": draw_vs_side,
            "overroundMean": overround_mean,
        },
    }


def build_phase_feature_vector(summary: dict) -> list[float]:
    metrics = summary["metrics"]
    return [
        *[value for row in summary["probabilityRows"] for value in (row["home"], row["draw"], row["away"])],
        metrics["meanProb"]["home"],
        metrics["meanProb"]["draw"],
        metrics["meanProb"]["away"],
        metrics["stdProb"]["home"],
        metrics["stdProb"]["draw"],
        metrics["stdProb"]["away"],
        metrics["rangeProb"]["home"],
        metrics["rangeProb"]["draw"],
        metrics["rangeProb"]["away"],
        metrics["homeVoteShare"],
        metrics["drawVoteShare"],
        metrics["awayVoteShare"],
        metrics["topProb"],
        metrics["secondProb"],
        metrics["topGap"],
        metrics["homeAwayGap"],
        metrics["skewSigned"],
        metrics["drawVsSide"],
        metrics["consensus"],
        metrics["outlierShare"],
        metrics["dispersion"],
        metrics["overroundMean"],
    ]


def build_polynomial_vector(metrics: dict) -> list[float]:
    return [
        metrics["meanProb"]["home"] * metrics["meanProb"]["draw"],
        metrics["meanProb"]["home"] * metrics["meanProb"]["away"],
        metrics["meanProb"]["draw"] * metrics["meanProb"]["away"],
        metrics["topGap"] * metrics["topGap"],
        metrics["skewSigned"] * metrics["skewSigned"],
        metrics["drawVsSide"] * metrics["drawVsSide"],
    ]


def build_calibrated_feature_vector(
    opening_rows: list[dict] | None,
    closing_rows: list[dict] | None,
    feature_mode: str,
) -> tuple[list[float], dict | None, dict | None]:
    opening_summary = build_market_summary(opening_rows) if opening_rows else None
    closing_summary = build_market_summary(closing_rows) if closing_rows else None

    if feature_mode == "opening_only":
        if opening_summary is None:
            raise ValueError("初赔模式缺少 opening rows。")
        return (
            build_phase_feature_vector(opening_summary)
            + build_polynomial_vector(opening_summary["metrics"]),
            opening_summary,
            closing_summary,
        )

    if feature_mode == "closing_only":
        if closing_summary is None:
            raise ValueError("临场模式缺少 closing rows。")
        return (
            build_phase_feature_vector(closing_summary)
            + build_polynomial_vector(closing_summary["metrics"]),
            opening_summary,
            closing_summary,
        )

    if feature_mode == "hybrid":
        if opening_summary is None or closing_summary is None:
            raise ValueError("初赔+临场模式需要同时提供 opening rows 和 closing rows。")

        delta_mean = {
            "home": closing_summary["metrics"]["meanProb"]["home"] - opening_summary["metrics"]["meanProb"]["home"],
            "draw": closing_summary["metrics"]["meanProb"]["draw"] - opening_summary["metrics"]["meanProb"]["draw"],
            "away": closing_summary["metrics"]["meanProb"]["away"] - opening_summary["metrics"]["meanProb"]["away"],
        }
        delta_abs_mean = {
            "home": average(
                [
                    abs(closing_summary["probabilityRows"][index]["home"] - row["home"])
                    for index, row in enumerate(opening_summary["probabilityRows"])
                ]
            ),
            "draw": average(
                [
                    abs(closing_summary["probabilityRows"][index]["draw"] - row["draw"])
                    for index, row in enumerate(opening_summary["probabilityRows"])
                ]
            ),
            "away": average(
                [
                    abs(closing_summary["probabilityRows"][index]["away"] - row["away"])
                    for index, row in enumerate(opening_summary["probabilityRows"])
                ]
            ),
        }
        favorite_flip_share = sum(
            1
            for index, row in enumerate(opening_rows)
            if sorted(
                [
                    ("home", row["home"]),
                    ("draw", row["draw"]),
                    ("away", row["away"]),
                ],
                key=lambda item: item[1],
            )[0][0]
            != sorted(
                [
                    ("home", closing_rows[index]["home"]),
                    ("draw", closing_rows[index]["draw"]),
                    ("away", closing_rows[index]["away"]),
                ],
                key=lambda item: item[1],
            )[0][0]
        ) / len(opening_rows)

        vector = (
            build_phase_feature_vector(opening_summary)
            + build_phase_feature_vector(closing_summary)
            + [
                delta_mean["home"],
                delta_mean["draw"],
                delta_mean["away"],
                delta_abs_mean["home"],
                delta_abs_mean["draw"],
                delta_abs_mean["away"],
                favorite_flip_share,
                closing_summary["metrics"]["topGap"] - opening_summary["metrics"]["topGap"],
                closing_summary["metrics"]["skewSigned"] - opening_summary["metrics"]["skewSigned"],
                closing_summary["metrics"]["drawVsSide"] - opening_summary["metrics"]["drawVsSide"],
                closing_summary["metrics"]["consensus"] - opening_summary["metrics"]["consensus"],
                closing_summary["metrics"]["overroundMean"] - opening_summary["metrics"]["overroundMean"],
            ]
            + build_polynomial_vector(opening_summary["metrics"])
        )
        return vector, opening_summary, closing_summary

    raise ValueError(f"不支持的 feature_mode: {feature_mode}")


def confidence_label(consensus: float, top_gap: float) -> str:
    if consensus >= 0.79 and top_gap >= 0.175:
        return "高"
    if consensus >= 0.74 and top_gap >= 0.015:
        return "中"
    return "谨慎"


def build_rule_confidence_profile(
    base_confidence: str,
    ranked: list[dict[str, float]],
    final_prob: dict[str, float],
    top_gap: float,
) -> dict[str, str]:
    leader_key = ranked[0]["key"]
    second_key = ranked[1]["key"]
    draw_prob = final_prob["draw"]

    if base_confidence == "高":
        if second_key == "draw":
            if leader_key == "home" and draw_prob < 0.24 and top_gap >= 0.25:
                return {
                    "label": "高-强主",
                    "note": "主胜排第一、平局排第二，而且平局概率较低、前二差值已经明显拉开，这类是高档里最强的主胜结构。",
                }
            if leader_key == "away" and draw_prob < 0.24 and top_gap >= 0.25:
                return {
                    "label": "高-强客",
                    "note": "客胜排第一、平局排第二，而且平局概率较低、前二差值已经明显拉开，这类是高档里最强的客胜结构。",
                }
            if leader_key == "home" and draw_prob < 0.27 and top_gap >= 0.2:
                return {
                    "label": "高-强主",
                    "note": "主胜排第一、平局排第二，且主和平之间已经有足够差距，当前更接近高档强主结构。",
                }
            if leader_key == "away" and draw_prob < 0.27 and top_gap >= 0.2:
                return {
                    "label": "高-强客",
                    "note": "客胜排第一、平局排第二，且客和平之间已经有足够差距，当前更接近高档强客结构。",
                }

        if draw_prob >= 0.281:
            return {
                "label": "高-防平",
                "note": "当前仍处在高档，但平局概率已经被明显抬高，更适合把它理解成高档防平结构，优先考虑 胜/平 或 平/负。",
            }

        return {
            "label": "高-分胜负",
            "note": "当前仍处在高档，但平局相对偏弱、主客两端仍有拉扯，这类更适合按分胜负结构理解，优先考虑 胜/负。",
        }

    if base_confidence == "中":
        if second_key == "draw":
            if top_gap < 0.1 or draw_prob >= 0.3:
                return {
                    "label": "中-偏平",
                    "note": "平局排第二且和第一名接近，或平局概率已明显抬高，优先按平局候选理解。",
                }
            return {
                "label": "中-偏主" if leader_key == "home" else "中-偏客",
                "note": "平局虽然排第二，但第一名仍保持领先，当前更适合按单边方向加防平来理解。",
            }

        if leader_key == "home":
            if top_gap >= 0.1:
                return {
                    "label": "中-偏主",
                    "note": "主胜排第一且前二差值已有一定拉开，当前更偏向主队。",
                }
            if draw_prob >= 0.28:
                return {
                    "label": "中-偏平",
                    "note": "虽然主胜排第一，但差值不大且平局概率不低，建议把平局作为更强候选。",
                }
            return {
                "label": "中-偏主",
                "note": "主胜排第一，但主客仍有拉扯，当前只是偏主而不是强主。",
            }

        if top_gap >= 0.1:
            return {
                "label": "中-偏客",
                "note": "客胜排第一且前二差值已有一定拉开，当前更偏向客队。",
            }
        if draw_prob >= 0.27:
            return {
                "label": "中-偏平",
                "note": "虽然客胜排第一，但差值不大且平局概率偏高，当前更适合优先防平。",
            }
        return {
            "label": "中-偏客",
            "note": "客胜排第一，但领先优势不算大，当前只是偏客而不是强客。",
        }

    if top_gap < 0.05 and second_key != "draw":
        return {
            "label": "谨慎-主客胶着",
            "note": "第一和第二概率几乎贴在一起，而且是主客直接对冲，这类更像主客胶着盘。",
        }

    return {
        "label": "谨慎-不建议单押",
        "note": "当前结构缺乏足够清晰的单边信号，更适合放弃单押或改看双结果。",
    }


def build_cold_upset_profile(
    confidence_profile: dict[str, str],
    leader_key: str,
    second_key: str,
    final_prob: dict[str, float],
    metrics: dict[str, float],
) -> dict[str, str | bool | None]:
    top_gap = metrics["topGap"]
    consensus = metrics["consensus"]
    home_away_gap = metrics["homeAwayGap"]
    favorite_vote_share = metrics["favoriteVoteShare"]
    draw_prob = final_prob["draw"]
    full_vote = favorite_vote_share >= 0.999
    strong_but_not_full_vote = favorite_vote_share >= 0.83 and favorite_vote_share < 0.999
    split_vote = favorite_vote_share < 0.67

    draw_cold = (
        confidence_profile["label"] == "中-偏平"
        and second_key == "draw"
        and draw_prob >= 0.30
        and full_vote
        and (
            (
                leader_key == "home"
                and 0.10 <= top_gap <= 0.15
                and 0.75 <= consensus < 0.85
                and 0.10 <= home_away_gap <= 0.18
            )
            or (
                leader_key == "away"
                and 0.10 <= top_gap <= 0.15
                and consensus >= 0.85
                and 0.10 <= home_away_gap <= 0.18
            )
            or (
                leader_key == "away"
                and 0.05 <= top_gap < 0.10
                and consensus >= 0.85
                and 0.10 <= home_away_gap <= 0.18
            )
            or (
                leader_key == "home"
                and 0.05 <= top_gap < 0.10
                and consensus >= 0.85
                and 0.05 <= home_away_gap < 0.10
            )
        )
    )
    if draw_cold:
        return {
            "active": True,
            "label": "冷门-平局",
            "predictedKey": "draw",
            "note": "热门方向虽然还在前面，但平局始终贴在第二位且结构足够紧，这类在历史样本里更容易直接打出平局冷门。",
        }

    side_cold = (
        (
            confidence_profile["label"] == "谨慎-主客胶着"
            and leader_key == "away"
            and second_key == "home"
            and top_gap < 0.05
            and 0.27 <= draw_prob < 0.30
            and consensus >= 0.85
            and home_away_gap < 0.05
            and split_vote
        )
        or (
            confidence_profile["label"] == "谨慎-主客胶着"
            and leader_key == "home"
            and second_key == "away"
            and top_gap < 0.05
            and draw_prob >= 0.30
            and consensus >= 0.85
            and home_away_gap < 0.05
            and strong_but_not_full_vote
        )
        or (
            confidence_profile["label"] == "谨慎-主客胶着"
            and leader_key == "home"
            and second_key == "away"
            and top_gap < 0.05
            and 0.27 <= draw_prob < 0.30
            and consensus >= 0.85
            and home_away_gap < 0.05
            and strong_but_not_full_vote
        )
        or (
            confidence_profile["label"] == "中-偏平"
            and leader_key == "away"
            and second_key == "home"
            and 0.05 <= top_gap < 0.10
            and draw_prob >= 0.30
            and consensus >= 0.85
            and 0.05 <= home_away_gap < 0.10
            and full_vote
        )
        or (
            confidence_profile["label"] == "中-偏主"
            and leader_key == "home"
            and second_key == "away"
            and top_gap < 0.05
            and 0.24 <= draw_prob < 0.27
            and consensus >= 0.85
            and home_away_gap < 0.05
            and full_vote
        )
    )
    if side_cold:
        return {
            "active": True,
            "label": f"冷门-{OUTCOME_LABELS[second_key]}",
            "predictedKey": second_key,
            "note": "主客两端贴得过近，热门方向并没有看起来那么稳，这类在历史样本里更容易直接打出反向赛果冷门。",
        }

    high_odds_draw_cold = (
        (
            confidence_profile["label"] == "中-偏客"
            and leader_key == "away"
            and favorite_vote_share >= 0.999
            and consensus >= 0.85
            and 0.24 <= draw_prob < 0.30
            and top_gap < 0.10
            and home_away_gap < 0.10
        )
        or (
            confidence_profile["label"] == "高-分胜负"
            and second_key == "draw"
            and favorite_vote_share >= 0.999
            and consensus >= 0.85
            and 0.27 <= draw_prob < 0.30
            and 0.15 <= top_gap < 0.20
            and home_away_gap >= 0.18
        )
    )
    if high_odds_draw_cold:
        return {
            "active": True,
            "label": "高赔冷门-平局",
            "predictedKey": "draw",
            "note": "这类结构更偏向 3.20 以上的高赔率平局冷门，热门方向虽然还领先，但平局在历史样本里更容易以高回报方式打出。",
        }

    return {
        "active": False,
        "label": "",
        "predictedKey": None,
        "note": "",
    }


def build_rule_explanation(
    final_prob: dict[str, float],
    metrics: dict[str, float],
    decision: dict[str, str | None],
    cold_profile: dict[str, str | bool | None],
) -> str:
    parts: list[str] = []
    lead_outcome = OUTCOME_LABELS[decision["primaryKey"]]
    second_outcome = (
        OUTCOME_LABELS[decision["secondaryKey"]] if decision["secondaryKey"] else ""
    )

    if metrics["consensus"] >= 0.75:
        parts.append("6 家公司的初始赔率方向较一致")
    elif metrics["consensus"] >= 0.6:
        parts.append("市场存在温和共识")
    else:
        parts.append("公司之间分歧较明显")

    if metrics["outlierCount"] > 0:
        parts.append("已对偏离市场的公司做轻度降权")

    if final_prob["draw"] >= 0.28:
        parts.append("平局概率没有被明显拉开")

    if metrics["favoriteVoteShare"] < THRESHOLDS["favoriteVoteShareMin"]:
        parts.append("各家公司最低赔方向并不完全一致")

    if decision["type"] == "abstain":
        return f"{'，'.join(parts)}，当前更适合把这场视为低确定性场次，主动放弃单押。"

    if decision["type"] == "cold-single" and cold_profile.get("active"):
        return f"{'，'.join(parts)}，{cold_profile['note']}，因此触发保守冷门层，直接改判为{OUTCOME_LABELS[cold_profile['predictedKey']]}。"

    if decision["type"] == "draw-single":
        return f"{'，'.join(parts)}，同时主客两端接近，因此把平局提升为单结果。"

    if decision["type"] == "double":
        return f"{'，'.join(parts)}，因此将结果收敛为 {lead_outcome}/{second_outcome} 双结果。"

    return f"{'，'.join(parts)}，最终偏向 {lead_outcome}。"


def normalize_decision_type(decision_type: str) -> str:
    if decision_type == "double":
        return "double"
    if decision_type == "abstain":
        return "abstain"
    return "single"


def top_gap_in_rule_range(
    top_gap: float,
    top_gap_min: float | None,
    top_gap_max: float | None,
) -> bool:
    if top_gap_min is not None and top_gap < top_gap_min:
        return False
    if top_gap_max is not None and top_gap >= top_gap_max:
        return False
    return True


def format_double_prediction(primary_key: str | None, secondary_key: str | None) -> str:
    if primary_key is None:
        return ""
    if secondary_key is None:
        return OUTCOME_LABELS[primary_key]
    return f"{OUTCOME_LABELS[primary_key]}/{OUTCOME_LABELS[secondary_key]}"


def format_percentage(value: float) -> str:
    return f"{value * 100:.2f}%"


def get_rule_history(rule_id: str) -> dict:
    return BETTING_DECISION_HISTORY.get(
        rule_id,
        {
            "samples": None,
            "metrics": (),
            "note": "无独立历史样本。",
        },
    )


def format_history_summary(history: dict) -> str:
    samples = history.get("samples")
    metrics = history.get("metrics", ())
    note = history.get("note", "")

    parts: list[str] = []
    if samples is not None:
        parts.append(f"样本{samples}场")
    for metric in metrics:
        parts.append(f"{metric['label']}{format_percentage(metric['value'])}")
    if note:
        parts.append(note)
    return "｜".join(parts) if parts else "无独立历史样本"


def format_prediction_from_mode(
    prediction_mode: str,
    decision: dict[str, str | None],
    ranked: list[dict[str, float]],
) -> str:
    primary_key = decision["primaryKey"]
    secondary_key = decision["secondaryKey"]

    if prediction_mode == "primary":
        return OUTCOME_LABELS[primary_key]
    if prediction_mode == "keep_order":
        return format_double_prediction(primary_key, secondary_key)
    if prediction_mode == "secondary_first":
        if secondary_key is None:
            return OUTCOME_LABELS[primary_key]
        return format_double_prediction(secondary_key, primary_key)
    if prediction_mode == "observe_leader":
        return f"观察：{OUTCOME_LABELS[ranked[0]['key']]}"
    if prediction_mode == "skip":
        return "不投注"
    raise ValueError(f"未知的 prediction_mode: {prediction_mode}")


def build_decision_basis(
    structure_label: str,
    decision_type: str,
    top_gap_label: str,
) -> str:
    return f"{structure_label}｜{DECISION_TYPE_LABELS[decision_type]}｜前二差值{top_gap_label}"


def resolve_betting_decision(
    base_confidence: str,
    confidence_profile: dict[str, str],
    decision: dict[str, str | None],
    ranked: list[dict[str, float]],
    metrics: dict[str, float],
) -> dict[str, str]:
    structure_label = confidence_profile["label"]
    decision_type = normalize_decision_type(decision["type"])
    top_gap = metrics["topGap"]

    for rule in BETTING_DECISION_RULES:
        if rule["confidence"] != base_confidence:
            continue
        if rule["structure"] is not None and rule["structure"] != structure_label:
            continue
        if decision_type not in rule["base_types"]:
            continue
        if not top_gap_in_rule_range(top_gap, rule["top_gap_min"], rule["top_gap_max"]):
            continue
        history = get_rule_history(rule["id"])

        return {
            "ruleId": rule["id"],
            "action": rule["action"],
            "finalPrediction": format_prediction_from_mode(
                rule["prediction_mode"],
                decision,
                ranked,
            ),
            "decisionBasis": build_decision_basis(
                structure_label,
                decision_type,
                rule["top_gap_label"],
            ),
            "predictionMode": rule["prediction_mode"],
            "ruleNote": rule["note"],
            "sampleNote": rule["sample_note"],
            "historySampleSize": (
                str(history["samples"]) if history.get("samples") is not None else "无独立样本"
            ),
            "historyAccuracySummary": format_history_summary(history),
        }

    return {
        "ruleId": "unmatched",
        "action": "过滤",
        "finalPrediction": "不投注",
        "decisionBasis": build_decision_basis(structure_label, decision_type, "全部"),
        "predictionMode": "skip",
        "ruleNote": "未命中显式规则，按过滤处理。",
        "sampleNote": "兜底规则。",
        "historySampleSize": "无独立样本",
        "historyAccuracySummary": "无独立历史样本，按过滤处理。",
    }


def get_betting_decision_table() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rule in BETTING_DECISION_RULES:
        structure_label = rule["structure"] or "全部（兜底）"
        base_types = "、".join(DECISION_TYPE_LABELS[item] for item in rule["base_types"])
        history = get_rule_history(rule["id"])
        history_metrics = list(history.get("metrics", ()))
        rows.append(
            {
                "信任等级": rule["confidence"],
                "结构标签": structure_label,
                "原始类型": base_types,
                "前二差值范围": rule["top_gap_label"],
                "最终决策动作": rule["action"],
                "最终预测结果规则": PREDICTION_MODE_LABELS[rule["prediction_mode"]],
                "历史样本数": (
                    str(history["samples"]) if history.get("samples") is not None else "无独立样本"
                ),
                "历史准确率1": (
                    f"{history_metrics[0]['label']}{format_percentage(history_metrics[0]['value'])}"
                    if len(history_metrics) >= 1
                    else ""
                ),
                "历史准确率2": (
                    f"{history_metrics[1]['label']}{format_percentage(history_metrics[1]['value'])}"
                    if len(history_metrics) >= 2
                    else ""
                ),
                "历史准确率3": (
                    f"{history_metrics[2]['label']}{format_percentage(history_metrics[2]['value'])}"
                    if len(history_metrics) >= 3
                    else ""
                ),
                "规则说明": rule["note"],
                "样本说明": format_history_summary(history),
            }
        )
    return rows


def validate_rows(rows: list[dict]) -> list[dict]:
    if len(rows) != len(FIXED_COMPANIES):
        raise ValueError(f"必须提供 {len(FIXED_COMPANIES)} 家公司的初始赔率。")

    normalized: list[dict] = []
    for index, row in enumerate(rows):
        item = {
            "company": FIXED_COMPANIES[index],
            "home": float(row["home"]),
            "draw": float(row["draw"]),
            "away": float(row["away"]),
        }
        for key in ("home", "draw", "away"):
            value = item[key]
            if not math.isfinite(value) or value <= 1.01 or value >= 100:
                raise ValueError(f"{FIXED_COMPANIES[index]} 的{OUTCOME_LABELS[key]}赔率无效。")
        normalized.append(item)
    return normalized


def compute_rule_prediction(rows: list[dict]) -> dict:
    clean_rows = validate_rows(rows)
    favorite_votes = {"home": 0, "draw": 0, "away": 0}

    for row in clean_rows:
        ordered = sorted(
            [
                {"key": "home", "odds": row["home"]},
                {"key": "draw", "odds": row["draw"]},
                {"key": "away", "odds": row["away"]},
            ],
            key=lambda item: item["odds"],
        )
        favorite_votes[ordered[0]["key"]] += 1

    probability_rows = [
        to_probability_row(row["home"], row["draw"], row["away"]) for row in clean_rows
    ]

    mean_prob = {
        "home": average([row["home"] for row in probability_rows]),
        "draw": average([row["draw"] for row in probability_rows]),
        "away": average([row["away"] for row in probability_rows]),
    }

    distances = [distance(row, mean_prob) for row in probability_rows]
    mean_distance = average(distances)
    std_distance = standard_deviation(distances)
    outlier_cutoff = max(0.045, mean_distance + std_distance)

    weights: list[float] = []
    for value in distances:
        if value <= outlier_cutoff:
            weights.append(1.0)
        else:
            weights.append(clamp(1 - (value - outlier_cutoff) * 8, 0.52, 0.92))

    weight_sum = sum(weights)
    final_prob = normalize_probabilities(
        {
            "home": sum(row["home"] * weights[index] for index, row in enumerate(probability_rows))
            / weight_sum,
            "draw": sum(row["draw"] * weights[index] for index, row in enumerate(probability_rows))
            / weight_sum,
            "away": sum(row["away"] * weights[index] for index, row in enumerate(probability_rows))
            / weight_sum,
        }
    )

    dispersion = average(
        [
            standard_deviation([row["home"] for row in probability_rows]),
            standard_deviation([row["draw"] for row in probability_rows]),
            standard_deviation([row["away"] for row in probability_rows]),
        ]
    )

    consensus = clamp(1 - mean_distance / 0.09, 0, 1)
    outlier_count = len([value for value in distances if value > outlier_cutoff])
    home_away_gap = abs(final_prob["home"] - final_prob["away"])
    draw_pressure = final_prob["draw"] - average([final_prob["home"], final_prob["away"]])
    strongest_side = max(final_prob["home"], final_prob["away"])
    draw_gap_to_leader = strongest_side - final_prob["draw"]

    ranked = sorted(
        [
            {"key": "home", "value": final_prob["home"]},
            {"key": "draw", "value": final_prob["draw"]},
            {"key": "away", "value": final_prob["away"]},
        ],
        key=lambda item: item["value"],
        reverse=True,
    )

    top_gap = ranked[0]["value"] - ranked[1]["value"]
    favorite_vote_share = favorite_votes[ranked[0]["key"]] / len(clean_rows)
    home_vote_share = favorite_votes["home"] / len(clean_rows)
    draw_vote_share = favorite_votes["draw"] / len(clean_rows)
    away_vote_share = favorite_votes["away"] / len(clean_rows)
    side_leader_key = "home" if final_prob["home"] >= final_prob["away"] else "away"
    side_leader_prob = final_prob[side_leader_key]
    split_sides = max(home_vote_share, away_vote_share) <= THRESHOLDS["splitVoteShareMax"]
    leader_key = ranked[0]["key"]
    second_key = ranked[1]["key"]

    draw_single = (
        final_prob["draw"] >= THRESHOLDS["drawMinimum"]
        and home_away_gap <= THRESHOLDS["drawHomeAwayGapMax"]
        and dispersion <= THRESHOLDS["drawDispersionMax"]
        and (
            draw_gap_to_leader <= THRESHOLDS["drawLeadSlack"]
            or (split_sides and draw_gap_to_leader <= THRESHOLDS["drawSplitLeadSlack"])
        )
    )

    strong_non_draw_single = (
        ranked[0]["key"] != "draw"
        and ranked[0]["value"] >= THRESHOLDS["strongSingleProbabilityMin"]
        and top_gap >= THRESHOLDS["strongSingleGapMin"]
        and favorite_vote_share >= THRESHOLDS["strongSingleVoteShareMin"]
        and final_prob["draw"] <= THRESHOLDS["strongSingleDrawMax"]
    )

    side_draw_double = (
        not draw_single
        and not strong_non_draw_single
        and side_leader_key != "draw"
        and final_prob["draw"] >= THRESHOLDS["sideDrawDoubleMin"]
        and (side_leader_prob - final_prob["draw"]) <= THRESHOLDS["sideDrawDoubleGapMax"]
    )

    home_away_double = (
        not draw_single
        and not strong_non_draw_single
        and not side_draw_double
        and split_sides
        and home_away_gap <= THRESHOLDS["homeAwayDoubleGapMax"]
        and final_prob["draw"] < THRESHOLDS["drawMinimum"]
    )

    base_confidence = confidence_label(consensus, top_gap)
    confidence_profile = build_rule_confidence_profile(
        base_confidence, ranked, final_prob, top_gap
    )
    cold_profile = build_cold_upset_profile(
        confidence_profile,
        leader_key,
        second_key,
        final_prob,
        {
            "topGap": top_gap,
            "consensus": consensus,
            "homeAwayGap": home_away_gap,
            "favoriteVoteShare": favorite_vote_share,
        },
    )

    if draw_single:
        decision = {"type": "draw-single", "primaryKey": "draw", "secondaryKey": None}
    elif base_confidence == "高" and strong_non_draw_single:
        decision = {"type": "single", "primaryKey": ranked[0]["key"], "secondaryKey": None}
    elif base_confidence == "高":
        if side_draw_double:
            decision = {"type": "double", "primaryKey": side_leader_key, "secondaryKey": "draw"}
        elif home_away_double:
            decision = {"type": "double", "primaryKey": "home", "secondaryKey": "away"}
        elif leader_key == "draw" or final_prob["draw"] >= THRESHOLDS["drawMinimum"]:
            decision = {"type": "draw-single", "primaryKey": "draw", "secondaryKey": None}
        else:
            secondary_key = ranked[2]["key"] if second_key == leader_key else second_key
            decision = {"type": "double", "primaryKey": leader_key, "secondaryKey": secondary_key}
    elif base_confidence == "中":
        if confidence_profile["label"] == "中-偏平":
            preferred_side = (
                "home" if final_prob["home"] >= final_prob["away"] else "away"
            ) if leader_key == "draw" else leader_key
            decision = {"type": "double", "primaryKey": preferred_side, "secondaryKey": "draw"}
        elif confidence_profile["label"] == "中-偏主":
            decision = {
                "type": "double",
                "primaryKey": "home",
                "secondaryKey": "draw" if second_key == "draw" or final_prob["draw"] >= 0.27 else "away",
            }
        else:
            decision = {
                "type": "double",
                "primaryKey": "away",
                "secondaryKey": "draw" if second_key == "draw" or final_prob["draw"] >= 0.27 else "home",
            }
    elif confidence_profile["label"] == "谨慎-主客胶着" and top_gap >= 0.04:
        decision = {"type": "double", "primaryKey": "home", "secondaryKey": "away"}
    else:
        decision = {"type": "abstain", "primaryKey": leader_key, "secondaryKey": None}

    if cold_profile["active"] and decision["type"] not in {"single", "draw-single"}:
        decision = {
            "type": "cold-single",
            "primaryKey": cold_profile["predictedKey"],
            "secondaryKey": None,
        }

    recommendation = (
        "不建议单押"
        if decision["type"] == "abstain"
        else (
            f"{OUTCOME_LABELS[decision['primaryKey']]}/{OUTCOME_LABELS[decision['secondaryKey']]}"
            if decision["type"] == "double"
            else OUTCOME_LABELS[decision["primaryKey"]]
        )
    )
    betting_decision = resolve_betting_decision(
        base_confidence,
        confidence_profile,
        decision,
        ranked,
        {
            "topGap": top_gap,
        },
    )

    return {
        "companies": FIXED_COMPANIES,
        "recommendation": recommendation,
        "bettingDecision": betting_decision,
        "allowDouble": decision["type"] == "double",
        "abstained": decision["type"] == "abstain",
        "drawSingle": decision["type"] == "draw-single",
        "decision": decision,
        "confidence": base_confidence,
        "confidenceProfile": confidence_profile,
        "coldProfile": cold_profile,
        "finalProb": final_prob,
        "metrics": {
            "consensus": consensus,
            "dispersion": dispersion,
            "outlierCount": outlier_count,
            "homeAwayGap": home_away_gap,
            "drawPressure": draw_pressure,
            "drawGapToLeader": draw_gap_to_leader,
            "homeVoteShare": home_vote_share,
            "drawVoteShare": draw_vote_share,
            "awayVoteShare": away_vote_share,
            "favoriteVoteShare": favorite_vote_share,
            "topGap": top_gap,
            "strongNonDrawSingle": strong_non_draw_single,
        },
        "engine": "rule",
        "engineLabel": "默认规则模型",
        "explanation": build_rule_explanation(
            final_prob,
            {
                "consensus": consensus,
                "outlierCount": outlier_count,
                "favoriteVoteShare": favorite_vote_share,
            },
            decision,
            cold_profile,
        ),
    }


def bucket_live_mode_top_gap(top_gap: float) -> str:
    if top_gap < 0.10:
        return "0-0.10"
    if top_gap < 0.20:
        return "0.10-0.20"
    if top_gap < 0.30:
        return "0.20-0.30"
    if top_gap < 0.40:
        return "0.30-0.40"
    if top_gap < 0.50:
        return "0.40-0.50"
    return "0.50以上"


def build_mode_selection_key(rule_prediction: dict) -> dict[str, str]:
    decision_type = normalize_decision_type(rule_prediction["decision"]["type"])
    return {
        "structure": rule_prediction["confidenceProfile"]["label"],
        "topGapBucket": bucket_live_mode_top_gap(rule_prediction["metrics"]["topGap"]),
        "decisionType": decision_type,
    }


def format_mode_selection_key_parts(key_parts: dict[str, str]) -> str:
    return (
        f"{key_parts['structure']}｜"
        f"{MODE_SELECTION_DECISION_TYPE_LABELS[key_parts['decisionType']]}｜"
        f"前二差值{key_parts['topGapBucket']}"
    )


def format_calibrated_prediction(decision: dict[str, str | None]) -> str:
    primary = decision["primary"]
    secondary = decision["secondary"]
    if decision["type"] == "double" and secondary:
        return f"{OUTCOME_LABELS[primary]}/{OUTCOME_LABELS[secondary]}"
    return OUTCOME_LABELS[primary]


def build_calibrated_history_summary(
    selection_row: dict,
    selected_mode: str,
    decision_type: str,
) -> str:
    metrics_key = {
        "opening_only": "openingOnly",
        "closing_only": "closingOnly",
        "hybrid": "hybrid",
    }.get(selected_mode, "closingOnly")
    metrics = selection_row[metrics_key]
    samples = selection_row["matches"]
    parts = [f"样本{samples}场"]
    if decision_type == "single":
        parts.append(f"单选准确率{format_percentage(metrics['singlePredictionAccuracy'])}")
        parts.append(f"Top1{format_percentage(metrics['top1Accuracy'])}")
        parts.append(f"覆盖率{format_percentage(metrics['inclusiveHitRate'])}")
    else:
        parts.append(f"覆盖率{format_percentage(metrics['inclusiveHitRate'])}")
        parts.append(f"Top1{format_percentage(metrics['top1Accuracy'])}")
        parts.append(f"单选准确率{format_percentage(metrics['singlePredictionAccuracy'])}")
    return "｜".join(parts)


def predict_calibrated_probabilities(vector: list[float], supervised_model: dict) -> dict[str, float]:
    means = supervised_model["normalization"]["means"]
    scales = supervised_model["normalization"]["scales"]
    standardized = [
        (value - means[index]) / scales[index] for index, value in enumerate(vector)
    ]
    logits: list[float] = []
    for weights, bias in zip(supervised_model["weights"], supervised_model["biases"]):
        logits.append(sum(weight * standardized[index] for index, weight in enumerate(weights)) + bias)
    probabilities = softmax(logits)
    return {
        label: probability
        for label, probability in zip(supervised_model["classOrder"], probabilities)
    }


def apply_calibrated_decision(probabilities: dict[str, float], decision_policy: dict) -> dict[str, str | None]:
    ranked = sorted(
        probabilities.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    if ranked[0][1] - ranked[1][1] <= decision_policy["doubleGapThreshold"]:
        return {
            "type": "double",
            "primary": OUTCOME_MAP[ranked[0][0]],
            "secondary": OUTCOME_MAP[ranked[1][0]],
        }
    return {
        "type": "single",
        "primary": OUTCOME_MAP[ranked[0][0]],
        "secondary": None,
    }


def compute_calibrated_prediction(
    opening_rows: list[dict] | None,
    closing_rows: list[dict] | None,
    feature_mode: str,
) -> dict:
    payload = get_calibration_model_data(feature_mode)
    if payload is None:
        raise ValueError(f"{feature_mode} 校准模型不可用。")

    supervised_model = payload["supervisedModel"]
    vector, opening_summary, closing_summary = build_calibrated_feature_vector(
        opening_rows,
        closing_rows,
        feature_mode,
    )
    probabilities = predict_calibrated_probabilities(vector, supervised_model)
    decision = apply_calibrated_decision(probabilities, supervised_model["decisionPolicy"])
    ranked = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
    top_gap = ranked[0][1] - ranked[1][1]

    return {
        "featureMode": feature_mode,
        "modeLabel": CALIBRATED_MODE_LABELS[feature_mode],
        "engine": "supervised",
        "engineLabel": CALIBRATED_ENGINE_LABELS[feature_mode],
        "decision": decision,
        "prediction": format_calibrated_prediction(decision),
        "probabilities": probabilities,
        "topProbability": ranked[0][1],
        "topGap": top_gap,
        "openingMetrics": opening_summary["metrics"] if opening_summary else None,
        "closingMetrics": closing_summary["metrics"] if closing_summary else None,
        "decisionPolicy": supervised_model["decisionPolicy"],
        "highConfidencePolicy": supervised_model.get("highConfidencePolicy"),
    }


def resolve_live_mode_selection(rule_prediction: dict) -> tuple[dict | None, dict[str, str], dict]:
    selection_index, meta = load_live_mode_selection()
    key_parts = build_mode_selection_key(rule_prediction)
    entry = selection_index.get(
        (key_parts["structure"], key_parts["topGapBucket"], key_parts["decisionType"])
    )
    return entry, key_parts, meta


def get_live_mode_selection_table() -> list[dict[str, str]]:
    _, meta = load_live_mode_selection()
    rows = []
    for row in meta["rows"]:
        rows.append(
            {
                "结构标签": row["structure"],
                "前二差值范围": row["topGapBucket"],
                "基础决策类型": MODE_SELECTION_DECISION_TYPE_LABELS.get(row["decisionType"], row["decisionType"]),
                "推荐模式": CALIBRATED_MODE_LABELS.get(row["recommendedMode"], row["recommendedMode"]),
                "历史样本数": str(row["matches"]),
                "初赔Top1": format_percentage(row["openingOnly"]["top1Accuracy"]),
                "初赔单选准确率": format_percentage(row["openingOnly"]["singlePredictionAccuracy"]),
                "初赔覆盖率": format_percentage(row["openingOnly"]["inclusiveHitRate"]),
                "临场Top1": format_percentage(row["closingOnly"]["top1Accuracy"]),
                "临场单选准确率": format_percentage(row["closingOnly"]["singlePredictionAccuracy"]),
                "临场覆盖率": format_percentage(row["closingOnly"]["inclusiveHitRate"]),
                "混合Top1": format_percentage(row["hybrid"]["top1Accuracy"]),
                "混合单选准确率": format_percentage(row["hybrid"]["singlePredictionAccuracy"]),
                "混合覆盖率": format_percentage(row["hybrid"]["inclusiveHitRate"]),
                "推荐依据": row["recommendationReason"],
            }
        )
    return rows


def compute_report_prediction(
    opening_rows: list[dict],
    closing_rows: list[dict] | None = None,
    *,
    match_started: bool = False,
) -> dict:
    opening_prediction = compute_rule_prediction(opening_rows)
    key_parts = build_mode_selection_key(opening_prediction)
    key_label = format_mode_selection_key_parts(key_parts)

    if not match_started:
        return {
            "openingPrediction": opening_prediction,
            "effectiveMode": "opening_only",
            "effectiveModeLabel": CALIBRATED_MODE_LABELS["opening_only"],
            "phaseStatus": "未开赛",
            "modeSelectionBasis": "未到开球时间，默认使用初赔模式。",
            "modeHistoryAccuracy": opening_prediction["bettingDecision"]["historyAccuracySummary"],
            "historySampleSize": opening_prediction["bettingDecision"]["historySampleSize"],
            "historyAccuracySummary": opening_prediction["bettingDecision"]["historyAccuracySummary"],
            "finalAction": opening_prediction["bettingDecision"]["action"],
            "finalPrediction": opening_prediction["bettingDecision"]["finalPrediction"],
            "decisionBasis": opening_prediction["bettingDecision"]["decisionBasis"],
            "effectivePrediction": opening_prediction,
        }

    if not closing_rows:
        return {
            "openingPrediction": opening_prediction,
            "effectiveMode": "opening_only",
            "effectiveModeLabel": CALIBRATED_MODE_LABELS["opening_only"],
            "phaseStatus": "已开球",
            "modeSelectionBasis": "已到开球时间，但临场赔率缺失，回退初赔模式。",
            "modeHistoryAccuracy": opening_prediction["bettingDecision"]["historyAccuracySummary"],
            "historySampleSize": opening_prediction["bettingDecision"]["historySampleSize"],
            "historyAccuracySummary": opening_prediction["bettingDecision"]["historyAccuracySummary"],
            "finalAction": opening_prediction["bettingDecision"]["action"],
            "finalPrediction": opening_prediction["bettingDecision"]["finalPrediction"],
            "decisionBasis": opening_prediction["bettingDecision"]["decisionBasis"],
            "effectivePrediction": opening_prediction,
        }

    live_selection_row, _, live_meta = resolve_live_mode_selection(opening_prediction)
    preferred_mode = "closing_only"
    selection_reason = f"{key_label} → 未命中临场模式选择表，默认使用临场模式。"
    if live_selection_row:
        preferred_mode = live_selection_row["recommendedMode"]
        selection_reason = (
            f"{key_label} → {live_selection_row['recommendationReason']}"
        )

    live_predictions: dict[str, dict] = {}
    live_errors: list[str] = []
    for feature_mode in ("opening_only", "closing_only", "hybrid"):
        try:
            live_predictions[feature_mode] = compute_calibrated_prediction(
                opening_rows,
                closing_rows,
                feature_mode,
            )
        except Exception as error:
            live_errors.append(f"{CALIBRATED_MODE_LABELS[feature_mode]}推理失败：{error}")

    if preferred_mode not in live_predictions:
        fallback_modes = (
            ("closing_only", "临场模式"),
            ("opening_only", "初赔模式"),
            ("hybrid", "初赔+临场模式"),
        )
        for fallback_mode, fallback_label in fallback_modes:
            if fallback_mode in live_predictions:
                preferred_mode = fallback_mode
                selection_reason = (
                    f"{selection_reason}；目标模式不可用，回退{fallback_label}。"
                )
                break
        else:
            fallback_reason = "；".join(live_errors) if live_errors else "临场增强模式均不可用。"
            return {
                "openingPrediction": opening_prediction,
                "effectiveMode": "opening_only",
                "effectiveModeLabel": CALIBRATED_MODE_LABELS["opening_only"],
                "phaseStatus": "已开球",
                "modeSelectionBasis": f"{selection_reason}；{fallback_reason}，回退初赔模式。",
                "modeHistoryAccuracy": opening_prediction["bettingDecision"]["historyAccuracySummary"],
                "historySampleSize": opening_prediction["bettingDecision"]["historySampleSize"],
                "historyAccuracySummary": opening_prediction["bettingDecision"]["historyAccuracySummary"],
                "finalAction": opening_prediction["bettingDecision"]["action"],
                "finalPrediction": opening_prediction["bettingDecision"]["finalPrediction"],
                "decisionBasis": opening_prediction["bettingDecision"]["decisionBasis"],
                "effectivePrediction": opening_prediction,
            }

    selected_prediction = live_predictions[preferred_mode]
    decision_type = normalize_decision_type(selected_prediction["decision"]["type"])
    if live_selection_row:
        history_summary = build_calibrated_history_summary(
            live_selection_row,
            preferred_mode,
            decision_type,
        )
        history_sample_size = str(live_selection_row["matches"])
    else:
        history_summary = (
            f"未命中模式选择表或样本低于{live_meta.get('minSample', MODE_SELECTION_DEFAULT_MIN_SAMPLE)}场，"
            f"默认使用{selected_prediction['modeLabel']}模式。"
        )
        history_sample_size = "样本不足"

    final_action = "单选" if decision_type == "single" else "双选"
    if live_errors:
        selection_reason = f"{selection_reason}；{'；'.join(live_errors)}"

    return {
        "openingPrediction": opening_prediction,
        "effectiveMode": preferred_mode,
        "effectiveModeLabel": selected_prediction["modeLabel"],
        "phaseStatus": "已开球",
        "modeSelectionBasis": selection_reason,
        "modeHistoryAccuracy": history_summary,
        "historySampleSize": history_sample_size,
        "historyAccuracySummary": history_summary,
        "finalAction": final_action,
        "finalPrediction": selected_prediction["prediction"],
        "decisionBasis": key_label,
        "effectivePrediction": selected_prediction,
    }
