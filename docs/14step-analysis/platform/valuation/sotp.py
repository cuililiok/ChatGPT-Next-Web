"""
分部估值 (SOTP)

提供 Sum-of-the-Parts 估值功能，适用于多元化公司。
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BusinessSegment:
    """业务板块"""
    name: str
    segment_type: str  # insurance, banking, asset_mgmt, new_business, etc.
    metric_name: str  # EV, net_assets, AUM, etc.
    metric_value: float  # 指标值（亿）
    valuation_method: str  # P/EV, P/B, P/AUM, P/S, DCF
    multiple_low: float  # 估值倍数下限
    multiple_high: float  # 估值倍数上限
    notes: str = ""


@dataclass
class SOTPResult:
    """SOTP 结果"""
    segments: List[Dict[str, any]]  # 各板块估值
    total_value: float  # 各板块加总
    holding_discount: float  # 控股折价
    holding_discount_pct: float  # 折价比例
    final_value: float  # 最终估值
    per_share_value: float  # 每股价值
    current_price: float  # 当前股价
    upside: float  # 上行空间


class SOTPValuation:
    """
    SOTP 分部估值计算器

    功能：
    1. 业务板块拆分
    2. 各板块独立估值
    3. 控股折价调整
    4. 敏感性分析
    """

    def __init__(self):
        """初始化 SOTP 估值计算器"""
        pass

    def calculate(
        self,
        segments: List[BusinessSegment],
        holding_discount_pct: float = 0.15,
        shares: float = 1.0,
        current_price: float = 0
    ) -> SOTPResult:
        """
        执行 SOTP 估值

        Args:
            segments: 业务板块列表
            holding_discount_pct: 控股折价比例
            shares: 总股本（亿股）
            current_price: 当前股价

        Returns:
            SOTP 结果
        """
        # 计算各板块估值
        segment_results = []
        total_value = 0

        for segment in segments:
            # 计算估值范围
            value_low = segment.metric_value * segment.multiple_low
            value_high = segment.metric_value * segment.multiple_high
            value_mid = (value_low + value_high) / 2

            segment_results.append({
                "name": segment.name,
                "type": segment.segment_type,
                "metric_name": segment.metric_name,
                "metric_value": segment.metric_value,
                "method": segment.valuation_method,
                "multiple_low": segment.multiple_low,
                "multiple_high": segment.multiple_high,
                "value_low": value_low,
                "value_high": value_high,
                "value_mid": value_mid,
                "notes": segment.notes
            })

            total_value += value_mid

        # 控股折价
        holding_discount = total_value * holding_discount_pct
        final_value = total_value - holding_discount

        # 每股价值
        per_share_value = final_value / shares if shares > 0 else 0

        # 上行空间
        upside = (per_share_value - current_price) / current_price if current_price > 0 else 0

        return SOTPResult(
            segments=segment_results,
            total_value=total_value,
            holding_discount=holding_discount,
            holding_discount_pct=holding_discount_pct,
            final_value=final_value,
            per_share_value=per_share_value,
            current_price=current_price,
            upside=upside
        )

    def format_table(self, result: SOTPResult) -> str:
        """
        格式化 SOTP 表格

        Returns:
            格式化的表格
        """
        lines = []
        lines.append("| 业务板块 | 核心指标 | 估值方法 | 参考倍数 | 估算价值 |")
        lines.append("|---------|----------|----------|----------|----------|")

        for seg in result.segments:
            multiple_range = f"{seg['multiple_low']:.1f}x–{seg['multiple_high']:.1f}x"
            value_str = f"{seg['value_mid']:.1f} 亿"
            lines.append(
                f"| {seg['name']} | {seg['metric_name']}={seg['metric_value']:.1f}亿 "
                f"| {seg['method']} | {multiple_range} | {value_str} |"
            )

        lines.append(f"| **合计** | | | | **{result.total_value:.1f} 亿** |")
        lines.append(f"| 控股折价 | {result.holding_discount_pct:.0%} | | | {result.holding_discount:.1f} 亿 |")
        lines.append(f"| **集团合理市值** | | | | **{result.final_value:.1f} 亿** |")

        lines.append("")
        lines.append(f"每股内在价值: {result.per_share_value:.2f} 元")
        lines.append(f"当前股价: {result.current_price:.2f} 元")
        lines.append(f"上行空间: {result.upside:.1%}")

        return "\n".join(lines)

    def sensitivity_analysis(
        self,
        segments: List[BusinessSegment],
        holding_discount_range: Tuple[float, float] = (0.10, 0.20),
        shares: float = 1.0,
        current_price: float = 0
    ) -> str:
        """
        敏感性分析

        Args:
            segments: 业务板块列表
            holding_discount_range: 折价范围
            shares: 总股本
            current_price: 当前股价

        Returns:
            敏感性分析表格
        """
        lines = []
        lines.append("### SOTP 敏感性分析")
        lines.append("")
        lines.append("| 控股折价 | 集团市值 | 每股价值 | 上行空间 |")
        lines.append("|----------|----------|----------|----------|")

        for discount in [0.10, 0.12, 0.15, 0.18, 0.20]:
            result = self.calculate(segments, discount, shares, current_price)
            lines.append(
                f"| {discount:.0%} | {result.final_value:.1f}亿 "
                f"| {result.per_share_value:.2f}元 | {result.upside:.1%} |"
            )

        return "\n".join(lines)
