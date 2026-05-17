---
name: peer-compare
description: 同业财务横向对比分析。当用户想比较同行业多只股票的基本面、估值、成长性、现金质量时使用。触发词包括："同业对比"、"横向比较"、"哪只更好"、"对比一下"、"没有比较就没有伤害"，或同时提到2只及以上股票代码并要求分析/比较时。输出终端彩色对比表 + Excel报告，每项指标自动排名标记🥇🥈🔴。
---

# 同业财务对比 Skill

把同行业多只股票的关键财务指标并排展示，每项自动排名，一眼看出取舍。

## 对比维度（16项指标）

| 分类 | 指标 |
|------|------|
| 💰 估值 | PE(TTM)、PB、PS(TTM)、股息率、总市值 |
| 📊 基本面 | ROE、毛利率、净利率、资产负债率、流动比率 |
| 🚀 成长性 | 营收增速、净利润增速、ROE(3年均)、EPS增速 |
| 🏆 现金质量 | 经营现金/净利润、自由现金收益率、应收/营收、毛利额增速 |

每项指标自动标注：🥇最优  🥈次优  🔴最差

最后输出**综合评分小结**，相对排名加总得分。

## 工作流程

### 第一步：安装依赖 & 运行

```bash
pip install akshare pandas openpyxl rich --break-system-packages -q

python os.path.join(os.getenv('skill_path'), 'peer-compare', 'scripts', 'compare.py') \
  --stocks 600519 000858 000568 \
  --year 2023 \
  --output /mnt/user-data/outputs/compare.xlsx
```

参数说明：
- `--stocks`：2~6只股票代码（A股6位代码）
- `--year`：财报年份，默认上一自然年
- `--output`：Excel导出路径，不填则自动保存到outputs目录

### 第二步：数据来源

```
AKShare（东方财富 + 同花顺接口）

实时估值  → stock_zh_a_spot_em        PE/PB/市值
利润表    → stock_profit_sheet_by_yearly_em
资产负债表 → stock_balance_sheet_by_yearly_em
现金流量表 → stock_cash_flow_sheet_by_yearly_em
主要指标  → stock_financial_abstract_ths  ROE/毛利率/增速
```

### 第三步：展示结果

1. 终端已输出彩色对比表，截图或直接阅读
2. 用 `present_files` 将 Excel 文件提供给用户

## 使用示例

```bash
# 白酒三兄弟
python compare.py --stocks 600519 000858 000568 --year 2023

# 新能源车
python compare.py --stocks 002594 601238 000800 --year 2023

# 黄金股
python compare.py --stocks 600547 601899 000975 --year 2023

# 银行对比
python compare.py --stocks 600036 601318 601166 601288 --year 2023
```

## 输出示例（终端）

```
╭─────────── 💰 估值 ───────────╮
│ 指标       │ 贵州茅台 │ 五粮液 │ 泸州老窖 │
│ PE(TTM)    │  25.3   │ 18.6 🥇│  22.1   │
│ PB         │   8.2   │  5.4 🥇│   7.8   │
│ 股息率     │   3.1%  │  3.8%🥇│   2.9% 🔴│
╰────────────────────────────────╯

🏅 综合评分小结
🥇 五粮液     38/56
🥈 贵州茅台   31/56
🥉 泸州老窖   23/56
```

## 注意事项

- 数据来源为公开财报，实时性依赖AKShare更新频率
- 综合评分仅供参考，不同行业横向对比意义有限
- 建议对比**同行业**股票，跨行业对比需自行判断权重
- AKShare接口偶有调整，若某字段返回N/A，不影响其他指标
