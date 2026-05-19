"""
DCF 估值引擎

提供标准 Damodaran 三阶段 FCFF DCF 估值功能。
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DCFInputs:
    """DCF 输入参数"""
    revenue_y0: float  # 初始收入（亿）
    revenue_cagr: float  # 收入 CAGR
    years: int  # 预测年数
    margin_y5: float  # Y5 EBIT 利润率
    margin_terminal: float  # 终值 EBIT 利润率
    sales_to_capital: float  # Sales/Capital
    tax: float  # 有效税率
    wacc: float  # WACC
    g_terminal: float  # 终值增长率
    margin_y0: Optional[float] = None  # Y0 当前利润率（可选，默认用 margin_y5 * 0.7）


@dataclass
class DCFYearlyData:
    """DCF 年度数据"""
    year: int
    revenue: float
    ebit_margin: float
    ebit: float
    nopat: float
    delta_ic: float
    fcff: float
    discount_factor: float
    pv_fcff: float


@dataclass
class DCFResult:
    """DCF 结果"""
    ev: float  # 企业价值
    equity_value: float  # 股权价值
    per_share_value: float  # 每股价值
    terminal_value_pct: float  # 终值占比
    pv_fcff: float  # 预测期 FCFF 现值
    pv_terminal: float  # 终值现值
    yearly_data: List[DCFYearlyData]  # 年度数据
    terminal_growth: float  # 终值增长率
    wacc: float  # WACC
    consistency_check: Dict[str, float]  # 一致性检查


class DCFEngine:
    """
    DCF 估值引擎

    实现标准 Damodaran 三阶段 FCFF DCF。
    """

    def __init__(self):
        """初始化 DCF 引擎"""
        pass

    def calculate(self, inputs: DCFInputs) -> DCFResult:
        """
        执行 DCF 计算

        Args:
            inputs: DCF 输入参数

        Returns:
            DCF 结果
        """
        # 计算利润率路径
        margins = self._calculate_margins(
            inputs.margin_y5,
            inputs.margin_terminal,
            inputs.years,
            margin_y0=inputs.margin_y0
        )

        # 计算收入和 FCFF
        yearly_data = []
        revenue_y0 = inputs.revenue_y0
        pv_fcff = 0.0
        last_fcff = 0.0

        for t in range(1, inputs.years + 1):
            # 收入
            revenue = revenue_y0 * ((1 + inputs.revenue_cagr) ** t)
            revenue_prev = revenue_y0 * ((1 + inputs.revenue_cagr) ** (t - 1))

            # EBIT
            ebit = revenue * margins[t - 1]

            # NOPAT
            nopat = ebit * (1 - inputs.tax)

            # 投资额变化
            delta_ic = (revenue - revenue_prev) / inputs.sales_to_capital

            # FCFF
            fcff = nopat - delta_ic

            # 折现
            discount_factor = 1 / ((1 + inputs.wacc) ** t)
            pv = fcff * discount_factor
            pv_fcff += pv

            if t == inputs.years:
                last_fcff = fcff

            yearly_data.append(DCFYearlyData(
                year=t,
                revenue=revenue,
                ebit_margin=margins[t - 1],
                ebit=ebit,
                nopat=nopat,
                delta_ic=delta_ic,
                fcff=fcff,
                discount_factor=discount_factor,
                pv_fcff=pv
            ))

        # 终值计算
        tv_fcff = last_fcff * (1 + inputs.g_terminal)
        if inputs.wacc <= inputs.g_terminal:
            raise ValueError("WACC 必须大于终值增长率")

        tv = tv_fcff / (inputs.wacc - inputs.g_terminal)
        pv_tv = tv / ((1 + inputs.wacc) ** inputs.years)

        # 企业价值
        ev = pv_fcff + pv_tv

        # 终值占比
        terminal_pct = pv_tv / ev if ev > 0 else 0

        # 一致性检查
        consistency = self._check_consistency(inputs, yearly_data)

        return DCFResult(
            ev=ev,
            equity_value=ev,  # 需要后续减去净负债
            per_share_value=0,  # 需要后续除以股本
            terminal_value_pct=terminal_pct,
            pv_fcff=pv_fcff,
            pv_terminal=pv_tv,
            yearly_data=yearly_data,
            terminal_growth=inputs.g_terminal,
            wacc=inputs.wacc,
            consistency_check=consistency
        )

    def _calculate_margins(
        self,
        margin_y5: float,
        margin_terminal: float,
        years: int,
        margin_y0: Optional[float] = None
    ) -> List[float]:
        """计算利润率路径"""
        margins = []
        # 如果提供了当前利润率，使用它；否则默认为 Y5 的 70%
        if margin_y0 is None:
            margin_y0 = margin_y5 * 0.7

        for t in range(1, years + 1):
            if t <= 5:
                # 前5年线性收敛到 Y5
                m = margin_y0 + (margin_y5 - margin_y0) * (t / 5)
            else:
                # 之后收敛到终值
                m = margin_y5 + (margin_terminal - margin_y5) * ((t - 5) / max(years - 5, 1))
            margins.append(m)

        return margins

    def _check_consistency(
        self,
        inputs: DCFInputs,
        yearly_data: List[DCFYearlyData]
    ) -> Dict[str, float]:
        """
        一致性检查

        检查 g = ROIC × RR 的一致性。
        """
        # 计算平均 ROIC
        avg_roic = np.mean([
            d.ebit * (1 - inputs.tax) / (d.revenue / inputs.sales_to_capital)
            for d in yearly_data
        ])

        # 计算平均 RR
        avg_rr = np.mean([
            d.delta_ic / d.nopat if d.nopat > 0 else 0
            for d in yearly_data
        ])

        # 隐含 RR
        implied_rr = inputs.revenue_cagr / avg_roic if avg_roic > 0 else 0

        # 偏差
        deviation = abs(implied_rr - avg_rr)

        return {
            "avg_roic": avg_roic,
            "avg_rr": avg_rr,
            "implied_rr": implied_rr,
            "deviation": deviation,
            "deviation_ppt": deviation * 100
        }

    def reverse_dcf(
        self,
        market_cap: float,
        net_debt: float,
        revenue_y0: float,
        wacc: float,
        g_terminal: float,
        margin_y5: float,
        margin_terminal: float,
        sales_to_capital: float,
        tax: float,
        years: int,
        solve_for: str = "cagr"
    ) -> float:
        """
        反向 DCF

        Args:
            market_cap: 市值
            net_debt: 净负债
            revenue_y0: 初始收入
            wacc: WACC
            g_terminal: 终值增长率
            margin_y5: Y5 利润率
            margin_terminal: 终值利润率
            sales_to_capital: Sales/Capital
            tax: 税率
            years: 预测年数
            solve_for: 求解变量 (cagr/margin)

        Returns:
            隐含的 CAGR 或利润率
        """
        target_ev = market_cap + net_debt

        if solve_for == "cagr":
            return self._solve_for_cagr(
                target_ev, revenue_y0, years, margin_y5, margin_terminal,
                sales_to_capital, tax, wacc, g_terminal
            )
        else:
            return self._solve_for_margin(
                target_ev, revenue_y0, 0.10, years, margin_y5,
                sales_to_capital, tax, wacc, g_terminal
            )

    def _solve_for_cagr(
        self,
        target_ev: float,
        revenue_y0: float,
        years: int,
        margin_y5: float,
        margin_terminal: float,
        sales_to_capital: float,
        tax: float,
        wacc: float,
        g_terminal: float
    ) -> float:
        """二分法求解 CAGR"""
        low, high = -0.20, 0.60

        for _ in range(80):
            mid = (low + high) / 2
            inputs = DCFInputs(
                revenue_y0=revenue_y0,
                revenue_cagr=mid,
                years=years,
                margin_y5=margin_y5,
                margin_terminal=margin_terminal,
                sales_to_capital=sales_to_capital,
                tax=tax,
                wacc=wacc,
                g_terminal=g_terminal
            )
            result = self.calculate(inputs)

            if result.ev > target_ev:
                high = mid
            else:
                low = mid

            if abs(high - low) < 1e-6:
                break

        return (low + high) / 2

    def _solve_for_margin(
        self,
        target_ev: float,
        revenue_y0: float,
        revenue_cagr: float,
        years: int,
        margin_y5: float,
        sales_to_capital: float,
        tax: float,
        wacc: float,
        g_terminal: float
    ) -> float:
        """二分法求解终值利润率"""
        low, high = 0.0, 0.60

        for _ in range(80):
            mid = (low + high) / 2
            inputs = DCFInputs(
                revenue_y0=revenue_y0,
                revenue_cagr=revenue_cagr,
                years=years,
                margin_y5=margin_y5,
                margin_terminal=mid,
                sales_to_capital=sales_to_capital,
                tax=tax,
                wacc=wacc,
                g_terminal=g_terminal
            )
            result = self.calculate(inputs)

            if result.ev > target_ev:
                high = mid
            else:
                low = mid

            if abs(high - low) < 1e-7:
                break

        return (low + high) / 2
