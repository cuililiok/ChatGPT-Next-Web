"""
数据提供者接口

定义统一的数据获取接口。
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import pandas as pd


@dataclass
class StockInfo:
    """股票基本信息"""
    ticker: str
    name: str
    market: str  # A股/港股/美股
    industry: str
    list_date: Optional[str] = None
    total_shares: Optional[float] = None  # 总股本（亿股）
    float_shares: Optional[float] = None  # 流通股本（亿股）


@dataclass
class PriceData:
    """行情数据"""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    adj_factor: float = 1.0  # 复权因子


@dataclass
class FinancialData:
    """财务数据"""
    ticker: str
    year: int
    quarter: int
    revenue: float  # 营业收入（亿）
    net_profit: float  # 净利润（亿）
    gross_margin: float  # 毛利率
    net_margin: float  # 净利率
    roe: float  # ROE
    debt_ratio: float  # 资产负债率
    eps: float  # EPS
    operating_cashflow: float  # 经营现金流（亿）
    total_assets: float  # 总资产（亿）
    total_equity: float  # 净资产（亿）
    book_value_per_share: float  # 每股净资产


@dataclass
class ValuationData:
    """估值数据"""
    ticker: str
    date: str
    pe_ratio: float  # PE
    pb_ratio: float  # PB
    ps_ratio: float  # PS
    market_cap: float  # 市值（亿）
    ev: float  # 企业价值（亿）
    ev_ebitda: float  # EV/EBITDA


class DataProvider(ABC):
    """
    数据提供者接口

    所有数据提供者必须实现此接口。
    """

    @abstractmethod
    def get_stock_info(self, ticker: str) -> StockInfo:
        """
        获取股票基本信息

        Args:
            ticker: 股票代码

        Returns:
            股票基本信息
        """
        pass

    @abstractmethod
    def get_price_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> pd.DataFrame:
        """
        获取行情数据

        Args:
            ticker: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权方式 (qfq/hfq/none)

        Returns:
            行情数据 DataFrame
        """
        pass

    @abstractmethod
    def get_financial_data(
        self,
        ticker: str,
        years: int = 5
    ) -> List[FinancialData]:
        """
        获取财务数据

        Args:
            ticker: 股票代码
            years: 年数

        Returns:
            财务数据列表
        """
        pass

    @abstractmethod
    def get_valuation_data(self, ticker: str) -> ValuationData:
        """
        获取估值数据

        Args:
            ticker: 股票代码

        Returns:
            估值数据
        """
        pass

    @abstractmethod
    def get_annual_avg_price(
        self,
        ticker: str,
        years: int = 10
    ) -> pd.DataFrame:
        """
        获取年度均价

        Args:
            ticker: 股票代码
            years: 年数

        Returns:
            年度均价 DataFrame
        """
        pass

    @abstractmethod
    def get_industry_data(self, industry: str) -> Dict[str, Any]:
        """
        获取行业数据

        Args:
            industry: 行业名称

        Returns:
            行业数据字典
        """
        pass

    @abstractmethod
    def get_peer_comparison(
        self,
        ticker: str,
        peers: List[str]
    ) -> pd.DataFrame:
        """
        获取同业对比数据

        Args:
            ticker: 股票代码
            peers: 同业股票代码列表

        Returns:
            同业对比 DataFrame
        """
        pass

    def validate_ticker(self, ticker: str) -> bool:
        """
        验证股票代码

        Args:
            ticker: 股票代码

        Returns:
            是否有效
        """
        try:
            self.get_stock_info(ticker)
            return True
        except Exception:
            return False

    def get_data_source(self) -> str:
        """
        获取数据源名称

        Returns:
            数据源名称
        """
        return self.__class__.__name__
