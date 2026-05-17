# 14-step-valuation skill 包修订记录（v2）

修订日期：2026-05-17
修订范围：14-step-analysis、ai-era-valuation、damodaran-valuation、sotp-valuation、
valuation-art、其余 skill 保持不变

> 本文档列出本次修订相对于原版（zip：skills-14step-valuation_20260517_142731.zip）的所有
> 改动，按"硬伤修复 → 方法论修正 → 流程增补 → 行业覆盖 → 工程升级"五层组织。

---

## 一、硬伤修复（必改）

### 1. WACC vs ROIC 方向反了

**位置：** damodaran-valuation/SKILL.md 第 1.3 节 Ke/WACC 校验表
- 原文：`WACC与ROIC关系 | 长期WACC应 > ROIC（否则价值毁灭）`
- 修正：`长期 ROIC ≥ WACC 才是创造股东价值；ROIC < WACC = 价值毁灭；终值年若 ROIC < WACC 必须解释为何继续经营或改用清算估值`

### 2. sotp-valuation/SKILL.md 是空文件

**位置：** sotp-valuation/SKILL.md（原 0 字节）
- 补全 6 步 SOTP 框架：业务拆分 → 各分部估值方法选择 → 加总 → 控股折价（10–35%）→ 敏感性 → 与市值对比
- 新增金融控股集团/平台型/控股投资公司的折扣率参考表
- 加入"低估来源拆解"框架（控股折价过深 vs 板块估值偏低 vs 隐藏资产 vs 净现金）
- 列出 7 类常见错误（集团 EV 误用、双重扣债务、漏扣 NCI 等）

### 3. 数据资产估值与利润率上调冲突

**位置：** ai-era-valuation/SKILL.md 维度二 + 14-step Section 12.0
- 新增双路径决策树：路径 A（DCF 用行业均值利润率）和路径 B（DCF 已含数据红利）**互斥**
- 4–6 分 / 7–10 分各自的处理方式按路径分别给出
- 明确禁止同时上调利润率 + 加单独数据资产价值（否则估值虚高 15–30%）

### 4. 金融公司估值入口不对

**位置：** damodaran-valuation/SKILL.md 步骤零分类表
- 单一行 `金融服务公司` 拆为 4 行：商业银行 / 寿险（**寿险板块 EV，非集团 EV**）/ 财险 / 证券资管
- 每行明确首选方法和注意事项

---

## 二、方法论层面修正

### 5. 终值 g 天花板：用 Rf 而非仅 GDP

- 规则：`g ≤ min(名义 GDP 长期增速, 无风险利率 Rf)`
- A 股当前 Rf ≈ 2.0–2.3%，多数公司 g 应取 2.0–2.5%
- 强制校验：g/Rf ≤ 1，否则禁用 Gordon Growth

### 6. A 股 ERP 默认含中国 CRP

- 原：仅"特殊高风险公司"才加 CRP
- 改：所有 A 股默认 ERP = 美国成熟 ERP 4.20% + 中国 CRP 0.95% ≈ 5.15%
- 影响：忽略 CRP 会使 Ke 系统性低估 70–100bps，估值高估 8–15%

### 7. g = ROIC × RR 一致性强制校验

**位置：** 14-step Section 12.6 模板新增、check_report.py 自动校验
- 校验项：隐含 RR = g / ROIC vs 实际 RR = (CapEx − D&A + ΔNWC) / NOPAT
- 红线：偏差 ≤ 1.5 ppt 通过；1.5–3 ppt 解释；> 3 ppt 必须重做

### 8. SBC 处理强制二选一

**位置：** 14-step Section 12.6、damodaran-valuation Section 1.2
- 路径 A：扣除 EBIT + 用基础股数
- 路径 B：不扣 EBIT + 用全摊薄股数（含 RSU/期权 TSM/可转债）
- 禁止"既不扣又不稀释"的双免错误

### 9. 少数股东权益（NCI）扣除

**位置：** 14-step Section 12.6、damodaran-valuation Section 1.2 + 常见陷阱表
- 新公式：EV − 净负债 − NCI（按公允价值/市值）= 归母股权价值
- ÷ 稀释后总股本 = 每股归母内在价值
- 中国平安等金融控股集团必扣（NCI 占合并净资产 8–15%）

### 10. 隐含 Ke 公式适用边界

**位置：** 14-step Section 12.7.2 增加警告
- ROE 接近或低于 g、ROE 多年波动 > 5pp、亏损/恢复期 → 公式失效
- 改用 P/B vs ROE 散点图 + 回归带

### 11. 算力通缩三机制分拆

**位置：** ai-era-valuation/SKILL.md 维度三
- GPU 单价通缩 → Sales/Capital 上调（资本端）
- 推理边际成本下降 → 利润率上调（运营端）
- Wright's Law 学习曲线 → 单独情景维度
- 禁止同一通缩同时塞进两个 DCF 输入

### 12. 双峰分布概率赋值规则

**位置：** ai-era-valuation/SKILL.md 双峰分布章节
- 起始 P(垄断) = 20%，按 11 类信号逐项加减
- 最终 P(垄断) 必须落在 [10%, 70%]
- 必须逐条勾选展示，不能直接给总概率

---

## 三、流程层面增补

### 13. Step 13.0 反向论文 / Pre-mortem

**位置：** 14-step Section 13.0
- 写出 3 个 kill points
- 每个含：触发信号（量化）、当前发生概率、预承诺反应

### 14. Step 6.5 管理层资本配置 5–10 年回测

**位置：** 14-step 第六点五步（介于第六、七步之间）
- 留存收益 → 市值创造测试（巴菲特一美元原则）
- 历次回购 vs 当时 BV / 合理价格
- 历次重大并购的减值情况
- IPO 以来净增发 − 净回购股本

### 15. 安全边际成为评分否决项

**位置：** 14-step Section 13.2
- IV / 价格 < 0.85 → 综合评级最高 B 级，仓位上限 5%
- IV / 价格 < 1.0 → 最高 A 级，仓位上限 15%
- IV / 价格 ≥ 1.0 → 标准应用 position-management

### 16. 能力圈自评（5 项检查）

**位置：** 14-step Section 13.1
- 5 项中 ≥ 4 项满足：标准应用
- 仅 3 项：评级最高 B + 仓位 ÷ 2
- ≤ 2 项：最高 C 级，禁止重仓

### 17. 12 个月复盘备忘

**位置：** 14-step 第十六步
- 报告末尾必须写入关键假设备忘录
- 12 个月后强制回看 4 类问题

### 18. 公司类型 H：平台 / 网络效应公司

**位置：** 14-step Section 12.-1 表
- 新增 H 类（腾讯、美团、阿里等）
- 估值方法：SOTP 为主 + 平台溢价补充情景

### 19. 副类型勾选

**位置：** 14-step Section 12.-1
- A/H 双重上市（流动性差和折扣 5–25%）
- 中概 ADR + VIE 结构（VIE 风险折扣 5–15%）
- H 股小盘流通（流动性折扣 5–15%）
- 大型央企/国企（β × 0.85，加 0.5–1.0% 政策溢价）
- AI 相关公司（强制触发 12.0）

### 20. 国企 Beta 与 ERP 调整

**位置：** damodaran-valuation Section 2.6（新增）
- 适用：国资委 ≥ 30% 控股 + 国家战略行业
- Levered Beta × 0.85（隐含国家担保）
- ERP 加 0.5–1.0% 政策风险溢价

---

## 四、市场预期诊断（最大单一新增）

### 21. Section 12.8 市场预期诊断（强制，所有公司）

**位置：** 14-step Section 12.8（全新章节）
- **12.8.1 反向 DCF**：固定 WACC/g/利润率，反求市场隐含的收入 CAGR
- **12.8.2 历史隐含 g 分位（10 年）**：每个时点重做反向 DCF，输出 implied_g(t) 时间序列 + P25/P50/P75
- **12.8.3 该股票的"估值溢价人格"**：当前溢价处于历史 P 几
- **12.8.4 四象限决策矩阵**：绝对估值 × 历史分位 → ★★★ 重仓买入 / ✗ 清仓
- **12.8.5 三个边界警告**：基本面拐点失效、宏观流动性范式切换需校准 Rf、上市 < 7 年用同业分位

### 22. 第十五步 操作触发器（A–E 五类）

**位置：** 14-step 第十五步（全新章节）
- A：估值低 + 历史分位低 → 重仓
- B：估值合理 + 强基本面催化 → 试仓
- C：估值合理偏高 + 双重确认 → 跟随仓位
- D：估值高估 → 对冲式持有，停止加仓
- E：估值 + 历史分位都高、kill point 触发、造假暴露 → 清仓

回应"市场不是理想状态、不能永远等到完美估值"的实际操作纪律。

---

## 五、行业覆盖修正

### 23. 特种化工 / 精细化工不应套用替代成本法

**位置：** valuation-art/references/cyclical-investing.md 第 3 节、14-step Section 12.-1
- 排除：精细化工、特种化工、化工新材料、电子化学品、CDMO
- 理由：价值来自客户认证壁垒和工艺 know-how，替代成本不能反映
- 应改用消费品/科技股框架

---

## 六、工程升级

### 24. check_report.py v2（结构性校验）

**位置：** 14-step-analysis/scripts/check_report.py
- 保留：字数 + 关键词
- 新增：g ≤ Rf、g = ROIC × RR、终值占比 < 80%、CRP、SBC、NCI、12.8 完整性、3 个 kill points、能力圈 ≥ 4/5、操作触发器、12 个月复盘备忘
- 新增"硬错误项"列表，任一硬错误即返工

### 25. reverse_dcf.py（新工具）

**位置：** 14-step-analysis/scripts/reverse_dcf.py
- 输入：当前市值、WACC、终值 g、终值 ROIC、利润率路径
- 输出：使 DCF = 当前市值的市场隐含收入 CAGR（或终值利润率）
- 已通过命令行测试

### 26. historical_premium.py（新工具）

**位置：** 14-step-analysis/scripts/historical_premium.py
- 拉取 10 年财务数据 + 年均价（AKShare）
- 每个时点重做反向 DCF，输出 implied_g(t) 时间序列、P25/P50/P75 分位、当前分位
- 输出 markdown 表格直接粘贴到 12.8.2

### 27. 14-step Section 12.0 去重

**位置：** 14-step Section 12.0
- 原：复制 ai-era-valuation 全部 5 维度内容（双源不同步隐患）
- 改：仅保留触发条件 + 强制串联规则 + 参数修正单输出格式，方法论详见 ai-era-valuation/SKILL.md

### 28. AKShare 数据可靠性强制规则

**位置：** 14-step 第零步
- 任意一年 AKShare 数与 PDF 差异 > 3% → 该年全部用 PDF
- 合并报表口径变化年份 → 强制 PDF
- AKShare 仅在最新季度（PDF 未发布时）作主源

### 29. 字数 + 信号密度并重

**位置：** 14-step 第六、七步
- 1200 字 → 800 字 + 信号密度（每段 ≥ 1 量化数字 / ≥ 1 时间锚 / ≥ 1 反方观察）
- 防止"凑字稀释关键信号"

### 30. 其他细节增强

- Step 11 分析师名字可配置（默认"江安澜"）
- 12.7 历史价格表新增"宏观背景"对照列
- Step 13 评分新增流动性/微观结构维度（5%）+ 反向论文 kill points 不发生概率（4%）
- Step 14 强制自动运行 check_report.py + 附 reverse-DCF 输出表
- damodaran-valuation 常见陷阱表新增 g/RR/NCI/SBC 4 行

---

## 修订前后对照速览

| 项目 | 修订前 | 修订后 |
|------|------|------|
| 硬伤数量 | 4 个（WACC/ROIC、空 SoTP、数据双重计数、金融公司错位） | 0 |
| 12.6 强制校验 | 仅字数 | g≤Rf、g=ROIC×RR、TV<80%、CRP、SBC、NCI 共 6 项 |
| 12.8 市场预期诊断 | 无 | 反向 DCF + 历史分位 + 四象限 + 3 警告 |
| 操作触发器 | 无 | A–E 5 类 |
| 反向论文 / kill points | 无 | 强制 3 个 |
| 能力圈自评 | 无 | 5 项 + 自动调档 |
| 12 个月复盘 | 无 | 强制写入备忘 |
| 公司类型分类 | 7 类 | 8 类 + 5 副类型 |
| check_report.py | 仅字数关键词 | 13 项结构性校验 + 硬错误返工机制 |
| 工具脚本 | 1 个 | 3 个（含 reverse_dcf、historical_premium）|

---

## 文件改动一览

```
新增文件：
  + sotp-valuation/SKILL.md  （原 0 字节，现 ~370 行）
  + 14-step-analysis/scripts/reverse_dcf.py
  + 14-step-analysis/scripts/historical_premium.py
  + CHANGELOG.md（本文件）

显著修改：
  ~ 14-step-analysis/SKILL.md（+ ~250 行：12.0 去重 / 12.6 强校验 / 12.8 全新 /
     6.5 / 13.0 / 13.1 / 第十五 / 第十六步）
  ~ 14-step-analysis/scripts/check_report.py（v1 → v2 全部重写）
  ~ ai-era-valuation/SKILL.md（数据双重计数边界、算力三分类、双峰概率赋值）
  ~ damodaran-valuation/SKILL.md（WACC/ROIC、g≤Rf、CRP、SBC、NCI、SOE 国企调整）
  ~ valuation-art/references/cyclical-investing.md（替代成本法排除精细化工）

删除文件（仅 .bak-pre-v5 备份文件）：
  - valuation-art/SKILL.md.bak-pre-v5
  - valuation-art/references/multiples-guide.md.bak-pre-v5
```
