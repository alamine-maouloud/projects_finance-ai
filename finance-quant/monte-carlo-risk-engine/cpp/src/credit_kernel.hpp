#pragma once
// Native portfolio-credit Monte Carlo kernel.
//
// Conditional on the systematic factors F and (t-copula) mixing variable s,
// obligor i defaults independently with probability
//
//     p_i = Phi(d_i),   d_i = a_i / s - g_i . F,   a_i = q_i / sd_i,  g_i = b_i / sd_i
//
// Instead of drawing one variate per obligor (O(N) per scenario) the kernel
// samples defaults by Bernoulli thinning: obligors are grouped in blocks, an
// upper bound p_max of p_i is computed per block from pre-computed ranges,
// candidates are drawn with probability p_max by geometric skipping and
// accepted with probability p_i / p_max. The result is exact, and the cost per
// scenario is O(#blocks + #candidates) - essentially the number of defaults.

#include <cstdint>
#include <vector>

namespace mcrisk {

struct CreditKernel {
    int n = 0;                       // obligors
    int k = 0;                       // factors
    double nu = 0.0;                 // 0 = Gaussian copula, else Student-t dof
    std::vector<double> chol;        // k*k, row-major lower-triangular
    // obligors sorted by block
    std::vector<int> perm;           // sorted position -> original index
    std::vector<double> a, c;        // threshold / sd and loss given default
    std::vector<int> nz_ptr, nz_f;   // CSR sparse g_i
    std::vector<double> nz_g;
    // blocks
    std::vector<int> blk_start;      // size n_blocks + 1
    std::vector<double> blk_amax;
    std::vector<int> bf_ptr, bf_f;   // per-block factor ranges
    std::vector<double> bf_gmin, bf_gmax;

    CreditKernel(int n, int k, const double* loadings /* n*k, correlated-factor space */,
                 const double* chol_lower /* k*k */, const double* threshold,
                 const double* idio_sd, const double* lgd_amount,
                 const std::int64_t* block_id, double nu);

    int n_blocks() const { return static_cast<int>(blk_start.size()) - 1; }

    // Portfolio loss of scenarios [0, n_scen), chunk c seeded by (seed, c).
    void simulate(std::int64_t n_scen, std::uint64_t seed, int threads,
                  std::int64_t chunk, double* losses_out) const;

    // Replays the same scenarios and accumulates, per obligor (original
    // order), the loss in scenarios with lo <= L <= hi. Returns the number of
    // such scenarios.
    std::int64_t conditional_sums(std::int64_t n_scen, std::uint64_t seed, int threads,
                                  std::int64_t chunk, double lo, double hi,
                                  double* sums_out) const;

    // Mean number of candidates per scenario (diagnostic of bound tightness).
    double candidates_per_scenario(std::int64_t n_scen, std::uint64_t seed) const;
};

}  // namespace mcrisk
