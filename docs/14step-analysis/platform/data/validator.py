"""
数据验证器

提供数据验证功能，确保数据质量。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from .provider import FinancialData, PriceData, ValuationData

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class DataValidator:
    """
    数据验证器

    功能：
    1. 财务数据验证
    2. 行情数据验证
    3. 估值数据验证
    4. 跨数据源一致性验证
    """

    def __init__(self, strict: bool = True):
        """
        初始化验证器

        Args:
            strict: 是否严格模式
        """
        self.strict = strict

    def validate_financial_data(self, data: FinancialData) -> ValidationResult:
        """
        验证财务数据

        Args:
            data: 财务数据

        Returns:
            验证结果
        """
        errors = []
        warnings = []

        # 基本范围检查
        if data.gross_margin < 0 or data.gross_margin > 100:
            errors.append(f"毛利率异常: {data.gross_margin}%")

        if data.net_margin < -100 or data.net_margin > 100:
            errors.append(f"净利率异常: {data.net_margin}%")

        if data.roe < -100 or data.roe > 100:
            errors.append(f"ROE 异常: {data.roe}%")

        if data.debt_ratio < 0 or data.debt_ratio > 100:
            errors.append(f"资产负债率异常: {data.debt_ratio}%")

        # 逻辑检查
        if data.revenue > 0 and data.net_profit < 0:
            warnings.append("收入为正但净利润为负")

        if data.gross_margin < data.net_margin:
            warnings.append("毛利率低于净利率，可能数据有误")

        # 现金流检查
        if data.revenue > 0 and data.operating_cashflow < 0:
            warnings.append("经营现金流为负，需关注")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details={
                "ticker": data.ticker,
                "year": data.year,
                "quarter": data.quarter
            }
        )

    def validate_price_data(self, data: List[PriceData]) -> ValidationResult:
        """
        验证行情数据

        Args:
            data: 行情数据列表

        Returns:
            验证结果
        """
        errors = []
        warnings = []

        if not data:
            errors.append("行情数据为空")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # 检查数据连续性
        dates = [d.date for d in data]
        if len(dates) != len(set(dates)):
            warnings.append("存在重复日期")

        # 检查价格合理性
        for d in data:
            if d.open <= 0 or d.high <= 0 or d.low <= 0 or d.close <= 0:
                errors.append(f"价格为0或负数: {d.date}")

            if d.high < d.low:
                errors.append(f"最高价低于最低价: {d.date}")

            if d.volume < 0:
                errors.append(f"成交量为负: {d.date}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details={"count": len(data)}
        )

    def validate_valuation_data(self, data: ValuationData) -> ValidationResult:
        """
        验证估值数据

        Args:
            data: 估值数据

        Returns:
            验证结果
        """
        errors = []
        warnings = []

        # PE 检查
        if data.pe_ratio < 0:
            warnings.append("PE 为负（亏损公司）")
        elif data.pe_ratio > 100:
            warnings.append(f"PE 过高: {data.pe_ratio}")

        # PB 检查
        if data.pb_ratio < 0:
            errors.append(f"PB 为负: {data.pb_ratio}")
        elif data.pb_ratio > 20:
            warnings.append(f"PB 过高: {data.pb_ratio}")

        # 市值检查
        if data.market_cap <= 0:
            errors.append(f"市值异常: {data.market_cap}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details={
                "ticker": data.ticker,
                "date": data.date
            }
        )

    def cross_validate_financials(
        self,
        akshare_data: FinancialData,
        pdf_data: FinancialData,
        tolerance: float = 0.03
    ) -> ValidationResult:
        """
        跨数据源一致性验证

        Args:
            akshare_data: AKShare 数据
            pdf_data: PDF 提取数据
            tolerance: 容差（3%）

        Returns:
            验证结果
        """
        errors = []
        warnings = []
        discrepancies = {}

        # 比较关键指标
        fields = [
            ("revenue", "营业收入"),
            ("net_profit", "净利润"),
            ("total_assets", "总资产"),
            ("total_equity", "净资产")
        ]

        for field, name in fields:
            ak_val = getattr(akshare_data, field)
            pdf_val = getattr(pdf_data, field)

            if ak_val == 0 and pdf_val == 0:
                continue

            if ak_val == 0 or pdf_val == 0:
                errors.append(f"{name}: 一个数据源为0")
                continue

            diff = abs(ak_val - pdf_val) / abs(pdf_val)
            if diff > tolerance:
                errors.append(f"{name}: 偏差 {diff:.1%} > {tolerance:.1%}")
                discrepancies[name] = {
                    "akshare": ak_val,
                    "pdf": pdf_val,
                    "diff_pct": diff
                }
            elif diff > tolerance / 2:
                warnings.append(f"{name}: 偏差 {diff:.1%}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details={"discrepancies": discrepancies}
        )

    def validate_wacc_parameters(
        self,
        rf: float,
        beta: float,
        erp: float,
        kd: float,
        tax: float,
        de_ratio: float
    ) -> ValidationResult:
        """
        验证 WACC 参数

        Args:
            rf: 无风险利率
            beta: Beta
            erp: 股权风险溢价
            kd: 债务成本
            tax: 税率
            de_ratio: 债务/权益比

        Returns:
            验证结果
        """
        errors = []
        warnings = []

        # Rf 检查
        if rf < 0 or rf > 0.10:
            errors.append(f"无风险利率异常: {rf:.2%}")

        # Beta 检查
        if beta < 0 or beta > 3:
            warnings.append(f"Beta 异常: {beta}")

        # ERP 检查
        if erp < 0.03 or erp > 0.10:
            warnings.append(f"ERP 异常: {erp:.2%}")

        # 债务成本检查
        if kd < 0 or kd > 0.15:
            warnings.append(f"债务成本异常: {kd:.2%}")

        # 税率检查
        if tax < 0 or tax > 0.50:
            errors.append(f"税率异常: {tax:.2%}")

        # D/E 比检查
        if de_ratio < 0:
            errors.append(f"D/E 比为负: {de_ratio}")
        elif de_ratio > 5:
            warnings.append(f"D/E 比过高: {de_ratio}")

        # 计算 WACC
        ke = rf + beta * erp
        wacc = ke * (1 / (1 + de_ratio)) + kd * (1 - tax) * (de_ratio / (1 + de_ratio))

        if wacc < 0.04 or wacc > 0.20:
            warnings.append(f"WACC 异常: {wacc:.2%}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details={
                "ke": ke,
                "wacc": wacc,
                "parameters": {
                    "rf": rf,
                    "beta": beta,
                    "erp": erp,
                    "kd": kd,
                    "tax": tax,
                    "de_ratio": de_ratio
                }
            }
        )

    def validate_dcf_inputs(
        self,
        revenue: float,
        cagr: float,
        margin: float,
        wacc: float,
        g_terminal: float,
        years: int
    ) -> ValidationResult:
        """
        验证 DCF 输入

        Args:
            revenue: 初始收入
            cagr: 收入增长率
            margin: 利润率
            wacc: WACC
            g_terminal: 终值增长率
            years: 预测年数

        Returns:
            验证结果
        """
        errors = []
        warnings = []

        # 收入检查
        if revenue <= 0:
            errors.append(f"收入必须为正: {revenue}")

        # CAGR 检查
        if cagr < -0.50 or cagr > 1.00:
            warnings.append(f"CAGR 异常: {cagr:.1%}")

        # 利润率检查
        if margin < 0 or margin > 0.50:
            warnings.append(f"利润率异常: {margin:.1%}")

        # WACC 检查
        if wacc <= 0 or wacc > 0.30:
            errors.append(f"WACC 异常: {wacc:.2%}")

        # g_terminal 检查
        if g_terminal < 0 or g_terminal > wacc:
            errors.append(f"终值 g 异常: {g_terminal:.2%}")

        # 年数检查
        if years < 5 or years > 20:
            warnings.append(f"预测年数异常: {years}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details={
                "revenue": revenue,
                "cagr": cagr,
                "margin": margin,
                "wacc": wacc,
                "g_terminal": g_terminal,
                "years": years
            }
        )
