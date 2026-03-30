---
name: titan007-odds-report
description: "根据北京时间时间范围生成球探未来赛程欧赔预测 Excel。适用于用户想输入开始和结束时间，然后自动抓取 Titan007 未来赛程、提取固定 6 家公司初始欧赔、运行 football-odds-predictor，并导出按日期分 Sheet、按联赛分块的 Excel 报表。触发词包括：球探、Titan007、未来赛程、欧赔、6家公司、初赔、预测报表、Excel、时间范围。"
---

# Titan007 Odds Report

用这个 skill 时，优先复用仓库里的 `scripts/generate_titan007_high_confidence_report.py`，不要重新手写抓取和导出流程。

## 输入要求

要求用户至少给出：

- 北京时间开始时间，格式 `YYYY-MM-DD HH:MM`
- 北京时间结束时间，格式 `YYYY-MM-DD HH:MM`

可选项：

- 信任等级：`高` 或 `高,中`
- 输出路径；如果用户不指定，就让脚本自动命名

## 工作流程

1. 优先在仓库根目录执行；如果不在仓库根目录，就确保能定位到包含 `scripts/generate_titan007_high_confidence_report.py` 的项目目录。
2. 运行 skill 自带脚本 `scripts/run_report.py`，把用户给的开始时间、结束时间、信任等级传进去。
3. 等待脚本生成 Excel。
4. 把最终 Excel 绝对路径告诉用户。
5. 如果脚本报错，先把关键错误返回给用户，不要编造成功结果。

## 运行方式

在项目根目录下优先运行：

```bash
python3 .codex/skills/titan007-odds-report/scripts/run_report.py \
  --start "2026-03-29 18:00" \
  --end "2026-04-03 00:00" \
  --confidences "高,中"
```

如果不在项目根目录，可以显式传 `--project-root`：

```bash
python3 /path/to/titan007-odds-report/scripts/run_report.py \
  --project-root "/path/to/your/repo" \
  --start "2026-03-29 18:00" \
  --end "2026-04-03 00:00" \
  --confidences "高,中"
```

如果 skill 作为仓库的一部分被提交，`run_report.py` 会先尝试使用当前工作目录；如果当前目录不是仓库根目录，它会再自动按自身所在位置向上推断项目根目录。

## 输出约定

默认输出到项目目录下的 `output/spreadsheet/`。

当前脚本会生成：

- 总览 Sheet
- 每天一个 Sheet
- 每个日期 Sheet 内按联赛分块

默认文件名会自动带上信任等级和时间范围，格式是：

```text
titan007_{信任等级}_confidence_{开始时间}_{结束时间}.xlsx
```

其中：

- `{信任等级}` 来自 `--confidences`，会按字面值拼接；例如 `高` 或 `中_高`
- `{开始时间}` 和 `{结束时间}` 使用北京时间，并格式化为 `YYYYMMDD_HHMM`

示例：

```text
titan007_高_confidence_20260329_1800_20260403_0000.xlsx
titan007_中_高_confidence_20260329_1800_20260403_0000.xlsx
```

如果用户显式传了 `--output`，就以用户给的输出路径为准，不再使用默认命名规则。

给用户汇报结果时，优先用一句固定模板：

```text
Excel 已生成：{绝对路径}
时间范围：{开始时间} 至 {结束时间}（北京时间）
信任等级：{信任等级}
```

## 注意事项

- 时间按北京时间解释。
- 当前固定 6 家公司口径是：`Bet365`、`William Hill`、`Bwin`、`Interwetten`、`Pinnacle`、`BetVictor`。
- 只要目标站点返回失败，就可能导致覆盖率下降；这是网络问题，不要误报为“没有比赛”。
- 如果用户只要 `高`，传 `--confidences "高"`；如果要 `高 + 中`，传 `--confidences "高,中"`。
