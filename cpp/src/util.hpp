#pragma once
// Shared utilities for the native kernels: random streams and a chunked
// thread pool whose results do not depend on the number of threads.

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <thread>
#include <vector>

namespace mcrisk {

inline std::uint64_t splitmix64(std::uint64_t& x) {
    std::uint64_t z = (x += 0x9e3779b97f4a7c15ULL);
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    return z ^ (z >> 31);
}

// xoshiro256** (Blackman & Vigna): one independent stream per task
class Rng {
  public:
    explicit Rng(std::uint64_t seed) {
        for (auto& v : s_) v = splitmix64(seed);
    }
    std::uint64_t next() {
        const std::uint64_t r = rotl(s_[1] * 5, 7) * 9;
        const std::uint64_t t = s_[1] << 17;
        s_[2] ^= s_[0]; s_[3] ^= s_[1]; s_[1] ^= s_[2]; s_[0] ^= s_[3];
        s_[2] ^= t;
        s_[3] = rotl(s_[3], 45);
        return r;
    }
    // uniform on (0, 1]
    double uniform() { return static_cast<double>((next() >> 11) + 1) * 0x1.0p-53; }
    double exponential(double rate) { return -std::log(uniform()) / rate; }
    // Marsaglia polar method
    double normal() {
        if (has_spare_) { has_spare_ = false; return spare_; }
        double u, v, q;
        do {
            u = 2.0 * uniform() - 1.0;
            v = 2.0 * uniform() - 1.0;
            q = u * u + v * v;
        } while (q >= 1.0 || q == 0.0);
        const double m = std::sqrt(-2.0 * std::log(q) / q);
        spare_ = v * m;
        has_spare_ = true;
        return u * m;
    }
    // Gamma(shape, 1), Marsaglia & Tsang (2000)
    double gamma(double shape) {
        if (shape < 1.0) return gamma(shape + 1.0) * std::pow(uniform(), 1.0 / shape);
        const double d = shape - 1.0 / 3.0, c = 1.0 / std::sqrt(9.0 * d);
        for (;;) {
            double x, v;
            do { x = normal(); v = 1.0 + c * x; } while (v <= 0.0);
            v = v * v * v;
            const double u = uniform();
            if (std::log(u) < 0.5 * x * x + d - d * v + d * std::log(v)) return d * v;
        }
    }
    // Poisson by inversion (small means, used to seed order books)
    int poisson(double mean) {
        const double l = std::exp(-mean);
        int k = 0;
        double p = uniform();
        while (p > l) { ++k; p *= uniform(); }
        return k;
    }
    // integer uniform on [0, n)
    std::uint64_t below(std::uint64_t n) { return static_cast<std::uint64_t>(uniform() * n) % n; }

  private:
    static std::uint64_t rotl(std::uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }
    std::uint64_t s_[4];
    double spare_ = 0.0;
    bool has_spare_ = false;
};

inline Rng task_rng(std::uint64_t seed, std::int64_t task) {
    return Rng(seed ^ (0xD1B54A32D192ED03ULL * static_cast<std::uint64_t>(task + 1)));
}

template <class Fn>
void parallel_tasks(std::int64_t n_tasks, int threads, Fn&& fn) {
    threads = std::max(1, std::min<int>(threads, static_cast<int>(std::max<std::int64_t>(n_tasks, 1))));
    std::atomic<std::int64_t> next{0};
    auto worker = [&](int tid) {
        for (std::int64_t c; (c = next.fetch_add(1)) < n_tasks;) fn(c, tid);
    };
    std::vector<std::thread> pool;
    for (int t = 1; t < threads; ++t) pool.emplace_back(worker, t);
    worker(0);
    for (auto& th : pool) th.join();
}

}  // namespace mcrisk
