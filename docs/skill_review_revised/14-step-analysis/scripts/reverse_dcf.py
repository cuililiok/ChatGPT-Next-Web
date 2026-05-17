#!/usr/bin/env python3
"""
反向 DCF (market-implied valuation)

输入：当前市值 + WACC + 终值 g + 终值 ROIC + 利润率路径 + 基础股本
输出：使 DCF 等于当前市值的市场隐含收入 CAGR（默认）或终值利润率（备选）

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

输出：估算市场隐含收入 CAGR 及对应的几个关键中间变量。
"""

import argparse
import sys


def dcf_value(revenue_y0, revenue_cagr, years, margin_y5, margin_terminal,
              sales_to_capital, tax, wacc, g_terminal):
    """三阶段简化 FCFF DCF。返回 EV。"""
    # 利润率从 Y0 当前值（先用 margin_y5 的 60% 作为简易起点）线性收敛
    # 这里用更稳健的实现：margin 从 margin_y5 起，到第 5 年达到 margin_y5，再向 margin_terminal 收敛
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


def solve_for_revenue_cagr(target_ev, low=-0.10, high=0.50, **kwargs):
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


def solve_for_terminal_margin(target_ev, low=0.0, high=0.60, **kwargs):
    """二分法求解使 DCF EV 等于目标 EV 的终值利润率。kwargs 不能包含 margin_terminal。"""
    for _ in range(80):
        mid = (low + high) / 2
        v = dcf_value(margin_terminal=mid, **kwargs)
        if v > target_ev:
            high = mid
        else:
            low = mid
        if abs(high - low) < 1e-7:
            break
    return (low + high) / 2


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
    p.add_argument("--sales-to-capital", type=float, default=1.5, help="Sales/Capital（默认 1.5）")
    p.add_argument("--tax", type=float, default=0.25, help="有效税率（默认 0.25）")
    p.add_argument("--years", type=int, default=10, help="预测期年数（默认 10）")
    p.add_argument("--solve", choices=["revenue-cagr", "terminal-margin"],
                   default="revenue-cagr",
                   help="求解的变量：market-implied 收入 CAGR 或终值利润率")
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
    else:
        if args.margin_terminal is not None:
            print("WARN: 求解 terminal-margin 时 --margin-terminal 会被忽略", file=sys.stderr)
        # 这里假设 revenue-cagr 已知，请通过下一个参数指定（默认 0.10）
        cagr = 0.10
        kw = dict(base_kwargs, revenue_cagr=cagr)
        # 但是 dcf_value 既需要 revenue_cagr 又需要 margin_terminal——重写：
        def dcf_only_margin(margin_terminal):
            return dcf_value(revenue_cagr=cagr, margin_terminal=margin_terminal, **base_kwargs)
        # 二分
        low, high = 0.0, 0.6
        for _ in range(80):
            mid = (low + high) / 2
            if dcf_only_margin(mid) > target_ev:
                high = mid
            else:
                low = mid
        m = (low + high) / 2
        print("=" * 60)
        print("反向 DCF：求市场隐含终值利润率")
        print("=" * 60)
        print(f"假设 收入 CAGR = {cagr*100:.1f}%")
        print(f"市场隐含终值利润率 = {m * 100:.2f}%")


if __name__ == "__main__":
    main()
