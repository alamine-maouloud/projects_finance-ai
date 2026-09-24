#pragma once

struct BSResult {
    double call;
    double put;
    double d1;
    double d2;
};

// N(x): cumulative standard normal distribution
double norm_cdf(double x);

// n(x): standard normal PDF
double norm_pdf(double x);

// Analytical Black-Scholes pricing
// S: spot, K: strike, T: maturity (years), r: risk-free rate, sigma: volatility
BSResult black_scholes(double S, double K, double T, double r, double sigma);
