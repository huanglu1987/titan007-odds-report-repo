#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from requests.adapters import HTTPAdapter
from pathlib import Path
from typing import Any

import requests
from urllib3.util.retry import Retry


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.titan007.com/",
}

ODDSLIST_REFERER_TEMPLATE = "https://1x2.titan007.com/oddslist/{schedule_id}.htm"
ODDSLIST_HTML_TEMPLATE = "https://1x2.titan007.com/oddslist/{schedule_id}.htm"

# 这里的 6 家公司顺序必须和 football-odds-predictor 插件保持一致。
# 球探同一家公司在不同接口/页面里可能出现不同缩写，因此这里允许别名候选。
PLUGIN_COMPANY_ALIAS_MAP = {
    "Bet365": ["36*", "36*(英国)"],
    "William Hill": ["威*", "威*(英国)"],
    "Bwin": ["Bwi*(奥地利)"],
    "Interwetten": ["Interwet*", "Interwet*(塞浦洛斯)", "Interwet*(塞浦路斯)"],
    "Pinnacle": ["Pinna*(荷兰)", "平*"],
    "BetVictor": ["伟*", "伟*(直布罗陀)"],
}

PLUGIN_COMPANY_CODE_CANDIDATES = {
    "Bwin": ["4"],
}


def create_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_text(url: str, extra_headers: dict[str, str] | None = None) -> str:
    headers = dict(DEFAULT_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = create_session().get(url, headers=headers, timeout=20)
            response.raise_for_status()
            response.encoding = "utf-8"
            return response.text
        except requests.RequestException as error:
            last_error = error
            if attempt == 3:
                break
            time.sleep(1.5 + attempt * 1.5)
    raise RuntimeError(f"抓取失败: {url}") from last_error


def parse_odds_triplet(raw_segment: str) -> dict[str, float] | None:
    parts = raw_segment.split(",")
    if len(parts) < 3:
        return None
    try:
        return {
            "home": float(parts[0]),
            "draw": float(parts[1]),
            "away": float(parts[2]),
        }
    except ValueError:
        return None


def parse_iframe_aodds(html: str) -> list[dict[str, Any]]:
    match = re.search(r"value='([^']+)' id='iframeAOdds'", html)
    if not match:
        raise ValueError("未找到 iframeAOdds 隐藏字段，无法解析欧赔数据。")

    records: list[dict[str, Any]] = []
    for chunk in match.group(1).split("^"):
        columns = chunk.split(";")
        if len(columns) < 4:
            continue

        company_code = columns[0].strip()
        company_name = columns[1].strip()
        opening = parse_odds_triplet(columns[2].strip())
        closing = parse_odds_triplet(columns[3].strip())

        if not company_name or not opening:
            continue

        records.append(
            {
                "companyCode": company_code,
                "companyName": company_name,
                "openingOdds": opening,
                "closingOdds": closing,
                "raw": chunk,
            }
        )

    if not records:
        raise ValueError("iframeAOdds 已找到，但没有解析出任何公司欧赔。")

    return records


def parse_allodds_candidates(html: str) -> list[dict[str, Any]]:
    match = re.search(r"allodds='([^']+)'", html)
    if not match:
        return []

    candidates: list[dict[str, Any]] = []
    for chunk in match.group(1).split(";"):
        parts = chunk.split(",")
        if len(parts) < 4:
            continue
        try:
            candidates.append(
                {
                    "companyCode": parts[0],
                    "odds": {
                        "home": float(parts[1]),
                        "draw": float(parts[2]),
                        "away": float(parts[3]),
                    },
                    "raw": chunk,
                }
            )
        except ValueError:
            continue
    return candidates


def parse_oddslist_js(js_text: str) -> list[dict[str, Any]]:
    match = re.search(r"var\s+game\s*=\s*Array\((.*?)\);\s*var\s", js_text, re.S)
    if not match:
        raise ValueError("未找到 oddslist JS 里的 game 数组，无法解析真实欧赔页数据。")

    records: list[dict[str, Any]] = []
    for raw_chunk in re.findall(r'"([^"]+)"', match.group(1)):
        columns = raw_chunk.split("|")
        if len(columns) < 22:
            continue

        try:
            opening = {
                "home": float(columns[3]),
                "draw": float(columns[4]),
                "away": float(columns[5]),
            }
            closing = {
                "home": float(columns[10]),
                "draw": float(columns[11]),
                "away": float(columns[12]),
            }
        except ValueError:
            continue

        records.append(
            {
                "companyCode": columns[0].strip(),
                "companyId": columns[1].strip(),
                "companyNameEn": columns[2].strip(),
                "openingOdds": opening,
                "closingOdds": closing,
                "lastUpdateTime": columns[20].strip(),
                "companyName": columns[21].strip(),
                "raw": raw_chunk,
            }
        )

    if not records:
        raise ValueError("oddslist JS 已找到，但没有解析出任何公司欧赔。")

    return records


def normalize_company_alias(value: str) -> str:
    normalized = value.strip()
    normalized = normalized.replace("塞浦洛斯", "塞浦路斯")
    return normalized


def build_plugin_company_rows(
    records: list[dict[str, Any]],
    supplemental_candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    by_name = {
        normalize_company_alias(record["companyName"]): record for record in records
    }
    supplemental_by_code = {
        record["companyCode"]: record for record in supplemental_candidates
    }
    rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    missing: list[str] = []

    for plugin_company, titan_aliases in PLUGIN_COMPANY_ALIAS_MAP.items():
        record = None
        matched_alias = None
        matched_source = None
        for titan_alias in titan_aliases:
            record = by_name.get(normalize_company_alias(titan_alias))
            if record:
                matched_alias = record["companyName"]
                matched_source = "oddslistJs"
                break
        if not record:
            for company_code in PLUGIN_COMPANY_CODE_CANDIDATES.get(plugin_company, []):
                if company_code in supplemental_by_code:
                    supplement = supplemental_by_code[company_code]
                    candidate_rows.append(
                        {
                            "company": plugin_company,
                            "titanAlias": company_code,
                            "titanCompanyCode": supplement["companyCode"],
                            "openingOdds": supplement["odds"],
                            "closingOdds": None,
                            "source": "supplementalAllOddsCandidates:codeCandidate",
                            "status": "candidate",
                        }
                    )
                    break
        if not record:
            missing.append(plugin_company)
            continue
        rows.append(
            {
                "company": plugin_company,
                "titanAlias": matched_alias,
                "titanCompanyCode": record["companyCode"],
                "openingOdds": record["openingOdds"],
                "closingOdds": record["closingOdds"],
                "source": matched_source,
            }
        )

    return rows, candidate_rows, missing


def fetch_oddslist_js(schedule_id: str) -> tuple[str, str]:
    referer = ODDSLIST_REFERER_TEMPLATE.format(schedule_id=schedule_id)
    direct_url = f"https://1x2d.titan007.com/{schedule_id}.js"
    try:
        text = fetch_text(direct_url, extra_headers={"Referer": referer})
        if "var game=Array(" in text:
            return direct_url, text
    except Exception:
        pass

    oddslist_html = fetch_text(
        ODDSLIST_HTML_TEMPLATE.format(schedule_id=schedule_id),
        extra_headers={"Referer": "https://www.titan007.com/"},
    )
    script_match = re.search(
        r'<script[^>]+src=["\'](//1x2d\.titan007\.com/[^"\']+\.js(?:\?[^"\']*)?)["\']',
        oddslist_html,
        re.IGNORECASE,
    )
    if not script_match:
        raise RuntimeError(f"未能从欧赔页提取真实 JS 地址: {schedule_id}")

    extracted_url = f"https:{script_match.group(1)}"
    text = fetch_text(extracted_url, extra_headers={"Referer": referer})
    if "var game=Array(" not in text:
        raise RuntimeError(f"真实 JS 内容不完整: {extracted_url}")
    return extracted_url, text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从球探分析接口抓取单场比赛欧赔，并抽取插件固定 6 家公司的初赔。"
    )
    parser.add_argument("--schedule-id", required=True, help="球探比赛 schedule id，例如 2807967")
    parser.add_argument(
        "--output",
        type=Path,
        help="输出 JSON 文件路径。不传则打印到标准输出。",
    )
    args = parser.parse_args()

    oddslist_js_url, oddslist_js = fetch_oddslist_js(str(args.schedule_id))
    oddslist_records = parse_oddslist_js(oddslist_js)

    analysis_url = f"https://info.titan007.com/analysis/odds/{args.schedule_id}.htm"
    analysis_html = fetch_text(analysis_url)
    analysis_records = parse_iframe_aodds(analysis_html)
    allodds_candidates = parse_allodds_candidates(analysis_html)
    plugin_rows, candidate_rows, missing = build_plugin_company_rows(
        oddslist_records,
        allodds_candidates,
    )

    payload = {
        "scheduleId": str(args.schedule_id),
        "sourceUrl": oddslist_js_url,
        "note": {
            "goal": "从球探真实欧赔页 JS 数据源提取当前比赛的独赢初赔/终赔。",
            "mappingAssumption": (
                "固定 6 家公司映射按页面/接口别名候选匹配：36*=Bet365、"
                "威*/威*(英国)=William Hill、Bwi*(奥地利)=Bwin、"
                "Interwet*/Interwet*(塞浦洛斯)=Interwetten、"
                "Pinna*(荷兰)/平*=Pinnacle、伟*/伟*(直布罗陀)=BetVictor。"
            ),
            "warning": (
                "球探分析页的 iframeAOdds 与真实欧赔页并不总是完全一致。"
                "脚本现已优先使用真实 oddslist JS，analysis/odds 仅作为回退和对照。"
            ),
            "strictMode": (
                "严格模式下，仅真实 oddslist JS 中已确认的公司才计入 fixed 6 company 命中。"
                "analysis/odds 的补源 companyCode 候选只作为人工核对线索，不自动视为正式命中。"
            ),
        },
        "oddslistJsSourceUrl": oddslist_js_url,
        "analysisSourceUrl": analysis_url,
        "allCompanies": oddslist_records,
        "analysisAllCompanies": analysis_records,
        "supplementalAllOddsCandidates": allodds_candidates,
        "confirmedPluginCompanies": plugin_rows,
        "candidatePluginCompanies": candidate_rows,
        "missingPluginCompanies": missing,
    }

    output_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_text, encoding="utf-8")
    else:
        print(output_text)


if __name__ == "__main__":
    main()
