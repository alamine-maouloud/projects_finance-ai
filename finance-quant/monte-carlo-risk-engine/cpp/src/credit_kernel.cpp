#include "credit_kernel.hpp"
#include "util.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <stdexcept>

namespace mcrisk {

// ------------------------------------------------------------ set-up -------
CreditKernel::CreditKernel(int n_, int k_, const double* loadings, const double* chol_lower,
                           const double* threshold, const double* idio_sd,
                           const double* lgd_amount, const std::int64_t* block_id, double nu_)
    : n(n_), k(k_), nu(nu_), chol(chol_lower, chol_lower + static_cast<std::size_t>(k_) * k_) {
    if (n <= 0 || k <= 0) throw std::invalid_argument("empty portfolio or factor model");
    perm.resize(n);
    std::iota(perm.begin(), perm.end(), 0);
    std::stable_sort(perm.begin(), perm.end(),
                     [&](int x, int y) { return block_id[x] < block_id[y]; });
    a.resize(n);
    c.resize(n);
    nz_ptr.assign(1, 0);
    for (int s = 0; s < n; ++s) {
        const int i = perm[s];
        if (!(idio_sd[i] > 0.0)) throw std::invalid_argument("idiosyncratic sd must be > 0");
        a[s] = threshold[i] / idio_sd[i];
        c[s] = lgd_amount[i];
        for (int f = 0; f < k; ++f) {
            const double g = loadings[static_cast<std::size_t>(i) * k + f] / idio_sd[i];
            if (g != 0.0) { nz_f.push_back(f); nz_g.push_back(g); }
        }
        nz_ptr.push_back(static_cast<int>(nz_f.size()));
    }
    // blocks: contiguous runs of equal id in sorted order
    bf_ptr.assign(1, 0);
    std::vector<double> gmin(k), gmax(k);
    std::vector<char> used(k);
    for (int s = 0; s < n;) {
        int e = s;
        while (e < n && block_id[perm[e]] == block_id[perm[s]]) ++e;
        blk_start.push_back(s);
        double amax = -INFINITY;
        std::fill(gmin.begin(), gmin.end(), 0.0);   // members without a factor have g = 0
        std::fill(gmax.begin(), gmax.end(), 0.0);
        std::fill(used.begin(), used.end(), 0);
        for (int j = s; j < e; ++j) {
            amax = std::max(amax, a[j]);
            for (int q = nz_ptr[j]; q < nz_ptr[j + 1]; ++q) {
                const int f = nz_f[q];
                used[f] = 1;
                gmin[f] = std::min(gmin[f], nz_g[q]);
                gmax[f] = std::max(gmax[f], nz_g[q]);
            }
        }
        blk_amax.push_back(amax);
        for (int f = 0; f < k; ++f)
            if (used[f]) { bf_f.push_back(f); bf_gmin.push_back(gmin[f]); bf_gmax.push_back(gmax[f]); }
        bf_ptr.push_back(static_cast<int>(bf_f.size()));
        s = e;
    }
    blk_start.push_back(n);
}

// --------------------------------------------------------- scenario ---------
namespace {

inline double norm_cdf(double x) { return 0.5 * std::erfc(-x * M_SQRT1_2); }

template <class OnDefault>
double run_scenario(const CreditKernel& m, Rng& rng, double* z, double* f,
                    std::int64_t* n_cand, OnDefault&& on_default) {
    const int k = m.k;
    for (int j = 0; j < k; ++j) z[j] = rng.normal();
    for (int i = 0; i < k; ++i) {
        double s = 0.0;
        for (int j = 0; j <= i; ++j) s += m.chol[static_cast<std::size_t>(i) * k + j] * z[j];
        f[i] = s;
    }
    // t-copula: default <=> eps < (q / s - sys) / sd with s = sqrt(nu / W)
    const double inv_s = m.nu > 0.0 ? std::sqrt(2.0 * rng.gamma(0.5 * m.nu) / m.nu) : 1.0;
    double loss = 0.0;
    const int nb = m.n_blocks();
    for (int b = 0; b < nb; ++b) {
        double dmax = m.blk_amax[b] * inv_s;
        for (int q = m.bf_ptr[b]; q < m.bf_ptr[b + 1]; ++q) {
            const double x = f[m.bf_f[q]];
            dmax += std::max(-m.bf_gmin[q] * x, -m.bf_gmax[q] * x);
        }
        const double pmax = norm_cdf(dmax);
        if (!(pmax > 0.0)) continue;
        const double log_q = std::log1p(-pmax);       // -inf when pmax == 1
        const int end = m.blk_start[b + 1];
        int i = m.blk_start[b] - 1;
        for (;;) {
            const double skip = std::log(rng.uniform()) / log_q;   // geometric(pmax) - 1
            if (!(skip < static_cast<double>(end - i - 1))) break;
            i += 1 + static_cast<int>(skip);
            if (n_cand) ++*n_cand;
            double d = m.a[i] * inv_s;
            for (int q = m.nz_ptr[i]; q < m.nz_ptr[i + 1]; ++q) d -= m.nz_g[q] * f[m.nz_f[q]];
            if (rng.uniform() * pmax <= norm_cdf(d)) {
                loss += m.c[i];
                on_default(i);
            }
        }
    }
    return loss;
}

}  // namespace

void CreditKernel::simulate(std::int64_t n_scen, std::uint64_t seed, int threads,
                            std::int64_t chunk, double* losses_out) const {
    const std::int64_t n_chunks = (n_scen + chunk - 1) / chunk;
    parallel_tasks(n_chunks, threads, [&](std::int64_t ch, int) {
        Rng rng = task_rng(seed, ch);
        std::vector<double> z(k), f(k);
        const std::int64_t lo = ch * chunk, hi = std::min(n_scen, lo + chunk);
        for (std::int64_t s = lo; s < hi; ++s)
            losses_out[s] = run_scenario(*this, rng, z.data(), f.data(), nullptr, [](int) {});
    });
}

std::int64_t CreditKernel::conditional_sums(std::int64_t n_scen, std::uint64_t seed, int threads,
                                            std::int64_t chunk, double lo_l, double hi_l,
                                            double* sums_out) const {
    const std::int64_t n_chunks = (n_scen + chunk - 1) / chunk;
    threads = std::max(1, std::min<int>(threads, static_cast<int>(n_chunks)));
    std::vector<std::vector<double>> part(threads, std::vector<double>(n, 0.0));
    std::vector<std::int64_t> count(threads, 0);
    parallel_tasks(n_chunks, threads, [&](std::int64_t ch, int tid) {
        Rng rng = task_rng(seed, ch);
        std::vector<double> z(k), f(k);
        std::vector<int> defaults;
        const std::int64_t lo = ch * chunk, hi = std::min(n_scen, lo + chunk);
        for (std::int64_t s = lo; s < hi; ++s) {
            defaults.clear();
            const double loss = run_scenario(*this, rng, z.data(), f.data(), nullptr,
                                             [&](int i) { defaults.push_back(i); });
            if (loss >= lo_l && loss <= hi_l) {
                ++count[tid];
                for (int i : defaults) part[tid][perm[i]] += c[i];
            }
        }
    });
    std::fill(sums_out, sums_out + n, 0.0);
    std::int64_t total = 0;
    for (int t = 0; t < threads; ++t) {
        total += count[t];
        for (int i = 0; i < n; ++i) sums_out[i] += part[t][i];
    }
    return total;
}

double CreditKernel::candidates_per_scenario(std::int64_t n_scen, std::uint64_t seed) const {
    Rng rng = task_rng(seed, 0);
    std::vector<double> z(k), f(k);
    std::int64_t cand = 0;
    for (std::int64_t s = 0; s < n_scen; ++s)
        run_scenario(*this, rng, z.data(), f.data(), &cand, [](int) {});
    return static_cast<double>(cand) / static_cast<double>(n_scen);
}

}  // namespace mcrisk
