#!/usr/bin/env python3
"""
14步深度投资研究报告 — 质检脚本（v2，结构性校验版）

此版相对于 v1 增加：
  1. 字数 + 关键词存在（保留）
  2. g = ROIC × Reinvestment Rate 一致性校验（解析 12.6 的数字）
  3. 终值占比 < 80% 校验
  4. 估值结论与 12.7 历史价格区间一致性校验
  5. 12.8 市场预期诊断的关键字段存在性
  6. Step 15 操作触发器类型（A–E）已勾选
  7. SBC 处理路径已声明
  8. A 股 ERP 是否包含中国 CRP
  9. 少数股东权益（NCI）是否扣除
 10. 反向论文 3 个 kill points + 能力圈自评 5 项
 11. 12 个月复盘备忘块是否写入
 12. 公司类型分类、SOTP（如适用）、终值 g ≤ Rf

用法：python check_report.py --report <path>
"""

import argparse
import re
import sys


# ---------- 工具函数 ----------

def find_section(content: str, start_markers, next_markers) -> str:
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


def parse_pct(s: str):
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


def parse_number(s: str):
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


# ---------- 校验函数 ----------

def check_word_count_and_keywords(content: str, results: dict):
    """v1 风格的字数 + 关键词存在校验（保留主干）。"""
    steps = [
        ("第一步：公司基本信息与术语通俗解释", 800,
         ["股票代码", "上市时间", "主营业务", "产业链位置", "术语"]),
        ("第二步：行业分析", 1200,
         ["生命周期", "TAM", "SAM", "SOM", "竞争格局", "供需"]),
        ("第三步：五年财务数据一览", 800,
         ["营业收入", "净利润", "毛利率", "净利率", "ROE", "资产负债率", "EPS", "经营现金流"]),
        ("第四步：财务分析", 2000,
         ["财务真实性", "盈利质量", "资产效率", "财务安全", "成长能力", "股东回报"]),
        ("第五步：年报掘金", 1200,
         ["异常波动", "管理层", "战略"]),
        ("第六步：巴菲特护城河诊断", 800,
         ["护城河", "规模效应", "成本优势", "品牌"]),
        ("第六点五步：管理层资本配置", 600,
         ["留存收益", "回购", "并购", "稀释"]),
        ("第七步：段永平生意模式诊断", 800,
         ["段永平", "产品", "商业模式", "管理层"]),
        ("第八步：发展史", 800, ["发展史"]),
        ("第九步：年报掘金及股价启示", 800, ["股价"]),
        ("第十步：投资秘诀", 800, ["核心逻辑", "跟踪指标", "风险提示"]),
        ("第十一步：江安澜点评", 400, ["亮点", "隐忧"]),
        ("第十二步：估值分析", 1500, ["估值", "DCF", "WACC"]),
        ("第十三步：投资建议+仓位管理", 1200,
         ["反向论文", "kill point", "能力圈", "评分", "确定性"]),
        ("第十四步：数据来源", 400, ["数据来源", "skill"]),
        ("第十五步：操作触发器", 500,
         ["触发", "估值面", "历史分位"]),
        ("第十六步：12 个月", 300, ["复盘", "假设", "回看"]),
    ]
    for name, min_chars, kws in steps:
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


def check_section_12_6_consistency(content: str, results: dict):
    """校验 12.6 的 g、ROIC、RR 一致性，以及终值占比、SBC、NCI、CRP。"""
    sec = find_section(content,
                       ["**第三层：终值与股权价值推导**", "12.6 估值计算", "12.6"],
                       ["12.7", "**12.7", "12.8", "第十三步"])
    if not sec:
        results["12.6 一致性"] = ("WARN", "未找到 12.6 章节内容")
        return

    # 1. g vs Rf
    g_match = re.search(r"终值增长率\s*g\s*=\s*([\d.]+)\s*%?", sec)
    rf_match = re.search(r"Rf\s*=?\s*([\d.]+)\s*%?", content[:5000])
    if g_match and rf_match:
        g = parse_pct(g_match.group(1) + "%")
        rf = parse_pct(rf_match.group(1) + "%")
        if g and rf and g > rf + 0.05:
            results["g ≤ Rf"] = ("FAIL", f"终值 g={g:.2f}% > Rf={rf:.2f}%；违反 g ≤ min(GDP, Rf)")
        else:
            results["g ≤ Rf"] = ("PASS", f"g={g}% Rf={rf}%")
    else:
        results["g ≤ Rf"] = ("WARN", "未能提取 g 或 Rf")

    # 2. g = ROIC × RR
    roic_m = re.search(r"预测期平均\s*ROIC\s*=\s*([\d.]+)\s*%", sec)
    g_avg_m = re.search(r"预测期平均\s*g(?:_revenue)?\s*=\s*([\d.]+)\s*%", sec)
    rr_imp = re.search(r"隐含\s*RR\s*[=：]\s*g\s*/\s*ROIC\s*=\s*([\d.]+)\s*%", sec)
    rr_act = re.search(r"实际\s*RR.*?=\s*([\d.]+)\s*%", sec)
    if g_avg_m and roic_m and rr_imp and rr_act:
        rr_implied = parse_pct(rr_imp.group(1) + "%")
        rr_actual = parse_pct(rr_act.group(1) + "%")
        if rr_implied and rr_actual:
            dev = abs(rr_implied - rr_actual)
            if dev > 3:
                results["g = ROIC × RR 一致"] = ("FAIL",
                    f"隐含 RR {rr_implied:.1f}% vs 实际 RR {rr_actual:.1f}%，偏差 {dev:.1f} ppt > 3 ppt")
            elif dev > 1.5:
                results["g = ROIC × RR 一致"] = ("WARN",
                    f"偏差 {dev:.1f} ppt（1.5–3 ppt 区间，需在叙事中解释）")
            else:
                results["g = ROIC × RR 一致"] = ("PASS", f"偏差 {dev:.1f} ppt")
    else:
        results["g = ROIC × RR 一致"] = ("WARN", "未能提取 g/ROIC/RR 完整数据")

    # 3. 终值占比 < 80%
    tv_m = re.search(r"终值占比\s*[=：]?\s*终值现值\s*[÷/]\s*EV\s*=\s*([\d.]+)\s*%", sec)
    if not tv_m:
        tv_m = re.search(r"终值占比.*?([\d.]+)\s*%", sec)
    if tv_m:
        tv = parse_pct(tv_m.group(1) + "%")
        if tv and tv > 80:
            results["终值占比 < 80%"] = ("FAIL", f"终值占比 {tv:.1f}% > 80%；预测期太短或终值假设过激进")
        elif tv:
            results["终值占比 < 80%"] = ("PASS", f"终值占比 {tv:.1f}%")
    else:
        results["终值占比 < 80%"] = ("WARN", "未能提取终值占比")

    # 4. CRP（A 股默认）
    if "CRP" in sec or "中国 CRP" in sec or "中国CRP" in sec:
        results["A 股 ERP 含 CRP"] = ("PASS", "已标注 CRP")
    else:
        results["A 股 ERP 含 CRP"] = ("FAIL", "12.6 未引用中国 CRP；A 股 ERP 必须 = 美国 ERP + 中国 CRP")

    # 5. SBC 路径声明
    sbc_a = "路径 A" in sec or "扣除 SBC" in sec or "扣 SBC" in sec or "扣除SBC" in sec
    sbc_b = "路径 B" in sec or "全摊薄股数" in sec or "TSM" in sec
    if sbc_a or sbc_b:
        results["SBC 处理路径已声明"] = ("PASS", f"路径 A={sbc_a}, 路径 B={sbc_b}")
    elif "SBC" in sec:
        results["SBC 处理路径已声明"] = ("WARN", "提到了 SBC，但未明确选择路径 A 或 B")
    else:
        results["SBC 处理路径已声明"] = ("WARN", "未涉及 SBC（若该公司 SBC 占净利润 > 5% 必须声明）")

    # 6. NCI 扣除
    if "少数股东权益" in sec or "NCI" in sec:
        results["少数股东权益 NCI 扣除"] = ("PASS", "已扣除 NCI")
    else:
        results["少数股东权益 NCI 扣除"] = ("WARN",
            "未扣除 NCI（金融控股集团/新能源车企/综合集团必扣，否则归母价值高估 5–15%）")


def check_section_12_8(content: str, results: dict):
    """检查 12.8 市场预期诊断是否有反向 DCF + 历史分位 + 四象限。"""
    sec = find_section(content,
                       ["**12.8 市场预期诊断", "12.8 市场预期诊断", "12.8.1"],
                       ["第十三步", "### 第十三步"])
    if not sec or len(sec) < 200:
        results["12.8 市场预期诊断"] = ("FAIL", "12.8 章节缺失或内容过少（< 200 字）")
        return
    has_reverse = "反向 DCF" in sec or "市场隐含" in sec
    has_percentile = "P25" in sec and "P75" in sec
    has_quadrant = "四象限" in sec or "★★★" in sec
    issues = []
    if not has_reverse:
        issues.append("缺反向 DCF")
    if not has_percentile:
        issues.append("缺历史分位 P25/P75")
    if not has_quadrant:
        issues.append("缺四象限决策矩阵")
    if issues:
        results["12.8 市场预期诊断"] = ("FAIL", "; ".join(issues))
    else:
        results["12.8 市场预期诊断"] = ("PASS", "反向 DCF + 历史分位 + 四象限齐全")


def check_step_13_kill_points(content: str, results: dict):
    """13.0 反向论文必须有 3 个具体的 kill point。"""
    sec = find_section(content,
                       ["#### 13.0 反向论文", "13.0 反向论文"],
                       ["13.1", "#### 13.1"])
    if not sec:
        results["13.0 反向论文 3 个 kill points"] = ("FAIL", "未找到 13.0 反向论文章节")
        return
    kp_count = len(re.findall(r"#\s*1\b|Kill Point\s*#\s*1|kill point\s*#?1", sec, re.IGNORECASE))
    kp_count2 = sec.count("Kill Point") + sec.count("kill point")
    found = max(kp_count, kp_count2)
    if found >= 3 or "#1" in sec and "#2" in sec and "#3" in sec:
        results["13.0 反向论文 3 个 kill points"] = ("PASS", "已提供 ≥ 3 个 kill points")
    else:
        results["13.0 反向论文 3 个 kill points"] = ("FAIL", "未提供 3 个 kill points")


def check_step_13_capability_circle(content: str, results: dict):
    sec = find_section(content,
                       ["#### 13.1 能力圈自评", "13.1 能力圈"],
                       ["13.2", "#### 13.2"])
    if not sec:
        results["13.1 能力圈自评"] = ("WARN", "未找到 13.1 能力圈自评章节")
        return
    items = ["研究时长", "3 句话", "年报", "可比同业", "产品体验"]
    found = sum(1 for it in items if it in sec)
    if found >= 4:
        results["13.1 能力圈自评 ≥ 4/5"] = ("PASS", f"5 项中找到 {found} 项")
    else:
        results["13.1 能力圈自评 ≥ 4/5"] = ("WARN",
            f"仅找到 {found}/5 项；若 < 4 项满足，仓位应自动 ÷2 且评级最高 B 级")


def check_step_15_trigger(content: str, results: dict):
    sec = find_section(content,
                       ["### 第十五步：操作触发器", "第十五步：操作触发器"],
                       ["### 第十六步", "## 质量门"])
    if not sec:
        results["第十五步 操作触发器"] = ("FAIL", "未找到第十五步操作触发器章节")
        return
    has_type = any(s in sec for s in ["A 类", "B 类", "C 类", "D 类", "E 类",
                                       "A.", "B.", "C.", "D.", "E.",
                                       "本次报告触发的操作类型"])
    if has_type:
        results["第十五步 操作触发器"] = ("PASS", "触发器类型已声明")
    else:
        results["第十五步 操作触发器"] = ("WARN", "未明确声明 A–E 触发器类型")


def check_step_16_review_memo(content: str, results: dict):
    sec = find_section(content,
                       ["### 第十六步：12 个月", "第十六步：12 个月"],
                       ["## 质量门", "## 完整执行流程"])
    if sec and "回看" in sec and "假设" in sec:
        results["第十六步 12 个月复盘备忘"] = ("PASS", "已写入复盘备忘")
    else:
        results["第十六步 12 个月复盘备忘"] = ("WARN", "复盘备忘缺失或不完整")


def check_company_classification(content: str, results: dict):
    if re.search(r"主类型\s*=\s*\[?[A-H]", content) or "公司类型判断" in content:
        results["12.-1 公司类型分类"] = ("PASS", "已分类")
    else:
        results["12.-1 公司类型分类"] = ("FAIL", "未做公司类型分类（必须前置）")


def check_skill_records(content: str, results: dict):
    n = len(re.findall(r"skill调用记录|skill 调用记录", content))
    if n >= 3:
        results["skill 调用记录"] = ("PASS", f"{n} 处")
    elif n > 0:
        results["skill 调用记录"] = ("WARN", f"仅 {n} 处")
    else:
        results["skill 调用记录"] = ("FAIL", "未找到 skill 调用记录")


def check_pdf_verification(content: str, results: dict):
    if "pdf-verifier" in content or "数据核验" in content or "PDF 核验" in content:
        results["数据核验"] = ("PASS", "已包含核验记录")
    else:
        results["数据核验"] = ("WARN", "未找到数据核验记录")


# ---------- 主入口 ----------

def check_report(report_path):
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    total_chars = len(content)
    results = {}

    check_word_count_and_keywords(content, results)
    check_company_classification(content, results)
    check_section_12_6_consistency(content, results)
    check_section_12_8(content, results)
    check_step_13_kill_points(content, results)
    check_step_13_capability_circle(content, results)
    check_step_15_trigger(content, results)
    check_step_16_review_memo(content, results)
    check_skill_records(content, results)
    check_pdf_verification(content, results)

    pass_n = sum(1 for s, _ in results.values() if s == "PASS")
    warn_n = sum(1 for s, _ in results.values() if s == "WARN")
    fail_n = sum(1 for s, _ in results.values() if s == "FAIL")
    total = pass_n + warn_n + fail_n

    print("=" * 70)
    print("14 步深度投资研究报告 — 质检报告 (v2 结构性校验)")
    print("=" * 70)
    print(f"报告文件: {report_path}")
    print(f"总字符数: {total_chars}")
    print("=" * 70)

    icons = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}
    for name, (status, detail) in results.items():
        print(f"  {icons[status]} [{status:4s}] {name}: {detail}")

    print("=" * 70)
    pass_rate = pass_n / total * 100 if total else 0
    print(f"达标率: {pass_rate:.1f}% (PASS {pass_n} / WARN {warn_n} / FAIL {fail_n})")

    # 任何结构性 FAIL（g/Rf, RR, NCI 类硬规则）→ 必须返工
    hard_fail_items = ["g ≤ Rf", "g = ROIC × RR 一致", "12.8 市场预期诊断",
                       "13.0 反向论文 3 个 kill points", "12.-1 公司类型分类"]
    hard_fails = [it for it in hard_fail_items if it in results and results[it][0] == "FAIL"]
    if hard_fails:
        print(f"❌ 结构性硬错误: {hard_fails}")
        print("结论: FAIL（必须返工）")
        return 1

    if pass_rate >= 75 and fail_n == 0:
        print("结论: PASS - 报告质量合格")
        return 0
    print("结论: FAIL - 报告需要返工")
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="14步报告质检脚本 v2")
    parser.add_argument("--report", required=True, help="报告文件路径")
    args = parser.parse_args()
    sys.exit(check_report(args.report))
