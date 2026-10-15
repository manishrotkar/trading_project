"""Unit tests for price_oi_buildup.py -- no data file or network needed."""

import unittest

from price_oi_buildup import (
    classify,
    classify_strike,
    merge_side,
    strike_window,
)


def side(oi=1000.0, oi_change=100.0, price=100.0, prev=90.0, volume=500.0):
    """A merge_side-shaped dict with sensible defaults."""
    return {
        "oi": oi,
        "oi_change": oi_change,
        "volume": volume,
        "price_change": (price / prev - 1.0) if prev else 0.0,
        "contracts": 1,
    }


class ClassifyTest(unittest.TestCase):
    def test_four_quadrants(self):
        self.assertEqual(classify(0.10, 0.20)["classification"], "Long buildup")
        self.assertEqual(classify(-0.10, 0.20)["classification"], "Short buildup")
        self.assertEqual(classify(0.10, -0.20)["classification"], "Short covering")
        self.assertEqual(classify(-0.10, -0.20)["classification"], "Long unwinding")

    def test_bias_words(self):
        self.assertEqual(classify(0.10, 0.20)["bias"], "bullish")
        self.assertEqual(classify(0.10, -0.20)["bias"], "bullish")
        self.assertEqual(classify(-0.10, 0.20)["bias"], "bearish")
        self.assertEqual(classify(-0.10, -0.20)["bias"], "bearish")

    def test_both_flat_is_no_activity(self):
        out = classify(0.0, 0.0)
        self.assertEqual(out["classification"], "No activity")
        self.assertEqual(out["bias"], "neutral")

    def test_price_only_move(self):
        out = classify(0.05, 0.0)
        self.assertEqual(out["classification"], "Price-only move (flat OI)")
        self.assertEqual(out["bias"], "uncertain")

    def test_oi_only_change(self):
        out = classify(0.0, -0.40)
        self.assertEqual(out["classification"], "OI-only change (flat price)")
        self.assertEqual(out["bias"], "uncertain")

    def test_epsilon_treated_as_flat(self):
        # just inside the threshold counts as flat
        self.assertEqual(classify(0.005, 0.005)["classification"], "No activity")
        # just outside does not
        self.assertEqual(classify(0.02, 0.005)["classification"],
                         "Price-only move (flat OI)")

    def test_percentages_are_reported(self):
        out = classify(0.1234, -0.5678)
        self.assertEqual(out["price_chg_pct"], 12.34)
        self.assertEqual(out["oi_chg_pct"], -56.78)


class MergeSideTest(unittest.TestCase):
    def test_volume_weighted_price_change(self):
        rows = [
            {"PrvsClsgPric": "100", "ClsPric": "110",
             "TtlTradgVol": "100", "OpnIntrst": "10", "ChngInOpnIntrst": "1"},
            {"PrvsClsgPric": "100", "ClsPric": "130",
             "TtlTradgVol": "100", "OpnIntrst": "10", "ChngInOpnIntrst": "1"},
        ]
        out = merge_side(rows, "CE")
        # 100 contracts: 10 closed at +10%, 10 at +30% -> +20%
        self.assertAlmostEqual(out["price_change"], 0.20)
        self.assertEqual(out["oi"], 20.0)
        self.assertEqual(out["oi_change"], 2.0)
        self.assertEqual(out["contracts"], 2)

    def test_zero_volume_falls_back_to_largest_oi_contract(self):
        rows = [
            {"PrvsClsgPric": "50", "ClsPric": "55", "TtlTradgVol": "0",
             "OpnIntrst": "5", "ChngInOpnIntrst": "0"},
            {"PrvsClsgPric": "80", "ClsPric": "88", "TtlTradgVol": "0",
             "OpnIntrst": "95", "ChngInOpnIntrst": "0"},
        ]
        out = merge_side(rows, "CE")
        self.assertAlmostEqual(out["price_change"], 0.10)  # the 95-OI contract
        self.assertEqual(out["oi"], 100.0)

    def test_zero_previous_price_gives_zero_change(self):
        out = merge_side([{"PrvsClsgPric": "0", "ClsPric": "10",
                           "TtlTradgVol": "0", "OpnIntrst": "1",
                           "ChngInOpnIntrst": "0"}], "CE")
        self.assertEqual(out["price_change"], 0.0)


class ClassifyStrikeTest(unittest.TestCase):
    def test_active_side_is_classified(self):
        out = classify_strike({"CE": side()})
        self.assertEqual(out["CE"]["classification"], "Long buildup")
        self.assertEqual(out["CE"]["oi"], 1000.0)

    def test_negligible_oi_is_inactive(self):
        out = classify_strike({"PE": side(oi=0.5)})
        self.assertEqual(out["PE"]["classification"], "Inactive")
        self.assertEqual(out["PE"]["bias"], "neutral")

    def test_both_sides_independent(self):
        out = classify_strike({"CE": side(oi_change=-200.0),
                               "PE": side(oi=0.0)})
        self.assertEqual(out["CE"]["classification"], "Short covering")
        self.assertEqual(out["PE"]["classification"], "Inactive")


class StrikeWindowTest(unittest.TestCase):
    def test_window_around_the_money(self):
        # enough strikes below the money that the window must truncate
        strikes = list(range(100, 400, 10))
        window = strike_window(strikes, 245)
        self.assertEqual(window[0], 150)     # ATM - 10*WINDOW
        self.assertEqual(window[-1], 340)    # ATM + 9*WINDOW
        self.assertEqual(len(window), 20)    # WINDOW on each side
        self.assertEqual(window, sorted(window))

    def test_atm_strike_included(self):
        window = strike_window([100, 200, 300], 200)
        self.assertIn(200, window)

    def test_smaller_book_returns_everything(self):
        self.assertEqual(strike_window([100, 110], 105), [100, 110])


if __name__ == "__main__":
    unittest.main()
