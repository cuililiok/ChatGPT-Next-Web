"""
Single-source FCFF DCF engine (rewrite of the 14-step skill's valuation module).

Why this rewrite exists (problems in the original it fixes):
  1. Constant revenue CAGR for the whole horizon  -> replaced with an explicit
     FADING growth path (high-growth plateau, then linear fade to terminal g).
  2. Hardcoded `margin_y0 = margin_y5 * 0.7`        -> margin is an explicit,
     configurable linear ramp from a real starting margin to a target margin.
  3. Two independent DCF implementations (engine + reverse_dcf script) that can
     drift apart -> ONE forward model; reverse-DCF is just a solver that calls it.
  4. Equity bridge never implemented (returned EV, per_share = 0) -> full bridge:
     EV - net debt - minority interest (+ non-operating assets) -> per share.
  5. Terminal value with no reinvestment-consistency check -> terminal FCFF is
     derived from g = ROIC_terminal x reinvestment_rate (Damodaran identity),
     and the model refuses internally inconsistent inputs.

Design choices (made explicit on purpose, unlike the original's hidden ones):
  - Pure standard library. No numpy / akshare / pandas. Easy to audit and test.
  - A single WACC is used for discounting the explicit period; the terminal
    Gordon denominator may use a separate `terminal_wacc`. This is a documented
    simplification, not a buried assumption.
  - Every non-obvious output carries a warning when it crosses a sanity threshold
    (terminal value share, terminal growth vs risk-free, excess terminal returns).

DISCLAIMER
  This is an educational modelling tool. Its output is entirely a function of the
  assumptions fed into it (growth, margins, WACC, terminal ROIC). It does NOT
  constitute investment advice or a recommendation to buy or sell any security.
  A precise-looking number is not a precise truth. Always stress-test assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
@dataclass
class DCFInputs:
    """All assumptions for a single FCFF DCF run. Amounts in the same currency unit."""

    # --- operating base ---
    revenue_0: float                      # latest actual annual revenue (the base year)
    ebit_margin_start: float              # CURRENT operating (EBIT) margin, e.g. 0.20
    ebit_margin_target: float             # mature/terminal operating margin, e.g. 0.30
    tax_rate: float                       # effective cash tax rate, e.g. 0.15
    sales_to_capital: float               # delta_revenue / reinvestment (capital efficiency)

    # --- growth path (fading, not flat) ---
    growth_start: float                   # growth in the high-growth plateau, e.g. 0.20
    growth_terminal: float                # perpetual growth, must be <= risk_free
    forecast_years: int = 10              # length of the explicit forecast
    high_growth_years: int = 3            # years held at growth_start before fading
    margin_ramp_years: int = 5            # years to reach ebit_margin_target (linear)

    # --- discounting ---
    wacc: float = 0.085                   # cost of capital for the explicit period
    terminal_wacc: Optional[float] = None  # defaults to `wacc` if None
    terminal_roic: Optional[float] = None  # terminal return on invested capital;
    #                                        defaults to terminal_wacc (value-neutral)

    # --- equity bridge ---
    net_debt: float = 0.0                 # total debt - cash & equivalents
    minority_interest: float = 0.0        # non-controlling interest (market/booked)
    non_operating_assets: float = 0.0     # e.g. long-term investments not in FCFF
    diluted_shares: float = 1.0           # fully diluted share count

    # --- sanity thresholds (for warnings, not hard errors) ---
    risk_free: float = 0.025              # used to sanity-check terminal growth

    def resolved_terminal_wacc(self) -> float:
        return self.terminal_wacc if self.terminal_wacc is not None else self.wacc

    def resolved_terminal_roic(self) -> float:
        # Conservative default: no excess returns in perpetuity (ROIC == WACC).
        return self.terminal_roic if self.terminal_roic is not None else self.resolved_terminal_wacc()


# --------------------------------------------------------------------------- #
# Per-year detail + result
# --------------------------------------------------------------------------- #
@dataclass
class YearRow:
    year: int
    growth: float
    revenue: float
    ebit_margin: float
    nopat: float
    reinvestment: float
    fcff: float
    discount_factor: float
    pv_fcff: float


@dataclass
class DCFResult:
    rows: List[YearRow]
    pv_explicit: float
    terminal_value: float
    pv_terminal: float
    enterprise_value: float
    equity_value: float
    per_share_value: float
    terminal_value_share: float           # pv_terminal / EV
    terminal_reinvestment_rate: float     # g_t / ROIC_t
    warnings: List[str] = field(default_factory=list)

    DISCLAIMER: str = (
        "Educational model only. Output is a direct function of the input "
        "assumptions and does NOT constitute investment advice."
    )

    def summary(self) -> str:
        lines = [
            "=== FCFF DCF result ===",
            f"PV(explicit FCFF) : {self.pv_explicit:,.1f}",
            f"PV(terminal)      : {self.pv_terminal:,.1f}  "
            f"({self.terminal_value_share:.1%} of EV)",
            f"Enterprise value  : {self.enterprise_value:,.1f}",
            f"Equity value      : {self.equity_value:,.1f}",
            f"Per-share value   : {self.per_share_value:,.4f}",
            f"Terminal reinvest. rate (g/ROIC): {self.terminal_reinvestment_rate:.1%}",
        ]
        if self.warnings:
            lines.append("--- warnings ---")
            lines.extend(f"  ! {w}" for w in self.warnings)
        lines.append(f"NOTE: {self.DISCLAIMER}")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# The model (single source of truth)
# --------------------------------------------------------------------------- #
class DCFModel:
    def __init__(self, inputs: DCFInputs):
        self.i = inputs
        self._validate_static()

    # ---- input validation (hard errors for impossible inputs) ----
    def _validate_static(self) -> None:
        i = self.i
        if i.forecast_years < 1:
            raise ValueError("forecast_years must be >= 1")
        if i.high_growth_years < 0 or i.high_growth_years > i.forecast_years:
            raise ValueError("high_growth_years must be in [0, forecast_years]")
        if i.margin_ramp_years < 1:
            raise ValueError("margin_ramp_years must be >= 1")
        if i.sales_to_capital <= 0:
            raise ValueError("sales_to_capital must be > 0")
        if i.wacc <= i.growth_terminal:
            raise ValueError("wacc must exceed terminal growth (Gordon model breaks otherwise)")
        if i.resolved_terminal_wacc() <= i.growth_terminal:
            raise ValueError("terminal_wacc must exceed terminal growth")
        roic_t = i.resolved_terminal_roic()
        if roic_t <= 0:
            raise ValueError("terminal_roic must be > 0")
        if roic_t <= i.growth_terminal:
            # reinvestment rate g/ROIC would be >= 1 (company reinvests >=100% of NOPAT)
            raise ValueError(
                "terminal_roic must exceed terminal growth, otherwise the implied "
                "terminal reinvestment rate is >= 100% (impossible to sustain)"
            )

    # ---- growth path: plateau then linear fade to terminal ----
    def growth_path(self) -> List[float]:
        i = self.i
        rates: List[float] = []
        fade_span = i.forecast_years - i.high_growth_years
        for t in range(1, i.forecast_years + 1):
            if t <= i.high_growth_years:
                rates.append(i.growth_start)
            else:
                step = t - i.high_growth_years
                frac = step / fade_span if fade_span > 0 else 1.0
                rates.append(i.growth_start + (i.growth_terminal - i.growth_start) * frac)
        return rates

    # ---- margin path: linear ramp to target, then held ----
    def margin_path(self) -> List[float]:
        i = self.i
        margins: List[float] = []
        for t in range(1, i.forecast_years + 1):
            if t >= i.margin_ramp_years:
                margins.append(i.ebit_margin_target)
            else:
                frac = t / i.margin_ramp_years
                margins.append(
                    i.ebit_margin_start + (i.ebit_margin_target - i.ebit_margin_start) * frac
                )
        return margins

    # ---- the valuation ----
    def value(self) -> DCFResult:
        i = self.i
        warnings: List[str] = []
        growths = self.growth_path()
        margins = self.margin_path()

        rows: List[YearRow] = []
        rev_prev = i.revenue_0
        pv_explicit = 0.0
        for idx in range(i.forecast_years):
            t = idx + 1
            g = growths[idx]
            m = margins[idx]
            rev = rev_prev * (1.0 + g)
            nopat = rev * m * (1.0 - i.tax_rate)
            delta_rev = rev - rev_prev
            reinvestment = delta_rev / i.sales_to_capital
            fcff = nopat - reinvestment
            df = (1.0 + i.wacc) ** t
            pv = fcff / df
            pv_explicit += pv
            rows.append(
                YearRow(
                    year=t, growth=g, revenue=rev, ebit_margin=m, nopat=nopat,
                    reinvestment=reinvestment, fcff=fcff, discount_factor=df, pv_fcff=pv,
                )
            )
            rev_prev = rev

        # --- terminal value via reinvestment-consistent FCFF ---
        g_t = i.growth_terminal
        roic_t = i.resolved_terminal_roic()
        wacc_t = i.resolved_terminal_wacc()
        rr_t = g_t / roic_t                      # Damodaran identity: g = ROIC * RR
        rev_n1 = rev_prev * (1.0 + g_t)
        nopat_n1 = rev_n1 * i.ebit_margin_target * (1.0 - i.tax_rate)
        fcff_n1 = nopat_n1 * (1.0 - rr_t)
        terminal_value = fcff_n1 / (wacc_t - g_t)
        pv_terminal = terminal_value / ((1.0 + i.wacc) ** i.forecast_years)

        enterprise_value = pv_explicit + pv_terminal
        equity_value = (
            enterprise_value - i.net_debt - i.minority_interest + i.non_operating_assets
        )
        per_share = equity_value / i.diluted_shares if i.diluted_shares else float("nan")
        tv_share = pv_terminal / enterprise_value if enterprise_value else float("nan")

        # --- soft sanity checks ---
        if tv_share > 0.80:
            warnings.append(
                f"Terminal value is {tv_share:.0%} of EV (>80%): value rests mostly on "
                "perpetuity assumptions, not the explicit forecast."
            )
        if g_t > i.risk_free:
            warnings.append(
                f"Terminal growth {g_t:.1%} exceeds risk-free {i.risk_free:.1%}: a company "
                "cannot grow faster than the economy forever."
            )
        if roic_t > wacc_t + 1e-9:
            warnings.append(
                f"Terminal ROIC {roic_t:.1%} > terminal WACC {wacc_t:.1%}: assumes excess "
                "returns persist in perpetuity (competition usually erodes these)."
            )
        if equity_value < 0:
            warnings.append("Equity value is negative after the debt/NCI bridge.")

        return DCFResult(
            rows=rows,
            pv_explicit=pv_explicit,
            terminal_value=terminal_value,
            pv_terminal=pv_terminal,
            enterprise_value=enterprise_value,
            equity_value=equity_value,
            per_share_value=per_share,
            terminal_value_share=tv_share,
            terminal_reinvestment_rate=rr_t,
            warnings=warnings,
        )


# --------------------------------------------------------------------------- #
# Reverse DCF: ONE solver that drives the SAME forward model.
# No second DCF implementation -> no drift.
# --------------------------------------------------------------------------- #
def _bisect(f: Callable[[float], float], lo: float, hi: float,
            tol: float = 1e-7, max_iter: int = 200) -> float:
    flo, fhi = f(lo), f(hi)
    if flo == 0:
        return lo
    if fhi == 0:
        return hi
    if flo * fhi > 0:
        raise ValueError(
            "Target not bracketed by [lo, hi]; widen the search range "
            f"(f(lo)={flo:.4g}, f(hi)={fhi:.4g})."
        )
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fmid = f(mid)
        if abs(fmid) < tol or (hi - lo) < tol:
            return mid
        if flo * fmid < 0:
            hi, fhi = mid, fmid
        else:
            lo, flo = mid, fmid
    return 0.5 * (lo + hi)


def implied_growth(base: DCFInputs, target_price: float,
                   lo: float = -0.50, hi: float = 1.50) -> float:
    """Solve for the high-growth-plateau rate that justifies `target_price`.

    This is the only honest way to read an expensive multiple: translate today's
    price into the growth the market is implicitly demanding, then judge whether
    that demand is realistic.
    """
    def diff(g_start: float) -> float:
        trial = DCFInputs(**{**base.__dict__, "growth_start": g_start})
        return DCFModel(trial).value().per_share_value - target_price

    return _bisect(diff, lo, hi)


def implied_terminal_margin(base: DCFInputs, target_price: float,
                            lo: float = 0.01, hi: float = 0.90) -> float:
    """Solve for the terminal EBIT margin that justifies `target_price`."""
    def diff(margin: float) -> float:
        trial = DCFInputs(**{**base.__dict__, "ebit_margin_target": margin})
        return DCFModel(trial).value().per_share_value - target_price

    return _bisect(diff, lo, hi)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    # Illustrative inputs only (NOT a recommendation). Numbers are placeholders.
    demo = DCFInputs(
        revenue_0=5_930.0,          # e.g. RMB mn
        ebit_margin_start=0.33,
        ebit_margin_target=0.38,
        tax_rate=0.15,
        sales_to_capital=1.5,
        growth_start=0.20,
        growth_terminal=0.025,
        forecast_years=10,
        high_growth_years=3,
        margin_ramp_years=5,
        wacc=0.085,
        terminal_roic=0.12,
        net_debt=-6_000.0,          # net cash -> negative net debt
        diluted_shares=462.0,
    )
    res = DCFModel(demo).value()
    print(res.summary())
    print()
    price = 256.0
    g_needed = implied_growth(demo, price)
    print(f"To justify a price of {price}, the market implies a high-growth-plateau "
          f"rate of ~{g_needed:.1%} (vs the {demo.growth_start:.1%} base case).")
