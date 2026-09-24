// pybind11 bindings: exposes the native credit kernel as mcrisk._native

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include "credit_kernel.hpp"

namespace py = pybind11;
using mcrisk::CreditKernel;

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
}
