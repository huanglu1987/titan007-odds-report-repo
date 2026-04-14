---
name: titan007-odds-report
description: "根据北京时间时间范围生成球探未来赛程欧赔预测 Excel。适用于用户想输入开始和结束时间，然后自动抓取 Titan007 未来赛程、提取固定 6 家公司初始欧赔、运行 football-odds-predictor 最新初赔监督学习模型，并导出按日期分 Sheet、按联赛分块的 Excel 报表。触发词包括：球探、Titan007、未来赛程、欧赔、6家公司、初赔、预测报表、Excel、时间范围。"
---

# Titan007 Odds Report

用这个 skill 时，优先复用 skill 目录内自带的 `scripts/generate_titan007_high_confidence_report.py`，不要重新手写抓取和导出流程。

## 输入要求

要求用户至少给出：

- 北京时间开始时间，格式 `YYYY-MM-DD HH:MM`
- 北京时间结束时间，格式 `YYYY-MM-DD HH:MM`

可选项：

- 信任等级：`高`、`高,中` 或 `高,中,谨慎`
- 信任等级筛选口径：`opening` 或 `effective`
- 输出路径；如果用户不指定，优先导出到 `~/Desktop`，如果目标设备没有桌面目录，则回退到 skill 目录下的 `output/`

不需要用户提供：

- 临场赔率
- 额外的模式切换参数

## 跨设备安装说明

这个 skill 现在按“自包含”方式打包，支持两种用法：

1. 作为仓库运行：
   - 在仓库根目录执行 `.codex/skills/titan007-odds-report/scripts/run_report.py`
2. 作为 GitHub skill 安装：
   - 只安装 `.codex/skills/titan007-odds-report` 这个目录后，也可以直接运行
   - skill 目录内部已经自带：
     - `scripts/generate_titan007_high_confidence_report.py`
     - `scripts/titan007_extract_euro_odds.py`
     - `runtime/football-odds-predictor/predictor_py.py`
     - `runtime/football-odds-predictor/calibration/*.json`
     - `requirements.txt`

首次在新设备上使用前，至少需要：

```bash
python3 -m pip install -r /path/to/titan007-odds-report/requirements.txt
```

## 当前模型口径

- 固定 6 家公司：`Bet365`、`William Hill`、`Bwin`、`Interwetten`、`Pinnacle`、`BetVictor`
- 只使用初始 1X2 赔率
- 训练集：`2017-18` 至 `2022-23`
- 验证集：`2023-24`
- 高信任阈值：`topProbabilityMin=0.58`、`topGapMin=0.08`、`consensusMin=0.75`、`favoriteVoteShareMin=1`
- 中信任双选阈值：`doubleGapThreshold=0.16`
- 当前验证结果：单选准确率 `55.46%`，高信任覆盖率 `24.98%`，高信任准确率 `69.90%`

## 工作流程

1. 优先直接运行 skill 自带的 `scripts/run_report.py`。
2. 默认按 skill 自身目录查找依赖；如果用户显式传了 `--project-root`，则改用该目录。
2. 运行 skill 自带脚本 `scripts/run_report.py`，把用户给的开始时间、结束时间、信任等级传进去。
3. 等待脚本生成 Excel。
4. 把最终 Excel 绝对路径告诉用户。
5. 如果脚本报错，先把关键错误返回给用户，不要编造成功结果。

## 运行方式

在仓库或已安装的 skill 目录下，都可以优先运行：

```bash
python3 scripts/run_report.py \
  --start "2026-03-29 18:00" \
  --end "2026-04-03 00:00" \
  --confidences "高,中,谨慎" \
  --confidence-source "opening"
```

如果是从仓库根目录运行，也可以：

```bash
python3 .codex/skills/titan007-odds-report/scripts/run_report.py \
  --start "2026-03-29 18:00" \
  --end "2026-04-03 00:00" \
  --confidences "高,中,谨慎" \
  --confidence-source "opening"
```

如果要显式指定仓库根目录，可以传 `--project-root`：

```bash
python3 /path/to/titan007-odds-report/scripts/run_report.py \
  --project-root "/path/to/your/repo" \
  --start "2026-03-29 18:00" \
  --end "2026-04-03 00:00" \
  --confidences "高,中,谨慎" \
  --confidence-source "opening"
```

如果 skill 是通过 GitHub 安装器单独安装的，`run_report.py` 会直接使用 skill 自己的目录，不依赖仓库根目录。

## 输出约定

默认优先输出到 `~/Desktop/`；如果当前设备没有该目录，则回退到 skill 目录下的 `output/`。

当前脚本会生成：

- 总览 Sheet
- 模型验证 Sheet
- 每天一个 Sheet
- 每个日期 Sheet 内按联赛分块

明细行现在会同时输出：

- `原始预测结果`
- `基础高信任判定`
- `结构标签`
- `原始信任等级`
- `最终信任等级`
- `信任等级依据`
- `前二差值`
- `比赛时点状态`
- `生效预测模式`
- `最终决策动作`
- `最终预测结果`
- `决策依据`
- `模式选择依据`
- `模式历史准确率`
- `历史样本数`
- `历史准确率提示`

其中：

- `原始信任等级`：按初始赔率基础分层结果保留
- `最终信任等级`：按最新初赔监督学习模型的高/中信任规则输出
- `基础高信任判定`：显示最新模型在“先判高信任单选”这一步的基础结果
- `--confidence-source opening`：按 `原始信任等级` 过滤，兼容旧行为
- `--confidence-source effective`：按 `最终信任等级` 过滤，更适合直接筛高信任

默认文件名会自动带上信任等级和时间范围，格式是：

```text
titan007_{信任等级}_confidence_{开始时间}_{结束时间}.xlsx
```

其中：

- `{信任等级}` 来自 `--confidences`，会按字面值拼接；例如 `高` 或 `中_高`
- 如果传 `高,中,谨慎`，默认文件名里会变成 `中_高_谨慎`
- `{开始时间}` 和 `{结束时间}` 使用北京时间，并格式化为 `YYYYMMDD_HHMM`

示例：

```text
titan007_高_confidence_20260329_1800_20260403_0000.xlsx
titan007_中_高_confidence_20260329_1800_20260403_0000.xlsx
titan007_中_高_谨慎_confidence_20260329_1800_20260403_0000.xlsx
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
- 当前 skill 的使用前提只要求时间范围，不要求用户提供临场赔率。
- 当前默认输出应理解为“最新初赔监督学习模型”的结果，而不是旧的临场增强模式。
- 只要目标站点返回失败，就可能导致覆盖率下降；这是网络问题，不要误报为“没有比赛”。
- 如果是刚安装到新设备，先安装 skill 目录中的 `requirements.txt`。
- 如果用户只要 `高`，传 `--confidences "高"`；如果要 `高 + 中`，传 `--confidences "高,中"`；如果要把 `高/中/谨慎` 三层都导出，传 `--confidences "高,中,谨慎"`。
- 生成后的 Excel 中，`最终预测结果` 应优先理解为当前初赔模型的输出。
- `原始预测结果` 会保留，方便与最终结果对照。
- `模型验证` Sheet 会列出当前生效模型的训练/验证样本、阈值，以及整体/高信任/中信任验证指标。
