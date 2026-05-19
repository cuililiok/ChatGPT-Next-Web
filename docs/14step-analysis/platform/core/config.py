"""
配置管理器

提供统一的配置管理，支持：
1. 默认配置
2. 用户配置覆盖
3. 环境变量
4. 配置验证
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field
from copy import deepcopy

logger = logging.getLogger(__name__)


@dataclass
class DataConfig:
    """数据层配置"""
    cache_dir: str = "~/.cache/investment-research"
    akshare_enabled: bool = True
    akshare_timeout: int = 30
    sina_fallback: bool = True
    pdf_storage_dir: str = "~/reports/pdfs"
    max_retry: int = 3
    data_validation_strict: bool = True


@dataclass
class AnalysisConfig:
    """分析层配置"""
    min_word_count: Dict[str, int] = field(default_factory=lambda: {
        "step_1": 800,
        "step_2": 1200,
        "step_3": 800,
        "step_4": 2000,
        "step_5": 1200,
        "step_6": 800,
        "step_6_5": 600,
        "step_7": 800,
        "step_8": 800,
        "step_9": 800,
        "step_10": 800,
        "step_11": 400,
        "step_12": 1500,
        "step_13": 1200,
        "step_14": 400,
        "step_15": 500,
        "step_16": 300,
    })
    signal_density_min: int = 2
    anomaly_threshold: float = 0.3  # 30% 同比变化阈值


@dataclass
class ValuationConfig:
    """估值层配置"""
    default_wacc: float = 0.085
    default_g_terminal: float = 0.022
    default_tax: float = 0.25
    default_sales_to_capital: float = 1.5
    default_years: int = 10
    terminal_value_max_pct: float = 0.80  # 终值占比上限
    sensitivity_wacc_bps: int = 100  # WACC 敏感性 ±bps
    sensitivity_g_bps: int = 50  # g 敏感性 ±bps
    monte_carlo_iterations: int = 10000


@dataclass
class QualityConfig:
    """质量层配置"""
    pass_rate_threshold: float = 75.0
    hard_fail_items: list = field(default_factory=lambda: [
        "g ≤ Rf",
        "g = ROIC × RR 一致性",
        "13.0 反向论文 3 个 kill points",
        "12.-1 公司类型分类",
        "12.8 市场预期诊断",
        "12.10 估值汇总表",
        "12 个月复盘备忘"
    ])
    pdf_verify_threshold: float = 0.08  # 8% 偏差阈值
    pdf_warn_threshold: float = 0.03   # 3% 偏差警告


@dataclass
class OutputConfig:
    """输出层配置"""
    output_dir: str = "~/reports"
    report_format: str = "markdown"
    include_charts: bool = True
    chart_style: str = "professional"
    auto_open: bool = False


@dataclass
class PlatformConfig:
    """平台总配置"""
    mode: str = "full"  # full/quick
    analyst_name: str = "江安澜"
    data: DataConfig = field(default_factory=DataConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    valuation: ValuationConfig = field(default_factory=ValuationConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


class ConfigManager:
    """
    配置管理器

    功能：
    1. 加载默认配置
    2. 支持用户配置覆盖
    3. 支持环境变量
    4. 配置验证
    5. 配置导出/导入
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径（可选）
        """
        self.config = PlatformConfig()
        self._config_path = config_path

        # 加载配置
        if config_path:
            self.load_config(config_path)

        # 应用环境变量
        self._apply_env_vars()

    def load_config(self, path: str):
        """
        从文件加载配置

        Args:
            path: 配置文件路径
        """
        try:
            path = Path(path).expanduser()
            if not path.exists():
                logger.warning(f"配置文件不存在: {path}")
                return

            with open(path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)

            if user_config:
                self._merge_config(user_config)
                logger.info(f"已加载配置: {path}")

        except Exception as e:
            logger.error(f"加载配置失败: {e}")

    def save_config(self, path: str):
        """
        保存配置到文件

        Args:
            path: 配置文件路径
        """
        try:
            path = Path(path).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)

            config_dict = self._config_to_dict()

            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"已保存配置: {path}")

        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def _merge_config(self, user_config: Dict[str, Any]):
        """合并用户配置"""
        # 模式
        if 'mode' in user_config:
            self.config.mode = user_config['mode']

        # 分析师
        if 'analyst_name' in user_config:
            self.config.analyst_name = user_config['analyst_name']

        # 数据配置
        if 'data' in user_config:
            for key, value in user_config['data'].items():
                if hasattr(self.config.data, key):
                    setattr(self.config.data, key, value)

        # 分析配置
        if 'analysis' in user_config:
            for key, value in user_config['analysis'].items():
                if hasattr(self.config.analysis, key):
                    setattr(self.config.analysis, key, value)

        # 估值配置
        if 'valuation' in user_config:
            for key, value in user_config['valuation'].items():
                if hasattr(self.config.valuation, key):
                    setattr(self.config.valuation, key, value)

        # 质量配置
        if 'quality' in user_config:
            for key, value in user_config['quality'].items():
                if hasattr(self.config.quality, key):
                    setattr(self.config.quality, key, value)

        # 输出配置
        if 'output' in user_config:
            for key, value in user_config['output'].items():
                if hasattr(self.config.output, key):
                    setattr(self.config.output, key, value)

    def _apply_env_vars(self):
        """应用环境变量"""
        env_mapping = {
            'RESEARCH_MODE': ('mode', str),
            'ANALYST_NAME': ('analyst_name', str),
            'DATA_CACHE_DIR': ('data.cache_dir', str),
            'AKSHARE_ENABLED': ('data.akshare_enabled', bool),
            'OUTPUT_DIR': ('output.output_dir', str),
        }

        for env_var, (attr_path, attr_type) in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    if attr_type == bool:
                        value = value.lower() in ('true', '1', 'yes')
                    elif attr_type == int:
                        value = int(value)
                    elif attr_type == float:
                        value = float(value)

                    self._set_nested_attr(attr_path, value)
                except Exception as e:
                    logger.warning(f"环境变量 {env_var} 处理失败: {e}")

    def _set_nested_attr(self, path: str, value: Any):
        """设置嵌套属性"""
        parts = path.split('.')
        obj = self.config
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)

    def _config_to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典"""
        return {
            'mode': self.config.mode,
            'analyst_name': self.config.analyst_name,
            'data': {
                'cache_dir': self.config.data.cache_dir,
                'akshare_enabled': self.config.data.akshare_enabled,
                'akshare_timeout': self.config.data.akshare_timeout,
                'sina_fallback': self.config.data.sina_fallback,
                'pdf_storage_dir': self.config.data.pdf_storage_dir,
                'max_retry': self.config.data.max_retry,
                'data_validation_strict': self.config.data.data_validation_strict,
            },
            'analysis': {
                'min_word_count': self.config.analysis.min_word_count,
                'signal_density_min': self.config.analysis.signal_density_min,
                'anomaly_threshold': self.config.analysis.anomaly_threshold,
            },
            'valuation': {
                'default_wacc': self.config.valuation.default_wacc,
                'default_g_terminal': self.config.valuation.default_g_terminal,
                'default_tax': self.config.valuation.default_tax,
                'default_sales_to_capital': self.config.valuation.default_sales_to_capital,
                'default_years': self.config.valuation.default_years,
                'terminal_value_max_pct': self.config.valuation.terminal_value_max_pct,
                'sensitivity_wacc_bps': self.config.valuation.sensitivity_wacc_bps,
                'sensitivity_g_bps': self.config.valuation.sensitivity_g_bps,
                'monte_carlo_iterations': self.config.valuation.monte_carlo_iterations,
            },
            'quality': {
                'pass_rate_threshold': self.config.quality.pass_rate_threshold,
                'hard_fail_items': self.config.quality.hard_fail_items,
                'pdf_verify_threshold': self.config.quality.pdf_verify_threshold,
                'pdf_warn_threshold': self.config.quality.pdf_warn_threshold,
            },
            'output': {
                'output_dir': self.config.output.output_dir,
                'report_format': self.config.output.report_format,
                'include_charts': self.config.output.include_charts,
                'chart_style': self.config.output.chart_style,
                'auto_open': self.config.output.auto_open,
            },
        }

    def get(self, path: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            path: 配置路径（如 'valuation.default_wacc'）
            default: 默认值

        Returns:
            配置值
        """
        try:
            parts = path.split('.')
            obj = self.config
            for part in parts:
                obj = getattr(obj, part)
            return obj
        except AttributeError:
            return default

    def set(self, path: str, value: Any):
        """
        设置配置值

        Args:
            path: 配置路径
            value: 配置值
        """
        self._set_nested_attr(path, value)

    def validate(self) -> list:
        """
        验证配置

        Returns:
            错误列表
        """
        errors = []

        # 验证模式
        if self.config.mode not in ('full', 'quick'):
            errors.append(f"无效的模式: {self.config.mode}")

        # 验证估值配置
        if self.config.valuation.default_wacc <= 0:
            errors.append("WACC 必须大于 0")

        if self.config.valuation.default_g_terminal >= self.config.valuation.default_wacc:
            errors.append("终值 g 必须小于 WACC")

        if self.config.valuation.default_tax < 0 or self.config.valuation.default_tax > 1:
            errors.append("税率必须在 0-1 之间")

        # 验证质量配置
        if self.config.quality.pass_rate_threshold < 0 or self.config.quality.pass_rate_threshold > 100:
            errors.append("通过率阈值必须在 0-100 之间")

        return errors
