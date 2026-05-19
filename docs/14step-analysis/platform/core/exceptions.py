"""
自定义异常

定义平台特有的异常类型。
"""


class PlatformError(Exception):
    """
    平台基础异常

    所有平台异常的基类。
    """

    def __init__(self, message: str, code: str = "PLATFORM_ERROR", details: dict = None):
        """
        初始化异常

        Args:
            message: 错误消息
            code: 错误代码
            details: 错误详情
        """
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "error": self.__class__.__name__,
            "code": self.code,
            "message": str(self),
            "details": self.details
        }


class DataError(PlatformError):
    """
    数据层异常

    用于数据获取、验证、缓存等场景。
    """

    def __init__(self, message: str, source: str = "", ticker: str = "", **kwargs):
        """
        初始化数据异常

        Args:
            message: 错误消息
            source: 数据来源
            ticker: 股票代码
        """
        super().__init__(
            message,
            code="DATA_ERROR",
            details={"source": source, "ticker": ticker, **kwargs}
        )
        self.source = source
        self.ticker = ticker


class DataFetchError(DataError):
    """数据获取失败"""

    def __init__(self, message: str, source: str = "", ticker: str = "", **kwargs):
        super().__init__(message, source=source, ticker=ticker, **kwargs)
        self.code = "DATA_FETCH_ERROR"


class DataValidationError(DataError):
    """数据验证失败"""

    def __init__(self, message: str, field: str = "", expected: any = None, actual: any = None, **kwargs):
        super().__init__(message, **kwargs)
        self.code = "DATA_VALIDATION_ERROR"
        self.details.update({
            "field": field,
            "expected": expected,
            "actual": actual
        })
        self.field = field


class DataCacheError(DataError):
    """数据缓存失败"""

    def __init__(self, message: str, cache_key: str = "", **kwargs):
        super().__init__(message, **kwargs)
        self.code = "DATA_CACHE_ERROR"
        self.details["cache_key"] = cache_key


class AnalysisError(PlatformError):
    """
    分析层异常

    用于分析过程中的错误。
    """

    def __init__(self, message: str, step: str = "", **kwargs):
        """
        初始化分析异常

        Args:
            message: 错误消息
            step: 步骤名称
        """
        super().__init__(
            message,
            code="ANALYSIS_ERROR",
            details={"step": step, **kwargs}
        )
        self.step = step


class WordCountError(AnalysisError):
    """字数不足异常"""

    def __init__(self, step: str, actual: int, required: int, **kwargs):
        message = f"字数不足: {actual}/{required}"
        super().__init__(message, step=step, **kwargs)
        self.code = "WORD_COUNT_ERROR"
        self.details.update({
            "actual_count": actual,
            "required_count": required,
            "deficit": required - actual
        })
        self.actual = actual
        self.required = required


class SignalDensityError(AnalysisError):
    """信号密度不足异常"""

    def __init__(self, step: str, found: list, required: int, **kwargs):
        message = f"信号密度不足: 找到 {len(found)}/{required}"
        super().__init__(message, step=step, **kwargs)
        self.code = "SIGNAL_DENSITY_ERROR"
        self.details.update({
            "found_keywords": found,
            "required_count": required
        })
        self.found = found


class AnomalyNotExplainedError(AnalysisError):
    """异常未解释异常"""

    def __init__(self, step: str, indicator: str, change_pct: float, **kwargs):
        message = f"异常未解释: {indicator} 变化 {change_pct:.1%}"
        super().__init__(message, step=step, **kwargs)
        self.code = "ANOMALY_NOT_EXPLAINED"
        self.details.update({
            "indicator": indicator,
            "change_pct": change_pct
        })


class ValuationError(PlatformError):
    """
    估值层异常

    用于估值计算中的错误。
    """

    def __init__(self, message: str, method: str = "", **kwargs):
        """
        初始化估值异常

        Args:
            message: 错误消息
            method: 估值方法
        """
        super().__init__(
            message,
            code="VALUATION_ERROR",
            details={"method": method, **kwargs}
        )
        self.method = method


class DCFError(ValuationError):
    """DCF 计算异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, method="DCF", **kwargs)
        self.code = "DCF_ERROR"


class TerminalValueError(DCFError):
    """终值计算异常"""

    def __init__(self, message: str, terminal_pct: float = 0, **kwargs):
        super().__init__(message, **kwargs)
        self.code = "TERMINAL_VALUE_ERROR"
        self.details["terminal_pct"] = terminal_pct
        self.terminal_pct = terminal_pct


class WACCError(DCFError):
    """WACC 计算异常"""

    def __init__(self, message: str, wacc: float = 0, **kwargs):
        super().__init__(message, **kwargs)
        self.code = "WACC_ERROR"
        self.details["wacc"] = wacc
        self.wacc = wacc


class ConsistencyError(ValuationError):
    """一致性校验异常"""

    def __init__(self, message: str, parameter: str = "", deviation: float = 0, **kwargs):
        super().__init__(message, method="consistency_check", **kwargs)
        self.code = "CONSISTENCY_ERROR"
        self.details.update({
            "parameter": parameter,
            "deviation": deviation
        })
        self.parameter = parameter
        self.deviation = deviation


class ValidationError(PlatformError):
    """
    质量校验异常

    用于质检过程中的错误。
    """

    def __init__(self, message: str, check_name: str = "", status: str = "FAIL", **kwargs):
        """
        初始化校验异常

        Args:
            message: 错误消息
            check_name: 检查项名称
            status: 状态 (FAIL/WARN)
        """
        super().__init__(
            message,
            code="VALIDATION_ERROR",
            details={"check_name": check_name, "status": status, **kwargs}
        )
        self.check_name = check_name
        self.status = status


class HardFailError(ValidationError):
    """硬错误异常"""

    def __init__(self, check_name: str, message: str, **kwargs):
        super().__init__(message, check_name=check_name, status="FAIL", **kwargs)
        self.code = "HARD_FAIL_ERROR"


class PDFVerificationError(ValidationError):
    """PDF 核验异常"""

    def __init__(self, message: str, field: str = "", deviation: float = 0, **kwargs):
        super().__init__(message, check_name="pdf_verification", **kwargs)
        self.code = "PDF_VERIFICATION_ERROR"
        self.details.update({
            "field": field,
            "deviation": deviation
        })
        self.field = field
        self.deviation = deviation


class ReportError(PlatformError):
    """
    报告生成异常

    用于报告生成过程中的错误。
    """

    def __init__(self, message: str, report_path: str = "", **kwargs):
        """
        初始化报告异常

        Args:
            message: 错误消息
            report_path: 报告路径
        """
        super().__init__(
            message,
            code="REPORT_ERROR",
            details={"report_path": report_path, **kwargs}
        )
        self.report_path = report_path


class ConfigError(PlatformError):
    """
    配置异常

    用于配置相关的错误。
    """

    def __init__(self, message: str, config_key: str = "", **kwargs):
        """
        初始化配置异常

        Args:
            message: 错误消息
            config_key: 配置键
        """
        super().__init__(
            message,
            code="CONFIG_ERROR",
            details={"config_key": config_key, **kwargs}
        )
        self.config_key = config_key
