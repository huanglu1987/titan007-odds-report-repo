# Titan007 Odds Report Skill Repo

这个仓库用于跨机器复用 `titan007-odds-report` skill。

## 包含内容

- `.codex/skills/titan007-odds-report`
- `scripts/generate_titan007_high_confidence_report.py`
- `scripts/titan007_extract_euro_odds.py`
- `runtime/football-odds-predictor/predictor_py.py`
- `runtime/football-odds-predictor/calibration/latest.json`

## 本地运行

在仓库根目录执行：

```bash
python3 .codex/skills/titan007-odds-report/scripts/run_report.py \
  --start "2026-03-29 18:00" \
  --end "2026-04-03 00:00" \
  --confidences "高,中,谨慎"
```

## 依赖

安装：

```bash
python3 -m pip install -r requirements.txt
```

## 输出

当前 Excel 会包含：

- `总览`
- `投注决策总表`
- 每日赛程 Sheet
- `原始预测结果 / 最终决策动作 / 最终预测结果 / 决策依据 / 历史准确率提示` 等明细列

默认输出到桌面；如果显式传 `--output`，则按你给的路径输出。
