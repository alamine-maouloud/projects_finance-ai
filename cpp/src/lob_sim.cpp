#include "lob_sim.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

#include "order_book.hpp"
#include "util.hpp"

namespace mcrisk::lob {
namespace {

class FlowSim {
  public:
    FlowSim(const FlowParams& p, Rng& rng) : p_(p), k_(static_cast<int>(p.lam.size())),
                                             book_(p.n_ticks), rng_(rng) {
        if (k_ == 0 || p.theta.size() != p.lam.size())
            throw std::invalid_argument("lam and theta must have the same, non-zero length");
        if (p.p0 < k_ + 2 || p.p0 > p.n_ticks - k_ - 2) throw std::invalid_argument("p0 too close to the grid edge");
        for (int i = 0; i < k_; ++i)
            if (!(p.lam[i] >= 0.0) || !(p.theta[i] > 0.0)) throw std::invalid_argument("rates must be positive");
        const double n = (p.alpha_self + p.alpha_cross) / p.beta;
        if (!(n < 1.0)) throw std::invalid_argument("Hawkes branching ratio must be < 1");
        mu0_ = p.mu * (1.0 - n);
        lam_cum_.resize(k_);
        double acc = 0.0;
        for (int i = 0; i < k_; ++i) lam_cum_[i] = (acc += p.lam[i]);
        lam_tot_ = acc;
        qb_.resize(k_);
        qa_.resize(k_);
        // stationary-like initial book: Poisson(lam / theta) unit orders per level
        last_ask_ = p.p0;
        last_bid_ = p.p0 - 1;
        for (int i = 1; i <= k_; ++i) {
            const double m = p.lam[i - 1] / p.theta[i - 1];
            const int nb = std::max(i == 1 ? 1 : 0, rng_.poisson(m));
            const int na = std::max(i == 1 ? 1 : 0, rng_.poisson(m));
            for (int j = 0; j < nb; ++j) book_.limit(BID, p.p0 - i, 1);
            for (int j = 0; j < na; ++j) book_.limit(ASK, p.p0 - 1 + i, 1);
        }
    }

    SimResult run(double horizon, double grid_dt, double depth_dt,
                  const std::vector<AgentOrder>& agent, bool record_mo,
                  const std::vector<double>& marks, std::vector<double>* mark_mid) {
        SimResult r;
        r.n_limit.assign(k_, 0);
        r.n_cancel.assign(k_, 0);
        r.queue_time.assign(k_, 0.0);
        grid_dt_ = grid_dt;
        depth_dt_ = depth_dt;
        next_grid_ = grid_dt > 0 ? grid_dt : INFINITY;
        next_depth_ = depth_dt > 0 ? depth_dt : INFINITY;
        std::size_t ai = 0, mi = 0;
        for (;;) {
            if (near_edge()) { r.hit_edge = true; break; }
            const int ra = ref_ask(), rb = ref_bid();
            std::int64_t in_b = 0, in_a = 0;
            double cb = 0.0, ca = 0.0;
            for (int i = 1; i <= k_; ++i) {
                qb_[i - 1] = static_cast<std::int64_t>(book_.count(BID, ra - i));
                qa_[i - 1] = static_cast<std::int64_t>(book_.count(ASK, rb + i));
                in_b += qb_[i - 1];
                in_a += qa_[i - 1];
                cb += p_.theta[i - 1] * qb_[i - 1];
                ca += p_.theta[i - 1] * qa_[i - 1];
            }
            const std::int64_t deep_b = static_cast<std::int64_t>(book_.total_orders(BID)) - in_b;
            const std::int64_t deep_a = static_cast<std::int64_t>(book_.total_orders(ASK)) - in_a;
            cb += p_.theta[k_ - 1] * deep_b;
            ca += p_.theta[k_ - 1] * deep_a;
            const double hb = mu0_ + eb_, hs = mu0_ + es_;
            const double rate = 2.0 * lam_tot_ + cb + ca + hb + hs;
            const double t_new = t_ + rng_.exponential(rate);

            if (ai < agent.size() && agent[ai].t <= std::min(t_new, horizon)) {
                advance(agent[ai].t, r, deep_b + deep_a, marks, mi, mark_mid, horizon);
                const AgentOrder& a = agent[ai++];
                r.ag_t.push_back(a.t);
                r.ag_mid_before.push_back(mid());
                const std::int64_t f = book_.market(a.side, a.qty, 1);
                double notional = 0.0;
                for (const Fill& x : book_.fills()) notional += static_cast<double>(x.price) * x.qty;
                book_.fills().clear();
                r.ag_filled.push_back(f);
                r.ag_notional.push_back(notional);
                continue;
            }
            if (t_new > horizon) {
                advance(horizon, r, deep_b + deep_a, marks, mi, mark_mid, horizon);
                break;
            }
            advance(t_new, r, deep_b + deep_a, marks, mi, mark_mid, horizon);
            double u = rng_.uniform() * rate;
            ++r.n_events;
            if (u <= 2.0 * lam_tot_) {                        // limit order
                const int side = u <= lam_tot_ ? BID : ASK;
                const double v = side == BID ? u : u - lam_tot_;
                const int i = static_cast<int>(std::lower_bound(lam_cum_.begin(), lam_cum_.end(), v) - lam_cum_.begin()) + 1;
                const int d = std::min(i, k_);
                const int price = side == BID ? ra - d : rb + d;
                book_.limit(side, price, 1);
                ++r.n_limit[d - 1];
                continue;
            }
            u -= 2.0 * lam_tot_;
            if (u <= cb) { cancel(BID, ra, u, deep_b, r); continue; }
            u -= cb;
            if (u <= ca) { cancel(ASK, rb, u, deep_a, r); continue; }
            u -= ca;
            // market orders by thinning: the band was reserved at the old
            // intensity, accept with the intensity at the event time
            int side = -1;
            if (u <= hb) { if (u <= mu0_ + eb_) side = BID; }
            else if (u - hb <= mu0_ + es_) side = ASK;
            if (side < 0) { --r.n_events; continue; }
            const double m_before = mid();
            book_.market(side, 1, 0);
            book_.fills().clear();
            ++r.n_market;
            if (side == BID) { eb_ += p_.alpha_self; es_ += p_.alpha_cross; }
            else { es_ += p_.alpha_self; eb_ += p_.alpha_cross; }
            if (record_mo) {
                r.mo_t.push_back(t_);
                r.mo_side.push_back(side);
                r.mo_mid_before.push_back(m_before);
                r.mo_mid_after.push_back(mid());
            }
        }
        r.t_end = t_;
        return r;
    }

  private:
    const FlowParams& p_;
    int k_;
    OrderBook book_;
    Rng& rng_;
    double t_ = 0.0, mu0_ = 0.0, eb_ = 0.0, es_ = 0.0, lam_tot_ = 0.0;
    std::vector<double> lam_cum_;
    std::vector<std::int64_t> qb_, qa_;
    int last_bid_, last_ask_;
    double next_grid_ = INFINITY, next_depth_ = INFINITY;
    double grid_dt_ = 0.0, depth_dt_ = 0.0;

    int ref_ask() {
        if (book_.best_ask() < book_.n_ticks()) return last_ask_ = book_.best_ask();
        if (book_.best_bid() >= 0) return book_.best_bid() + 1;
        return last_ask_;
    }
    int ref_bid() {
        if (book_.best_bid() >= 0) return last_bid_ = book_.best_bid();
        if (book_.best_ask() < book_.n_ticks()) return book_.best_ask() - 1;
        return last_bid_;
    }
    double mid() { return 0.5 * (ref_bid() + ref_ask()); }
    bool near_edge() {
        return ref_bid() < 2 * k_ + 2 || ref_ask() > book_.n_ticks() - 2 * k_ - 2;
    }

    // Moves the clock to t_to with the state frozen: integrates queue sizes,
    // samples the grids and decays the Hawkes excitation.
    void advance(double t_to, SimResult& r, std::int64_t deep, const std::vector<double>& marks,
                 std::size_t& mi, std::vector<double>* mark_mid, double horizon) {
        const double dt = t_to - t_;
        for (int i = 0; i < k_; ++i) r.queue_time[i] += static_cast<double>(qb_[i] + qa_[i]) * dt;
        r.queue_time[k_ - 1] += static_cast<double>(deep) * dt;
        while (next_grid_ <= t_to && next_grid_ <= horizon) {
            r.bid.push_back(ref_bid());
            r.ask.push_back(ref_ask());
            next_grid_ += grid_dt_;
        }
        while (next_depth_ <= t_to && next_depth_ <= horizon) {
            const int bb = ref_bid(), ba = ref_ask();
            for (int j = 0; j < k_; ++j) {
                r.depth_bid.push_back(book_.volume(BID, bb - j));
                r.depth_ask.push_back(book_.volume(ASK, ba + j));
            }
            next_depth_ += depth_dt_;
        }
        while (mark_mid && mi < marks.size() && marks[mi] <= t_to) {
            mark_mid->push_back(mid());
            ++mi;
        }
        const double f = std::exp(-p_.beta * dt);
        eb_ *= f;
        es_ *= f;
        t_ = t_to;
    }

    void cancel(int side, int ref, double u, std::int64_t deep, SimResult& r) {
        const int sgn = side == BID ? -1 : 1;
        for (int i = 1; i <= k_; ++i) {
            const std::int64_t q = side == BID ? qb_[i - 1] : qa_[i - 1];
            const double w = p_.theta[i - 1] * q;
            if (q > 0 && u <= w) {
                const auto k = static_cast<std::size_t>(std::min<std::int64_t>(
                    static_cast<std::int64_t>(std::ceil(u / p_.theta[i - 1])) - 1, q - 1));
                book_.cancel_at(side, ref + sgn * i, k);
                ++r.n_cancel[i - 1];
                return;
            }
            u -= w;
        }
        if (deep <= 0) return;
        std::int64_t k = std::min<std::int64_t>(
            std::max<std::int64_t>(static_cast<std::int64_t>(std::ceil(u / p_.theta[k_ - 1])) - 1, 0), deep - 1);
        for (int price = ref + sgn * (k_ + 1); price >= 0 && price < book_.n_ticks(); price += sgn) {
            const auto c = static_cast<std::int64_t>(book_.count(side, price));
            if (k < c) {
                book_.cancel_at(side, price, static_cast<std::size_t>(k));
                ++r.n_cancel[k_ - 1];
                return;
            }
            k -= c;
        }
    }
};

}  // namespace

SimResult simulate_flow(const FlowParams& prm, double horizon, std::uint64_t seed,
                        double grid_dt, double depth_dt, const std::vector<AgentOrder>& agent,
                        bool record_mo) {
    Rng rng = task_rng(seed, 0);
    FlowSim sim(prm, rng);
    std::vector<AgentOrder> sorted = agent;
    std::stable_sort(sorted.begin(), sorted.end(), [](const AgentOrder& a, const AgentOrder& b) { return a.t < b.t; });
    return sim.run(horizon, grid_dt, depth_dt, sorted, record_mo, {}, nullptr);
}

void simulate_agent_paths(const FlowParams& prm, double horizon, double warmup,
                          const std::vector<AgentOrder>& agent, std::int64_t n_paths,
                          std::uint64_t seed, int threads, std::int64_t* filled,
                          double* notional, double* mid_before, double* mid0, double* mid_end) {
    std::vector<AgentOrder> shifted = agent;
    for (auto& a : shifted) a.t += warmup;
    std::stable_sort(shifted.begin(), shifted.end(), [](const AgentOrder& a, const AgentOrder& b) { return a.t < b.t; });
    const std::size_t m = shifted.size();
    const std::vector<double> marks = {warmup, warmup + horizon};
    parallel_tasks(n_paths, threads, [&](std::int64_t path, int) {
        Rng rng = task_rng(seed, path);
        FlowSim sim(prm, rng);
        std::vector<double> mm;
        SimResult r = sim.run(warmup + horizon, 0.0, 0.0, shifted, false, marks, &mm);
        for (std::size_t j = 0; j < m; ++j) {
            const bool ok = j < r.ag_filled.size();
            filled[path * m + j] = ok ? r.ag_filled[j] : 0;
            notional[path * m + j] = ok ? r.ag_notional[j] : 0.0;
            mid_before[path * m + j] = ok ? r.ag_mid_before[j] : NAN;
        }
        mid0[path] = mm.size() > 0 ? mm[0] : NAN;
        mid_end[path] = mm.size() > 1 ? mm[1] : NAN;
    });
}

}  // namespace mcrisk::lob
