"""
新浪数据提供者（Fallback）

当 AKShare 不可用时，作为备用数据源。
使用新浪财经日 K 线 API 获取行情数据。
"""

import json
import logging
import warnings
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    raise ImportError("requests 未安装。请运行: pip install requests")

try:
    import pandas as pd
except ImportError:
    raise ImportError("pandas 未安装。请运行: pip install pandas")

from .provider import (
    DataProvider, StockInfo, PriceData,
    FinancialData, ValuationData
)

logger = logging.getLogger(__name__)


class SinaProvider(DataProvider):
    """
    新浪财经数据提供者（Fallback）

    仅提供行情数据，其他接口需要 AKShare。
    """

    BASE_URL = (
        "http://money.finance.sina.com.cn/quotes_service/api/"
        "json_v2.php/CN_MarketData.getKLineData"
    )

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def _get_symbol(self, ticker: str) -> str:
        prefix = "sh" if ticker.startswith(("6", "9")) else "sz"
        return f"{prefix}{ticker}"

    def get_stock_info(self, ticker: str) -> StockInfo:
        return StockInfo(ticker=ticker, name="", market="A股", industry="")

    def get_price_data(self, ticker: str, start_date: str, end_date: str, adjust: str = "qfq") -> "pd.DataFrame":
        symbol = self._get_symbol(ticker)
        params = {"symbol": symbol, "scale": "240", "ma": "no", "datalen": "5000"}
        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            text = resp.text.strip()
            if not text or text == "null":
                raise RuntimeError("新浪返回空数据")
            data = json.loads(text)
            if not data:
                raise RuntimeError("新浪返回空列表")
            df = pd.DataFrame(data)
            df = df.rename(columns={"day": "date"})
            df["date"] = pd.to_datetime(df["date"])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
            if start_date:
                try:
                    df = df[df["date"] >= pd.to_datetime(start_date)]
                except Exception:
                    pass
            if end_date:
                try:
                    df = df[df["date"] <= pd.to_datetime(end_date)]
                except Exception:
                    pass
            return df
        except Exception as e:
            logger.error(f"新浪日K线获取失败 [{ticker}]: {e}")
            raise

    def get_financial_data(self, ticker: str, years: int = 5) -> List[FinancialData]:
        logger.warning("SinaProvider 不支持财务数据获取，请使用 AKShareProvider")
        return []

    def get_valuation_data(self, ticker: str) -> ValuationData:
        logger.warning("SinaProvider 不支持估值数据获取，请使用 AKShareProvider")
        return ValuationData(ticker=ticker, date=datetime.now().strftime("%Y-%m-%d"),
                            pe_ratio=0, pb_ratio=0, ps_ratio=0, market_cap=0, ev=0, ev_ebitda=0)

    def get_annual_avg_price(self, ticker: str, years: int = 10) -> "pd.DataFrame":
        df = self.get_price_data(ticker, "", "")
        if df is None or df.empty:
            raise RuntimeError(f"新浪数据源无法获取 {ticker} 行情")
        df["year"] = df["date"].dt.year
        current_year = datetime.now().year
        df = df[df["year"] >= current_year - years]
        result = df.groupby("year")["close"].mean().reset_index()
        result.columns = ["year", "avg_price"]
        return result

    def get_industry_data(self, industry: str) -> Dict[str, Any]:
        logger.warning("SinaProvider 不支持行业数据获取")
        return {"industry": industry}

    def get_peer_comparison(self, ticker: str, peers: List[str]) -> "pd.DataFrame":
        logger.warning("SinaProvider 不支持同业对比数据获取")
        return pd.DataFrame()
