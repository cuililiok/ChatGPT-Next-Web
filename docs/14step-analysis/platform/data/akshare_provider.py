"""
AKShare 数据提供者

基于 AKShare 库实现统一数据接口。
"""

import logging
import warnings
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    warnings.warn(
        "akshare 未安装。请运行: pip install akshare\n"
        "AKShareProvider 将不可用。"
    )

try:
    import pandas as pd
except ImportError:
    raise ImportError("pandas 未安装。请运行: pip install pandas")

from .provider import (
    DataProvider, StockInfo, PriceData,
    FinancialData, ValuationData
)

logger = logging.getLogger(__name__)


class AKShareProvider(DataProvider):
    """
    AKShare 数据提供者

    主要数据源，用于获取 A 股行情、财务、估值等数据。
    """

    def __init__(self, timeout: int = 30, max_retry: int = 3):
        if not AKSHARE_AVAILABLE:
            raise ImportError("akshare 未安装，无法使用 AKShareProvider")
        self.timeout = timeout
        self.max_retry = max_retry

    def get_stock_info(self, ticker: str) -> StockInfo:
        try:
            info = ak.stock_individual_info_em(symbol=ticker)
            info_dict = dict(zip(info["item"], info["value"]))
            total_shares = None
            for k in ["总股本", "总股本（股）"]:
                if k in info_dict:
                    v = str(info_dict[k]).replace(",", "")
                    if "亿" in v:
                        total_shares = float(v.replace("亿", ""))
                    else:
                        try:
                            total_shares = float(v) / 1e8
                        except ValueError:
                            pass
                    break
            return StockInfo(
                ticker=ticker,
                name=info_dict.get("股票简称", ""),
                market="A股",
                industry=info_dict.get("行业", ""),
                list_date=info_dict.get("上市时间", None),
                total_shares=total_shares,
                float_shares=None
            )
        except Exception as e:
            logger.error(f"获取股票信息失败 [{ticker}]: {e}")
            raise

    def get_price_data(self, ticker: str, start_date: str, end_date: str, adjust: str = "qfq") -> "pd.DataFrame":
        try:
            df = ak.stock_zh_a_hist(
                symbol=ticker, period="daily",
                start_date=start_date, end_date=end_date,
                adjust=adjust if adjust != "none" else ""
            )
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "日期": "date", "开盘": "open", "最高": "high",
                    "最低": "low", "收盘": "close",
                    "成交量": "volume", "成交额": "amount"
                })
                df["date"] = pd.to_datetime(df["date"])
            return df
        except Exception as e:
            logger.error(f"获取行情数据失败 [{ticker}]: {e}")
            raise

    def get_financial_data(self, ticker: str, years: int = 5) -> List[FinancialData]:
        try:
            df = ak.stock_financial_abstract_ths(symbol=ticker, indicator="按年度")
            if df is None or df.empty:
                return []
            df["year"] = df["报告期"].astype(str).str[:4].astype(int)
            current_year = datetime.now().year
            df = df[df["year"] >= current_year - years]
            results = []
            for _, row in df.iterrows():
                results.append(FinancialData(
                    ticker=ticker, year=int(row["year"]), quarter=4,
                    revenue=self._safe_float(row, "营业总收入", 0) / 1e8,
                    net_profit=self._safe_float(row, "净利润", 0) / 1e8,
                    gross_margin=self._safe_float(row, "毛利率", 0),
                    net_margin=self._safe_float(row, "净利率", 0),
                    roe=self._safe_float(row, "净资产收益率", 0),
                    debt_ratio=self._safe_float(row, "资产负债率", 0),
                    eps=self._safe_float(row, "基本每股收益", 0),
                    operating_cashflow=self._safe_float(row, "经营活动产生的现金流量净额", 0) / 1e8,
                    total_assets=self._safe_float(row, "总资产", 0) / 1e8,
                    total_equity=self._safe_float(row, "净资产", 0) / 1e8,
                    book_value_per_share=self._safe_float(row, "每股净资产", 0)
                ))
            return results
        except Exception as e:
            logger.error(f"获取财务数据失败 [{ticker}]: {e}")
            raise

    def get_valuation_data(self, ticker: str) -> ValuationData:
        try:
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == ticker]
            if row.empty:
                raise ValueError(f"未找到股票 {ticker}")
            row = row.iloc[0]
            return ValuationData(
                ticker=ticker, date=datetime.now().strftime("%Y-%m-%d"),
                pe_ratio=float(row.get("市盈率-动态", 0) or 0),
                pb_ratio=float(row.get("市净率", 0) or 0),
                ps_ratio=0, market_cap=float(row.get("总市值", 0) or 0) / 1e8,
                ev=0, ev_ebitda=0
            )
        except Exception as e:
            logger.error(f"获取估值数据失败 [{ticker}]: {e}")
            raise

    def get_annual_avg_price(self, ticker: str, years: int = 10) -> "pd.DataFrame":
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=365 * (years + 2))
        df = self.get_price_data(ticker, start_dt.strftime("%Y%m%d"), end_dt.strftime("%Y%m%d"), "qfq")
        if df is None or df.empty:
            raise RuntimeError(f"无法获取 {ticker} 的历史行情")
        df["year"] = df["date"].dt.year
        result = df.groupby("year")["close"].mean().reset_index()
        result.columns = ["year", "avg_price"]
        return result

    def get_industry_data(self, industry: str) -> Dict[str, Any]:
        logger.warning("行业数据获取为简化实现")
        return {"industry": industry, "avg_pe": None, "avg_pb": None, "companies": []}

    def get_peer_comparison(self, ticker: str, peers: List[str]) -> "pd.DataFrame":
        all_tickers = [ticker] + peers
        rows = []
        for t in all_tickers:
            try:
                val = self.get_valuation_data(t)
                rows.append({"ticker": t, "pe": val.pe_ratio, "pb": val.pb_ratio, "market_cap": val.market_cap})
            except Exception as e:
                logger.warning(f"获取 {t} 对比数据失败: {e}")
        return pd.DataFrame(rows)

    def _safe_float(self, row, col: str, default: float = 0) -> float:
        try:
            val = row.get(col, default)
            if val is None or str(val).strip() in ("", "--", "N/A"):
                return default
            return float(str(val).replace(",", "").replace("亿", ""))
        except (ValueError, TypeError):
            return default
