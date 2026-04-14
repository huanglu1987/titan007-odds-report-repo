#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


DESKTOP_DIR = Path.home() / "Desktop"
SKILL_ROOT = Path(__file__).resolve().parents[1]


def resolve_project_root(explicit_root: Path | None) -> Path:
    if explicit_root is not None:
        return explicit_root.resolve()

    bundled_script = SKILL_ROOT / "scripts" / "generate_titan007_high_confidence_report.py"
    if bundled_script.exists():
        return SKILL_ROOT

    cwd_root = Path.cwd().resolve()
    cwd_script = cwd_root / "scripts" / "generate_titan007_high_confidence_report.py"
    if cwd_script.exists():
        return cwd_root

    inferred_root = Path(__file__).resolve().parents[4]
    inferred_script = inferred_root / "scripts" / "generate_titan007_high_confidence_report.py"
    if inferred_script.exists():
        return inferred_root

    raise FileNotFoundError(
        "未找到项目根目录。请显式传入 --project-root 指向包含 scripts/generate_titan007_high_confidence_report.py 的目录。"
    )


def build_default_output_path(project_root: Path, start: str, end: str, confidences: str) -> Path:
    confidence_slug = "_".join(sorted(item.strip() for item in confidences.split(",") if item.strip()))
    start_slug = start.replace("-", "").replace(":", "").replace(" ", "_")
    end_slug = end.replace("-", "").replace(":", "").replace(" ", "_")
    filename = f"titan007_{confidence_slug}_confidence_{start_slug}_{end_slug}.xlsx"
    if DESKTOP_DIR.exists():
        return DESKTOP_DIR / filename
    return project_root / "output" / filename


def main() -> None:
    parser = argparse.ArgumentParser(
        description="运行 Titan007 欧赔预测 Excel 报表生成器。"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        help="项目根目录；不传时会优先使用当前工作目录，否则自动按 skill 所在仓库推断。",
    )
    parser.add_argument("--start", required=True, help="开始时间，格式：YYYY-MM-DD HH:MM")
    parser.add_argument("--end", required=True, help="结束时间，格式：YYYY-MM-DD HH:MM")
    parser.add_argument(
        "--confidences",
        default="高,中",
        help="信任等级，逗号分隔，例如：高、高,中、高,中,谨慎",
    )
    parser.add_argument(
        "--confidence-source",
        default="opening",
        help="信任等级筛选口径：opening=按原始信任等级；effective=按最终信任等级。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="输出 Excel 路径；不传则默认导出到桌面并自动命名。",
    )
    args = parser.parse_args()

    project_root = resolve_project_root(args.project_root)
    target_script = project_root / "scripts" / "generate_titan007_high_confidence_report.py"
    if not target_script.exists():
        raise FileNotFoundError(f"未找到报表脚本: {target_script}")

    output_path = args.output.resolve() if args.output else build_default_output_path(
        project_root,
        args.start,
        args.end,
        args.confidences,
    )

    command = [
        "python3",
        str(target_script),
        "--start",
        args.start,
        "--end",
        args.end,
        "--confidences",
        args.confidences,
        "--confidence-source",
        args.confidence_source,
        "--output",
        str(output_path),
    ]

    completed = subprocess.run(
        command,
        cwd=str(project_root),
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="")
        raise SystemExit(completed.returncode)

    confidence_text = args.confidences.replace(",", " + ")
    print(f"Excel 已生成：{output_path}")
    print(f"时间范围：{args.start} 至 {args.end}（北京时间）")
    print(f"信任等级：{confidence_text}")


if __name__ == "__main__":
    main()
