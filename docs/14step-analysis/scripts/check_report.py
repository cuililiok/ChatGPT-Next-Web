#!/usr/bin/env python3
"""
14步深度投资研究报告 — 质检脚本（v4，L3-L4 增强版）

v4 相对于 v3 新增：
  1. L3 数据完备性检查：五年表格空格、WACC推导链完整性、DCF逐年表
  2. L4 业务逻辑检查：WACC算术平衡、终值占比合理性、估值-触发器方向一致性、
     评分权重加总100%、ROIC>WACC价值创造校验
  3. 借鉴 KC_CLI 五层质量保障理念：L1文本→L2语法→L3数据→L4逻辑→L5跨阶段一致性

v3 相对于 v2 修复：
  1. 修复 check_company_classification 中 tuple key bug
  2. 补充 check_signal_density 调用
  3. Quick Mode 标记跳过步骤为 SKIPPED
  4. 添加类型注解和日志支持
  5. 统一配置管理

用法：python check_report.py --report <path> [--mode full|quick]
"""

import argparse
import re
import sys
import logging
from typing import Dict, Tuple, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ---------- 配置常量 ----------

class Config:
    """质检配置"""
    # 字数阈值
    WORD_COUNT_THRESHOLDS = {
        "full": {
            "第一步：公司基本信息": 800,
            "第二步：行业分析": 1200,
            "第三步：五年财务": 800,
            "第四步：财务分析": 2000,
            "第五步：年报掘金": 1200,
            "第六步：巴菲特护城河": 800,
            "第六点五步：管理层资本配置": 600,
            "第七步：段永平": 800,
            "第八步：发展史": 800,
            "第九步：年报掘金及股价": 800,
            "第十步：投资秘诀": 800,
            "第十一步": 400,
            "第十二步：估值分析": 1500,
            "第十三步：投资建议": 1200,
            "第十四步：数据来源": 400,
            "第十五步：操作触发器": 500,
            "第十六步": 300,
        },
        "quick": {
            "第一步：公司基本信息": 300,
            "第二步：行业分析": 500,
            "第三步：五年财务": 800,
            "第四步：财务分析": 800,
            "第五步：年报掘金": 300,
            "第十一步": 200,
            "第十二步：估值分析": 1200,
            "第十三步：投资建议": 800,
            "第十四步：数据来源": 200,
            "第十五步：操作触发器": 500,
            "第十六步": 300,
        }
    }

    # Quick Mode 跳过的步骤
    QUICK_MODE_SKIPPED_STEPS = [
        "第六步：巴菲特护城河",
        "第六点五步：管理层资本配置",
        "第七步：段永平",
        "第八步：发展史",
        "第九步：年报掘金及股价",
        "第十步：投资秘诀",
    ]

    # 关键词配置
    KEYWORDS = {
        "full": {
            "第一步：公司基本信息": ["股票代码", "上市时间", "主营业务", "产业链位置", "术语"],
            "第二步：行业分析": ["生命周期", "TAM", "竞争格局", "供需"],
            "第三步：五年财务": ["营业收入", "净利润", "毛利率", "净利率", "ROE", "资产负债率", "EPS", "经营现金流"],
            "第四步：财务分析": ["财务真实性", "盈利质量", "资产效率", "财务安全", "成长能力", "股东回报"],
            "第五步：年报掘金": ["异常波动", "管理层", "战略"],
            "第六步：巴菲特护城河": ["护城河", "规模效应", "成本优势", "品牌"],
            "第六点五步：管理层资本配置": ["留存收益", "回购", "并购", "稀释"],
            "第七步：段永平": ["段永平", "产品", "商业模式", "管理层"],
            "第八步：发展史": ["发展史"],
            "第九步：年报掘金及股价": ["股价"],
            "第十步：投资秘诀": ["核心逻辑", "跟踪指标", "风险提示"],
            "第十一步": ["亮点", "隐忧"],
            "第十二步：估值分析": ["估值", "DCF", "WACC"],
            "第十三步：投资建议": ["反向论文", "kill point", "能力圈", "评分", "确定性"],
            "第十四步：数据来源": ["数据来源", "skill"],
            "第十五步：操作触发器": ["触发", "估值面", "历史分位"],
            "第十六步": ["复盘", "假设", "回看"],
        },
        "quick": {
            "第一步：公司基本信息": ["股票代码", "主营业务", "术语"],
            "第二步：行业分析": ["生命周期", "竞争格局"],
            "第三步：五年财务": ["营业收入", "净利润", "毛利率", "ROE"],
            "第四步：财务分析": ["财务真实性", "盈利质量", "财务安全"],
            "第五步：年报掘金": ["管理层", "战略"],
            "第十一步": ["亮点", "隐忧", "风险"],
            "第十二步：估值分析": ["估值", "WACC"],
            "第十三步：投资建议": ["反向论文", "kill point", "能力圈", "评分"],
            "第十四步：数据来源": ["数据来源"],
            "第十五步：操作触发器": ["触发", "估值面"],
            "第十六步": ["复盘", "假设", "回看"],
        }
    }

    # 信号密度检查配置
    SIGNAL_DENSITY_CHECKS = {
        "第四步": {
            "keywords": ["量化", "同比", "趋势", "异常"],
            "label": "财务分析信号密度",
            "min_found": 2
        },
        "第五步": {
            "keywords": ["量化", "同比", "变化", "反向"],
            "label": "年报掘金信号密度",
            "min_found": 2
        },
        "第十二步": {
            "keywords": ["来源", "对照", "敏感性", "分位"],
            "label": "估值分析信号密度",
            "min_found": 2
        }
    }

    # 结构性硬错误列表
    HARD_FAIL_ITEMS = [
        "g ≤ Rf",
        "g = ROIC × RR 一致性",
        "13.0 反向论文 3 个 kill points",
        "12.-1 公司类型分类",
        "12.8 市场预期诊断",
        "12.10 估值汇总表",
        "12 个月复盘备忘",
        "L3 WACC推导链",
        "L4 WACC算术平衡",
    ]

    # 通过阈值
    PASS_RATE_THRESHOLD = 75


# ---------- 工具函数 ----------

def find_section(content: str, start_markers: list, next_markers: list) -> str:
    """找出从某个标题到下一个标题之间的内容。"""
    for sm in start_markers:
        idx = content.find(sm)
        if idx >= 0:
            tail = content[idx:]
            cut = len(tail)
            for nm in next_markers:
                ni = tail.find(nm, len(sm))
                if 0 < ni < cut:
                    cut = ni
            return tail[:cut]
    return ""


def parse_pct(s: str) -> Optional[float]:
    """从字符串中提取百分数，如 '3.0%' / '3%' / '0.03'。"""
    if s is None:
        return None
    s = s.strip().replace(",", "").replace("％", "%")
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*%", s)
    if m:
        return float(m.group(1))
    try:
        v = float(s)
        if abs(v) < 1:
            return v * 100
        return v
    except Exception:
        return None


def parse_number(s: str) -> Optional[float]:
    """从字符串中提取数字。"""
    if s is None:
        return None
    s = s.strip().replace(",", "")
    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None


def extract_rr_actual(sec: str) -> Optional[float]:
    """行级容错提取：找包含'实际 RR'的整行，提取最后一个百分数。"""
    for line in sec.split('\n'):
        if "实际 RR" in line or "实际RR" in line:
            nums = re.findall(r"(\d+(?:\.\d+)?)\s*%", line)
            if nums:
                return float(nums[-1])
    return None


def extract_rr_implied(sec: str) -> Optional[float]:
    """行级容错提取：找包含'隐含 RR'的整行，提取最后一个百分数。"""
    for line in sec.split('\n'):
        if "隐含 RR" in line or "隐含RR" in line or "隐含 Reinvestment" in line:
            nums = re.findall(r"(\d+(?:\.\d+)?)\s*%", line)
            if nums:
                return float(nums[-1])
    return None


# ---------- 校验函数 ----------

def check_word_count_and_keywords(content: str, results: Dict[str, Tuple[str, str]], mode: str):
    """字数 + 关键词存在校验。"""
    steps = Config.WORD_COUNT_THRESHOLDS[mode]
    keywords = Config.KEYWORDS[mode]

    # 标记 Quick Mode 跳过的步骤
    if mode == "quick":
        for skipped_step in Config.QUICK_MODE_SKIPPED_STEPS:
            results[skipped_step] = ("SKIPPED", "Quick Mode 跳过")

    for name, min_chars in steps.items():
        kws = keywords.get(name, [])
        sec = find_section(content,
                           [f"### {name}", f"## {name}", f"# {name}", name],
                           [f"### 第", f"## 第", "## 质量门"])
        chars = len(sec)
        missing = [kw for kw in kws if kw not in sec]
        if chars < min_chars and missing:
            results[name] = ("FAIL", f"字数 {chars}/{min_chars}，缺关键词 {missing}")
        elif chars < min_chars:
            results[name] = ("WARN", f"字数 {chars}/{min_chars}（关键词全）")
        elif missing:
            results[name] = ("WARN", f"字数 OK，缺关键词 {missing}")
        else:
            results[name] = ("PASS", f"字数 {chars}")


def check_section_12_6_consistency(content: str, results: Dict[str, Tuple[str, str]]):
    """校验 12.6 的 g、ROIC、RR 一致性，以及终值占比、SBC、NCI、CRP。"""
    sec = find_section(content,
                       ["**第三层：终值与股权价值推导**", "### 12.6 ", "12.6 完整DCF", "12.6 DCF"],
                       ["### 12.7", "### 12.8", "## 第十三步"])
    if not sec:
        results["12.6 一致性"] = ("WARN", "未找到 12.6 章节内容")
        return

    # 1. g vs Rf
    g_match = re.search(r"终值增长率\s*g\s*=\s*([\d.]+)\s*%?", sec)
    rf_match = re.search(r"Rf\s*[约≈]?\s*=?\s*([\d.]+)\s*%?", content[:8000])
    if g_match and rf_match:
        g = parse_pct(g_match.group(1) + "%")
        rf = parse_pct(rf_match.group(1) + "%")
        if g and rf and g > rf + 0.05:
            results["g ≤ Rf"] = ("FAIL", f"终值 g={g:.2f}% > Rf={rf:.2f}%；违反 g ≤ min(GDP, Rf)")
        else:
            results["g ≤ Rf"] = ("PASS", f"g={g}% Rf={rf}%")
    else:
        results["g ≤ Rf"] = ("WARN", "未能提取 g 或 Rf")

    # 1b. g vs GDP（要求报告中明确写出GDP增速假设）
    gdp_match = re.search(r"GDP.*?增速.*?([\d.]+)\s*%|名义GDP.*?([\d.]+)\s*%", content[:8000])
    if gdp_match and g_match:
        gdp = parse_pct(gdp_match.group(1) or gdp_match.group(2))
        g = parse_pct(g_match.group(1) + "%")
        if gdp and g and g > gdp + 0.05:
            results["g ≤ GDP"] = ("FAIL", f"终值 g={g:.2f}% > GDP增速={gdp:.2f}%")
        elif gdp and g:
            results["g ≤ GDP"] = ("PASS", f"g={g}% GDP={gdp}%")
        else:
            results["g ≤ GDP"] = ("WARN", "GDP增速假设不明确，请报告12.6中补充GDP增速假设")
    else:
        results["g ≤ GDP"] = ("WARN", "未找到GDP增速假设——请在12.6中明确写出'名义GDP长期增速 = X%'")

    # 2. g = ROIC × RR
    roic_m = re.search(r"预测期平均\s*ROIC\s*=\s*([\d.]+)\s*%", sec)
    if roic_m:
        rr_implied = extract_rr_implied(sec)
        rr_actual = extract_rr_actual(sec)
        if rr_implied and rr_actual:
            dev = abs(rr_implied - rr_actual)
            if dev > 3:
                results["g = ROIC × RR 一致性"] = ("FAIL",
                    f"隐含RR={rr_implied:.1f}% vs 实际RR={rr_actual:.1f}%，偏差{dev:.1f}ppt > 3ppt，必须重做")
            elif dev > 1.5:
                results["g = ROIC × RR 一致性"] = ("WARN",
                    f"隐含RR={rr_implied:.1f}% vs 实际RR={rr_actual:.1f}%，偏差{dev:.1f}ppt（1.5–3ppt，需解释）")
            else:
                results["g = ROIC × RR 一致性"] = ("PASS",
                    f"隐含RR={rr_implied:.1f}% vs 实际RR={rr_actual:.1f}%，偏差{dev:.1f}ppt")
        else:
            results["g = ROIC × RR 一致性"] = ("WARN", "未能提取隐含 RR 或实际 RR")
    else:
        results["g = ROIC × RR 一致性"] = ("WARN", "未找到预测期平均 ROIC")

    # 3. 终值占比
    tv_match = re.search(r"终值占比\s*=\s*([\d.]+)\s*%", sec)
    if tv_match:
        tv_pct = float(tv_match.group(1))
        if tv_pct > 80:
            results["终值占比 < 80%"] = ("FAIL", f"终值占比 {tv_pct:.0f}% > 80%，需延长预测期或审视终值假设")
        else:
            results["终值占比 < 80%"] = ("PASS", f"终值占比 {tv_pct:.0f}%")
    else:
        results["终值占比 < 80%"] = ("WARN", "未找到终值占比数据")

    # 4. SBC 处理声明
    if "路径 A" in sec or "路径 B" in sec or "SBC" in sec:
        if ("路径 A" in sec or "路径 B" in sec) and ("全摊薄" in sec or "基础股数" in sec):
            results["SBC 处理"] = ("PASS", "已声明SBC处理路径")
        else:
            results["SBC 处理"] = ("WARN", "提及SBC但未明确声明二选一路径")
    else:
        results["SBC 处理"] = ("WARN", "未找到SBC处理声明")

    # 5. NCI 扣除
    has_nci = "少数股东权益" in sec or "NCI" in sec
    has_deduct = "扣除" in sec or "减" in sec
    if has_nci and has_deduct:
        results["NCI 扣除"] = ("PASS", "已提及少数股东权益扣除")
    elif has_nci:
        results["NCI 扣除"] = ("WARN", "提及NCI但扣除方式不明确")
    else:
        results["NCI 扣除"] = ("WARN", "未找到少数股东权益（NCI）扣除声明")

    # 6. A 股 ERP 含 CRP
    if "CRP" in content[:8000] and "中国" in content[:8000]:
        if "5.1" in content[:8000] or "5.15" in content[:8000] or "5.13" in content[:8000]:
            results["A股 ERP 含 CRP"] = ("PASS", "ERP 已含中国 CRP")
        else:
            results["A股 ERP 含 CRP"] = ("WARN", "提及CRP但ERP数值待确认")
    else:
        results["A股 ERP 含 CRP"] = ("WARN", "未找到A股ERP含中国CRP的声明")


def check_section_12_9(content: str, results: Dict[str, Tuple[str, str]]):
    """校验 12.9 近期驱动事件日历。"""
    sec = find_section(content,
                       ["12.9 近期驱动事件", "12.9 近期", "### 12.9"],
                       ["## 第十三步", "### 第十三步", "### 13.0"])
    if not sec:
        results["12.9 催化剂日历"] = ("FAIL", "未找到 12.9 近期驱动事件日历章节")
        return

    # 检查是否有表格（至少3行数据行）
    lines = sec.split('\n')
    # 找到表格行（以 | 开头），排除分隔行（只有 -、|、:、空格）
    separator_pattern = re.compile(r'^\|[\s\-:|]+\|$')
    table_lines = [l.strip() for l in lines if l.strip().startswith('|')]
    data_rows = [l for l in table_lines if not separator_pattern.match(l)]
    # 减去表头行（第一行通常是表头）
    data_row_count = max(0, len(data_rows) - 1)

    if data_row_count < 3:
        results["12.9 催化剂日历"] = ("FAIL", f"事件数量 {data_row_count} < 3，最少需要3个事件")
        return

    # 检查是否有关联kill point
    has_kill_point_link = "kill point" in sec.lower() or "触发 kill" in sec
    if not has_kill_point_link:
        results["12.9 催化剂日历"] = ("WARN", f"有{data_row_count}个事件但未关联13.0 kill point")
        return

    # 检查影响幅度是否有数字（不能只有模糊词）
    has_number = bool(re.search(r'[\+\-]?\d+\s*[\-\u2013~]?\s*\d+\s*%', sec))
    if not has_number:
        results["12.9 催化剂日历"] = ("WARN", f"有{data_row_count}个事件但影响幅度缺少数字区间")
        return

    # 检查事件分类标签（[财报]/[产能]/[政策]/[竞品]/[宏观]/[资本]）
    has_category = bool(re.search(r'\[(财报|产能|政策|竞品|宏观|资本)\]', sec))
    if not has_category:
        results["12.9 催化剂日历"] = ("WARN", f"有{data_row_count}个事件但缺少分类标签（[财报]/[产能]等）")
        return

    # 检查DCF价格内声明
    has_dcf_link = bool(re.search(r'DCF.*(?:price in|反映|已.*假设|增量)', sec, re.IGNORECASE))
    if not has_dcf_link:
        results["12.9 催化剂日历"] = ("WARN", f"有{data_row_count}个事件但缺少DCF价格内声明")
        return

    results["12.9 催化剂日历"] = ("PASS", f"{data_row_count} 个事件，已关联 kill point，有数字区间，有分类标签，有DCF声明")


def check_section_12_10(content: str, results: Dict[str, Tuple[str, str]]):
    """校验 12.10 估值方法汇总表。"""
    sec = find_section(content,
                       ["12.10 估值方法汇总", "12.10 估值", "### 12.10", "估值方法完整汇总"],
                       ["## 第十三步", "### 第十三步", "### 12.9", "## 质量门"])
    if not sec:
        results["12.10 估值汇总表"] = ("FAIL", "未找到 12.10 估值方法汇总表章节")
        return

    # 检查是否包含估值方法表格
    has_table = bool(re.search(r'\|.*估值方法.*\|.*估值结果.*\|', sec))
    if not has_table:
        results["12.10 估值汇总表"] = ("FAIL", "缺少估值方法汇总表格")
        return

    # 检查是否包含各方法的具体价格
    methods = ["DCF", "PE历史分位", "PB历史分位", "同业对比", "反向DCF", "加权估值"]
    found_methods = [m for m in methods if m in sec]
    if len(found_methods) < 4:
        results["12.10 估值汇总表"] = ("FAIL", f"估值方法不完整，仅找到 {found_methods}（需≥4种）")
        return

    # 检查是否有具体价格（XX元格式）
    price_pattern = r'\d+\.?\d*元'
    prices = re.findall(price_pattern, sec)
    if len(prices) < 4:
        results["12.10 估值汇总表"] = ("FAIL", f"缺少具体价格，仅找到 {len(prices)} 个（需≥4个）")
        return

    # 检查是否有可视化图
    has_visualization = bool(re.search(r'价格轴|估值区间|深度低估|低估|合理|高估|泡沫', sec))
    if not has_visualization:
        results["12.10 估值汇总表"] = ("WARN", "缺少估值区间可视化图")
        return

    # 检查是否有投资决策建议表
    has_decision_table = bool(re.search(r'操作建议|买入|建仓|减仓|清仓', sec))
    if not has_decision_table:
        results["12.10 估值汇总表"] = ("WARN", "缺少投资决策建议表")
        return

    results["12.10 估值汇总表"] = ("PASS", f"包含{len(found_methods)}种估值方法，{len(prices)}个价格，有可视化和决策建议")


def check_signal_density(content: str, results: Dict[str, Tuple[str, str]]):
    """信号密度校验：第四步、第五步、第十二步的段落应包含量化证据。"""
    for step_name, config in Config.SIGNAL_DENSITY_CHECKS.items():
        sec = find_section(content,
                           [f"### {step_name}", f"## {step_name}"],
                           [f"### 第", f"## 第", "## 质量门"])
        if not sec:
            continue
        found_kws = [kw for kw in config["keywords"] if kw in sec]
        if len(found_kws) >= config["min_found"]:
            results[config["label"]] = ("PASS", f"信号密度关键词 {found_kws}")
        else:
            results[config["label"]] = ("WARN", f"信号密度偏低，仅找到 {found_kws}（需≥{config['min_found']}）")


def check_section_12_8(content: str, results: Dict[str, Tuple[str, str]], mode: str):
    """校验 12.8 市场预期诊断。"""
    sec = find_section(content,
                       ["12.8 市场预期诊断", "12.8.1", "反向 DCF"],
                       ["第十三步", "质量门"])

    if not sec:
        results["12.8 市场预期诊断"] = ("FAIL" if mode == "full" else "WARN", "未找到 12.8 章节")
        return

    checks = []
    # Full mode: 需要 12.8.1 + 12.8.2 + 12.8.4
    # Quick mode: 仅需 12.8.1 + 12.8.4
    checks.append(("12.8.1 反向 DCF", any(k in sec for k in ["反向 DCF", "隐含", "市场隐含", "delta"])))
    if mode == "full":
        checks.append(("12.8.2 历史隐含 g", any(k in sec for k in ["历史隐含", "implied_g", "P25", "P50", "P75"])))
    checks.append(("12.8.4 四象限", "四象限" in sec or "决策矩阵" in sec))

    all_pass = True
    details = []
    for name, found in checks:
        if found:
            details.append(f"{name} ✓")
        else:
            details.append(f"{name} ✗")
            all_pass = False

    # 检查是否只引用了delta（禁止引用绝对值）
    if "市场隐含" in sec and "Delta" in sec:
        results["12.8 市场预期诊断"] = ("PASS", "; ".join(details))
    elif "市场隐含" in sec and "delta" in sec.lower():
        results["12.8 市场预期诊断"] = ("PASS", "; ".join(details))
    elif "市场隐含" in sec:
        results["12.8 市场预期诊断"] = ("WARN", "; ".join(details) + "（请确认只引用 delta 而非绝对值）")
    else:
        results["12.8 市场预期诊断"] = ("PASS" if all_pass else "WARN", "; ".join(details))


def check_step_13_kill_points(content: str, results: Dict[str, Tuple[str, str]]):
    """检查 13.0 反向论文 kill points。"""
    sec = find_section(content,
                       ["13.0 反向论文", "反向论文", "Pre-mortem"],
                       ["13.1", "能力圈", "13.2"])
    kp_count = len(re.findall(r"Kill Point|kill point|Kill point|kill #", sec, re.IGNORECASE))
    if kp_count >= 3:
        results["13.0 反向论文 3 个 kill points"] = ("PASS", f"{kp_count} 个")
    elif kp_count > 0:
        results["13.0 反向论文 3 个 kill points"] = ("WARN", f"仅 {kp_count} 个")
    else:
        results["13.0 反向论文 3 个 kill points"] = ("FAIL", "未找到 kill points")


def check_step_13_capability_circle(content: str, results: Dict[str, Tuple[str, str]]):
    """检查能力圈自评。"""
    sec = find_section(content,
                       ["13.1 能力圈", "能力圈自评"],
                       ["13.2", "评分表", "否决项"])
    items = re.findall(r"☑|☐|✓|✗|√|×|满足项", sec)
    if len(items) >= 5 or "满足项" in sec:
        results["能力圈自评 5 项"] = ("PASS", f"{len(items)} 项勾选")
    elif len(items) > 0:
        results["能力圈自评 5 项"] = ("WARN", f"仅 {len(items)} 项勾选")
    else:
        results["能力圈自评 5 项"] = ("WARN", "未找到勾选项格式（请用 ☑/☐）")


def check_step_15_trigger(content: str, results: Dict[str, Tuple[str, str]]):
    """检查操作触发器。"""
    sec = find_section(content,
                       ["第十五步：操作触发器", "操作触发器", "Operation Trigger"],
                       ["第十六步", "12 个月"])
    trigger_types = re.findall(r"\b[A-E]\s*类", sec)
    if trigger_types:
        results["Step 15 操作触发器"] = ("PASS", f"勾选类型: {trigger_types}")
    elif "触发" in sec and "操作" in sec:
        results["Step 15 操作触发器"] = ("WARN", "有触发器内容但未明确标注 A–E 类型")
    else:
        results["Step 15 操作触发器"] = ("WARN", "未找到操作触发器章节")


def check_step_16_review_memo(content: str, results: Dict[str, Tuple[str, str]]):
    """检查复盘备忘。"""
    sec = find_section(content,
                       ["第十六步", "12 个月", "复盘备忘"],
                       ["质量门"])
    if not sec:
        results["12 个月复盘备忘"] = ("FAIL", "未找到复盘备忘章节")
        return

    required = ["核心假设", "kill point", "回看", "复盘"]
    found = [r for r in required if r.lower() in sec.lower()]
    if len(found) >= 3:
        results["12 个月复盘备忘"] = ("PASS", f"包含 {len(found)}/{len(required)} 项")
    elif len(found) > 0:
        results["12 个月复盘备忘"] = ("WARN", f"仅包含 {len(found)}/{len(required)} 项")
    else:
        results["12 个月复盘备忘"] = ("FAIL", "复盘备忘缺失或不完整")

    # 检查 frontmatter
    if "review_due" in content[:500]:
        results["frontmatter review_due"] = ("PASS", "已设置回看日期")
    else:
        results["frontmatter review_due"] = ("WARN", "报告开头未包含 frontmatter（ticker/report_date/review_due/mode）")


def check_company_classification(content: str, results: Dict[str, Tuple[str, str]]):
    """检查公司类型分类。"""
    # 修复：原来是 tuple key bug，现在改为正确的 string key
    if re.search(r"主类型\s*=\s*\[?[A-H]", content) or "公司类型判断" in content:
        results["12.-1 公司类型分类"] = ("PASS", "已分类")
    else:
        results["12.-1 公司类型分类"] = ("FAIL", "未做公司类型分类（必须前置）")


def check_skill_records(content: str, results: Dict[str, Tuple[str, str]]):
    """检查 skill 调用记录。"""
    n = len(re.findall(r"skill调用记录|skill 调用记录", content))
    if n >= 3:
        results["skill 调用记录"] = ("PASS", f"{n} 处")
    elif n > 0:
        results["skill 调用记录"] = ("WARN", f"仅 {n} 处")
    else:
        results["skill 调用记录"] = ("FAIL", "未找到 skill 调用记录")


def check_pdf_verification(content: str, results: Dict[str, Tuple[str, str]]):
    """检查 PDF 数据核验记录。"""
    if "pdf-verifier" in content or "数据核验" in content or "PDF 核验" in content:
        results["数据核验"] = ("PASS", "已包含核验记录")
    else:
        results["数据核验"] = ("WARN", "未找到数据核验记录")


# ---------- L3 数据完备性检查 ----------

def check_l3_data_completeness(content: str, results: Dict[str, Tuple[str, str]]):
    """
    L3 数据完备性校验（不需要 LLM，纯正则检查）：
    1. 五年财务表格是否有空格/缺失
    2. DCF WACC 推导链是否完整（Rf → Beta → ERP → Ke → Kd → WACC）
    3. 终值占比是否已计算
    4. 估值汇总表每个方法是否有具体数字
    """
    # --- L3.1 五年财务表格空格检查 ---
    sec_step3 = find_section(content,
                             ["### 第三步", "## 第三步", "五年财务"],
                             ["### 第四步", "## 第四步"])
    if sec_step3:
        # 找表格行，检查是否有空单元格（连续的 | | 或 |  |）
        table_lines = [l for l in sec_step3.split('\n') if l.strip().startswith('|')]
        empty_cells = 0
        for line in table_lines:
            # 排除分隔行
            if re.match(r'^\|[\s\-:|]+\|$', line.strip()):
                continue
            # 检查空单元格：| | 或 |   | 或 |--|
            cells = line.split('|')[1:-1]  # 去掉首尾空串
            for cell in cells:
                if cell.strip() == '' or cell.strip() == '-' or cell.strip() == '--':
                    empty_cells += 1

        if empty_cells == 0:
            results["L3 五年表格完整性"] = ("PASS", "表格无空格")
        elif empty_cells <= 3:
            results["L3 五年表格完整性"] = ("WARN", f"表格有 {empty_cells} 个空单元格")
        else:
            results["L3 五年表格完整性"] = ("FAIL", f"表格有 {empty_cells} 个空单元格（>3 处缺失）")
    else:
        results["L3 五年表格完整性"] = ("WARN", "未找到第三步章节")

    # --- L3.2 WACC 推导链完整性检查 ---
    sec_dcf = find_section(content,
                           ["12.6 ", "**第一层：关键参数", "参数设定依据"],
                           ["### 12.7", "**第二层", "年度预测"])
    if not sec_dcf:
        sec_dcf = find_section(content,
                               ["WACC", "Ke =", "Kd"],
                               ["### 12.7", "### 12.8"])

    wacc_chain = {
        "Rf": bool(re.search(r'Rf\s*[=≈]\s*[\d.]+\s*%?', content)),
        "Beta": bool(re.search(r'[Bb]eta\s*[=≈]\s*[\d.]+', content)),
        "ERP": bool(re.search(r'ERP\s*[=≈]?\s*[\d.]+\s*%?', content)),
        "Ke": bool(re.search(r'Ke\s*[=≈]\s*[\d.]+\s*%?', content)),
        "Kd": bool(re.search(r'Kd\s*[×x*]?\s*\(?1\s*[-–]\s*t\)?.*?[=≈]\s*[\d.]+\s*%?|税后债务成本', content)),
        "WACC": bool(re.search(r'WACC\s*[=≈]\s*[\d.]+\s*%?', content)),
    }
    missing_chain = [k for k, v in wacc_chain.items() if not v]

    if not missing_chain:
        results["L3 WACC推导链"] = ("PASS", "Rf→Beta→ERP→Ke→Kd→WACC 完整")
    elif len(missing_chain) <= 2:
        results["L3 WACC推导链"] = ("WARN", f"推导链缺少: {missing_chain}")
    else:
        results["L3 WACC推导链"] = ("FAIL", f"推导链严重不完整，缺少: {missing_chain}")

    # --- L3.3 DCF 逐年预测表检查（Full Mode）---
    # 找 DCF 逐年表格，检查是否有 ≥5 行数据行
    sec_annual = find_section(content,
                              ["**第二层：年度预测", "年度预测展示", "逐年预测"],
                              ["**第三层", "终值与股权", "### 12.7"])
    if sec_annual:
        table_lines = [l for l in sec_annual.split('\n') if l.strip().startswith('|')]
        separator_pattern = re.compile(r'^\|[\s\-:|]+\|$')
        data_rows = [l for l in table_lines
                     if not separator_pattern.match(l.strip()) and 'E' in l]
        if len(data_rows) >= 5:
            results["L3 DCF逐年表"] = ("PASS", f"{len(data_rows)} 年预测数据")
        elif len(data_rows) >= 3:
            results["L3 DCF逐年表"] = ("WARN", f"仅 {len(data_rows)} 年预测（建议≥5年）")
        else:
            results["L3 DCF逐年表"] = ("FAIL", f"仅 {len(data_rows)} 年预测数据（需≥5年）")
    else:
        results["L3 DCF逐年表"] = ("WARN", "未找到逐年预测表章节")


# ---------- L4 业务逻辑检查（轻量版，纯算术） ----------

def check_l4_business_logic(content: str, results: Dict[str, Tuple[str, str]]):
    """
    L4 业务逻辑校验（不需要 LLM，纯算术）：
    1. WACC = Ke × 权重 + Kd×(1-t) × 权重 两端是否平衡
    2. 终值占比是否 < 80%
    3. 隐含 RR vs 实际 RR 偏差是否 < 3ppt
    4. 估值结论自洽性：DCF估值与操作触发器方向是否一致
    5. 评分维度权重加总是否 = 100%
    """
    # --- L4.1 WACC 算术平衡 ---
    # 尝试提取 Ke, Kd(1-t), 权重
    ke_match = re.search(r'Ke\s*[=≈]\s*([\d.]+)\s*%', content)
    kd_match = re.search(r'(?:税后债务成本|Kd[×x*]\s*\(1[-–]t\))\s*[=≈]\s*([\d.]+)\s*%', content)
    wacc_match = re.search(r'WACC\s*[=≈]\s*([\d.]+)\s*%', content)
    # 权重提取
    equity_weight = re.search(r'([\d.]+)\s*%\s*(?:股权|权益|equity)', content, re.IGNORECASE)
    debt_weight = re.search(r'([\d.]+)\s*%\s*(?:债务|负债|debt)', content, re.IGNORECASE)

    if ke_match and kd_match and wacc_match and equity_weight and debt_weight:
        ke = float(ke_match.group(1))
        kd = float(kd_match.group(1))
        wacc = float(wacc_match.group(1))
        we = float(equity_weight.group(1)) / 100
        wd = float(debt_weight.group(1)) / 100

        calculated_wacc = ke * we + kd * wd
        diff = abs(calculated_wacc - wacc)

        if diff <= 0.3:  # 容差 0.3ppt（四舍五入差异）
            results["L4 WACC算术平衡"] = ("PASS",
                f"Ke({ke}%)×{we:.0%} + Kd({kd}%)×{wd:.0%} = {calculated_wacc:.2f}% ≈ WACC({wacc}%)")
        elif diff <= 0.8:
            results["L4 WACC算术平衡"] = ("WARN",
                f"计算 WACC={calculated_wacc:.2f}% vs 报告 WACC={wacc}%，偏差{diff:.2f}ppt（需检查四舍五入）")
        else:
            results["L4 WACC算术平衡"] = ("FAIL",
                f"计算 WACC={calculated_wacc:.2f}% vs 报告 WACC={wacc}%，偏差{diff:.2f}ppt > 0.8ppt")
    else:
        results["L4 WACC算术平衡"] = ("WARN", "未能完整提取Ke/Kd/权重/WACC，无法自动校验")

    # --- L4.2 终值占比（已在 check_section_12_6_consistency 中覆盖，此处做冗余确认）---
    tv_match = re.search(r'终值占比\s*=\s*([\d.]+)\s*%', content)
    if tv_match:
        tv_pct = float(tv_match.group(1))
        if tv_pct > 80:
            results["L4 终值占比合理性"] = ("FAIL", f"终值占比 {tv_pct:.0f}% > 80%（估值可能不可靠）")
        elif tv_pct > 70:
            results["L4 终值占比合理性"] = ("PASS", f"终值占比 {tv_pct:.0f}%（偏高但可接受，建议延长预测期）")
        else:
            results["L4 终值占比合理性"] = ("PASS", f"终值占比 {tv_pct:.0f}%")
    else:
        results["L4 终值占比合理性"] = ("WARN", "未找到终值占比数据")

    # --- L4.3 估值方向与操作触发器一致性 ---
    # 提取估值偏离幅度
    overunder = re.search(r'(?:高估|低估).*?(\d+(?:\.\d+)?)\s*%', content[content.find("12.10") if "12.10" in content else 0:])
    trigger_type = re.search(r'本次报告触发的操作类型：\s*\[?\s*([A-E])', content)

    if overunder and trigger_type:
        is_undervalued = "低估" in content[max(0, overunder.start() - 20):overunder.end()]
        trigger = trigger_type.group(1)

        # 简单一致性：低估应对应 A/B 类触发器，高估应对应 D/E 类
        if is_undervalued and trigger in ('A', 'B'):
            results["L4 估值-触发器一致性"] = ("PASS", f"低估 → {trigger}类触发器（买入方向），一致")
        elif not is_undervalued and trigger in ('D', 'E'):
            results["L4 估值-触发器一致性"] = ("PASS", f"高估 → {trigger}类触发器（减仓/禁止方向），一致")
        elif is_undervalued and trigger in ('D', 'E'):
            results["L4 估值-触发器一致性"] = ("WARN",
                f"估值显示低估但触发器为 {trigger} 类（减仓方向）——请检查是否有 kill point 或能力圈约束")
        elif not is_undervalued and trigger in ('A', 'B'):
            results["L4 估值-触发器一致性"] = ("WARN",
                f"估值显示高估但触发器为 {trigger} 类（买入方向）——请检查是否有催化剂支撑")
        else:
            results["L4 估值-触发器一致性"] = ("PASS", f"触发器类型 {trigger}，需结合上下文判断")
    else:
        results["L4 估值-触发器一致性"] = ("WARN", "未能提取估值方向或触发器类型")

    # --- L4.4 评分表权重加总 = 100% ---
    weights = re.findall(r'(\d+)\s*%\s*\|', content[content.find("13.2") if "13.2" in content else 0:])
    if weights:
        total_weight = sum(int(w) for w in weights)
        if total_weight == 100:
            results["L4 评分权重加总"] = ("PASS", f"权重合计 {total_weight}%")
        elif 95 <= total_weight <= 105:
            results["L4 评分权重加总"] = ("WARN", f"权重合计 {total_weight}%（≠100%，可能四舍五入）")
        else:
            results["L4 评分权重加总"] = ("FAIL", f"权重合计 {total_weight}%（严重偏离100%）")
    else:
        results["L4 评分权重加总"] = ("WARN", "未能从评分表中提取权重")

    # --- L4.5 ROIC vs WACC 方向校验 ---
    roic_match = re.search(r'预测期平均\s*ROIC\s*[=≈]\s*([\d.]+)\s*%', content)
    if roic_match and wacc_match:
        roic = float(roic_match.group(1))
        wacc = float(wacc_match.group(1))
        if roic >= wacc:
            results["L4 ROIC>WACC价值创造"] = ("PASS", f"ROIC({roic}%) ≥ WACC({wacc}%)：价值创造")
        else:
            # 不是自动FAIL——有些公司确实在毁灭价值，但报告需要解释
            has_explanation = bool(re.search(r'为什么.*继续经营|清算|价值毁灭.*解释', content))
            if has_explanation:
                results["L4 ROIC>WACC价值创造"] = ("PASS",
                    f"ROIC({roic}%) < WACC({wacc}%)：已有价值毁灭解释")
            else:
                results["L4 ROIC>WACC价值创造"] = ("WARN",
                    f"ROIC({roic}%) < WACC({wacc}%)：价值毁灭，需解释'为什么不清算'")
    else:
        results["L4 ROIC>WACC价值创造"] = ("WARN", "未能提取ROIC或WACC")


# ---------- 主入口 ----------

def check_report(report_path: str, mode: str = "full") -> int:
    """主检查函数，返回 0 表示通过，1 表示失败。"""
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    total_chars = len(content)
    results: Dict[str, Tuple[str, str]] = {}

    logger.info(f"开始检查报告: {report_path}")
    logger.info(f"模式: {mode}, 总字符数: {total_chars}")

    # 执行所有检查
    check_word_count_and_keywords(content, results, mode)
    check_company_classification(content, results)
    check_section_12_6_consistency(content, results)
    check_section_12_8(content, results, mode)
    check_section_12_9(content, results)
    check_section_12_10(content, results)  # 新增：估值汇总表检查
    check_signal_density(content, results)
    check_step_13_kill_points(content, results)
    check_step_13_capability_circle(content, results)
    check_step_15_trigger(content, results)
    check_step_16_review_memo(content, results)
    check_skill_records(content, results)
    check_pdf_verification(content, results)
    check_l3_data_completeness(content, results)  # L3 数据完备性
    check_l4_business_logic(content, results)     # L4 业务逻辑

    # 统计结果
    pass_n = sum(1 for s, _ in results.values() if s == "PASS")
    warn_n = sum(1 for s, _ in results.values() if s == "WARN")
    fail_n = sum(1 for s, _ in results.values() if s == "FAIL")
    skipped_n = sum(1 for s, _ in results.values() if s == "SKIPPED")
    total = pass_n + warn_n + fail_n

    # 输出报告
    print("=" * 70)
    print(f"14 步深度投资研究报告 — 质检报告 (v4 L3-L4增强版, mode={mode})")
    print("=" * 70)
    print(f"报告文件: {report_path}")
    print(f"总字符数: {total_chars}")
    print("=" * 70)

    icons = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌", "SKIPPED": "⏭️ "}
    for name, (status, detail) in results.items():
        print(f"  {icons[status]} [{status:7s}] {name}: {detail}")

    print("=" * 70)
    pass_rate = pass_n / total * 100 if total else 0
    print(f"达标率: {pass_rate:.1f}% (PASS {pass_n} / WARN {warn_n} / FAIL {fail_n} / SKIPPED {skipped_n})")

    # 结构性硬错误列表
    hard_fails = [it for it in Config.HARD_FAIL_ITEMS if it in results and results[it][0] == "FAIL"]
    if hard_fails:
        print(f"❌ 结构性硬错误: {hard_fails}")
        print("结论: FAIL（必须返工）")
        return 1

    if pass_rate >= Config.PASS_RATE_THRESHOLD and fail_n == 0:
        print("结论: PASS - 报告质量合格")
        return 0
    print("结论: FAIL - 报告需要返工")
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="14步报告质检脚本 v4")
    parser.add_argument("--report", required=True, help="报告文件路径")
    parser.add_argument("--mode", default="full", choices=["full", "quick"],
                        help="执行模式（默认 full）")
    args = parser.parse_args()
    sys.exit(check_report(args.report, mode=args.mode))
