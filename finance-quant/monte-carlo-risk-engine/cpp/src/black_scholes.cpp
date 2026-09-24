#include "black_scholes.hpp"
#include <cmath>

double norm_cdf(double x) {
    return 0.5 * std::erfc(-x / std::sqrt(2.0));
}

double norm_pdf(double x) {
    return std::exp(-0.5 * x * x) / std::sqrt(2.0 * M_PI);
}

BSResult black_scholes(double S, double K, double T, double r, double sigma) {
    double d1 = (std::log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * std::sqrt(T));
    double d2 = d1 - sigma * std::sqrt(T);

    double call = S * norm_cdf(d1) - K * std::exp(-r * T) * norm_cdf(d2);
    double put  = K * std::exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1);

    return {call, put, d1, d2};
}
