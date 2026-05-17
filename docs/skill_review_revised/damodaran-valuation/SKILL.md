---
name: damodaran-valuation
description: |
  专业股票估值技能，基于达摩达兰（Aswath Damodaran）《Investment Valuation》第3版与《The Dark Side of Valuation》第3版的完整方法论体系。涵盖 DCF（内在价值）、相对估值（可比倍数）、资产基础估值三大框架，以及针对高成长/负盈利/周期性/金融/新兴市场等特殊公司的专项处理方法。

  当用户提出以下类型请求时，立即使用本技能：
  - 对某只股票做估值 / 给出目标价 / 判断高估低估
  - 构建或审查 DCF 模型
  - 计算 WACC / 折现率 / Beta / 股权成本
  - 分析估值倍数（P/E、EV/EBITDA、P/B、P/S 等）
  - 对初创公司、负盈利公司、周期股、金融股、资源股、新兴市场公司做估值
  - 解释达摩达兰估值方法或公式
  - 构建"故事转数字"（Narrative-to-Numbers）框架
  - 任何涉及"公司值多少钱"的讨论，即使用户没有显式说"估值"
---

# 达摩达兰股票估值技能

## 核心哲学

> "价值来自现金流、增长与风险的函数。所有估值方法，不过是这一逻辑的不同表达形式。"  
> —— Aswath Damodaran

估值是叙事（Narrative）与数字（Numbers）的桥梁。在动笔建模之前，必须先有清晰的**商业故事**，再将故事中的每个假设转化为财务输入。

---

## 步骤零：公司分类——选择正确的估值路径

在开始任何估值之前，先判断公司类型，因为这决定整个方法论路径。

| 公司类型 | 核心挑战 | 首选方法 | 参考文件 |
|---------|---------|---------|---------|
| 成熟稳定公司 | 增长放缓，历史数据充足 | 标准 FCFF/FCFE DCF | `references/dcf-standard.md` |
| 高速成长/初创公司 | 无盈利，短历史，高不确定性 | 场景 DCF + VC 概率折扣 | `references/darkside-growth.md` |
| 周期性公司 | 盈利随经济周期大幅波动 | 正常化盈利 DCF | `references/darkside-cyclical.md` |
| 金融公司——商业银行 | FCFE DCF 为主 + P/B-ROE 交叉验证 | `references/darkside-financials.md` |
| 金融公司——寿险公司 | P/EV + ANV/VIF/PV(VNB) 三段法（**寿险板块 EV，非集团 EV**）| `references/darkside-financials.md` |
| 金融公司——财险公司 | P/B + 5–10 年平均综合成本率 COR | `references/darkside-financials.md` |
| 金融公司——证券/资管 | FCFE DCF 为主（含 ROE 多周期正规化），P/B-ROE 仅作辅助 | `references/darkside-financials.md` + `references/valuation-methods.md` 第八部分续 |
| 大宗商品/资源公司 | 盈利由外部价格决定 | 价格情景 DCF | `references/darkside-commodity.md` |
| 新兴市场公司 | 国家风险、货币风险、信息不透明 | 调整后 DCF（含国家风险溢价） | `references/darkside-commodity.md`（Part B）|
| 资产密集/困境公司 | 现金流为负或无意义 | 清算价值 / 期权定价 | `references/darkside-commodity.md`（Part C）|

---

## 框架一：内在价值——折现现金流（DCF）

### 1.1 核心公式

**企业价值（EV）：**
$$EV = \sum_{t=1}^{N} \frac{FCFF_t}{(1+WACC)^t} + \frac{Terminal\ Value}{(1+WACC)^N}$$

**股权价值：**
$$Equity\ Value = EV - Net\ Debt$$

**每股内在价值：**
$$Intrinsic\ Value\ per\ Share = \frac{Equity\ Value}{Diluted\ Shares\ Outstanding}$$

### 1.2 构建 FCFF

```
FCFF = EBIT × (1 - Tax Rate)
     + Depreciation & Amortization
     - Capital Expenditures
     - Changes in Working Capital
```

**关键提示（Damodaran 强调）：**
- 使用**有效税率**（Effective Tax Rate），而非法定税率
- CapEx 须包含**收购性支出**（视为资本投资）
- 营运资本变动只算**非现金流动资产**变化（排除现金）
- R&D 通常应**资本化**而非费用化（尤其科技/制药公司）
- **SBC（股权激励）必须计入真实经济成本**——二选一不可两免：
  - 路径 A：在 EBIT 中扣除 SBC，FCFF 用基础股数
  - 路径 B：EBIT 不扣 SBC，FCFF 用全摊薄股数（含 RSU/期权 TSM/可转债转换）
  - 错误：既不扣 EBIT 又不稀释（Damodaran 反复批评的"经典科技股估值高估法"）
- **股权价值桥接必须扣除少数股东权益（NCI）**：
  ```
  EV - 净负债 - 少数股东权益（按公允价值或市值，非账面值）= 归母股权价值
  ÷ 稀释后总股本（含期权/可转债 TSM）= 每股归母内在价值
  ```
  忽略 NCI 在金融控股集团、新能源车企、综合集团的估值中会高估 5–15%

### 1.3 三阶段增长模型（标准结构）

| 阶段 | 年数 | 特点 |
|-----|-----|-----|
| 高速增长期（Stage 1） | 5–10年 | 逐年预测，与公司故事对齐 |
| 过渡期（Stage 2） | 可选 | 向稳态线性收敛 |
| 永续增长期（Stage 3） | 永续 | 终值，增长率≤名义GDP增速 |

**终值公式（Gordon Growth Model）：**
$$Terminal\ Value = \frac{FCFF_{N+1}}{WACC - g}$$

> ⚠️ **Damodaran 警告：终值往往占总价值60–80%，是估值中最大的不确定性来源。**

**终值增长率 g 的天花板（强制规则）：**

```
g ≤ min(名义 GDP 长期增速,  无风险利率 Rf)
```

- 长期看名义 GDP 应收敛于 Rf（实证：美国 1900–2020 名义 GDP ≈ 3 个月国债 + 2%, 长期国债则更接近）
- 中国 10 年期国债当前 ≈ 2.0–2.3%（2026 年 4 月），因此 A 股大多数公司终值 g 应取 **2.0–2.5%**，不应超过 3%
- 例外：极少数公司有合理的"超 GDP 永续增长"逻辑（如全球扩张型公司），需在叙事中显式辩护
- **必做检查**：g/Rf 比值应 ≤ 1，>1 时禁止使用 Gordon Growth，需切换到衰退/清算路径

**Ke / WACC 参数校验步骤（强制执行）：**

在确定折现率后、计算终值前，必须完成以下校验，任何一项未通过需记录偏差原因：

| 校验项 | 方法 | 红线 |
|--------|------|------|
| Ke合理性 | 与同行业上市公司Implied Ke对比 | 偏差 > 300bps 需解释 |
| Beta合理性 | 与Damodaran行业Unlevered Beta × relever对比 | 偏差 > 0.3 需解释 |
| ERP时效性 | 检查引用来源的发布日期 | 超过18个月需更新 |
| ROIC与WACC关系（价值创造）| 长期 **ROIC ≥ WACC** 才是创造股东价值；ROIC < WACC = 价值毁灭 | 终值年若 ROIC < WACC，必须解释为何继续经营、是否应改用清算价值估值 |
| 隐含Ke反推（可选） | 用当前PB和ROE反推Ke_implied = g + (ROE-g)/PB | 记录为参考，不作为Ke设定依据 |

> **注意**：隐含Ke（从市场价格反推）反映的是市场定价，不等于"正确的Ke"。它的用途是帮助判断当前价格隐含了什么假设，而非替代框架参数。框架Ke与隐含Ke的偏差本身就是投资信号。


---

## 框架二：折现率——WACC 的构建

### 2.1 WACC 公式

$$WACC = \frac{E}{E+D} \times k_e + \frac{D}{E+D} \times k_d \times (1 - t)$$

### 2.2 股权成本（Cost of Equity）——CAPM

$$k_e = R_f + \beta \times ERP + \alpha$$

其中：
- **R_f**：无风险利率 = 当前长期国债到期收益率（TTM 10yr）
- **β**：系统性风险（见下方 Beta 处理）
- **ERP**：股权风险溢价（Damodaran 每年1月更新，见 damodaran.com）

<details>
<summary>ERP 数据来源规范（点击展开）</summary>

**推荐数据源（按优先级）：**

| 来源 | URL | 更新频率 | 说明 |
|------|-----|---------|------|
| Damodaran ERP（全球） | http://www.damodaran.com | 每年1月 | 全球各国家/地区总ERP，含分国家CRP |
| Damodaran ERP（美国） | 同上 | 每年1月 | 基础ERP基准（成熟市场参考锚） |
| CSMAR / Wind | 本地数据库 | 日频 | 中国A股历史ERP序列，用于敏感性分析 |

**中国A股ERP实操建议（强制规则）：**

A 股属于 Damodaran 划分的新兴市场（emerging market）范畴，因此 **所有 A 股公司均默认计入中国 CRP**——而不是只对"特殊高风险公司"才加：

```
A 股 ERP_total = 美国成熟市场 ERP + 中国 CRP

当前（2026年4月，Damodaran ERPApril26.xlsx + ctrypremApr26.xlsx）：
  - 美国基础 ERP ≈ 4.20%
  - 中国 CRP   ≈ 0.92–1.03%
  - A 股 ERP   ≈ 5.13–5.23%（推荐 5.15% 作为基准）
```

**这一默认规则不可省略。** 若忽略 CRP（即直接用美国 4.20%），会系统性低估 Ke 约 70–100bps，
继而在终值的 (WACC - g) 分母上产生约 8–15% 的估值高估。

**例外：**
- 海外业务占比 > 50% 的中概股（如部分港股）：CRP 按业务地理收入加权
- 注册于香港、收入主要来自全球的公司：CRP 取香港或全球加权
- A 股大型央企（油、电、电信、银行等）：CRP 按下文 SOE 调整规则处理

**其他要点：**
- 切勿混用不同时点的 ERP 和 Rf（如用 2024 年的 ERP 配 2026 年的 Rf）
- 禁止凭直觉设定 ERP——必须引用 Damodaran 或等质量数据源并标注日期
- CSMAR/Wind 的中国本地 ERP 序列仅供敏感性分析，不作为基准来源

</details>

- **α**：公司特定风险溢价（可选，成熟公司通常为0）

### 2.3 Beta 的处理

Damodaran 对 Beta 的核心洞见：
1. **历史 Beta 噪声大**，应使用**行业平均 Unlevered Beta**再重新加杠杆
2. **公式：** $\beta_{Levered} = \beta_{Unlevered} \times [1 + (1-t) \times D/E]$
3. **实操**：从 Damodaran 网站下载对应行业的 Unlevered Beta，按目标资本结构重新计算
4. 对新兴市场公司：加入**Lambda（λ）× 国家风险溢价（CRP）**

### 2.4 债务成本（Cost of Debt）

$$k_d = R_f + Default\ Spread$$

- 有债券评级的公司：直接查 spread table
- 无评级公司：用**利息覆盖率**（EBIT/Interest）推算合成评级

### 2.5 资本结构

- 使用**市值权重**（Market Value Weights），不用账面价值
- 对目标资本结构与当前偏离较大的公司，可使用行业平均或管理层目标值

### 2.6 国企 Beta 与 ERP 调整（A 股大型央企/国企专项）

A 股大型央企（油、电、电信、银行、军工等国家战略行业，国资委直接控股）有"national champion"
隐含担保 + 政策风险双向敞口，标准 CAPM 会同时高估系统性风险和低估政策风险。

**调整规则：**

| 维度 | 调整 | 理由 |
|------|------|------|
| Levered Beta | × 0.85（即下调 15%）| 隐含国家担保降低破产/系统性风险（实证：A 股央企历史 Beta 通常低于行业均值 0.10–0.20）|
| 总 ERP | 加 0.5–1.0% 政策风险溢价 | 决策不完全市场化（如电网/电信定价受发改委影响）|

**调整后 Ke 公式（A 股大型央企）：**
```
Ke_央企 = Rf + 0.85 × Beta_industry × (ERP_mature + CRP_China + 0.5–1.0% 政策溢价)
```

**何时使用：**
- 国资委直接控股 ≥ 30%
- 行业属于国家战略行业（油/电/电信/银行/军工/铁路/核电）
- 主营业务定价受政府指导（受发改委或行业主管部门约束）

**何时不使用：**
- 地方国企（不享国家级隐性担保）
- 央企但所在行业完全市场化（如部分央企控股的消费品公司）
- 已经处于深度亏损或重组中（此时国家担保已计入定价，不要重复扣）

---

## 框架三：相对估值（可比倍数法）

### 3.1 倍数选择逻辑

| 倍数 | 适用场景 | 注意事项 |
|-----|---------|---------|
| **P/E** | 成熟盈利公司 | 负盈利时无效；受资本结构影响 |
| **EV/EBITDA** | 资本密集行业（制造、电信） | 不含折旧差异，更可比；忽视CapEx差异 |
| **EV/EBIT** | CapEx 差异大的行业 | 比 EBITDA 更严谨 |
| **P/B** | 金融股、资产重资产公司 | 需关注 ROE vs COE |
| **EV/Sales (P/S)** | 高成长/负盈利公司 | 不含利润率信息，需配合利润率预期 |
| **PEG** | 高成长公司 | PEG = P/E ÷ 增长率；PEG<1 可能低估 |
| **EV/FCF** | 现金流成熟公司 | 最接近 DCF 的倍数 |

### 3.2 可比公司的选择标准（Damodaran 强调）

> 可比公司不是"同行业"，而是**相近现金流特征、风险特征、增长特征**的公司。

筛选维度：
1. 相近的**增长率**（Revenue CAGR, EPS CAGR）
2. 相近的**盈利利润率**（EBIT margin, Net margin）
3. 相近的**再投资率**
4. 相近的**风险**（Beta, 财务杠杆）

### 3.3 控制差异：回归倍数法

当可比公司差异较大时，用**截面回归**控制：

```
P/E ~ f(增长率, 利润率, Beta)
EV/EBITDA ~ f(增长率, ROIC, 再投资率)
```

**实操**：Damodaran 每年在 damodaran.com 发布各行业的回归结果，可直接使用。

---

## 框架四：资产基础估值

适用场景：房地产、自然资源、困境公司、控股公司

| 方法 | 说明 |
|-----|-----|
| **账面价值** | 最低参考，不等于市场价值 |
| **清算价值** | 资产按变现价格估算；减去负债 |
| **重置成本** | 复制同等资产所需的成本 |
| **NAV（净资产价值）** | 持有资产的市场价值之和；常用于 REITs、投资公司 |

---

## 框架五：特殊情境（《估值的阴暗面》核心）

对于下列情境，标准 DCF 会失效，需专项处理。详见各参考文件：

- **负盈利/高成长公司** → 读 `references/darkside-growth.md`
- **周期性公司** → 读 `references/darkside-cyclical.md`
- **金融服务公司** → 读 `references/darkside-financials.md`
- **大宗商品公司** → 读 `references/darkside-commodity.md`
- **新兴市场公司** → 读 `references/darkside-commodity.md`（Part B）
- **困境/濒临破产公司** → 读 `references/darkside-commodity.md`（Part C）

---

## 框架六：叙事转数字（Narrative-to-Numbers）

Damodaran 在后期著作中强调的核心方法论，避免估值沦为数字游戏。

### 步骤：
1. **写出商业故事**（用文字，不用数字）
   - 公司在做什么市场？市场有多大？
   - 竞争优势（Moat）是什么？能持续多久？
   - 谁是主要威胁？
   
2. **将故事转化为财务驱动因子**

   | 故事元素 | 对应财务假设 |
   |---------|------------|
   | 市场规模 | 长期可寻址收入上限 |
   | 市场份额 | 收入增速与最终收入规模 |
   | 竞争优势 | 目标营业利润率 |
   | 再投资需求 | Sales-to-Capital Ratio |
   | 风险 | Beta & 默认利差 |

3. **建立场景（Scenario Analysis）**
   - 悲观 / 基准 / 乐观 三个故事版本
   - 为每个场景赋予概率
   - 加权得出**概率加权估值**

4. **识别价值驱动因子**
   - 做敏感性分析（tornado chart）
   - 找出哪个假设对估值影响最大，重点验证

---

## 常见陷阱与 Damodaran 警示

| 陷阱 | 正确做法 |
|-----|---------|
| 终值增长率 g 超出 min(GDP, Rf) | g ≤ min(名义GDP增速, 无风险利率 Rf)；A 股当前 Rf ≈ 2.0–2.3%，多数公司 g 应取 2.0–2.5%；g/Rf > 1 时禁止使用 Gordon Growth |
| g 与 ROIC、RR 三者不一致 | 强制校验 g = ROIC × RR；偏差 > 1.5 ppt 必须解释，> 3 ppt 必须重做（防止"高 g + 低 RR + 不变 ROIC"虚增估值）|
| 循环引用：用市值权重计算 WACC 再倒推市值 | 迭代求解，或先用行业 WACC |
| 用账面价值权重计算 WACC | 必须用市场价值权重 |
| 忽视稀释（期权/可转债） | 用完全稀释股数；期权用 Black-Scholes 处理；SBC 公司必须 TSM |
| 忽视少数股东权益（NCI）| EV - 净负债 - NCI = 归母股权价值；金融控股集团/新能源车企/综合集团必扣 |
| SBC 既不扣 EBIT 又不稀释 | 二选一不可两免：扣 EBIT+基础股数 / 不扣 EBIT+全摊薄股数 |
| 对周期股用当期盈利做乘数 | 用正常化盈利（Normalized Earnings） |
| 加控制权溢价时双重计入 | 内在价值DCF若已含协同效应则不再加溢价 |
| 对新兴市场忽视国家风险 | 在折现率或现金流中显式加入国家风险（A 股默认含中国 CRP）|
| 把估值当精确科学 | 估值是估计（Estimate），始终给出价值区间而非单点 |

**金融公司特别提示：**

> 若分析对象是**证券、经纪商、信托、资管公司**，在Step 3前必须额外执行：
> 1. 读取 `references/valuation-methods.md` 的"第八部分（续）：金融（证券/资管）专项"
> 2. ROE正规化：使用**指数加权均值**（半衰5年），而非简单算术平均——证券ROE波动极大（-10%到20%），简单平均会严重失真
> 3. Ke参数：券商Beta参考值（Damodaran 2026）— Unlevered Beta ≈ 1.171，Levered Beta ≈ 1.356；中国A股券商建议Ke = Rf(2.0-2.5%) + Beta(1.1-1.4) × ERP(5.7%) ≈ 8.3-10.5%
> 4. P/B-ROE公式在ROE接近或低于Ke时失效（分母趋零或为负），此时必须切换FCFE DCF
> 5. 估值结果必须与FCFE DCF交叉验证，P/B-ROE仅作辅助参考


---

## 输出规范

每次完整估值输出应包含：

1. **公司故事概述**（2–3句）
2. **估值方法选择说明**（为何用此方法）
3. **关键假设汇总表**（增长率、利润率、WACC、g）
4. **估值结果**（价值区间，而非单点）
5. **敏感性分析**（至少两个关键变量）
6. **与当前市价对比**（高估/低估/合理）
7. **主要风险提示**

---

## 数据来源参考

**本 skill 的 `assets/damodaran-templates/` 目录已包含达摩达兰官网最新数据文件，优先使用本地文件，无需上网查询。**

| 数据 | 本地文件（优先） | 备用外部来源 |
|-----|----------------|------------|
| ERP（股权风险溢价） | `assets/damodaran-templates/ERPApril26.xlsx` | damodaran.com |
| 国家/地区风险溢价（CRP） | `assets/damodaran-templates/ctrypremApr26.xlsx` | damodaran.com |
| 行业 Unlevered Beta | `assets/damodaran-templates/betas.xls` | damodaran.com |
| 默认利差 / 合成评级 | `assets/damodaran-templates/ratings.xls` | damodaran.com |
| 行业综合数据（利润率/ROIC/倍数）| `assets/damodaran-templates/AlldataMarch2026.xlsx` | damodaran.com |
| 行业 P/E 回归数据 | `assets/damodaran-templates/pedata.xls` | damodaran.com |
| 行业 P/B 回归数据 | `assets/damodaran-templates/pbvdata.xls` | — |
| 无风险利率 | — | 各国央行官网，10年期国债YTM |
| 公司财务数据 | — | 公司年报、10-K/20-F、Wind、Bloomberg |

**Python DCF 引擎：** `scripts/damodaran_dcf.py` 实现完整三阶段 FCFF DCF，含 EPV、情景分析、敏感性分析、Excel 输出。调用示例见 `references/valuation-methods.md`。

**模板速查（哪个 .xls 对应哪个场景）：** 见 `references/valuation-methods.md`。
