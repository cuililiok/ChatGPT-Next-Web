"""
进度管理器

提供任务进度跟踪、可视化和预估剩余时间功能。
"""

import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class StepInfo:
    """步骤信息"""
    step_id: str
    name: str
    status: str = "pending"  # pending, in_progress, completed, skipped, failed
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    progress: float = 0.0  # 0-100
    message: str = ""
    estimated_duration: float = 0.0  # 预估时长（秒）


class ProgressManager:
    """
    进度管理器

    功能：
    1. 跟踪每个步骤的执行状态
    2. 计算总体进度
    3. 预估剩余时间
    4. 提供进度回调
    """

    def __init__(self, mode: str = "full"):
        """
        初始化进度管理器

        Args:
            mode: 执行模式 (full/quick)
        """
        self.mode = mode
        self.steps: Dict[str, StepInfo] = {}
        self.start_time = time.time()
        self.callbacks: List[Callable] = []
        self._init_steps()

    def _init_steps(self):
        """初始化步骤配置"""
        if self.mode == "full":
            step_configs = [
                ("step_0", "数据准备", 300),  # 5分钟
                ("step_1", "公司基本信息", 600),  # 10分钟
                ("step_2", "行业分析", 900),  # 15分钟
                ("step_3", "五年财务", 600),  # 10分钟
                ("step_4", "财务分析", 1200),  # 20分钟
                ("step_5", "年报掘金", 900),  # 15分钟
                ("step_6", "护城河诊断", 600),  # 10分钟
                ("step_6_5", "资本配置回测", 300),  # 5分钟
                ("step_7", "段永平诊断", 600),  # 10分钟
                ("step_8", "发展史", 600),  # 10分钟
                ("step_9", "年报掘金+股价", 600),  # 10分钟
                ("step_10", "投资秘诀", 600),  # 10分钟
                ("step_11", "分析师点评", 300),  # 5分钟
                ("step_12", "估值分析", 2400),  # 40分钟
                ("step_13", "投资建议", 900),  # 15分钟
                ("step_14", "数据来源", 300),  # 5分钟
                ("step_15", "操作触发器", 300),  # 5分钟
                ("step_16", "复盘备忘", 300),  # 5分钟
                ("qa_1", "PDF数据核验", 600),  # 10分钟
                ("qa_2", "质检脚本", 300),  # 5分钟
            ]
        else:  # quick
            step_configs = [
                ("step_0", "数据准备", 300),
                ("step_1", "公司基本信息", 300),
                ("step_2", "行业分析", 300),
                ("step_3", "五年财务", 600),
                ("step_4", "财务分析", 600),
                ("step_5", "年报掘金", 300),
                ("step_11", "分析师点评", 300),
                ("step_12", "估值分析", 1200),
                ("step_13", "投资建议", 600),
                ("step_14", "数据来源", 300),
                ("step_15", "操作触发器", 300),
                ("step_16", "复盘备忘", 300),
                ("qa_1", "PDF数据核验", 300),
                ("qa_2", "质检脚本", 300),
            ]

        for step_id, name, duration in step_configs:
            self.steps[step_id] = StepInfo(
                step_id=step_id,
                name=name,
                estimated_duration=duration
            )

    def start_step(self, step_id: str, message: str = ""):
        """
        开始执行步骤

        Args:
            step_id: 步骤ID
            message: 状态消息
        """
        if step_id not in self.steps:
            logger.warning(f"未知步骤: {step_id}")
            return

        step = self.steps[step_id]
        step.status = "in_progress"
        step.start_time = time.time()
        step.message = message
        step.progress = 0.0

        logger.info(f"开始: {step.name}")
        self._notify_callbacks()

    def update_progress(self, step_id: str, progress: float, message: str = ""):
        """
        更新步骤进度

        Args:
            step_id: 步骤ID
            progress: 进度 (0-100)
            message: 状态消息
        """
        if step_id not in self.steps:
            return

        step = self.steps[step_id]
        step.progress = min(100.0, max(0.0, progress))
        if message:
            step.message = message

        self._notify_callbacks()

    def complete_step(self, step_id: str, message: str = ""):
        """
        完成步骤

        Args:
            step_id: 步骤ID
            message: 完成消息
        """
        if step_id not in self.steps:
            return

        step = self.steps[step_id]
        step.status = "completed"
        step.end_time = time.time()
        step.progress = 100.0
        step.message = message

        logger.info(f"完成: {step.name}")
        self._notify_callbacks()

    def skip_step(self, step_id: str, reason: str = ""):
        """
        跳过步骤

        Args:
            step_id: 步骤ID
            reason: 跳过原因
        """
        if step_id not in self.steps:
            return

        step = self.steps[step_id]
        step.status = "skipped"
        step.end_time = time.time()
        step.progress = 100.0
        step.message = f"跳过: {reason}"

        logger.info(f"跳过: {step.name} - {reason}")
        self._notify_callbacks()

    def fail_step(self, step_id: str, error: str):
        """
        步骤失败

        Args:
            step_id: 步骤ID
            error: 错误信息
        """
        if step_id not in self.steps:
            return

        step = self.steps[step_id]
        step.status = "failed"
        step.end_time = time.time()
        step.message = f"失败: {error}"

        logger.error(f"失败: {step.name} - {error}")
        self._notify_callbacks()

    def get_overall_progress(self) -> float:
        """
        获取总体进度

        Returns:
            总体进度 (0-100)
        """
        if not self.steps:
            return 0.0

        total_weight = sum(s.estimated_duration for s in self.steps.values())
        if total_weight == 0:
            return 0.0

        weighted_progress = sum(
            s.progress * s.estimated_duration / total_weight
            for s in self.steps.values()
        )
        return weighted_progress

    def get_elapsed_time(self) -> float:
        """
        获取已用时间

        Returns:
            已用时间（秒）
        """
        return time.time() - self.start_time

    def get_estimated_remaining(self) -> float:
        """
        预估剩余时间

        Returns:
            预估剩余时间（秒）
        """
        progress = self.get_overall_progress()
        if progress <= 0:
            return sum(s.estimated_duration for s in self.steps.values())

        elapsed = self.get_elapsed_time()
        total_estimated = elapsed / (progress / 100)
        return max(0, total_estimated - elapsed)

    def get_step_status(self, step_id: str) -> Optional[StepInfo]:
        """
        获取步骤状态

        Args:
            step_id: 步骤ID

        Returns:
            步骤信息
        """
        return self.steps.get(step_id)

    def get_all_steps(self) -> List[StepInfo]:
        """
        获取所有步骤

        Returns:
            步骤列表
        """
        return list(self.steps.values())

    def add_callback(self, callback: Callable):
        """
        添加进度回调

        Args:
            callback: 回调函数
        """
        self.callbacks.append(callback)

    def _notify_callbacks(self):
        """通知所有回调"""
        for callback in self.callbacks:
            try:
                callback(self)
            except Exception as e:
                logger.warning(f"回调执行失败: {e}")

    def print_progress(self):
        """打印进度到控制台"""
        progress = self.get_overall_progress()
        elapsed = self.get_elapsed_time()
        remaining = self.get_estimated_remaining()

        # 进度条
        bar_length = 40
        filled = int(bar_length * progress / 100)
        bar = '█' * filled + '░' * (bar_length - filled)

        # 时间格式化
        elapsed_str = self._format_time(elapsed)
        remaining_str = self._format_time(remaining)

        # 输出
        print(f"\r进度: [{bar}] {progress:.1f}% | "
              f"已用: {elapsed_str} | 剩余: {remaining_str}", end='', flush=True)

        # 换行（如果是100%）
        if progress >= 100:
            print()

    def _format_time(self, seconds: float) -> str:
        """格式化时间"""
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}小时"

    def generate_report(self) -> str:
        """
        生成进度报告

        Returns:
            格式化的进度报告
        """
        lines = []
        lines.append("=" * 60)
        lines.append("投资研究进度报告")
        lines.append("=" * 60)
        lines.append(f"模式: {self.mode}")
        lines.append(f"总体进度: {self.get_overall_progress():.1f}%")
        lines.append(f"已用时间: {self._format_time(self.get_elapsed_time())}")
        lines.append(f"预估剩余: {self._format_time(self.get_estimated_remaining())}")
        lines.append("-" * 60)

        # 步骤详情
        for step in self.steps.values():
            status_icon = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "skipped": "⏭️",
                "failed": "❌"
            }.get(step.status, "❓")

            progress_str = f"{step.progress:.0f}%" if step.status != "pending" else ""
            lines.append(f"{status_icon} {step.name:<20} {progress_str:<6} {step.message}")

        lines.append("=" * 60)
        return "\n".join(lines)
