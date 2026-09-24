#pragma once

struct MCResult {
    double call;
    double put;
    double call_stderr;  // standard error for confidence interval
    double put_stderr;
};

// Monte Carlo pricing via geometric Brownian motion
// N: number of simulated paths
MCResult monte_carlo(double S, double K, double T, double r, double sigma,
                     int N = 1'000'000);
