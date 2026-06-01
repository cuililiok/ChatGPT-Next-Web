"""
Tests for dcf_model. Runnable with `pytest -q` or `python test_dcf_model.py`.
Pure stdlib; no third-party dependencies.
"""

import math

from dcf_model import (
    DCFInputs,
    DCFModel,
    implied_growth,
    implied_terminal_margin,
)


def _base(**overrides) -> DCFInputs:
    defaults = dict(
        revenue_0=1_000.0,
        ebit_margin_start=0.20,
        ebit_margin_target=0.20,
        tax_rate=0.25,
        sales_to_capital=2.0,
        growth_start=0.10,
        growth_terminal=0.02,
        forecast_years=10,
        high_growth_years=3,
        margin_ramp_years=5,
        wacc=0.09,
        terminal_roic=0.12,
        diluted_shares=100.0,
    )
    defaults.update(overrides)
    return DCFInputs(**defaults)


def test_zero_growth_no_reinvestment_is_a_perpetuity():
    """If g=0 everywhere and no reinvestment, EV must equal NOPAT / WACC."""
    inp = _base(
        growth_start=0.0,
        growth_terminal=0.0,
        high_growth_years=10,   # flat, no fade
        margin_ramp_years=1,    # margin constant from year 1
        terminal_roic=0.12,     # with g=0, reinvestment rate = 0 regardless
    )
    res = DCFModel(inp).value()
    nopat = inp.revenue_0 * inp.ebit_margin_target * (1 - inp.tax_rate)
    expected_ev = nopat / inp.wacc
    assert math.isclose(res.enterprise_value, expected_ev, rel_tol=1e-6), (
        res.enterprise_value, expected_ev,
    )
    # No reinvestment at g=0, so terminal reinvestment rate is 0.
    assert math.isclose(res.terminal_reinvestment_rate, 0.0, abs_tol=1e-12)


def test_growth_path_fades_to_terminal():
    m = DCFModel(_base(growth_start=0.10, growth_terminal=0.02,
                       high_growth_years=3, forecast_years=10))
    path = m.growth_path()
    assert all(math.isclose(g, 0.10) for g in path[:3])   # plateau held
    assert math.isclose(path[-1], 0.02, abs_tol=1e-12)    # ends at terminal g
    # strictly non-increasing during the fade
    fade = path[3:]
    assert all(a >= b - 1e-12 for a, b in zip(fade, fade[1:]))


def test_margin_ramps_then_holds():
    m = DCFModel(_base(ebit_margin_start=0.10, ebit_margin_target=0.30,
                       margin_ramp_years=5, forecast_years=10))
    margins = m.margin_path()
    assert math.isclose(margins[0], 0.10 + (0.30 - 0.10) * (1 / 5))
    assert math.isclose(margins[4], 0.30)            # reached target at ramp year
    assert margins[-1] == 0.30                        # held thereafter


def test_equity_bridge_uses_net_debt_and_shares():
    """Net cash should lift per-share value above EV/shares; net debt should lower it."""
    net_cash = _base(net_debt=-500.0, diluted_shares=100.0)
    res_cash = DCFModel(net_cash).value()
    ev_per_share = res_cash.enterprise_value / 100.0
    assert res_cash.per_share_value > ev_per_share    # cash added back

    net_debt = _base(net_debt=500.0, diluted_shares=100.0)
    res_debt = DCFModel(net_debt).value()
    assert res_debt.per_share_value < res_debt.enterprise_value / 100.0


def test_reverse_dcf_round_trip_growth():
    """value() at g* gives price P; implied_growth(P) must recover g*."""
    base = _base(growth_start=0.18)
    price = DCFModel(base).value().per_share_value
    # solve starting from a different base growth to prove the solver works
    start = _base(growth_start=0.05)
    g_star = implied_growth(start, price)
    assert math.isclose(g_star, 0.18, abs_tol=1e-4), g_star


def test_reverse_dcf_round_trip_margin():
    base = _base(ebit_margin_target=0.28)
    price = DCFModel(base).value().per_share_value
    start = _base(ebit_margin_target=0.15)
    m_star = implied_terminal_margin(start, price)
    assert math.isclose(m_star, 0.28, abs_tol=1e-4), m_star


def test_terminal_value_share_warning_fires_for_aggressive_growth():
    res = DCFModel(_base(growth_start=0.45, high_growth_years=8,
                         growth_terminal=0.04)).value()
    assert any("Terminal value" in w for w in res.warnings)


def test_invalid_terminal_roic_below_growth_raises():
    try:
        DCFModel(_base(growth_terminal=0.05, terminal_roic=0.04))
    except ValueError as e:
        assert "terminal_roic" in str(e)
    else:
        raise AssertionError("expected ValueError for ROIC <= terminal growth")


def test_wacc_must_exceed_terminal_growth():
    try:
        DCFModel(_base(wacc=0.03, growth_terminal=0.04))
    except ValueError as e:
        assert "terminal growth" in str(e)
    else:
        raise AssertionError("expected ValueError for WACC <= terminal growth")


def test_unbracketed_reverse_target_raises():
    base = _base()
    huge_price = DCFModel(base).value().per_share_value * 1000
    try:
        implied_growth(base, huge_price, lo=-0.5, hi=0.5)
    except ValueError as e:
        assert "bracket" in str(e).lower()
    else:
        raise AssertionError("expected ValueError when target not bracketed")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"PASS  {t.__name__}")
    print(f"\n{passed}/{len(tests)} tests passed.")
