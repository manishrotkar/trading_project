import math
from scipy.optimize import brentq
from scipy.stats import norm


# ============================================================
# TEST DATA
# ============================================================

F = 23186.0          # NIFTY Sep Futures
K = 22550.0          # Strike
option_price = 4.55  # OTM PE LTP

risk_free_rate = 0.08

# 25-Sep-2026 15:29 -> 29-Sep-2026 15:30
time_to_expiry = (
    (4 * 24 * 60 + 1) * 60
) / (365.0 * 24 * 60 * 60)


# ============================================================
# BLACK-76
# ============================================================

def black76_price(F, K, T, r, sigma, option_type):
    if T <= 0:
        return max(F - K, 0.0) if option_type == "CE" else max(K - F, 0.0)

    if sigma <= 0:
        return math.exp(-r * T) * (
            max(F - K, 0.0)
            if option_type == "CE"
            else max(K - F, 0.0)
        )

    sqrt_T = math.sqrt(T)

    d1 = (
        math.log(F / K)
        + 0.5 * sigma * sigma * T
    ) / (sigma * sqrt_T)

    d2 = d1 - sigma * sqrt_T

    discount = math.exp(-r * T)

    if option_type == "CE":
        return discount * (
            F * norm.cdf(d1)
            - K * norm.cdf(d2)
        )

    return discount * (
        K * norm.cdf(-d2)
        - F * norm.cdf(-d1)
    )


# ============================================================
# IV SOLVER
# ============================================================

def calculate_iv(F, K, T, r, market_price, option_type):

    def objective(sigma):
        return (
            black76_price(
                F,
                K,
                T,
                r,
                sigma,
                option_type,
            )
            - market_price
        )

    return brentq(
        objective,
        0.0001,
        5.0,
    )


# ============================================================
# CALCULATE
# ============================================================

iv = calculate_iv(
    F,
    K,
    time_to_expiry,
    risk_free_rate,
    option_price,
    "PE",
)


# ============================================================
# VALIDATION
# ============================================================

calculated_price = black76_price(
    F,
    K,
    time_to_expiry,
    risk_free_rate,
    iv,
    "PE",
)


print("=" * 60)
print("FYERS-STYLE IV TEST")
print("=" * 60)

print(f"Futures price       : {F}")
print(f"Strike              : {K}")
print(f"Option type         : PE")
print(f"Option LTP          : {option_price}")
print(f"Risk-free rate      : {risk_free_rate:.2%}")
print(f"Time to expiry      : {time_to_expiry:.10f} years")
print(f"Calculated IV       : {iv:.6%}")
print(f"Calculated price    : {calculated_price:.6f}")
print(f"Price difference    : {calculated_price - option_price:.10f}")

print("=" * 60)