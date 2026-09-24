#pragma once
// Monte Carlo simulation of order flow in a limit order book.
//
// Background flow: the zero-intelligence model of Cont, Stoikov & Talreja
// (2010), with unit orders:
//   * limit buy (sell) orders arrive at rate lam[i] at i ticks from the best
//     ask (bid), i = 1..K
//   * every resting order at distance i is cancelled at rate theta[i]
//     (theta[K] beyond the window)
//   * market buy and sell orders arrive with intensity lambda_mo(t)
// Market orders follow a bivariate Hawkes process with exponential kernel,
//   lambda_b(t) = mu0 + sum_k alpha_self e^{-beta (t - t_k^b)} + sum_k alpha_cross e^{-beta (t - t_k^s)}
// with mu0 = mu (1 - n), n = (alpha_self + alpha_cross) / beta, so that the mean
// rate stays mu; n = 0 recovers the Poisson model. Poisson parts are exact
// (competing exponential clocks, state constant between events) and the
// Hawkes part uses Ogata thinning.
//
// An optional agent submits market orders at fixed times (execution studies).

#include <cstdint>
#include <vector>

namespace mcrisk::lob {

struct FlowParams {
    std::vector<double> lam;     // K limit-order rates per side, distance 1..K
    std::vector<double> theta;   // K per-order cancellation rates
    double mu = 0.94;            // mean market-order rate per side
    double alpha_self = 0.0;
    double alpha_cross = 0.0;
    double beta = 1.0;
    int n_ticks = 1 << 16;
    int p0 = 1 << 15;
};

struct AgentOrder {
    double t;
    int side;                    // BID = buy, ASK = sell
    std::int64_t qty;
};

struct SimResult {
    // quotes sampled on a regular grid (state just before each grid time)
    std::vector<double> bid, ask;
    // depth snapshots: volume at 0..K-1 ticks from each side's own best
    std::vector<std::int64_t> depth_bid, depth_ask;   // n_snap * K
    // background market orders
    std::vector<double> mo_t, mo_mid_before, mo_mid_after;
    std::vector<int> mo_side;
    // agent executions (one entry per agent order)
    std::vector<double> ag_t, ag_mid_before, ag_notional;
    std::vector<std::int64_t> ag_filled;
    // sufficient statistics for maximum-likelihood calibration
    std::vector<std::int64_t> n_limit, n_cancel;      // by distance bucket 1..K (both sides)
    std::vector<double> queue_time;                   // integral of queue size dt, by bucket
    std::int64_t n_market = 0, n_events = 0;
    double t_end = 0.0;
    bool hit_edge = false;
};

SimResult simulate_flow(const FlowParams& prm, double horizon, std::uint64_t seed,
                        double grid_dt, double depth_dt, const std::vector<AgentOrder>& agent,
                        bool record_mo);

// Independent paths of the same agent schedule, run in parallel. Each path
// warms the book up for `warmup` seconds before t = 0. Outputs (n_paths x n_orders)
// agent fills and notionals, plus the mid at t = 0 and at the horizon.
void simulate_agent_paths(const FlowParams& prm, double horizon, double warmup,
                          const std::vector<AgentOrder>& agent, std::int64_t n_paths,
                          std::uint64_t seed, int threads, std::int64_t* filled,
                          double* notional, double* mid_before, double* mid0, double* mid_end);

}  // namespace mcrisk::lob
