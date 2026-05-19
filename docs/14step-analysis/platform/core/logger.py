"""
日志管理

提供统一的日志配置和管理功能。
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logger(
    name: str = "investment_research",
    level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: Optional[str] = None,
    console: bool = True
) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        log_file: 日志文件路径
        log_dir: 日志目录（自动生成文件名）
        console: 是否输出到控制台

    Returns:
        配置好的日志记录器
    """
    # 创建记录器
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除现有处理器
    logger.handlers.clear()

    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # 文件处理器
    if log_file or log_dir:
        if log_dir:
            log_dir = Path(log_dir).expanduser()
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"{name}_{timestamp}.log"
        elif log_file:
            log_file = Path(log_file).expanduser()
            log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


class StepLogger:
    """
    步骤日志记录器

    为每个步骤提供独立的日志记录功能。
    """

    def __init__(self, step_id: str, step_name: str, logger: Optional[logging.Logger] = None):
        """
        初始化步骤日志记录器

        Args:
            step_id: 步骤ID
            step_name: 步骤名称
            logger: 父日志记录器
        """
        self.step_id = step_id
        self.step_name = step_name
        self.logger = logger or logging.getLogger("investment_research")
        self.start_time: Optional[float] = None
        self.messages: list = []

    def start(self, message: str = ""):
        """记录步骤开始"""
        import time
        self.start_time = time.time()
        msg = f"开始 [{self.step_name}]"
        if message:
            msg += f": {message}"
        self.logger.info(msg)
        self.messages.append(("INFO", msg))

    def info(self, message: str):
        """记录信息"""
        self.logger.info(f"[{self.step_name}] {message}")
        self.messages.append(("INFO", message))

    def warning(self, message: str):
        """记录警告"""
        self.logger.warning(f"[{self.step_name}] {message}")
        self.messages.append(("WARNING", message))

    def error(self, message: str):
        """记录错误"""
        self.logger.error(f"[{self.step_name}] {message}")
        self.messages.append(("ERROR", message))

    def complete(self, message: str = ""):
        """记录步骤完成"""
        import time
        if self.start_time:
            duration = time.time() - self.start_time
            msg = f"完成 [{self.step_name}] (耗时: {duration:.1f}秒)"
        else:
            msg = f"完成 [{self.step_name}]"
        if message:
            msg += f": {message}"
        self.logger.info(msg)
        self.messages.append(("INFO", msg))

    def get_messages(self) -> list:
        """获取所有消息"""
        return self.messages.copy()


class AnalysisLogger:
    """
    分析日志记录器

    记录分析过程中的关键数据和结论。
    """

    def __init__(self, ticker: str, output_dir: Optional[str] = None):
        """
        初始化分析日志记录器

        Args:
            ticker: 股票代码
            output_dir: 输出目录
        """
        self.ticker = ticker
        self.output_dir = Path(output_dir) if output_dir else None
        self.entries: list = []
        self.logger = logging.getLogger("investment_research.analysis")

    def log_data(self, data_type: str, data: dict, source: str = ""):
        """
        记录数据

        Args:
            data_type: 数据类型
            data: 数据内容
            source: 数据来源
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "data",
            "data_type": data_type,
            "data": data,
            "source": source
        }
        self.entries.append(entry)
        self.logger.debug(f"数据 [{data_type}]: {source}")

    def log_conclusion(self, step: str, conclusion: str, confidence: float = 1.0):
        """
        记录结论

        Args:
            step: 步骤
            conclusion: 结论
            confidence: 置信度 (0-1)
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "conclusion",
            "step": step,
            "conclusion": conclusion,
            "confidence": confidence
        }
        self.entries.append(entry)
        self.logger.info(f"结论 [{step}]: {conclusion}")

    def log_assumption(self, parameter: str, value: any, basis: str = ""):
        """
        记录假设

        Args:
            parameter: 参数名
            value: 参数值
            basis: 依据
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "assumption",
            "parameter": parameter,
            "value": value,
            "basis": basis
        }
        self.entries.append(entry)
        self.logger.info(f"假设 [{parameter}] = {value}: {basis}")

    def log_warning(self, message: str, context: str = ""):
        """
        记录警告

        Args:
            message: 警告消息
            context: 上下文
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "warning",
            "message": message,
            "context": context
        }
        self.entries.append(entry)
        self.logger.warning(f"警告: {message}")

    def save_log(self, filename: Optional[str] = None):
        """
        保存日志到文件

        Args:
            filename: 文件名
        """
        if not self.output_dir:
            return

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.ticker}_analysis_{timestamp}.json"

        filepath = self.output_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "ticker": self.ticker,
                "entries": self.entries
            }, f, ensure_ascii=False, indent=2)

        self.logger.info(f"分析日志已保存: {filepath}")

    def get_summary(self) -> dict:
        """
        获取日志摘要

        Returns:
            日志摘要
        """
        data_count = sum(1 for e in self.entries if e["type"] == "data")
        conclusion_count = sum(1 for e in self.entries if e["type"] == "conclusion")
        assumption_count = sum(1 for e in self.entries if e["type"] == "assumption")
        warning_count = sum(1 for e in self.entries if e["type"] == "warning")

        return {
            "ticker": self.ticker,
            "total_entries": len(self.entries),
            "data_count": data_count,
            "conclusion_count": conclusion_count,
            "assumption_count": assumption_count,
            "warning_count": warning_count
        }
