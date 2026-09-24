#pragma once

struct Greeks {
    double delta_call;
    double delta_put;
    double gamma;    // same for call and put
    double vega;     // same for call and put (per 1% move)
    double theta_call;
    double theta_put;
    double rho_call;
    double rho_put;
};

// Analytical Greeks derived from Black-Scholes
// d1, d2 come from the BS computation
Greeks compute_greeks(double S, double K, double T, double r, double sigma,
                      double d1, double d2);
