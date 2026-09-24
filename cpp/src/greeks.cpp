#include "greeks.hpp"
#include "black_scholes.hpp"
#include <cmath>

Greeks compute_greeks(double S, double K, double T, double r, double sigma,
                      double d1, double d2) {
    double sqrtT   = std::sqrt(T);
    double expRT   = std::exp(-r * T);
    double nd1_pdf = norm_pdf(d1);

    Greeks g;

    // Delta: dV/dS
    g.delta_call = norm_cdf(d1);
    g.delta_put  = g.delta_call - 1.0;

    // Gamma: d²V/dS²  (identical for call and put)
    g.gamma = nd1_pdf / (S * sigma * sqrtT);

    // Vega: dV/dσ  (per 1% move in vol, i.e. /100)
    g.vega = S * nd1_pdf * sqrtT / 100.0;

    // Theta: dV/dT  (per calendar day, i.e. /365)
    double common_theta = -(S * nd1_pdf * sigma) / (2.0 * sqrtT);
    g.theta_call = (common_theta - r * K * expRT * norm_cdf(d2))  / 365.0;
    g.theta_put  = (common_theta + r * K * expRT * norm_cdf(-d2)) / 365.0;

    // Rho: dV/dr  (per 1% move in rate, i.e. /100)
    g.rho_call =  K * T * expRT * norm_cdf(d2)  / 100.0;
    g.rho_put  = -K * T * expRT * norm_cdf(-d2) / 100.0;

    return g;
}
