// pybind11 bindings: native kernels (credit portfolio, order book, order flow) as mcrisk._native

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include <pybind11/stl.h>

#include "credit_kernel.hpp"
#include "lob_sim.hpp"
#include "order_book.hpp"

namespace py = pybind11;
using mcrisk::CreditKernel;
namespace lob = mcrisk::lob;

template <class T>
py::array_t<T> to_numpy(const std::vector<T>& v) {
    py::array_t<T> a(static_cast<py::ssize_t>(v.size()));
    std::copy(v.begin(), v.end(), a.mutable_data());
    return a;
}

static lob::FlowParams flow_params(const std::vector<double>& lam, const std::vector<double>& theta,
                                   double mu, double alpha_self, double alpha_cross, double beta,
                                   int n_ticks, int p0) {
    lob::FlowParams p;
    p.lam = lam; p.theta = theta; p.mu = mu;
    p.alpha_self = alpha_self; p.alpha_cross = alpha_cross; p.beta = beta;
    p.n_ticks = n_ticks; p.p0 = p0;
    return p;
}

static std::vector<lob::AgentOrder> agent_orders(const std::vector<double>& t, const std::vector<int>& side,
                                                 const std::vector<std::int64_t>& qty) {
    if (t.size() != side.size() || t.size() != qty.size())
        throw std::invalid_argument("agent schedule arrays must have equal length");
    std::vector<lob::AgentOrder> out;
    for (std::size_t i = 0; i < t.size(); ++i) out.push_back({t[i], side[i], qty[i]});
    return out;
}

template <class T>
using carray = py::array_t<T, py::array::c_style | py::array::forcecast>;

PYBIND11_MODULE(_native, m) {
    m.doc() = "Native Monte Carlo kernels for mcrisk";

    py::class_<CreditKernel>(m, "CreditKernel")
        .def(py::init([](carray<double> loadings, carray<double> chol, carray<double> threshold,
                         carray<double> idio, carray<double> lgd_amount,
                         carray<std::int64_t> blocks, double nu) {
                 if (loadings.ndim() != 2) throw std::invalid_argument("loadings must be (n, k)");
                 const int n = static_cast<int>(loadings.shape(0));
                 const int k = static_cast<int>(loadings.shape(1));
                 if (chol.size() != static_cast<py::ssize_t>(k) * k || threshold.size() != n ||
                     idio.size() != n || lgd_amount.size() != n || blocks.size() != n)
                     throw std::invalid_argument("inconsistent array shapes");
                 return new CreditKernel(n, k, loadings.data(), chol.data(), threshold.data(),
                                         idio.data(), lgd_amount.data(), blocks.data(), nu);
             }),
             py::arg("loadings"), py::arg("chol"), py::arg("threshold"), py::arg("idio"),
             py::arg("lgd_amount"), py::arg("blocks"), py::arg("nu") = 0.0)
        .def_property_readonly("n_blocks", &CreditKernel::n_blocks)
        .def("simulate",
             [](const CreditKernel& self, std::int64_t n_scen, std::uint64_t seed, int threads,
                std::int64_t chunk) {
                 py::array_t<double> out(n_scen);
                 double* ptr = out.mutable_data();
                 {
                     py::gil_scoped_release release;
                     self.simulate(n_scen, seed, threads, chunk, ptr);
                 }
                 return out;
             },
             py::arg("n_scenarios"), py::arg("seed"), py::arg("threads") = 1,
             py::arg("chunk") = 4096)
        .def("conditional_sums",
             [](const CreditKernel& self, std::int64_t n_scen, std::uint64_t seed, int threads,
                std::int64_t chunk, double lo, double hi) {
                 py::array_t<double> out(self.n);
                 double* ptr = out.mutable_data();
                 std::int64_t count;
                 {
                     py::gil_scoped_release release;
                     count = self.conditional_sums(n_scen, seed, threads, chunk, lo, hi, ptr);
                 }
                 return py::make_tuple(out, count);
             },
             py::arg("n_scenarios"), py::arg("seed"), py::arg("threads"), py::arg("chunk"),
             py::arg("lo"), py::arg("hi"))
        .def("candidates_per_scenario", &CreditKernel::candidates_per_scenario,
             py::arg("n_scenarios"), py::arg("seed") = 0);

    // ----------------------------------------------------------- order book
    m.attr("BID") = lob::BID;
    m.attr("ASK") = lob::ASK;
    py::class_<lob::OrderBook>(m, "OrderBook")
        .def(py::init<int>(), py::arg("n_ticks"))
        .def_property_readonly("n_ticks", &lob::OrderBook::n_ticks)
        .def("limit", &lob::OrderBook::limit, py::arg("side"), py::arg("price"), py::arg("qty"),
             py::arg("owner") = 0)
        .def("market", &lob::OrderBook::market, py::arg("side"), py::arg("qty"), py::arg("owner") = 0)
        .def("cancel", &lob::OrderBook::cancel, py::arg("order_id"))
        .def("cancel_at", &lob::OrderBook::cancel_at, py::arg("side"), py::arg("price"), py::arg("k"))
        .def_property_readonly("best_bid", &lob::OrderBook::best_bid)
        .def_property_readonly("best_ask", &lob::OrderBook::best_ask)
        .def("volume", &lob::OrderBook::volume, py::arg("side"), py::arg("price"))
        .def("count", &lob::OrderBook::count, py::arg("side"), py::arg("price"))
        .def("total_volume", &lob::OrderBook::total_volume, py::arg("side"))
        .def("total_orders", &lob::OrderBook::total_orders, py::arg("side"))
        .def("is_live", &lob::OrderBook::is_live, py::arg("order_id"))
        .def("check_invariants", &lob::OrderBook::check_invariants)
        .def("take_fills", [](lob::OrderBook& b) {
            // (maker_id, taker_id, price, qty, taker_side, maker_owner, taker_owner)
            py::list out;
            for (const auto& f : b.fills())
                out.append(py::make_tuple(f.maker_id, f.taker_id, f.price, f.qty, f.taker_side,
                                          f.maker_owner, f.taker_owner));
            b.fills().clear();
            return out;
        });

    // ----------------------------------------------------------- simulation
    m.def("simulate_flow",
          [](std::vector<double> lam, std::vector<double> theta, double mu, double alpha_self,
             double alpha_cross, double beta, double horizon, std::uint64_t seed, double grid_dt,
             double depth_dt, std::vector<double> agent_t, std::vector<int> agent_side,
             std::vector<std::int64_t> agent_qty, bool record_mo, int n_ticks, int p0) {
              const auto prm = flow_params(lam, theta, mu, alpha_self, alpha_cross, beta, n_ticks, p0);
              const auto ag = agent_orders(agent_t, agent_side, agent_qty);
              lob::SimResult r;
              {
                  py::gil_scoped_release release;
                  r = lob::simulate_flow(prm, horizon, seed, grid_dt, depth_dt, ag, record_mo);
              }
              py::dict d;
              d["bid"] = to_numpy(r.bid); d["ask"] = to_numpy(r.ask);
              d["depth_bid"] = to_numpy(r.depth_bid); d["depth_ask"] = to_numpy(r.depth_ask);
              d["mo_t"] = to_numpy(r.mo_t); d["mo_side"] = to_numpy(r.mo_side);
              d["mo_mid_before"] = to_numpy(r.mo_mid_before); d["mo_mid_after"] = to_numpy(r.mo_mid_after);
              d["ag_t"] = to_numpy(r.ag_t); d["ag_mid_before"] = to_numpy(r.ag_mid_before);
              d["ag_filled"] = to_numpy(r.ag_filled); d["ag_notional"] = to_numpy(r.ag_notional);
              d["n_limit"] = to_numpy(r.n_limit); d["n_cancel"] = to_numpy(r.n_cancel);
              d["queue_time"] = to_numpy(r.queue_time);
              d["n_market"] = r.n_market; d["n_events"] = r.n_events;
              d["t_end"] = r.t_end; d["hit_edge"] = r.hit_edge;
              return d;
          },
          py::arg("lam"), py::arg("theta"), py::arg("mu"), py::arg("alpha_self"), py::arg("alpha_cross"),
          py::arg("beta"), py::arg("horizon"), py::arg("seed"), py::arg("grid_dt"), py::arg("depth_dt"),
          py::arg("agent_t"), py::arg("agent_side"), py::arg("agent_qty"), py::arg("record_mo"),
          py::arg("n_ticks"), py::arg("p0"));

    m.def("simulate_agent_paths",
          [](std::vector<double> lam, std::vector<double> theta, double mu, double alpha_self,
             double alpha_cross, double beta, double horizon, double warmup,
             std::vector<double> agent_t, std::vector<int> agent_side, std::vector<std::int64_t> agent_qty,
             std::int64_t n_paths, std::uint64_t seed, int threads, int n_ticks, int p0) {
              const auto prm = flow_params(lam, theta, mu, alpha_self, alpha_cross, beta, n_ticks, p0);
              const auto ag = agent_orders(agent_t, agent_side, agent_qty);
              const auto m_ = static_cast<py::ssize_t>(ag.size());
              py::array_t<std::int64_t> filled({static_cast<py::ssize_t>(n_paths), m_});
              py::array_t<double> notional({static_cast<py::ssize_t>(n_paths), m_});
              py::array_t<double> mid_before({static_cast<py::ssize_t>(n_paths), m_});
              py::array_t<double> mid0(n_paths), mid_end(n_paths);
              auto* pf = filled.mutable_data(); auto* pn = notional.mutable_data();
              auto* pb = mid_before.mutable_data(); auto* p0_ = mid0.mutable_data(); auto* pe = mid_end.mutable_data();
              {
                  py::gil_scoped_release release;
                  lob::simulate_agent_paths(prm, horizon, warmup, ag, n_paths, seed, threads,
                                            pf, pn, pb, p0_, pe);
              }
              py::dict d;
              d["filled"] = filled; d["notional"] = notional; d["mid_before"] = mid_before;
              d["mid0"] = mid0; d["mid_end"] = mid_end;
              return d;
          },
          py::arg("lam"), py::arg("theta"), py::arg("mu"), py::arg("alpha_self"), py::arg("alpha_cross"),
          py::arg("beta"), py::arg("horizon"), py::arg("warmup"), py::arg("agent_t"),
          py::arg("agent_side"), py::arg("agent_qty"), py::arg("n_paths"), py::arg("seed"),
          py::arg("threads"), py::arg("n_ticks"), py::arg("p0"));
}
