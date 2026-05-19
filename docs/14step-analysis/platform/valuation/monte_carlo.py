"""
蒙特卡洛 DCF 模拟

对关键参数赋予概率分布，运行蒙特卡洛模拟，输出估值的概率分布。
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
from .dcf import DCFEngine, DCFInputs, DCFResult

logger = logging.getLogger(__name__)


@dataclass
class ParameterDistribution:
    """参数分布"""
    name: str
    distribution: str  # normal, uniform, triangular, lognormal
    params: Dict[str, float]  # 分布参数

    def sample(self, n: int = 1) -> np.ndarray:
        """
        从分布中采样

        Args:
            n: 采样数量

        Returns:
            采样结果
        """
        if self.distribution == "normal":
            return np.random.normal(
                self.params.get("mean", 0),
                self.params.get("std", 1),
                n
            )
        elif self.distribution == "uniform":
            return np.random.uniform(
                self.params.get("low", 0),
                self.params.get("high", 1),
                n
            )
        elif self.distribution == "triangular":
            return np.random.triangular(
                self.params.get("left", 0),
                self.params.get("mode", 0.5),
                self.params.get("right", 1),
                n
            )
        elif self.distribution == "lognormal":
            return np.random.lognormal(
                self.params.get("mean", 0),
                self.params.get("sigma", 1),
                n
            )
        else:
            raise ValueError(f"未知分布类型: {self.distribution}")


@dataclass
class MonteCarloInputs:
    """蒙特卡洛输入"""
    revenue_y0: float
    years: int
    tax: float
    # 概率分布参数
    revenue_cagr: ParameterDistribution
    margin_y5: ParameterDistribution
    margin_terminal: ParameterDistribution
    wacc: ParameterDistribution
    g_terminal: ParameterDistribution
    sales_to_capital: ParameterDistribution


@dataclass
class MonteCarloResult:
    """蒙特卡洛结果"""
    mean_ev: float  # 平均企业价值
    median_ev: float  # 中位数企业价值
    std_ev: float  # 标准差
    percentiles: Dict[int, float]  # 分位数
    confidence_interval: Tuple[float, float]  # 置信区间
    probability_above_market: float  # 高于当前市值的概率
    iterations: int  # 迭代次数
    all_values: np.ndarray  # 所有模拟值
    parameter_sensitivity: Dict[str, float]  # 参数敏感性


class MonteCarloDCF:
    """
    蒙特卡洛 DCF 模拟器

    功能：
    1. 对关键参数赋予概率分布
    2. 运行 N 次 DCF 模拟
    3. 输出估值的概率分布
    4. 计算参数敏感性
    """

    def __init__(self, iterations: int = 10000):
        """
        初始化蒙特卡洛模拟器

        Args:
            iterations: 迭代次数
        """
        self.iterations = iterations
        self.dcf_engine = DCFEngine()

    def simulate(
        self,
        inputs: MonteCarloInputs,
        market_cap: Optional[float] = None,
        net_debt: float = 0,
        shares: Optional[float] = None
    ) -> MonteCarloResult:
        """
        运行蒙特卡洛模拟

        Args:
            inputs: 蒙特卡洛输入
            market_cap: 当前市值（可选，用于计算概率）
            net_debt: 净负债
            shares: 总股本（亿股，可选）

        Returns:
            蒙特卡洛结果
        """
        logger.info(f"开始蒙特卡洛模拟: {self.iterations} 次迭代")

        # 采样参数
        cagr_samples = inputs.revenue_cagr.sample(self.iterations)
        margin_y5_samples = inputs.margin_y5.sample(self.iterations)
        margin_terminal_samples = inputs.margin_terminal.sample(self.iterations)
        wacc_samples = inputs.wacc.sample(self.iterations)
        g_terminal_samples = inputs.g_terminal.sample(self.iterations)
        stc_samples = inputs.sales_to_capital.sample(self.iterations)

        # 运行模拟
        ev_values = []
        valid_count = 0

        for i in range(self.iterations):
            try:
                # 确保参数有效
                wacc = wacc_samples[i]
                g_term = g_terminal_samples[i]

                # WACC 必须大于 g_terminal
                if wacc <= g_term:
                    continue

                # 利润率必须合理
                margin_y5 = max(0.01, min(0.50, margin_y5_samples[i]))
                margin_term = max(0.01, min(0.50, margin_terminal_samples[i]))

                dcf_inputs = DCFInputs(
                    revenue_y0=inputs.revenue_y0,
                    revenue_cagr=cagr_samples[i],
                    years=inputs.years,
                    margin_y5=margin_y5,
                    margin_terminal=margin_term,
                    sales_to_capital=max(0.5, stc_samples[i]),
                    tax=inputs.tax,
                    wacc=wacc,
                    g_terminal=g_term
                )

                result = self.dcf_engine.calculate(dcf_inputs)

                # 计算股权价值
                equity_value = result.ev - net_debt
                ev_values.append(equity_value)
                valid_count += 1

            except Exception as e:
                logger.debug(f"迭代 {i} 失败: {e}")
                continue

        if not ev_values:
            raise ValueError("所有模拟迭代都失败了")

        ev_array = np.array(ev_values)

        # 计算统计量
        mean_ev = np.mean(ev_array)
        median_ev = np.median(ev_array)
        std_ev = np.std(ev_array)

        # 计算分位数
        percentiles = {
            p: np.percentile(ev_array, p)
            for p in [5, 10, 25, 50, 75, 90, 95]
        }

        # 95% 置信区间
        ci_lower = np.percentile(ev_array, 2.5)
        ci_upper = np.percentile(ev_array, 97.5)

        # 高于当前市值的概率
        prob_above = 0.0
        if market_cap:
            prob_above = np.mean(ev_array > market_cap) * 100

        # 参数敏感性（简化版：计算相关系数）
        sensitivity = self._calculate_sensitivity(
            ev_array,
            cagr_samples[:valid_count],
            margin_y5_samples[:valid_count],
            wacc_samples[:valid_count],
            g_terminal_samples[:valid_count]
        )

        logger.info(f"蒙特卡洛模拟完成: {valid_count}/{self.iterations} 有效迭代")

        return MonteCarloResult(
            mean_ev=mean_ev,
            median_ev=median_ev,
            std_ev=std_ev,
            percentiles=percentiles,
            confidence_interval=(ci_lower, ci_upper),
            probability_above_market=prob_above,
            iterations=valid_count,
            all_values=ev_array,
            parameter_sensitivity=sensitivity
        )

    def _calculate_sensitivity(
        self,
        ev_values: np.ndarray,
        cagr: np.ndarray,
        margin: np.ndarray,
        wacc: np.ndarray,
        g_terminal: np.ndarray
    ) -> Dict[str, float]:
        """
        计算参数敏感性

        使用 Spearman 秩相关系数。
        """
        from scipy import stats

        sensitivity = {}

        # 计算每个参数与 EV 的相关系数
        params = {
            "revenue_cagr": cagr,
            "margin_y5": margin,
            "wacc": wacc,
            "g_terminal": g_terminal
        }

        for name, values in params.items():
            if len(values) > 1:
                corr, _ = stats.spearmanr(values, ev_values)
                sensitivity[name] = abs(corr)  # 使用绝对值

        # 归一化
        total = sum(sensitivity.values())
        if total > 0:
            sensitivity = {k: v / total for k, v in sensitivity.items()}

        return sensitivity

    def format_report(
        self,
        result: MonteCarloResult,
        market_cap: Optional[float] = None,
        shares: Optional[float] = None
    ) -> str:
        """
        格式化蒙特卡洛报告

        Args:
            result: 蒙特卡洛结果
            market_cap: 当前市值
            shares: 总股本

        Returns:
            格式化的报告
        """
        lines = []
        lines.append("=" * 60)
        lines.append("蒙特卡洛 DCF 模拟报告")
        lines.append("=" * 60)
        lines.append(f"迭代次数: {result.iterations}")
        lines.append("")

        # 统计摘要
        lines.append("【估值统计】")
        lines.append(f"  平均企业价值: {result.mean_ev:.1f} 亿")
        lines.append(f"  中位数企业价值: {result.median_ev:.1f} 亿")
        lines.append(f"  标准差: {result.std_ev:.1f} 亿")
        lines.append("")

        # 分位数
        lines.append("【分位数分布】")
        for p, value in result.percentiles.items():
            marker = "★" if p == 50 else " "
            lines.append(f"  P{p:2d}: {value:.1f} 亿 {marker}")
        lines.append("")

        # 置信区间
        lines.append("【95% 置信区间】")
        lines.append(f"  [{result.confidence_interval[0]:.1f}, {result.confidence_interval[1]:.1f}] 亿")
        lines.append("")

        # 与当前市值对比
        if market_cap:
            lines.append("【与当前市值对比】")
            lines.append(f"  当前市值: {market_cap:.1f} 亿")
            lines.append(f"  高于市值概率: {result.probability_above_market:.1f}%")

            if shares:
                lines.append(f"  每股内在价值:")
                lines.append(f"    P25: {result.percentiles[25] / shares:.2f} 元")
                lines.append(f"    P50: {result.percentiles[50] / shares:.2f} 元")
                lines.append(f"    P75: {result.percentiles[75] / shares:.2f} 元")
            lines.append("")

        # 参数敏感性
        lines.append("【参数敏感性】")
        sorted_sensitivity = sorted(
            result.parameter_sensitivity.items(),
            key=lambda x: x[1],
            reverse=True
        )
        for name, value in sorted_sensitivity:
            bar = "█" * int(value * 20)
            lines.append(f"  {name:<20} {bar} {value:.1%}")
        lines.append("")

        lines.append("=" * 60)
        lines.append("⚠ 注意：蒙特卡洛模拟结果依赖于输入的概率分布假设。")
        lines.append("  请确保概率分布反映了你对公司前景的真实判断。")
        lines.append("=" * 60)

        return "\n".join(lines)
