"""
14步深度投资研究平台 - 主入口

提供统一的平台入口和 CLI 接口。
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional

from .core import ProgressManager, ConfigManager, setup_logger
from .core.exceptions import PlatformError
from .valuation import DCFEngine, MonteCarloDCF, RelativeValuation, SOTPValuation
from .quality import QualityChecker, ReportValidator

logger = logging.getLogger(__name__)


class InvestmentResearchPlatform:
    """
    投资研究平台

    整合所有模块，提供统一的研究流程。
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        mode: str = "full",
        log_level: str = "INFO"
    ):
        """
        初始化平台

        Args:
            config_path: 配置文件路径
            mode: 执行模式 (full/quick)
            log_level: 日志级别
        """
        # 设置日志
        self.logger = setup_logger(
            name="investment_research",
            level=log_level,
            log_dir="~/.logs/investment-research"
        )

        # 加载配置
        self.config = ConfigManager(config_path)
        self.config.config.mode = mode

        # 初始化进度管理器
        self.progress = ProgressManager(mode)

        # 初始化估值引擎
        self.dcf_engine = DCFEngine()
        self.monte_carlo = MonteCarloDCF(
            iterations=self.config.get("valuation.monte_carlo_iterations", 10000)
        )
        self.relative_valuation = RelativeValuation()
        self.sotp_valuation = SOTPValuation()

        # 初始化质量检查器
        self.quality_checker = QualityChecker(mode)
        self.report_validator = ReportValidator()

        self.logger.info(f"平台初始化完成: mode={mode}")

    def run_dcf(
        self,
        revenue_y0: float,
        revenue_cagr: float,
        margin_y5: float,
        margin_terminal: float,
        wacc: float,
        g_terminal: float,
        sales_to_capital: float = 1.5,
        tax: float = 0.25,
        years: int = 10
    ) -> dict:
        """
        运行 DCF 估值

        Args:
            revenue_y0: 初始收入
            revenue_cagr: 收入 CAGR
            margin_y5: Y5 利润率
            margin_terminal: 终值利润率
            wacc: WACC
            g_terminal: 终值增长率
            sales_to_capital: Sales/Capital
            tax: 税率
            years: 预测年数

        Returns:
            DCF 结果
        """
        from .valuation.dcf import DCFInputs

        inputs = DCFInputs(
            revenue_y0=revenue_y0,
            revenue_cagr=revenue_cagr,
            years=years,
            margin_y5=margin_y5,
            margin_terminal=margin_terminal,
            sales_to_capital=sales_to_capital,
            tax=tax,
            wacc=wacc,
            g_terminal=g_terminal
        )

        result = self.dcf_engine.calculate(inputs)

        return {
            "ev": result.ev,
            "terminal_value_pct": result.terminal_value_pct,
            "pv_fcff": result.pv_fcff,
            "pv_terminal": result.pv_terminal,
            "consistency_check": result.consistency_check
        }

    def run_monte_carlo(
        self,
        revenue_y0: float,
        iterations: int = 10000,
        **kwargs
    ) -> str:
        """
        运行蒙特卡洛模拟

        Args:
            revenue_y0: 初始收入
            iterations: 迭代次数

        Returns:
            蒙特卡洛报告
        """
        from .valuation.monte_carlo import MonteCarloInputs, ParameterDistribution

        # 创建参数分布（简化版，实际应从配置或用户输入获取）
        inputs = MonteCarloInputs(
            revenue_y0=revenue_y0,
            years=kwargs.get("years", 10),
            tax=kwargs.get("tax", 0.25),
            revenue_cagr=ParameterDistribution(
                name="revenue_cagr",
                distribution="normal",
                params={"mean": kwargs.get("cagr_mean", 0.10), "std": kwargs.get("cagr_std", 0.05)}
            ),
            margin_y5=ParameterDistribution(
                name="margin_y5",
                distribution="normal",
                params={"mean": kwargs.get("margin_mean", 0.18), "std": kwargs.get("margin_std", 0.03)}
            ),
            margin_terminal=ParameterDistribution(
                name="margin_terminal",
                distribution="normal",
                params={"mean": kwargs.get("margin_terminal_mean", 0.20), "std": 0.02}
            ),
            wacc=ParameterDistribution(
                name="wacc",
                distribution="normal",
                params={"mean": kwargs.get("wacc_mean", 0.085), "std": kwargs.get("wacc_std", 0.01)}
            ),
            g_terminal=ParameterDistribution(
                name="g_terminal",
                distribution="normal",
                params={"mean": kwargs.get("g_mean", 0.022), "std": 0.005}
            ),
            sales_to_capital=ParameterDistribution(
                name="sales_to_capital",
                distribution="normal",
                params={"mean": kwargs.get("stc_mean", 1.5), "std": 0.2}
            )
        )

        self.monte_carlo.iterations = iterations
        result = self.monte_carlo.simulate(
            inputs,
            market_cap=kwargs.get("market_cap"),
            net_debt=kwargs.get("net_debt", 0),
            shares=kwargs.get("shares")
        )

        return self.monte_carlo.format_report(result)

    def check_report(self, report_path: str) -> str:
        """
        检查报告质量

        Args:
            report_path: 报告路径

        Returns:
            检查报告
        """
        # 这里应该调用现有的 check_report.py
        # 简化版：返回提示
        return f"请运行: python scripts/check_report.py --report {report_path} --mode {self.config.config.mode}"

    def get_progress_report(self) -> str:
        """
        获取进度报告

        Returns:
            进度报告
        """
        return self.progress.generate_report()

    def print_status(self):
        """打印当前状态"""
        self.progress.print_progress()


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        description="14步深度投资研究平台",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--mode",
        choices=["full", "quick"],
        default="full",
        help="执行模式 (默认: full)"
    )

    parser.add_argument(
        "--config",
        help="配置文件路径"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别 (默认: INFO)"
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # DCF 命令
    dcf_parser = subparsers.add_parser("dcf", help="运行 DCF 估值")
    dcf_parser.add_argument("--revenue", type=float, required=True, help="初始收入（亿）")
    dcf_parser.add_argument("--cagr", type=float, required=True, help="收入 CAGR")
    dcf_parser.add_argument("--margin-y5", type=float, required=True, help="Y5 利润率")
    dcf_parser.add_argument("--margin-terminal", type=float, required=True, help="终值利润率")
    dcf_parser.add_argument("--wacc", type=float, required=True, help="WACC")
    dcf_parser.add_argument("--g-terminal", type=float, required=True, help="终值增长率")

    # 蒙特卡洛命令
    mc_parser = subparsers.add_parser("monte-carlo", help="运行蒙特卡洛模拟")
    mc_parser.add_argument("--revenue", type=float, required=True, help="初始收入（亿）")
    mc_parser.add_argument("--iterations", type=int, default=10000, help="迭代次数")
    mc_parser.add_argument("--market-cap", type=float, help="当前市值（亿）")

    # 质检命令
    check_parser = subparsers.add_parser("check", help="检查报告质量")
    check_parser.add_argument("--report", required=True, help="报告路径")

    args = parser.parse_args()

    try:
        # 初始化平台
        platform = InvestmentResearchPlatform(
            config_path=args.config,
            mode=args.mode,
            log_level=args.log_level
        )

        # 执行命令
        if args.command == "dcf":
            result = platform.run_dcf(
                revenue_y0=args.revenue,
                revenue_cagr=args.cagr,
                margin_y5=args.margin_y5,
                margin_terminal=args.margin_terminal,
                wacc=args.wacc,
                g_terminal=args.g_terminal
            )
            print("\nDCF 估值结果:")
            print(f"  企业价值: {result['ev']:.1f} 亿")
            print(f"  终值占比: {result['terminal_value_pct']:.1%}")
            print(f"  预测期现值: {result['pv_fcff']:.1f} 亿")
            print(f"  终值现值: {result['pv_terminal']:.1f} 亿")

        elif args.command == "monte-carlo":
            report = platform.run_monte_carlo(
                revenue_y0=args.revenue,
                iterations=args.iterations,
                market_cap=args.market_cap
            )
            print(report)

        elif args.command == "check":
            report = platform.check_report(args.report)
            print(report)

        else:
            parser.print_help()

    except PlatformError as e:
        logger.error(f"平台错误: {e}")
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"未知错误: {e}")
        print(f"未知错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
