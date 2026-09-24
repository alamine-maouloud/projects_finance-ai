#include <iostream>
#include <iomanip>
#include <stdexcept>
#include <string>
#include "black_scholes.hpp"
#include "greeks.hpp"
#include "monte_carlo.hpp"

static void print_usage(const char* prog) {
    std::cerr << "Usage: " << prog
              << " <S> <K> <T> <r> <sigma> [N_paths]\n\n"
              << "  S       Spot price        (e.g. 100)\n"
              << "  K       Strike price      (e.g. 100)\n"
              << "  T       Maturity in years (e.g. 1.0)\n"
              << "  r       Risk-free rate    (e.g. 0.05 for 5%)\n"
              << "  sigma   Volatility        (e.g. 0.20 for 20%)\n"
              << "  N_paths Monte Carlo paths (default: 1000000)\n";
}

int main(int argc, char* argv[]) {
    if (argc < 6 || argc > 7) {
        print_usage(argv[0]);
        return 1;
    }

    double S, K, T, r, sigma;
    int N = 1'000'000;

    try {
        S     = std::stod(argv[1]);
        K     = std::stod(argv[2]);
        T     = std::stod(argv[3]);
        r     = std::stod(argv[4]);
        sigma = std::stod(argv[5]);
        if (argc == 7) N = std::stoi(argv[6]);
    } catch (const std::exception& e) {
        std::cerr << "Error parsing arguments: " << e.what() << "\n";
        return 1;
    }

    if (S <= 0 || K <= 0 || T <= 0 || sigma <= 0) {
        std::cerr << "S, K, T and sigma must be strictly positive.\n";
        return 1;
    }

    // ── Analytical pricing ──────────────────────────────────────────────────
    BSResult bs = black_scholes(S, K, T, r, sigma);
    Greeks   g  = compute_greeks(S, K, T, r, sigma, bs.d1, bs.d2);

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "\n=== Black-Scholes Analytical Pricer ===\n";
    std::cout << "  Parameters : S=" << S << "  K=" << K
              << "  T=" << T << "  r=" << r << "  σ=" << sigma << "\n\n";

    std::cout << "--- Prices ---\n";
    std::cout << "  Call  : " << bs.call << "\n";
    std::cout << "  Put   : " << bs.put  << "\n";
    std::cout << "  d1    : " << bs.d1   << "\n";
    std::cout << "  d2    : " << bs.d2   << "\n\n";

    std::cout << "--- Greeks ---\n";
    std::cout << "  Delta (call) : " << g.delta_call << "\n";
    std::cout << "  Delta (put)  : " << g.delta_put  << "\n";
    std::cout << "  Gamma        : " << g.gamma      << "\n";
    std::cout << "  Vega  (1%)   : " << g.vega       << "\n";
    std::cout << "  Theta (1d)   : " << g.theta_call << "  (call)\n";
    std::cout << "  Theta (1d)   : " << g.theta_put  << "  (put)\n";
    std::cout << "  Rho   (1%)   : " << g.rho_call   << "  (call)\n";
    std::cout << "  Rho   (1%)   : " << g.rho_put    << "  (put)\n\n";

    // ── Monte Carlo ─────────────────────────────────────────────────────────
    std::cout << "--- Monte Carlo (" << N << " paths) ---\n";
    MCResult mc = monte_carlo(S, K, T, r, sigma, N);

    auto pct_err = [](double mc_val, double bs_val) {
        return (mc_val - bs_val) / bs_val * 100.0;
    };

    std::cout << "  Call  : " << mc.call << "  ± " << mc.call_stderr
              << "  (error vs BS: " << std::showpos << pct_err(mc.call, bs.call) << std::noshowpos << "%)\n";
    std::cout << "  Put   : " << mc.put  << "  ± " << mc.put_stderr
              << "  (error vs BS: " << std::showpos << pct_err(mc.put, bs.put)   << std::noshowpos << "%)\n\n";

    return 0;
}
