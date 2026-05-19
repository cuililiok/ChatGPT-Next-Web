#!/usr/bin/env python3
"""
反向 DCF (market-implied valuation) - v2 修复版

输入：当前市值 + WACC + 终值 g + 终值 ROIC + 利润率路径 + 基础股本
输出：使 DCF 等于当前市值的市场隐含收入 CAGR（默认）或终值利润率（备选）

v2 修复：
  1. terminal-margin 求解路径现在支持 --revenue-cagr 参数
  2. 添加类型注解
  3. 改进错误处理

数学逻辑（标准 Damodaran 三阶段 FCFF DCF）：
  Y0 收入 → Y1..YN 收入 = Y0 × (1+g)^t；
  EBIT_t = Revenue_t × margin_t；
  NOPAT_t = EBIT_t × (1 - tax)；
  ΔIC_t = (Revenue_{t} - Revenue_{t-1}) / sales_to_capital；
  FCFF_t = NOPAT_t - ΔIC_t；
  TV = FCFF_{N+1} / (WACC - g_terminal)；
  EV = Σ FCFF_t / (1+WACC)^t + TV / (1+WACC)^N

用法示例（命令行）：
  python reverse_dcf.py \
      --market-cap 1500 \
      --net-debt -200 \
      --revenue-y0 800 \
      --wacc 0.078 \
      --g-terminal 0.022 \
      --margin-y5 0.18 \
      --margin-terminal 0.20 \
      --sales-to-capital 1.5 \
      --tax 0.25 \
      --years 10 \
      --solve revenue-cagr

带敏感性分析：
  python reverse_dcf.py \
      --market-cap 1500 \
      --net-debt -200 \
      --revenue-y0 800 \
      --wacc 0.078 \
      --g-terminal 0.022 \
      --margin-y5 0.18 \
      --margin-terminal 0.20 \
      --sales-to-capital 1.5 \
      --tax 0.25 \
      --years 10 \
      --solve revenue-cagr \
      --sensitivity

求解终值利润率（需指定收入 CAGR）：
  python reverse_dcf.py \
      --market-cap 1500 \
      --net-debt -200 \
      --revenue-y0 800 \
      --wacc 0.078 \
      --g-terminal 0.022 \
      --margin-y5 0.18 \
      --revenue-cagr 0.10 \
      --sales-to-capital 1.5 \
      --tax 0.25 \
      --years 10 \
      --solve terminal-margin

输出：估算市场隐含收入 CAGR 及对应的几个关键中间变量。
启用 --sensitivity 时额外输出 WACC±100bps × g终±50bps 的 3×3 敏感性表格。
"""

import argparse
import sys
import logging
from typing import Optional, Tuple, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def dcf_value(
    revenue_y0: float,
    revenue_cagr: float,
    years: int,
    margin_y5: float,
    margin_terminal: float,
    sales_to_capital: float,
    tax: float,
    wacc: float,
    g_terminal: float
) -> float:
    """三阶段简化 FCFF DCF。返回 EV。"""
    # 利润率从 Y0 当前值（先用 margin_y5 的 70% 作为简易起点）线性收敛
    margins = []
    margin_y0 = margin_y5 * 0.7  # 起点：略低于 Y5 利润率
    for t in range(1, years + 1):
        if t <= 5:
            m = margin_y0 + (margin_y5 - margin_y0) * (t / 5)
        else:
            m = margin_y5 + (margin_terminal - margin_y5) * ((t - 5) / max(years - 5, 1))
        margins.append(m)

    revenues = [revenue_y0 * ((1 + revenue_cagr) ** t) for t in range(1, years + 1)]
    revenues_with_y0 = [revenue_y0] + revenues

    pv_fcff = 0.0
    last_fcff = 0.0
    for t in range(1, years + 1):
        rev = revenues[t - 1]
        ebit = rev * margins[t - 1]
        nopat = ebit * (1 - tax)
        delta_ic = (revenues_with_y0[t] - revenues_with_y0[t - 1]) / sales_to_capital
        fcff = nopat - delta_ic
        pv = fcff / ((1 + wacc) ** t)
        pv_fcff += pv
        if t == years:
            last_fcff = fcff

    # 终值：FCFF_{N+1} ≈ FCFF_N × (1 + g_terminal)
    tv_fcff = last_fcff * (1 + g_terminal)
    if wacc <= g_terminal:
        return float("inf")
    tv = tv_fcff / (wacc - g_terminal)
    pv_tv = tv / ((1 + wacc) ** years)

    return pv_fcff + pv_tv


def solve_for_revenue_cagr(
    target_ev: float,
    low: float = -0.10,
    high: float = 0.50,
    **kwargs
) -> float:
    """二分法求解使 DCF EV 等于目标 EV 的收入 CAGR。"""
    for _ in range(80):
        mid = (low + high) / 2
        v = dcf_value(revenue_cagr=mid, **kwargs)
        if v > target_ev:
            high = mid
        else:
            low = mid
        if abs(high - low) < 1e-6:
            break
    return (low + high) / 2


def solve_for_terminal_margin(
    target_ev: float,
    revenue_cagr: float,
    low: float = 0.0,
    high: float = 0.60,
    **kwargs
) -> float:
    """二分法求解使 DCF EV 等于目标 EV 的终值利润率。"""
    for _ in range(80):
        mid = (low + high) / 2
        v = dcf_value(margin_terminal=mid, revenue_cagr=revenue_cagr, **kwargs)
        if v > target_ev:
            high = mid
        else:
            low = mid
        if abs(high - low) < 1e-7:
            break
    return (low + high) / 2


def run_sensitivity(
    target_ev: float,
    base_wacc: float,
    base_g_terminal: float,
    base_kwargs: dict
) -> Tuple[List[List[Optional[float]]], Optional[float], Optional[float]]:
    """
    WACC±100bps × g终±50bps 的 3×3 敏感性表。
    返回 (grid, lo, hi)，其中 grid 是 3×3 list of float（百分比），lo/hi 是稳健区间。
    """
    wacc_deltas = [-0.01, 0.0, 0.01]
    g_deltas = [-0.005, 0.0, 0.005]
    grid = []
    for gd in g_deltas:
        row = []
        for wd in wacc_deltas:
            w = base_wacc + wd
            g = base_g_terminal + gd
            if w <= g:
                row.append(None)  # 数学上无解
            else:
                kw = dict(base_kwargs, wacc=w, g_terminal=g)
                cagr = solve_for_revenue_cagr(target_ev=target_ev, **kw)
                row.append(cagr * 100)
        grid.append(row)

    # 计算稳健区间（排除 None）
    vals = [v for row in grid for v in row if v is not None]
    lo = min(vals) if vals else None
    hi = max(vals) if vals else None
    return grid, lo, hi


def format_sensitivity_table(
    grid: List[List[Optional[float]]],
    lo: Optional[float],
    hi: Optional[float],
    base_wacc: float,
    base_g_terminal: float
) -> str:
    """格式化 3×3 敏感性表格为 markdown。"""
    wacc_deltas = [-0.01, 0.0, 0.01]
    g_deltas = [-0.005, 0.0, 0.005]

    lines = []
    lines.append("")
    lines.append("### 敏感性分析：WACC × g终 对市场隐含 g 的影响")
    lines.append("")
    lines.append("|  | WACC {:.2f}% | WACC {:.2f}% (基准) | WACC {:.2f}% |".format(
        (base_wacc - 0.01) * 100, base_wacc * 100, (base_wacc + 0.01) * 100))
    lines.append("|---|---|---|---|")
    g_labels = [
        "g终 {:.2f}%".format((base_g_terminal - 0.005) * 100),
        "g终 {:.2f}% (基准)".format(base_g_terminal * 100),
        "g终 {:.2f}%".format((base_g_terminal + 0.005) * 100),
    ]
    for i, label in enumerate(g_labels):
        cells = []
        for j in range(3):
            v = grid[i][j]
            if v is None:
                cells.append("N/A")
            elif i == 1 and j == 1:
                cells.append("{:.2f}% ★".format(v))
            else:
                cells.append("{:.2f}%".format(v))
        lines.append("| {} | {} |".format(label, " | ".join(cells)))

    lines.append("")
    lines.append("★ = 基准情景")
    if lo is not None and hi is not None:
        lines.append("市场隐含 g 稳健区间：[ {:.2f}%, {:.2f}% ] ( {:.1f} ppt )".format(
            lo, hi, hi - lo))
    lines.append("")
    lines.append("⚠ 你应该信任的是 delta（你的假设 vs 市场假设），不是绝对值。")
    lines.append("")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="反向 DCF：从当前市值反推市场隐含假设")
    p.add_argument("--market-cap", type=float, required=True, help="当前股权市值（亿元）")
    p.add_argument("--net-debt", type=float, default=0.0, help="净负债（亿元；负数表示净现金）")
    p.add_argument("--revenue-y0", type=float, required=True, help="Y0（最近完整财年）收入（亿元）")
    p.add_argument("--wacc", type=float, required=True, help="WACC（小数，如 0.078）")
    p.add_argument("--g-terminal", type=float, required=True, help="终值 g（小数，如 0.022）")
    p.add_argument("--margin-y5", type=float, required=True, help="Y5 EBIT 利润率（小数）")
    p.add_argument("--margin-terminal", type=float, default=None,
                   help="终值 EBIT 利润率（小数；当 solve=revenue-cagr 时必填）")
    p.add_argument("--revenue-cagr", type=float, default=None,
                   help="收入 CAGR（小数；当 solve=terminal-margin 时必填）")
    p.add_argument("--sales-to-capital", type=float, default=1.5, help="Sales/Capital（默认 1.5）")
    p.add_argument("--tax", type=float, default=0.25, help="有效税率（默认 0.25）")
    p.add_argument("--years", type=int, default=10, help="预测期年数（默认 10）")
    p.add_argument("--solve", choices=["revenue-cagr", "terminal-margin"],
                   default="revenue-cagr",
                   help="求解的变量：market-implied 收入 CAGR 或终值利润率")
    p.add_argument("--sensitivity", action="store_true",
                   help="启用敏感性分析：输出 WACC±100bps × g终±50bps 的 3×3 表格")
    args = p.parse_args()

    target_ev = args.market_cap + args.net_debt

    base_kwargs = dict(
        revenue_y0=args.revenue_y0,
        years=args.years,
        margin_y5=args.margin_y5,
        sales_to_capital=args.sales_to_capital,
        tax=args.tax,
        wacc=args.wacc,
        g_terminal=args.g_terminal,
    )

    if args.solve == "revenue-cagr":
        if args.margin_terminal is None:
            print("ERROR: 求解 revenue-cagr 时必须给 --margin-terminal", file=sys.stderr)
            sys.exit(1)
        kw = dict(base_kwargs, margin_terminal=args.margin_terminal)
        cagr = solve_for_revenue_cagr(target_ev=target_ev, **kw)
        ev_check = dcf_value(revenue_cagr=cagr, **kw)
        print("=" * 60)
        print("反向 DCF：求市场隐含收入 CAGR")
        print("=" * 60)
        print(f"输入：")
        print(f"  当前股权市值        = {args.market_cap:.1f} 亿")
        print(f"  净负债             = {args.net_debt:.1f} 亿")
        print(f"  目标 EV            = {target_ev:.1f} 亿")
        print(f"  Y0 收入            = {args.revenue_y0:.1f} 亿")
        print(f"  WACC               = {args.wacc * 100:.2f}%")
        print(f"  终值 g             = {args.g_terminal * 100:.2f}%")
        print(f"  Y5 利润率          = {args.margin_y5 * 100:.2f}%")
        print(f"  终值利润率         = {args.margin_terminal * 100:.2f}%")
        print(f"  Sales/Capital      = {args.sales_to_capital}")
        print(f"  税率               = {args.tax * 100:.0f}%")
        print(f"  预测期             = {args.years} 年")
        print("-" * 60)
        print(f"市场隐含收入 CAGR    = {cagr * 100:.2f}%")
        print(f"对应 DCF EV          = {ev_check:.1f} 亿（目标 {target_ev:.1f}）")
        print("=" * 60)
        print("叙事翻译模板：")
        print(f"  在 WACC={args.wacc*100:.2f}%、终值利润率 {args.margin_terminal*100:.1f}% 的假设下，")
        print(f"  市场目前为这只股票定价隐含的未来 {args.years} 年收入 CAGR ≈ {cagr*100:.2f}%。")
        print(f"  与你的基础假设比较，可以判断市场比你乐观/悲观/合理。")

        # 敏感性分析
        if args.sensitivity:
            sens_kwargs = dict(
                revenue_y0=args.revenue_y0,
                years=args.years,
                margin_y5=args.margin_y5,
                margin_terminal=args.margin_terminal,
                sales_to_capital=args.sales_to_capital,
                tax=args.tax,
            )
            grid, lo, hi = run_sensitivity(target_ev, args.wacc, args.g_terminal, sens_kwargs)
            table = format_sensitivity_table(grid, lo, hi, args.wacc, args.g_terminal)
            print(table)

    else:  # solve == "terminal-margin"
        if args.revenue_cagr is None:
            print("ERROR: 求解 terminal-margin 时必须给 --revenue-cagr", file=sys.stderr)
            sys.exit(1)

        kw = dict(base_kwargs, revenue_cagr=args.revenue_cagr)
        margin = solve_for_terminal_margin(target_ev=target_ev, **kw)
        ev_check = dcf_value(margin_terminal=margin, **kw)

        print("=" * 60)
        print("反向 DCF：求市场隐含终值利润率")
        print("=" * 60)
        print(f"输入：")
        print(f"  当前股权市值        = {args.market_cap:.1f} 亿")
        print(f"  净负债             = {args.net_debt:.1f} 亿")
        print(f"  目标 EV            = {target_ev:.1f} 亿")
        print(f"  Y0 收入            = {args.revenue_y0:.1f} 亿")
        print(f"  WACC               = {args.wacc * 100:.2f}%")
        print(f"  终值 g             = {args.g_terminal * 100:.2f}%")
        print(f"  Y5 利润率          = {args.margin_y5 * 100:.2f}%")
        print(f"  收入 CAGR          = {args.revenue_cagr * 100:.2f}%")
        print(f"  Sales/Capital      = {args.sales_to_capital}")
        print(f"  税率               = {args.tax * 100:.0f}%")
        print(f"  预测期             = {args.years} 年")
        print("-" * 60)
        print(f"市场隐含终值利润率    = {margin * 100:.2f}%")
        print(f"对应 DCF EV          = {ev_check:.1f} 亿（目标 {target_ev:.1f}）")
        print("=" * 60)
        print("叙事翻译模板：")
        print(f"  在 WACC={args.wacc*100:.2f}%、收入 CAGR {args.revenue_cagr*100:.2f}% 的假设下，")
        print(f"  市场目前为这只股票定价隐含的终值利润率 ≈ {margin*100:.2f}%。")
        print(f"  与你的基础假设比较，可以判断市场对盈利能力的预期。")

        # 敏感性分析（terminal-margin 模式暂不支持）
        if args.sensitivity:
            print("\n⚠ 敏感性分析暂不支持 terminal-margin 模式，请使用 revenue-cagr 模式。")


if __name__ == "__main__":
    main()
