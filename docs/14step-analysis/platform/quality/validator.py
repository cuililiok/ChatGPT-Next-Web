"""
报告核验器

提供报告内容核验功能。
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from ..core.exceptions import PDFVerificationError

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """核验结果"""
    field: str
    expected: float
    actual: float
    deviation: float
    status: str  # PASS, WARN, FAIL


class ReportValidator:
    """
    报告核验器

    功能：
    1. PDF 数据核验
    2. 跨数据源一致性核验
    3. 估值结论核验
    """

    def __init__(self, tolerance: float = 0.08, warn_tolerance: float = 0.03):
        """
        初始化核验器

        Args:
            tolerance: 容差（8%）
            warn_tolerance: 警告容差（3%）
        """
        self.tolerance = tolerance
        self.warn_tolerance = warn_tolerance
        self.results: List[VerificationResult] = []

    def verify_financial_data(
        self,
        report_data: Dict[str, float],
        pdf_data: Dict[str, float]
    ) -> List[VerificationResult]:
        """
        核验财务数据

        Args:
            report_data: 报告中的数据
            pdf_data: PDF 提取的数据

        Returns:
            核验结果列表
        """
        results = []

        for field in report_data:
            if field not in pdf_data:
                continue

            report_val = report_data[field]
            pdf_val = pdf_data[field]

            # 计算偏差
            if pdf_val == 0:
                deviation = 0 if report_val == 0 else 1.0
            else:
                deviation = abs(report_val - pdf_val) / abs(pdf_val)

            # 判断状态
            if deviation <= self.warn_tolerance:
                status = "PASS"
            elif deviation <= self.tolerance:
                status = "WARN"
            else:
                status = "FAIL"

            result = VerificationResult(
                field=field,
                expected=pdf_val,
                actual=report_val,
                deviation=deviation,
                status=status
            )

            results.append(result)
            self.results.append(result)

        return results

    def verify_valuation_consistency(
        self,
        dcf_value: float,
        market_price: float,
        historical_range: tuple
    ) -> VerificationResult:
        """
        核验估值一致性

        Args:
            dcf_value: DCF 估值
            market_price: 市场价格
            historical_range: 历史价格范围

        Returns:
            核验结果
        """
        # 计算偏差
        deviation = (dcf_value - market_price) / market_price

        # 判断是否在历史范围内
        low, high = historical_range
        if dcf_value < low:
            status = "WARN"
            message = f"估值低于历史最低 ({low:.2f})"
        elif dcf_value > high:
            status = "WARN"
            message = f"估值高于历史最高 ({high:.2f})"
        else:
            status = "PASS"
            message = f"估值在历史范围内 [{low:.2f}, {high:.2f}]"

        result = VerificationResult(
            field="valuation_consistency",
            expected=market_price,
            actual=dcf_value,
            deviation=deviation,
            status=status
        )

        self.results.append(result)
        return result

    def get_summary(self) -> Dict[str, any]:
        """
        获取核验摘要

        Returns:
            摘要信息
        """
        pass_count = sum(1 for r in self.results if r.status == "PASS")
        warn_count = sum(1 for r in self.results if r.status == "WARN")
        fail_count = sum(1 for r in self.results if r.status == "FAIL")
        total = len(self.results)

        return {
            "total": total,
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
            "status": "PASS" if fail_count == 0 else "FAIL"
        }

    def format_report(self) -> str:
        """
        格式化核验报告

        Returns:
            格式化的报告
        """
        lines = []
        lines.append("=" * 60)
        lines.append("数据核验报告")
        lines.append("=" * 60)

        for result in self.results:
            icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(result.status, "❓")
            lines.append(
                f"{icon} {result.field}: "
                f"报告={result.actual:.2f}, PDF={result.expected:.2f}, "
                f"偏差={result.deviation:.1%}"
            )

        lines.append("-" * 60)

        summary = self.get_summary()
        lines.append(f"总计: {summary['total']} 项核验")
        lines.append(f"通过: {summary['pass']} | 警告: {summary['warn']} | 失败: {summary['fail']}")
        lines.append(f"结论: {summary['status']}")

        lines.append("=" * 60)

        return "\n".join(lines)
