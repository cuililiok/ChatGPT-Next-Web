"""
质量检查器

提供报告质量检查功能。
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from ..core.exceptions import ValidationError, HardFailError

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """检查结果"""
    name: str
    status: str  # PASS, WARN, FAIL, SKIPPED
    message: str
    details: Dict = None


class QualityChecker:
    """
    质量检查器

    功能：
    1. 字数检查
    2. 关键词检查
    3. 信号密度检查
    4. 结构完整性检查
    """

    def __init__(self, mode: str = "full"):
        """
        初始化质量检查器

        Args:
            mode: 执行模式 (full/quick)
        """
        self.mode = mode
        self.results: List[CheckResult] = []

    def check_word_count(
        self,
        step_name: str,
        content: str,
        min_words: int
    ) -> CheckResult:
        """
        检查字数

        Args:
            step_name: 步骤名称
            content: 内容
            min_words: 最低字数

        Returns:
            检查结果
        """
        word_count = len(content)

        if word_count >= min_words:
            status = "PASS"
            message = f"字数 {word_count}/{min_words}"
        else:
            status = "FAIL"
            message = f"字数不足 {word_count}/{min_words}"

        result = CheckResult(
            name=f"{step_name}_字数",
            status=status,
            message=message,
            details={"actual": word_count, "required": min_words}
        )

        self.results.append(result)
        return result

    def check_keywords(
        self,
        step_name: str,
        content: str,
        required_keywords: List[str]
    ) -> CheckResult:
        """
        检查关键词

        Args:
            step_name: 步骤名称
            content: 内容
            required_keywords: 必须包含的关键词

        Returns:
            检查结果
        """
        missing = [kw for kw in required_keywords if kw not in content]

        if not missing:
            status = "PASS"
            message = f"关键词完整 ({len(required_keywords)}/{len(required_keywords)})"
        else:
            status = "WARN"
            message = f"缺少关键词: {missing}"

        result = CheckResult(
            name=f"{step_name}_关键词",
            status=status,
            message=message,
            details={"missing": missing}
        )

        self.results.append(result)
        return result

    def check_signal_density(
        self,
        step_name: str,
        content: str,
        required_keywords: List[str],
        min_found: int = 2
    ) -> CheckResult:
        """
        检查信号密度

        Args:
            step_name: 步骤名称
            content: 内容
            required_keywords: 信号关键词
            min_found: 最少找到数量

        Returns:
            检查结果
        """
        found = [kw for kw in required_keywords if kw in content]

        if len(found) >= min_found:
            status = "PASS"
            message = f"信号密度 {len(found)}/{min_found}"
        else:
            status = "WARN"
            message = f"信号密度不足 {len(found)}/{min_found}"

        result = CheckResult(
            name=f"{step_name}_信号密度",
            status=status,
            message=message,
            details={"found": found, "required": min_found}
        )

        self.results.append(result)
        return result

    def check_consistency(
        self,
        name: str,
        expected: float,
        actual: float,
        tolerance: float = 0.03
    ) -> CheckResult:
        """
        检查一致性

        Args:
            name: 检查名称
            expected: 期望值
            actual: 实际值
            tolerance: 容差

        Returns:
            检查结果
        """
        if expected == 0 and actual == 0:
            status = "PASS"
            message = "一致"
        elif expected == 0:
            status = "WARN"
            message = "期望值为0"
        else:
            diff = abs(actual - expected) / abs(expected)
            if diff <= tolerance:
                status = "PASS"
                message = f"偏差 {diff:.1%}"
            elif diff <= tolerance * 2:
                status = "WARN"
                message = f"偏差 {diff:.1%}（需解释）"
            else:
                status = "FAIL"
                message = f"偏差 {diff:.1%}（超过容差）"

        result = CheckResult(
            name=name,
            status=status,
            message=message,
            details={"expected": expected, "actual": actual, "tolerance": tolerance}
        )

        self.results.append(result)
        return result

    def get_summary(self) -> Dict[str, any]:
        """
        获取检查摘要

        Returns:
            摘要信息
        """
        pass_count = sum(1 for r in self.results if r.status == "PASS")
        warn_count = sum(1 for r in self.results if r.status == "WARN")
        fail_count = sum(1 for r in self.results if r.status == "FAIL")
        total = len(self.results)

        pass_rate = (pass_count / total * 100) if total > 0 else 0

        return {
            "total": total,
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
            "pass_rate": pass_rate,
            "status": "PASS" if fail_count == 0 and pass_rate >= 75 else "FAIL"
        }

    def format_report(self) -> str:
        """
        格式化检查报告

        Returns:
            格式化的报告
        """
        lines = []
        lines.append("=" * 60)
        lines.append("质量检查报告")
        lines.append("=" * 60)

        for result in self.results:
            icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIPPED": "⏭️"}.get(result.status, "❓")
            lines.append(f"{icon} [{result.status:4s}] {result.name}: {result.message}")

        lines.append("-" * 60)

        summary = self.get_summary()
        lines.append(f"总计: {summary['total']} 项检查")
        lines.append(f"通过: {summary['pass']} | 警告: {summary['warn']} | 失败: {summary['fail']}")
        lines.append(f"通过率: {summary['pass_rate']:.1f}%")
        lines.append(f"结论: {summary['status']}")

        lines.append("=" * 60)

        return "\n".join(lines)
