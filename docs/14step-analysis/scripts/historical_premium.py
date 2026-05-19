#!/usr/bin/env python3
"""
历史隐含增长率分位 (historical implied-g percentile)

给定一只 A 股股票，自动从 AKShare 拉取 ≥ 10 年的财务数据 + 年均价，
对每个时点重做反向 DCF（用当时的财务数据 + 当时的股价），输出 implied_g 时间序列、
P25/P50/P75 分位、当前位置，以及 markdown 格式的表格供报告使用。

数据源优先级：
  1. AKShare（主源）— stock_financial_abstract_ths + stock_zh_a_hist
  2. 新浪日 K 线 API（fallback）— AKShare 失败时自动切换

缺失年份不打断序列，输出 "10 年中可用 X 年"，
图表标注 "基于 X 个数据点的分位数"，少于 5 个点时改用同业均值参考。

用法：
  python historical_premium.py \
      --stock 600519 \
      --wacc 0.085 \
      --g-terminal 0.022 \
      --margin-terminal 0.55 \
      --sales-to-capital 2.0 \
      --tax 0.25 \
      --years 10

依赖：akshare, pandas, requests（fallback 用）
"""

import argparse
import datetime
import subprocess
import sys
import re
import warnings

def ensure(pkg, import_name=None):
    try:
        __import__(import_name or pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg,
                               "--break-system-packages", "-q"])

ensure("akshare")
ensure("pandas")
ensure("requests")

import akshare as ak
import pandas as pd
import requests


# ==============================================================================
# 数据获取层：主源 AKShare + Fallback 新浪日 K 线
# ==============================================================================

def _fetch_sina_daily(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    从新浪日 K 线 API 拉取前复权日行情数据。
    stock_code: 6 位 A 股代码，如 "600519"
    返回 DataFrame，列 ['date', 'open', 'high', 'low', 'close', 'volume']
    """
    # 新浪接口区分沪市(sh)和深市(sz)
    prefix = "sh" if stock_code.startswith(("6", "9")) else "sz"
    symbol = f"{prefix}{stock_code}"

    params = {
        "symbol": symbol,
        "end_date": end_date.replace("-", ""),
        "begin_date": start_date.replace("-", ""),
    }
    url = "https://finance.sina.com.cn/realstock/company/{}/hisdata/klc_kl.js".format(symbol)

    # 尝试 CSV 接口
    csv_url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    csv_params = {
        "symbol": symbol,
        "scale": "240",  # 日线
        "ma": "no",
        "datalen": "5000",
    }
    try:
        resp = requests.get(csv_url, params=csv_params, timeout=15)
        resp.raise_for_status()
        text = resp.text.strip()
        if not text or text == "null":
            raise RuntimeError("新浪返回空数据")

        # 解析 JSON 格式：[{day:"2025-01-02",open:"xx",high:"xx",low:"xx",close:"xx",volume:"xx"}, ...]
        import json
        data = json.loads(text)
        if not data:
            raise RuntimeError("新浪返回空列表")

        df = pd.DataFrame(data)
        df = df.rename(columns={"day": "date"})
        df["date"] = pd.to_datetime(df["date"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close"])
        df = df.sort_values("date").reset_index(drop=True)
        return df
    except Exception as e:
        warnings.warn(f"新浪日K线获取失败: {e}")
        return pd.DataFrame()


def fetch_annual_revenue(stock: str) -> pd.DataFrame:
    """从 AKShare 拉取年度收入序列。返回 DataFrame，列 ['year', 'revenue']（亿元）。"""
    df = ak.stock_financial_abstract_ths(symbol=stock, indicator="按年度")
    df = df.copy()
    df["year"] = df["报告期"].astype(str).str[:4].astype(int)
    rev_col = None
    for c in df.columns:
        if "营业总收入" in c or "营业收入" in c:
            rev_col = c
            break
    if rev_col is None:
        raise RuntimeError("未找到营业收入字段")
    df[rev_col] = df[rev_col].astype(str).str.replace(",", "").str.replace("亿", "")
    df["revenue"] = pd.to_numeric(df[rev_col], errors="coerce")
    return df[["year", "revenue"]].dropna().sort_values("year")


def fetch_annual_avg_price(stock: str, years_back: int = 10) -> pd.DataFrame:
    """
    拉取年度均价（前复权）。
    主源：AKShare stock_zh_a_hist。失败时 fallback 到新浪日 K 线。
    返回 DataFrame，列 ['year', 'avg_price']。
    """
    end_dt = datetime.date.today()
    start_dt = end_dt - datetime.timedelta(days=365 * (years_back + 2))
    start_str = start_dt.strftime("%Y%m%d")
    end_str = end_dt.strftime("%Y%m%d")

    # 主源：AKShare
    try:
        df = ak.stock_zh_a_hist(symbol=stock, period="daily", adjust="qfq",
                                start_date=start_str, end_date=end_str)
        if df is not None and not df.empty:
            df = df.copy()
            df["year"] = pd.to_datetime(df["日期"]).dt.year
            g = df.groupby("year")["收盘"].mean().reset_index()
            g.columns = ["year", "avg_price"]
            return g, "akshare"
    except Exception as e:
        warnings.warn(f"AKShare 日行情获取失败: {e}，切换到新浪 fallback")

    # Fallback：新浪日 K 线
    try:
        start_fmt = start_dt.strftime("%Y-%m-%d")
        end_fmt = end_dt.strftime("%Y-%m-%d")
        df = _fetch_sina_daily(stock, start_fmt, end_fmt)
        if not df.empty:
            df["year"] = df["date"].dt.year
            g = df.groupby("year")["close"].mean().reset_index()
            g.columns = ["year", "avg_price"]
            return g, "sina"
    except Exception as e:
        warnings.warn(f"新浪 fallback 也失败: {e}")

    raise RuntimeError("所有数据源均失败，无法获取历史行情")


def fetch_total_shares(stock: str) -> float:
    """拉取最新总股本（亿股）。"""
    try:
        info = ak.stock_individual_info_em(symbol=stock)
        info = dict(zip(info["item"], info["value"]))
        for k in ["总股本", "总股本（股）"]:
            if k in info:
                try:
                    v = str(info[k]).replace(",", "")
                    # 处理 "X.XX亿" 格式
                    if "亿" in v:
                        return float(v.replace("亿", ""))
                    return float(v) / 1e8
                except Exception:
                    pass
    except Exception as e:
        warnings.warn(f"获取总股本失败: {e}")
    return None


# ==============================================================================
# DCF 引擎（与 reverse_dcf.py 保持一致）
# ==============================================================================

def dcf_value(revenue_y0, revenue_cagr, years, margin_y5, margin_terminal,
              sales_to_capital, tax, wacc, g_terminal):
    margins = []
    margin_y0 = margin_y5 * 0.7
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

    if wacc <= g_terminal:
        return float("inf")
    tv_fcff = last_fcff * (1 + g_terminal)
    tv = tv_fcff / (wacc - g_terminal)
    pv_tv = tv / ((1 + wacc) ** years)
    return pv_fcff + pv_tv


def solve_implied_cagr(target_ev, **kwargs):
    low, high = -0.20, 0.60
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


# ==============================================================================
# 主流程
# ==============================================================================

def main():
    p = argparse.ArgumentParser(description="历史隐含增长率分位")
    p.add_argument("--stock", required=True, help="A 股 6 位代码，如 600519")
    p.add_argument("--wacc", type=float, required=True)
    p.add_argument("--g-terminal", type=float, required=True)
    p.add_argument("--margin-y5", type=float, default=None,
                   help="Y5 EBIT 利润率（默认用当年实际营业利润率）")
    p.add_argument("--margin-terminal", type=float, required=True)
    p.add_argument("--sales-to-capital", type=float, default=1.5)
    p.add_argument("--tax", type=float, default=0.25)
    p.add_argument("--years", type=int, default=10)
    p.add_argument("--years-back", type=int, default=10, help="历史回看年数（默认 10）")
    args = p.parse_args()

    print(f"[INFO] 拉取 {args.stock} 数据...", file=sys.stderr)

    # 拉取收入数据
    try:
        rev = fetch_annual_revenue(args.stock)
    except Exception as e:
        print(f"[ERROR] 收入数据获取失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 拉取行情数据（AKShare → 新浪 fallback）
    data_source = None
    try:
        price, data_source = fetch_annual_avg_price(args.stock, args.years_back)
    except Exception as e:
        print(f"[ERROR] 行情数据获取失败: {e}", file=sys.stderr)
        sys.exit(1)

    shares = fetch_total_shares(args.stock)
    if shares is None:
        print("[ERROR] 无法获取总股本", file=sys.stderr)
        sys.exit(1)

    # 合并
    df = rev.merge(price, on="year", how="inner")
    df = df.tail(args.years_back).reset_index(drop=True)

    # 计算目标年数中可用的数据点数
    target_years = list(range(df["year"].min(), df["year"].max() + 1))
    available_years = sorted(df["year"].tolist())
    missing_years = [y for y in target_years if y not in available_years]

    rows = []
    for _, r in df.iterrows():
        market_cap = r["avg_price"] * shares  # 亿元
        if pd.isna(market_cap) or pd.isna(r["revenue"]):
            continue
        margin_y5 = args.margin_y5 if args.margin_y5 is not None else 0.18
        kw = dict(
            revenue_y0=float(r["revenue"]),
            years=args.years,
            margin_y5=margin_y5,
            margin_terminal=args.margin_terminal,
            sales_to_capital=args.sales_to_capital,
            tax=args.tax,
            wacc=args.wacc,
            g_terminal=args.g_terminal,
        )
        try:
            cagr = solve_implied_cagr(target_ev=market_cap, **kw)
            rows.append({
                "year": int(r["year"]),
                "avg_price": round(float(r["avg_price"]), 2),
                "revenue": round(float(r["revenue"]), 2),
                "market_cap": round(market_cap, 2),
                "implied_g_pct": round(cagr * 100, 2),
            })
        except Exception:
            pass

    if not rows:
        print("[ERROR] 没有可用历史数据", file=sys.stderr)
        sys.exit(1)

    n_points = len(rows)
    n_target = len(target_years)
    data_quality = f"{n_points}/{n_target} 年可用"
    if missing_years:
        data_quality += f"，缺失 {missing_years}"

    out = pd.DataFrame(rows).sort_values("year")
    print()
    print("# 历史隐含增长率分位")
    print()
    print(f"股票: {args.stock}")
    print(f"WACC: {args.wacc*100:.2f}% | 终值 g: {args.g_terminal*100:.2f}% | "
          f"终值利润率: {args.margin_terminal*100:.1f}% | Sales/Capital: {args.sales_to_capital}")
    print(f"数据源: {data_source} | 数据质量: {data_quality}")
    print()

    # 数据点不足警告
    if n_points < 5:
        print(f"**[WARN] 仅 {n_points} 个数据点，分位数统计不可靠。建议改用同业均值参考。**")
        print()

    print("| 年份 | 当年均价 | 当年收入(亿) | 当年市值(亿) | 隐含 g (%) |")
    print("|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['year']} | {r['avg_price']} | {r['revenue']} | "
              f"{r['market_cap']} | {r['implied_g_pct']} |")

    s = out["implied_g_pct"]
    print()
    print(f"基于 {n_points} 个数据点的分位数：")
    print(f"  P25  = {s.quantile(0.25):.2f}%")
    print(f"  P50  = {s.quantile(0.50):.2f}%")
    print(f"  P75  = {s.quantile(0.75):.2f}%")
    print(f"  当前 (最近一年) = {s.iloc[-1]:.2f}%")
    cur_pct = (s.iloc[-1] > s).mean() * 100
    print(f"  当前分位 ≈ P{cur_pct:.0f}")
    print()
    if cur_pct < 25:
        print("→ 市场对该股票当前预期处于历史悲观区，参考 12.8.4 四象限决策")
    elif cur_pct > 75:
        print("→ 市场对该股票当前预期处于历史乐观区，参考 12.8.4 四象限决策")
    else:
        print("→ 市场对该股票当前预期处于历史中性区")


if __name__ == "__main__":
    main()
