"""
相对估值

提供 PE/PB/PS/EV-EBITDA 等相对估值方法。
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RelativeValuationResult:
    """相对估值结果"""
    pe_ratio: float
    pb_ratio: float
    ps_ratio: float
    ev_ebitda: float
    pe_percentile: float  # 历史分位
    pb_percentile: float
    industry_pe: float  # 行业平均
    industry_pb: float
    pe_premium: float  # 相对行业溢价
    pb_premium: float
    conclusion: str  # 结论


class RelativeValuation:
    """
    相对估值计算器

    功能：
    1. 计算各种估值倍数
    2. 与历史均值对比
    3. 与行业均值对比
    4. 生成估值结论
    """

    def __init__(self):
        """初始化相对估值计算器"""
        pass

    def calculate_pe_valuation(
        self,
        current_pe: float,
        historical_pe: List[float],
        industry_pe: float,
        earnings_growth: float
    ) -> Dict[str, any]:
        """
        PE 估值分析

        Args:
            current_pe: 当前 PE
            historical_pe: 历史 PE 列表
            industry_pe: 行业平均 PE
            earnings_growth: 盈利增长率

        Returns:
            分析结果
        """
        # 历史分位
        percentile = self._calculate_percentile(current_pe, historical_pe)

        # 行业溢价
        industry_premium = (current_pe - industry_pe) / industry_pe if industry_pe > 0 else 0

        # PEG
        peg = current_pe / (earnings_growth * 100) if earnings_growth > 0 else float('inf')

        # 结论
        conclusion = self._generate_pe_conclusion(percentile, industry_premium, peg)

        return {
            "current_pe": current_pe,
            "historical_mean": np.mean(historical_pe) if historical_pe else None,
            "historical_percentile": percentile,
            "industry_pe": industry_pe,
            "industry_premium": industry_premium,
            "peg": peg,
            "conclusion": conclusion
        }

    def calculate_pb_valuation(
        self,
        current_pb: float,
        historical_pb: List[float],
        industry_pb: float,
        roe: float
    ) -> Dict[str, any]:
        """
        PB 估值分析

        Args:
            current_pb: 当前 PB
            historical_pb: 历史 PB 列表
            industry_pb: 行业平均 PB
            roe: ROE

        Returns:
            分析结果
        """
        # 历史分位
        percentile = self._calculate_percentile(current_pb, historical_pb)

        # 行业溢价
        industry_premium = (current_pb - industry_pb) / industry_pb if industry_pb > 0 else 0

        # PB-ROE 隐含 Ke
        implied_ke = self._calculate_implied_ke(roe, current_pb)

        # 结论
        conclusion = self._generate_pb_conclusion(percentile, industry_premium, implied_ke)

        return {
            "current_pb": current_pb,
            "historical_mean": np.mean(historical_pb) if historical_pb else None,
            "historical_percentile": percentile,
            "industry_pb": industry_pb,
            "industry_premium": industry_premium,
            "implied_ke": implied_ke,
            "conclusion": conclusion
        }

    def _calculate_percentile(self, current: float, historical: List[float]) -> float:
        """计算历史分位"""
        if not historical:
            return 50.0

        historical = sorted(historical)
        count_below = sum(1 for h in historical if h < current)
        return (count_below / len(historical)) * 100

    def _calculate_implied_ke(self, roe: float, pb: float, g: float = 0.03) -> Optional[float]:
        """
        计算隐含 Ke

        使用 Gordon Growth Model: Ke = g + (ROE - g) / PB

        注意：以下情况公式失效，返回 None：
        - PB <= 0
        - ROE 接近或低于 g（分子趋零或为负）
        - 结果为负值（无经济意义）
        """
        if pb <= 0:
            return None
        roe_decimal = roe / 100
        # ROE 接近或低于 g 时公式无效
        if roe_decimal <= g + 0.005:
            return None
        ke = g + (roe_decimal - g) / pb
        # 负值无经济意义
        if ke < 0:
            return None
        return ke

    def _generate_pe_conclusion(
        self,
        percentile: float,
        industry_premium: float,
        peg: float
    ) -> str:
        """生成 PE 结论"""
        conclusions = []

        if percentile < 25:
            conclusions.append("PE 处于历史低位")
        elif percentile > 75:
            conclusions.append("PE 处于历史高位")

        if industry_premium > 0.2:
            conclusions.append(f"相对行业溢价 {industry_premium:.0%}")
        elif industry_premium < -0.2:
            conclusions.append(f"相对行业折价 {abs(industry_premium):.0%}")

        if peg < 1:
            conclusions.append("PEG < 1，估值合理")
        elif peg > 2:
            conclusions.append("PEG > 2，估值偏高")

        return "；".join(conclusions) if conclusions else "估值处于合理区间"

    def _generate_pb_conclusion(
        self,
        percentile: float,
        industry_premium: float,
        implied_ke: Optional[float]
    ) -> str:
        """生成 PB 结论"""
        conclusions = []

        if percentile < 25:
            conclusions.append("PB 处于历史低位")
        elif percentile > 75:
            conclusions.append("PB 处于历史高位")

        if industry_premium > 0.3:
            conclusions.append(f"相对行业溢价 {industry_premium:.0%}")
        elif industry_premium < -0.3:
            conclusions.append(f"相对行业折价 {abs(industry_premium):.0%}")

        if implied_ke is None:
            conclusions.append("隐含 Ke 不可计算（ROE ≈ g 或 PB 异常，建议用 PB-ROE 散点图替代）")
        elif implied_ke > 0.12:
            conclusions.append(f"隐含 Ke {implied_ke:.1%}，要求回报率高")
        elif implied_ke < 0.06:
            conclusions.append(f"隐含 Ke {implied_ke:.1%}，市场预期乐观")

        return "；".join(conclusions) if conclusions else "估值处于合理区间"

    def format_table(
        self,
        pe_result: Dict,
        pb_result: Dict,
        ps_ratio: float,
        ev_ebitda: float
    ) -> str:
        """
        格式化估值表格

        Returns:
            格式化的表格
        """
        lines = []
        lines.append("| 估值指标 | 当前值 | 历史分位 | 行业均值 | 溢价/折价 |")
        lines.append("|---------|--------|----------|----------|-----------|")

        # PE
        pe_pct = f"{pe_result.get('historical_percentile', 0):.0f}%"
        pe_ind = f"{pe_result.get('industry_pe', 0):.1f}x"
        pe_prem = f"{pe_result.get('industry_premium', 0):.0%}"
        lines.append(f"| PE | {pe_result.get('current_pe', 0):.1f}x | {pe_pct} | {pe_ind} | {pe_prem} |")

        # PB
        pb_pct = f"{pb_result.get('historical_percentile', 0):.0f}%"
        pb_ind = f"{pb_result.get('industry_pb', 0):.1f}x"
        pb_prem = f"{pb_result.get('industry_premium', 0):.0%}"
        lines.append(f"| PB | {pb_result.get('current_pb', 0):.1f}x | {pb_pct} | {pb_ind} | {pb_prem} |")

        # PS
        lines.append(f"| PS | {ps_ratio:.1f}x | - | - | - |")

        # EV/EBITDA
        lines.append(f"| EV/EBITDA | {ev_ebitda:.1f}x | - | - | - |")

        lines.append("")
        lines.append(f"**PE 结论**: {pe_result.get('conclusion', '-')}")
        lines.append(f"**PB 结论**: {pb_result.get('conclusion', '-')}")

        return "\n".join(lines)
