#!/usr/bin/env python3
"""
报告到期提醒检查器 (review_due_check)

扫描指定目录下所有 14 步分析报告的 frontmatter，
列出 review_due <= today 的报告，生成 markdown 提醒。

报告 frontmatter 规范：
  ---
  ticker: 600519
  report_date: 2026-05-17
  review_due: 2027-05-17
  analyst: 江安澜
  mode: full
  status: active
  ---

用法：
  python review_due_check.py [--dir /path/to/reports] [--days-ahead 30]

  --dir        报告目录（默认 ~/reports/）
  --days-ahead 提前提醒天数（默认 30，即 review_due 在 30 天内也提醒）
  --all        显示所有报告（不限到期与否）

集成方式：
  - 命令行手动执行
  - cron 定时任务（每天早 9 点运行）
  - 在 14-step skill 启动时自动调用
"""

import argparse
import datetime
import os
import re
import sys


def parse_frontmatter(filepath: str) -> dict:
    """
    解析 markdown 文件开头的 YAML frontmatter。
    返回 dict，如果无 frontmatter 则返回 None。
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read(500)  # 只读前 500 字符，frontmatter 不会太长

    # 匹配 --- 分隔的 frontmatter
    pattern = r"^---\s*\n(.*?)\n---"
    match = re.match(pattern, content, re.DOTALL)
    if not match:
        return None

    fm_text = match.group(1)
    fm = {}
    for line in fm_text.strip().split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm


def scan_reports(report_dir: str) -> list:
    """
    扫描目录下所有 .md 文件，解析 frontmatter。
    返回 list of dict，每个 dict 包含文件路径和 frontmatter 字段。
    """
    if not os.path.isdir(report_dir):
        print(f"[WARN] 目录不存在: {report_dir}", file=sys.stderr)
        return []

    results = []
    for root, dirs, files in os.walk(report_dir):
        for fname in files:
            if fname.endswith(".md"):
                fpath = os.path.join(root, fname)
                fm = parse_frontmatter(fpath)
                if fm and "ticker" in fm:
                    fm["_path"] = fpath
                    fm["_filename"] = fname
                    results.append(fm)
    return results


def main():
    p = argparse.ArgumentParser(description="14 步分析报告到期提醒检查器")
    p.add_argument("--dir", default=None,
                   help="报告目录（默认 ~/reports/）")
    p.add_argument("--days-ahead", type=int, default=30,
                   help="提前提醒天数（默认 30）")
    p.add_argument("--all", action="store_true",
                   help="显示所有报告（不限到期与否）")
    args = p.parse_args()

    # 默认目录
    home = os.path.expanduser("~")
    report_dir = args.dir if args.dir else os.path.join(home, "reports")

    # Windows 兼容
    if not os.path.isdir(report_dir) and os.path.isdir(os.path.join("D:\\", "reports")):
        report_dir = "D:\\reports"

    today = datetime.date.today()

    reports = scan_reports(report_dir)

    if not reports:
        print(f"目录 {report_dir} 下未找到包含 frontmatter 的报告。")
        return

    # 解析日期并分类
    overdue = []
    upcoming = []
    active = []

    for r in reports:
        ticker = r.get("ticker", "?")
        report_date = r.get("report_date", "?")
        review_due_str = r.get("review_due", "")
        analyst = r.get("analyst", "?")
        mode = r.get("mode", "?")
        status = r.get("status", "active")
        fpath = r.get("_path", "")

        # 跳过非 active 的报告
        if status != "active":
            continue

        # 解析 review_due
        review_due = None
        if review_due_str:
            try:
                review_due = datetime.date.fromisoformat(review_due_str)
            except ValueError:
                pass

        entry = {
            "ticker": ticker,
            "report_date": report_date,
            "review_due": review_due_str if review_due_str else "未设置",
            "analyst": analyst,
            "mode": mode,
            "path": fpath,
        }

        if review_due is None:
            entry["status"] = "无到期日"
            active.append(entry)
        elif review_due < today:
            entry["days_overdue"] = (today - review_due).days
            entry["status"] = "已过期"
            overdue.append(entry)
        elif review_due <= today + datetime.timedelta(days=args.days_ahead):
            entry["days_left"] = (review_due - today).days
            entry["status"] = "即将到期"
            upcoming.append(entry)
        else:
            entry["days_left"] = (review_due - today).days
            entry["status"] = "正常"
            active.append(entry)

    # 输出
    print("# 报告到期提醒")
    print()
    print(f"扫描目录: `{report_dir}`")
    print(f"当前日期: {today.isoformat()}")
    print(f"提醒窗口: review_due 前 {args.days_ahead} 天")
    print(f"扫描结果: {len(reports)} 份报告，{len(overdue)} 份已过期，{len(upcoming)} 份即将到期")
    print()

    if overdue:
        print("## 已过期报告（需立即复审）")
        print()
        print("| Ticker | 报告日期 | 到期日 | 超期天数 | 模式 | 分析师 |")
        print("|---|---|---|---|---|---|")
        for e in overdue:
            print(f"| {e['ticker']} | {e['report_date']} | {e['review_due']} | "
                  f"**{e['days_overdue']} 天** | {e['mode']} | {e['analyst']} |")
        print()

    if upcoming:
        print("## 即将到期报告")
        print()
        print("| Ticker | 报告日期 | 到期日 | 剩余天数 | 模式 | 分析师 |")
        print("|---|---|---|---|---|---|")
        for e in upcoming:
            print(f"| {e['ticker']} | {e['report_date']} | {e['review_due']} | "
                  f"{e['days_left']} 天 | {e['mode']} | {e['analyst']} |")
        print()

    if args.all:
        print("## 所有 Active 报告")
        print()
        print("| Ticker | 报告日期 | 到期日 | 状态 | 模式 | 分析师 |")
        print("|---|---|---|---|---|---|")
        all_entries = sorted(upcoming + active, key=lambda x: x.get("review_due", "9999"))
        for e in all_entries:
            days_info = ""
            if "days_left" in e:
                days_info = f"{e['days_left']} 天"
            print(f"| {e['ticker']} | {e['report_date']} | {e['review_due']} | "
                  f"{e['status']} | {e['mode']} | {e['analyst']} |")
        print()

    if not overdue and not upcoming:
        print("所有报告均在正常周期内。")
        if not args.all:
            print("使用 --all 查看完整列表。")


if __name__ == "__main__":
    main()
