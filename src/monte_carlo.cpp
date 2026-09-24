#include "monte_carlo.hpp"
#include <cmath>
#include <random>
#include <numeric>
#include <vector>

MCResult monte_carlo(double S, double K, double T, double r, double sigma, int N) {
    std::mt19937_64 rng(42);
    std::normal_distribution<double> dist(0.0, 1.0);

    double drift   = (r - 0.5 * sigma * sigma) * T;
    double diffusion = sigma * std::sqrt(T);
    double discount  = std::exp(-r * T);

    std::vector<double> call_payoffs(N);
    std::vector<double> put_payoffs(N);

    for (int i = 0; i < N; ++i) {
        double Z   = dist(rng);
        double S_T = S * std::exp(drift + diffusion * Z);
        call_payoffs[i] = std::max(S_T - K, 0.0);
        put_payoffs[i]  = std::max(K - S_T, 0.0);
    }

    auto mean_and_stderr = [&](const std::vector<double>& v) -> std::pair<double, double> {
        double mean = std::accumulate(v.begin(), v.end(), 0.0) / N;
        double var  = 0.0;
        for (double x : v) var += (x - mean) * (x - mean);
        var /= (N - 1);
        return {mean * discount, std::sqrt(var / N) * discount};
    };

    auto [call_mean, call_se] = mean_and_stderr(call_payoffs);
    auto [put_mean,  put_se]  = mean_and_stderr(put_payoffs);

    return {call_mean, put_mean, call_se, put_se};
}
