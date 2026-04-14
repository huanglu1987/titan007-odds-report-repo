# Titan007 Odds Report Skill Repo

这个仓库用于跨机器复用 `titan007-odds-report` skill，并支持作为 GitHub skill 目录直接安装。

## 包含内容

- `.codex/skills/titan007-odds-report`
- `.codex/skills/titan007-odds-report/scripts/generate_titan007_high_confidence_report.py`
- `.codex/skills/titan007-odds-report/scripts/titan007_extract_euro_odds.py`
- `.codex/skills/titan007-odds-report/runtime/football-odds-predictor/predictor_py.py`
- `.codex/skills/titan007-odds-report/runtime/football-odds-predictor/calibration/*.json`
- 仓库根目录下的同名 `scripts/` 和 `runtime/` 副本，便于仓库内开发同步

## 用法

### 1. 作为仓库运行

在仓库根目录执行：

```bash
python3 -m pip install -r requirements.txt
python3 .codex/skills/titan007-odds-report/scripts/run_report.py \
  --start "2026-03-29 18:00" \
  --end "2026-04-03 00:00" \
  --confidences "高,中,谨慎"
```

### 2. 作为 GitHub skill 直接安装

安装后，进入已安装的 skill 目录执行：

```bash
python3 -m pip install -r requirements.txt
python3 scripts/run_report.py \
  --start "2026-03-29 18:00" \
  --end "2026-04-03 00:00" \
  --confidences "高,中,谨慎"
```

## 输出

当前 Excel 会包含：

- `总览`
- `模型验证`
- 每日赛程 Sheet
- `原始预测结果 / 原始信任等级 / 最终信任等级 / 最终决策动作 / 最终预测结果 / 决策依据 / 历史准确率提示` 等明细列

默认优先输出到桌面；如果目标设备没有 `~/Desktop`，则自动回退到运行目录下的 `output/`。
