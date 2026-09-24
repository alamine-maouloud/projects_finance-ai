#!/usr/bin/env python3
"""
Two-qubit CZ gate:
OCT vs residual RL (SAC, TD3, DDPG, PPO) trained sequentially in a contextual
cosine-basis environment. Saves data as .dat and produces paper-ready figures.
To run Only OCT : python agentRL_2qubits.py --no-rl
To run OCT + RL : python agentRL_2qubits.py
"""

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt

import gymnasium as gym
from gymnasium import spaces

from qutip import Qobj, qeye, destroy, tensor

# RL algorithms (Stable-Baselines3)
from stable_baselines3 import SAC, TD3, DDPG, PPO
from stable_baselines3.common.noise import NormalActionNoise
from stable_baselines3.common.callbacks import BaseCallback

# -----------------------------------------------------------------------------
# Matplotlib style (LaTeX-like, but without external LaTeX)
# -----------------------------------------------------------------------------
mpl.rcParams.update({
    "text.usetex": False,
    "font.family": "serif",
    "mathtext.fontset": "cm",
    "axes.labelsize": 16,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "legend.fontsize": 14,
    "figure.dpi": 120,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# -----------------------------------------------------------------------------
# Target gate and utilities
# -----------------------------------------------------------------------------

def cz_gate():
    """
    Standard 2-qubit CZ gate:
    diag(1, 1, 1, -1)
    Acts on the |11> state with a phase flip.
    """
    phases = np.array([1, 1, 1, -1], dtype=complex)
    return Qobj(np.diag(phases), dims=[[2, 2], [2, 2]])


def average_gate_fidelity(U, U_target):
    """
    Average gate fidelity:
    F_avg(U, U_t) = (|Tr(U_t^dagger U)|^2 + d) / [ d (d+1) ].
    """
    d = U.shape[0]
    M = U_target.dag() * U
    trM = M.tr()
    F = (abs(trM) ** 2 + d) / (d * (d + 1))
    return float(np.real(F))


# -----------------------------------------------------------------------------
# System construction
# -----------------------------------------------------------------------------

def build_two_qubit_system(
    n_segments=160,
    dt=10.0,
    max_amp=0.3,
    w1=1.0,
    w2=0.9,
    g=0.0025,
):
    """
    2-qubit Hamiltonian (transmon-like, 2-level truncation):

    H = sum_i [ omega_i * a_i^dag a_i ]
        + g (a1 + a1^dag)(a2 + a2^dag)
        + eps_i(t) * (a_i + a_i^dag)

    Note: anharmonicity chi terms vanish identically for 2-level systems
    since a^dag a^dag a a |n> = n(n-1)|n> = 0 for n in {0,1}.
    """
    n_levels = 2
    dim = n_levels ** 2  # = 4

    a = destroy(n_levels)
    I = qeye(n_levels)
    a1 = tensor(a, I)
    a2 = tensor(I, a)

    n1 = a1.dag() * a1
    n2 = a2.dag() * a2

    H0 = (
        w1 * n1
        + w2 * n2
        + g * (a1 + a1.dag()) * (a2 + a2.dag())
    )  # dims [[2,2],[2,2]]

    Hc1 = (a1 + a1.dag())
    Hc2 = (a2 + a2.dag())

    # For OCT (dimension as a single 4x4 Hilbert space)
    Hd_oct = Qobj(H0.full(), dims=[[dim], [dim]])
    Hc1_oct = Qobj(Hc1.full(), dims=[[dim], [dim]])
    Hc2_oct = Qobj(Hc2.full(), dims=[[dim], [dim]])

    U0_oct = Qobj(qeye(dim).full(), dims=[[dim], [dim]])
    U_targ_oct = Qobj(cz_gate().full(), dims=[[dim], [dim]])

    evo_time = n_segments * dt

    return {
        "H0": H0,
        "Hc1": Hc1,
        "Hc2": Hc2,
        "Hd_oct": Hd_oct,
        "Hc1_oct": Hc1_oct,
        "Hc2_oct": Hc2_oct,
        "U0_oct": U0_oct,
        "U_targ_oct": U_targ_oct,
        "n_segments": n_segments,
        "dt": dt,
        "evo_time": evo_time,
        "max_amp": max_amp,
        "a1": a1,
        "a2": a2,
        "w1_nom": w1,
        "w2_nom": w2,
        "g_nom": g,
    }


def make_H0_tensored(a1, a2, w1, w2, g):
    n1 = a1.dag() * a1
    n2 = a2.dag() * a2
    H0 = (
        w1 * n1
        + w2 * n2
        + g * (a1 + a1.dag()) * (a2 + a2.dag())
    )
    return H0


def propagate_with_pulse(H0, Hc1, Hc2, eps1, eps2, dt):
    """
    Propagate using static H0 and piecewise-constant eps1, eps2.
    H0, Hc1, Hc2 are Qobj with dims [[2,2],[2,2]].
    """
    U = tensor(qeye(2), qeye(2))
    for j in range(len(eps1)):
        H = H0 + eps1[j] * Hc1 + eps2[j] * Hc2
        U_step = (-1j * H * dt).expm()
        U = U_step * U
    return U


# -----------------------------------------------------------------------------
# OCT / GRAPE
# -----------------------------------------------------------------------------

try:
    import qutip_qtrl.pulseoptim as cpo
    print("Using qutip_qtrl.pulseoptim")
except ImportError:
    from qutip.control import pulseoptim as cpo
    print("Using qutip.control.pulseoptim (fallback)")


def run_oct_grape_two_qubit_cz(
    sys,
    n_segments=160,
    dt=10.0,
    max_amp=0.3,
    g=0.0025,
    n_iters=4000,
    fid_err_targ=1e-10,
):
    """
    Run OCT/GRAPE on the nominal Hamiltonian (no noise).
    Returns eps1, eps2, process fidelity, avg gate fidelity, fidelity history.
    """
    Hd = sys["Hd_oct"]
    Hcs = [sys["Hc1_oct"], sys["Hc2_oct"]]
    U0 = sys["U0_oct"]
    U_targ = sys["U_targ_oct"]
    evo_time = sys["evo_time"]

    print(f"Dim = {Hd.shape[0]}, T = {evo_time}, n_segments = {n_segments}")

    result = cpo.optimize_pulse_unitary(
        H_d=Hd,
        H_c=Hcs,
        U_0=U0,
        U_targ=U_targ,
        num_tslots=n_segments,
        evo_time=evo_time,
        amp_lbound=-max_amp,
        amp_ubound=max_amp,
        fid_err_targ=fid_err_targ,
        max_iter=n_iters,
        init_pulse_type="RND",
        log_level=0,
        gen_stats=True,
    )

    fid_err = result.fid_err
    F_proc = 1.0 - fid_err

    print("\nOCT / GRAPE finished (nominal):")
    print(f"  final fid_err  = {fid_err:.3e}")
    print(f"  final fidelity = {F_proc:.6f}")

    pulses = result.final_amps  # [n_ts, 2]
    eps1 = pulses[:, 0]
    eps2 = pulses[:, 1]

    a1 = sys["a1"]
    a2 = sys["a2"]
    w1_nom = sys["w1_nom"]
    w2_nom = sys["w2_nom"]
    g_nom = sys["g_nom"]

    H0_nom = make_H0_tensored(a1, a2, w1_nom, w2_nom, g_nom)
    Hc1_tens = sys["Hc1"]
    Hc2_tens = sys["Hc2"]

    U = propagate_with_pulse(H0_nom, Hc1_tens, Hc2_tens, eps1, eps2, dt)
    U_targ_tens = cz_gate()
    F_avg_nom = average_gate_fidelity(U, U_targ_tens)
    print(f"  average gate fidelity (our check, nominal) = {F_avg_nom:.6f}")

    fid_hist = None
    if hasattr(result, "stats") and hasattr(result.stats, "fid_err"):
        fid_hist = 1.0 - np.array(result.stats.fid_err)

    return eps1, eps2, F_proc, F_avg_nom, fid_hist


def quick_oct_convergence_run(sys, n_segments, dt, max_amp, g, n_iters_plot=10):
    """
    Run OCT with increasing max_iter values to produce a convergence curve.
    """
    Hd = sys["Hd_oct"]
    Hcs = [sys["Hc1_oct"], sys["Hc2_oct"]]
    U0 = sys["U0_oct"]
    U_targ = sys["U_targ_oct"]
    evo_time = sys["evo_time"]

    iter_points = np.logspace(1, np.log10(4000), n_iters_plot).astype(int)
    iter_points = np.unique(iter_points)

    results = []
    for it in iter_points:
        result = cpo.optimize_pulse_unitary(
            H_d=Hd, H_c=Hcs, U_0=U0, U_targ=U_targ,
            num_tslots=n_segments, evo_time=evo_time,
            amp_lbound=-max_amp, amp_ubound=max_amp,
            fid_err_targ=1e-10, max_iter=it,
            init_pulse_type="RND", log_level=0, gen_stats=False,
        )
        F_proc = 1.0 - result.fid_err
        results.append((it, F_proc))
        print(f"  max_iter = {it:4d} -> F_proc = {F_proc:.6f}")

    iters = np.array([r[0] for r in results])
    fvals = np.array([r[1] for r in results])
    np.savetxt("oct_fid_vs_iter.dat",
               np.column_stack((iters, fvals)),
               header="max_iter F_process", comments="")
    print("Saved oct_fid_vs_iter.dat")

    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    ax.plot(iters, fvals, "-o", lw=2)
    ax.set_xlabel("Iterations")
    ax.set_ylabel("Fidelity")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig("oct_fid_vs_iter.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("Saved oct_fid_vs_iter.png")
    return results


# -----------------------------------------------------------------------------
# Cosine basis for residual pulses
# -----------------------------------------------------------------------------

def build_cosine_basis(n_segments, n_modes):
    """
    Discrete cosine basis (DCT-II like) matrix [n_segments, n_modes].
    """
    j = np.arange(n_segments)[:, None] + 0.5
    k = np.arange(1, n_modes + 1)[None, :]
    mat = np.cos(np.pi * k * j / n_segments)
    mat /= np.sqrt((mat ** 2).sum(axis=0, keepdims=True) + 1e-12)
    return mat


# -----------------------------------------------------------------------------
# Contextual residual RL environment (cosine basis)
# -----------------------------------------------------------------------------

class CZResidualContextualEnv(gym.Env):
    """
    One-step contextual bandit for the 2-qubit CZ gate:

    - Observation: standardized device parameters:
        obs = [dw1 / sigma_w, dw2 / sigma_w, dg / sigma_g]
    - Action: cosine coefficients for residual pulses
        a in R^{2 * n_modes} in [-1, 1]
    - Total pulse: eps_total = eps_OCT + residual(a)
    - Hamiltonian: new noisy device sampled every episode
    - Reward: F(U, U_target) - F_baseline(device)
    """

    metadata = {"render_modes": []}

    def __init__(self,
                 sys_nominal,
                 eps1_base,
                 eps2_base,
                 cos_mat,
                 max_amp=0.3,
                 coeff_scale=0.03,
                 noise_std_w=0.001,
                 noise_std_g=5e-5,
                 seed=None):

        super().__init__()

        self.sys = sys_nominal
        self.eps1_base = np.asarray(eps1_base, dtype=float)
        self.eps2_base = np.asarray(eps2_base, dtype=float)
        self.n_segments = len(eps1_base)

        self.Hc1 = sys_nominal["Hc1"]
        self.Hc2 = sys_nominal["Hc2"]
        self.a1 = sys_nominal["a1"]
        self.a2 = sys_nominal["a2"]

        self.w1_nom = sys_nominal["w1_nom"]
        self.w2_nom = sys_nominal["w2_nom"]
        self.g_nom = sys_nominal["g_nom"]

        self.dt = sys_nominal["dt"]
        self.max_amp = max_amp
        self.coeff_scale = coeff_scale
        self.noise_std_w = noise_std_w
        self.noise_std_g = noise_std_g
        self.cos_mat = cos_mat
        self.n_modes = cos_mat.shape[1]

        self.U_target = cz_gate()

        self.rng = np.random.default_rng(seed)

        self.observation_space = spaces.Box(
            low=-3.0, high=3.0, shape=(3,), dtype=np.float32
        )
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(2 * self.n_modes,), dtype=np.float32
        )

        self.H0_eff = None
        self.F_baseline = None
        self.dw1 = 0.0
        self.dw2 = 0.0
        self.dg = 0.0
        self.obs = None

    def _sample_device(self):
        self.dw1 = float(self.rng.normal(0.0, self.noise_std_w))
        self.dw2 = float(self.rng.normal(0.0, self.noise_std_w))
        self.dg = float(self.rng.normal(0.0, self.noise_std_g))

        w1_eff = self.w1_nom + self.dw1
        w2_eff = self.w2_nom + self.dw2
        g_eff = self.g_nom + self.dg

        self.H0_eff = make_H0_tensored(self.a1, self.a2, w1_eff, w2_eff, g_eff)

        U_baseline = propagate_with_pulse(
            self.H0_eff, self.Hc1, self.Hc2,
            self.eps1_base, self.eps2_base, self.dt
        )
        self.F_baseline = average_gate_fidelity(U_baseline, self.U_target)

        self.obs = np.array([
            self.dw1 / self.noise_std_w,
            self.dw2 / self.noise_std_w,
            self.dg / self.noise_std_g,
        ], dtype=np.float32)

    def expand_action_to_pulses(self, action):
        action = np.asarray(action, dtype=float)
        action = np.clip(action, -1.0, 1.0)
        coeffs = self.coeff_scale * action.reshape(2, self.n_modes)

        res1 = self.cos_mat @ coeffs[0]
        res2 = self.cos_mat @ coeffs[1]

        eps1 = np.clip(self.eps1_base + res1, -self.max_amp, self.max_amp)
        eps2 = np.clip(self.eps2_base + res2, -self.max_amp, self.max_amp)

        return eps1, eps2

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self._sample_device()
        return self.obs.copy(), {}

    def step(self, action):
        eps1, eps2 = self.expand_action_to_pulses(action)
        U = propagate_with_pulse(self.H0_eff, self.Hc1, self.Hc2, eps1, eps2, self.dt)
        F = average_gate_fidelity(U, self.U_target)
        reward = F - self.F_baseline
        info = {
            "fidelity": float(F),
            "dw1": self.dw1, "dw2": self.dw2, "dg": self.dg,
            "eps1": eps1, "eps2": eps2,
            "F_baseline": float(self.F_baseline),
        }
        return self.obs.copy(), float(reward), True, False, info

    def render(self): pass
    def close(self): pass


class CZNominalRLOnlyEnv(gym.Env):
    """
    RL-only environment on the nominal Hamiltonian (no noise, no OCT baseline).
    Reward = absolute fidelity F(U, U_target).
    Purpose: show RL alone cannot match OCT on a known Hamiltonian.
    """

    metadata = {"render_modes": []}

    def __init__(self, sys_nominal, cos_mat, max_amp=0.3, coeff_scale=0.3, seed=None):
        super().__init__()

        self.sys = sys_nominal
        self.cos_mat = cos_mat
        self.n_modes = cos_mat.shape[1]
        self.n_segments = sys_nominal["n_segments"]
        self.dt = sys_nominal["dt"]
        self.max_amp = max_amp
        self.coeff_scale = coeff_scale

        self.a1 = sys_nominal["a1"]
        self.a2 = sys_nominal["a2"]
        self.w1_nom = sys_nominal["w1_nom"]
        self.w2_nom = sys_nominal["w2_nom"]
        self.g_nom = sys_nominal["g_nom"]

        self.H0_nom = make_H0_tensored(
            self.a1, self.a2, self.w1_nom, self.w2_nom, self.g_nom
        )
        self.Hc1 = sys_nominal["Hc1"]
        self.Hc2 = sys_nominal["Hc2"]
        self.U_target = cz_gate()

        self.rng = np.random.default_rng(seed)

        self.observation_space = spaces.Box(low=-3.0, high=3.0, shape=(3,), dtype=np.float32)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(2 * self.n_modes,), dtype=np.float32)
        self.obs = np.zeros(3, dtype=np.float32)

    def expand_action_to_pulses(self, action):
        action = np.asarray(action, dtype=float)
        action = np.clip(action, -1.0, 1.0)
        coeffs = self.coeff_scale * action.reshape(2, self.n_modes)
        eps1 = np.clip(self.cos_mat @ coeffs[0], -self.max_amp, self.max_amp)
        eps2 = np.clip(self.cos_mat @ coeffs[1], -self.max_amp, self.max_amp)
        return eps1, eps2

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.obs[:] = 0.0
        return self.obs.copy(), {}

    def step(self, action):
        eps1, eps2 = self.expand_action_to_pulses(action)
        U = propagate_with_pulse(self.H0_nom, self.Hc1, self.Hc2, eps1, eps2, self.dt)
        F = average_gate_fidelity(U, self.U_target)
        info = {"fidelity": float(F), "eps1": eps1, "eps2": eps2}
        return self.obs.copy(), float(F), True, False, info

    def render(self): pass
    def close(self): pass


# -----------------------------------------------------------------------------
# RL logging callback
# -----------------------------------------------------------------------------

class FidelityLoggingCallback(BaseCallback):
    def __init__(self, verbose=0):
        super().__init__(verbose)
        self.episode_idx = []
        self.episode_fids = []
        self._episode_counter = 0

    def _on_step(self) -> bool:
        for i, done in enumerate(self.locals.get("dones", [])):
            if done:
                F = self.locals.get("infos", [{}])[i].get("fidelity", None)
                if F is not None:
                    self._episode_counter += 1
                    self.episode_idx.append(self._episode_counter)
                    self.episode_fids.append(float(F))
        return True

    def get_arrays(self, ma_window=200):
        ep = np.array(self.episode_idx, dtype=int)
        fids = np.array(self.episode_fids, dtype=float)
        if len(fids) == 0:
            return ep, fids, fids, (ep, fids)
        best = np.maximum.accumulate(fids)
        if len(fids) < ma_window:
            return ep, fids, best, (ep, fids)
        kernel = np.ones(ma_window) / ma_window
        ma = np.convolve(fids, kernel, mode="valid")
        ep_ma = ep[ma_window - 1:]
        return ep, fids, best, (ep_ma, ma)


# -----------------------------------------------------------------------------
# Evaluation helpers
# -----------------------------------------------------------------------------

def evaluate_policy_on_device(model, env_template, dw1, dw2, dg):
    sys = env_template.sys
    H0_eff = make_H0_tensored(
        sys["a1"], sys["a2"],
        sys["w1_nom"] + dw1, sys["w2_nom"] + dw2,
        sys["g_nom"] + dg,
    )
    obs = np.array([
        dw1 / env_template.noise_std_w,
        dw2 / env_template.noise_std_w,
        dg / env_template.noise_std_g,
    ], dtype=np.float32)
    action, _ = model.predict(obs, deterministic=True)
    eps1, eps2 = env_template.expand_action_to_pulses(action)
    U = propagate_with_pulse(H0_eff, sys["Hc1"], sys["Hc2"], eps1, eps2, sys["dt"])
    F = average_gate_fidelity(U, cz_gate())
    return F, eps1, eps2


def evaluate_policy_ensemble(model, env_template, n_samples=100,
                             noise_std_w=0.001, noise_std_g=5e-5):
    rng = np.random.default_rng(1234)
    F_list = [
        evaluate_policy_on_device(
            model, env_template,
            float(rng.normal(0.0, noise_std_w)),
            float(rng.normal(0.0, noise_std_w)),
            float(rng.normal(0.0, noise_std_g)),
        )[0]
        for _ in range(n_samples)
    ]
    F_arr = np.array(F_list)
    return float(F_arr.mean()), float(F_arr.std()), F_arr


def evaluate_oct_on_device(sys, eps1, eps2, dw1, dw2, dg):
    H0_eff = make_H0_tensored(
        sys["a1"], sys["a2"],
        sys["w1_nom"] + dw1, sys["w2_nom"] + dw2,
        sys["g_nom"] + dg,
    )
    U = propagate_with_pulse(H0_eff, sys["Hc1"], sys["Hc2"], eps1, eps2, sys["dt"])
    return average_gate_fidelity(U, cz_gate())


def evaluate_oct_ensemble(sys, eps1, eps2, n_samples=100,
                          noise_std_w=0.001, noise_std_g=5e-5):
    rng = np.random.default_rng(5678)
    F_list = [
        evaluate_oct_on_device(
            sys, eps1, eps2,
            float(rng.normal(0.0, noise_std_w)),
            float(rng.normal(0.0, noise_std_w)),
            float(rng.normal(0.0, noise_std_g)),
        )
        for _ in range(n_samples)
    ]
    F_arr = np.array(F_list)
    return float(F_arr.mean()), float(F_arr.std()), F_arr


# -----------------------------------------------------------------------------
# Plotting helpers
# -----------------------------------------------------------------------------

def plot_learning_curves_nominal_vs_oct(logs_nominal, F_OCT_nominal,
                                        ma_window=200,
                                        fname="learning_curves_nominal_vs_oct.png"):
    colors = dict(SAC="C0", TD3="C2", DDPG="C3", PPO="C1")
    linestyles = dict(SAC="-", TD3="--", DDPG="-.", PPO=":")
    fig, ax = plt.subplots(figsize=(6, 4))
    for algo in ["SAC", "TD3", "DDPG", "PPO"]:
        if algo not in logs_nominal:
            continue
        ep, fids, best, (ep_ma, ma) = logs_nominal[algo]["callback"].get_arrays(ma_window)
        if len(ep) == 0:
            continue
        ax.plot(ep, best, linestyle=linestyles[algo], color=colors[algo],
                linewidth=2, label=f"{algo} best (RL-only)")
        ax.plot(ep_ma, ma, linestyle=":", color=colors[algo],
                linewidth=1.5, label=f"{algo} mean (RL-only)")
    ax.axhline(F_OCT_nominal, color="k", linestyle="-", linewidth=2, label="OCT (GRAPE)")
    ax.set_xlabel("Episode")
    ax.set_ylabel("Average gate fidelity")
    ax.set_ylim(0.0, 1.02)
    ax.legend(frameon=True, loc="lower right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(fname, bbox_inches="tight", dpi=300)
    plt.close(fig)


def plot_learning_curves_all(logs, F_OCT_ens_mean, ma_window=200,
                             fname="learning_curves_all_algos.png"):
    colors = dict(SAC="C0", TD3="C2", DDPG="C3", PPO="C4")
    linestyles = dict(SAC="-", TD3="--", DDPG="-.", PPO=":")
    fig, ax = plt.subplots(figsize=(6, 4))
    for algo in ["SAC", "TD3", "DDPG", "PPO"]:
        ep, fids, best, (ep_ma, ma) = logs[algo]["callback"].get_arrays(ma_window)
        if len(ep) == 0:
            continue
        ax.plot(ep, best, linestyle=linestyles[algo], color=colors[algo],
                linewidth=2, label=f"{algo} best")
        ax.plot(ep_ma, ma, linestyle=":", color=colors[algo],
                linewidth=1.5, label=f"{algo} mean")
    ax.axhline(F_OCT_ens_mean, color="k", linestyle=":", linewidth=2, label="OCT ensemble")
    ax.set_xlabel("Episode")
    ax.set_ylabel("Fidelity")
    ax.set_ylim(0.0, 1.02)
    ax.legend(frameon=True, loc="lower right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)


def plot_ensemble_bar(logs, F_OCT_ens_mean, F_OCT_ens_std,
                      fname="ensemble_bar_all_algos.png"):
    labels = ["OCT", "SAC", "TD3", "DDPG", "PPO"]
    means = [F_OCT_ens_mean] + [logs[a]["ens_mean"] for a in ["SAC", "TD3", "DDPG", "PPO"]]
    stds = [F_OCT_ens_std] + [logs[a]["ens_std"] for a in ["SAC", "TD3", "DDPG", "PPO"]]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(x, means, yerr=stds, capsize=4)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0.0, 1.02)
    ax.set_ylabel("Fidelity")
    fig.tight_layout()
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)


def plot_eps1_pulses_all(logs, eps1_OCT, fname="pulses_eps1_all_algos.png"):
    steps = np.arange(len(eps1_OCT))
    colors = dict(SAC="C0", TD3="C2", DDPG="C3", PPO="C4")
    linestyles = dict(SAC="-", TD3="--", DDPG="-.", PPO=":")
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.step(steps, eps1_OCT, where="post", color="k", linewidth=2.0, label="OCT")
    for algo in ["SAC", "TD3", "DDPG", "PPO"]:
        ax.step(steps, logs[algo]["eps1"], where="post",
                color=colors[algo], linestyle=linestyles[algo],
                linewidth=1.5, label=algo)
    ax.set_xlabel("segment")
    ax.set_ylabel(r"$\epsilon_1$")
    ax.grid(True, alpha=0.3)
    ax.legend(frameon=True)
    fig.tight_layout()
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)


# -----------------------------------------------------------------------------
# Data saving helpers (.dat)
# -----------------------------------------------------------------------------

def save_oct_fid_hist(fid_hist):
    if fid_hist is None:
        return
    it = np.arange(1, len(fid_hist) + 1, dtype=int)
    np.savetxt("oct_fid_vs_iter.dat",
               np.column_stack((it, fid_hist)),
               header="iter F_process", comments='')


def save_learning_dat(algo, cb, ma_window=200):
    ep, fids, best, (ep_ma, ma) = cb.get_arrays(ma_window)
    if len(ep) > 0:
        np.savetxt(f"{algo.lower()}_learning.dat",
                   np.column_stack((ep, fids, best)),
                   header="episode F_episode F_best", comments='')
        np.savetxt(f"{algo.lower()}_learning_ma.dat",
                   np.column_stack((ep_ma, ma)),
                   header=f"episode_ma F_mean_window_{ma_window}", comments='')


def save_stats_dat(F_OCT_nominal, F_OCT_single, F_OCT_ens_mean, F_OCT_ens_std, logs):
    with open("ensemble_stats.dat", "w") as f:
        f.write("# method F_mean F_std\n")
        f.write(f"OCT {F_OCT_ens_mean:.8f} {F_OCT_ens_std:.8e}\n")
        for a in ["SAC", "TD3", "DDPG", "PPO"]:
            f.write(f"{a} {logs[a]['ens_mean']:.8f} {logs[a]['ens_std']:.8e}\n")
    with open("nominal_stats.dat", "w") as f:
        f.write("# method F_nominal\n")
        f.write(f"OCT {F_OCT_nominal:.8f}\n")
        for a in ["SAC", "TD3", "DDPG", "PPO"]:
            f.write(f"{a} {logs[a]['nominal']:.8f}\n")
    with open("single_device_stats.dat", "w") as f:
        f.write("# method F_single_device\n")
        f.write(f"OCT {F_OCT_single:.8f}\n")
        for a in ["SAC", "TD3", "DDPG", "PPO"]:
            f.write(f"{a} {logs[a]['single']:.8f}\n")


def save_pulses_dat(eps1_OCT, eps2_OCT, logs):
    seg = np.arange(len(eps1_OCT), dtype=int)
    np.savetxt("pulses_OCT.dat",
               np.column_stack((seg, eps1_OCT, eps2_OCT)),
               header="segment eps1 eps2", comments='')
    for algo in ["SAC", "TD3", "DDPG", "PPO"]:
        np.savetxt(f"pulses_{algo}.dat",
                   np.column_stack((seg, logs[algo]["eps1"], logs[algo]["eps2"])),
                   header="segment eps1 eps2", comments='')


# -----------------------------------------------------------------------------
# Main routine
# -----------------------------------------------------------------------------

def main():
    np.random.seed(0)

    # ------------------ Hyperparameters ------------------
    n_segments = 160
    dt = 10.0
    max_amp = 0.3
    g = 0.0025
    N_MODES = 20
    COEFF_SCALE = 0.03
    noise_std_w = 0.001
    noise_std_g = 5e-5
    TIMESTEPS = 50_000       # fewer steps needed: 4x4 system is smaller than 9x9

    # ------------------ Build system ------------------
    sys = build_two_qubit_system(
        n_segments=n_segments, dt=dt, max_amp=max_amp, g=g,
    )

    # ------------------ OCT convergence curve ------------------
    quick_oct_convergence_run(sys, n_segments=n_segments, dt=dt,
                              max_amp=max_amp, g=g, n_iters_plot=30)

    # ------------------ Main OCT run ------------------
    eps1_oct, eps2_oct, F_proc_nom, F_avg_nom, fid_hist = run_oct_grape_two_qubit_cz(
        sys, n_segments=n_segments, dt=dt, max_amp=max_amp, g=g,
        n_iters=4000, fid_err_targ=1e-10,
    )
    print(f"\nNominal OCT: process fidelity = {F_proc_nom:.6f}, "
          f"avg gate fidelity = {F_avg_nom:.6f}")
    save_oct_fid_hist(fid_hist)

    # ------------------ RL-only on nominal (for comparison) ------------------
    cos_mat = build_cosine_basis(n_segments, N_MODES)
    logs_nominal_rlonly = {}

    print("\n===== Training RL-only (no OCT) on nominal Hamiltonian =====")
    for algo_name in ["SAC", "TD3", "DDPG", "PPO"]:
        print(f"\n--- RL-only nominal: {algo_name} ---")
        env_nom = CZNominalRLOnlyEnv(
            sys_nominal=sys, cos_mat=cos_mat,
            max_amp=max_amp, coeff_scale=0.3,
            seed=321 + hash(algo_name) % 1000,
        )
        n_actions = env_nom.action_space.shape[0]
        action_noise = NormalActionNoise(
            mean=np.zeros(n_actions), sigma=0.3 * np.ones(n_actions)
        )
        cb_nom = FidelityLoggingCallback()
        common_kwargs = dict(learning_rate=3e-4, batch_size=256,
                             gamma=0.99, tau=0.005, verbose=0,
                             tensorboard_log=None, device="auto")
        policy_kwargs = dict(net_arch=[256, 256])

        if algo_name == "SAC":
            model = SAC("MlpPolicy", env_nom, action_noise=action_noise,
                        policy_kwargs=policy_kwargs, **common_kwargs)
        elif algo_name == "TD3":
            model = TD3("MlpPolicy", env_nom, action_noise=action_noise,
                        policy_kwargs=policy_kwargs, **common_kwargs)
        elif algo_name == "DDPG":
            model = DDPG("MlpPolicy", env_nom, action_noise=action_noise,
                         policy_kwargs=policy_kwargs, **common_kwargs)
        else:  # PPO
            model = PPO("MlpPolicy", env_nom, policy_kwargs=policy_kwargs,
                        verbose=0, tensorboard_log=None, device="auto",
                        learning_rate=3e-4, batch_size=256, gamma=0.99)

        model.learn(total_timesteps=TIMESTEPS, callback=cb_nom, progress_bar=False)
        logs_nominal_rlonly[algo_name] = dict(callback=cb_nom, model=model)

    plot_learning_curves_nominal_vs_oct(
        logs_nominal_rlonly, F_OCT_nominal=F_avg_nom,
        fname="learning_curves_nominal_vs_oct.png"
    )

    # ------------------ OCT ensemble (noisy devices) ------------------
    print("\n===== Evaluating OCT on ensemble of noisy devices =====")
    F_OCT_ens_mean, F_OCT_ens_std, _ = evaluate_oct_ensemble(
        sys, eps1_oct, eps2_oct,
        n_samples=100, noise_std_w=noise_std_w, noise_std_g=noise_std_g,
    )
    F_OCT_single = evaluate_oct_on_device(sys, eps1_oct, eps2_oct,
                                          dw1=noise_std_w, dw2=0.0, dg=0.0)
    print(f"OCT ensemble: mean={F_OCT_ens_mean:.6f}, std={F_OCT_ens_std:.2e}")

    # ------------------ Residual RL on noisy devices ------------------
    print("\n===== Training residual RL (OCT + RL) on noisy devices =====")
    env_res = CZResidualContextualEnv(
        sys_nominal=sys, eps1_base=eps1_oct, eps2_base=eps2_oct,
        cos_mat=cos_mat, max_amp=max_amp, coeff_scale=COEFF_SCALE,
        noise_std_w=noise_std_w, noise_std_g=noise_std_g, seed=42,
    )
    logs = {}
    for algo_name in ["SAC", "TD3", "DDPG", "PPO"]:
        print(f"\n--- Residual RL: {algo_name} ---")
        n_actions = env_res.action_space.shape[0]
        action_noise = NormalActionNoise(
            mean=np.zeros(n_actions), sigma=0.1 * np.ones(n_actions)
        )
        cb = FidelityLoggingCallback()
        common_kwargs = dict(learning_rate=3e-4, batch_size=256,
                             gamma=0.99, tau=0.005, verbose=0,
                             tensorboard_log=None, device="auto")
        policy_kwargs = dict(net_arch=[256, 256])

        if algo_name == "SAC":
            model = SAC("MlpPolicy", env_res, action_noise=action_noise,
                        policy_kwargs=policy_kwargs, **common_kwargs)
        elif algo_name == "TD3":
            model = TD3("MlpPolicy", env_res, action_noise=action_noise,
                        policy_kwargs=policy_kwargs, **common_kwargs)
        elif algo_name == "DDPG":
            model = DDPG("MlpPolicy", env_res, action_noise=action_noise,
                         policy_kwargs=policy_kwargs, **common_kwargs)
        else:  # PPO
            model = PPO("MlpPolicy", env_res, policy_kwargs=policy_kwargs,
                        verbose=0, tensorboard_log=None, device="auto",
                        learning_rate=3e-4, batch_size=256, gamma=0.99)

        model.learn(total_timesteps=TIMESTEPS, callback=cb, progress_bar=False)
        save_learning_dat(algo_name, cb)

        # Evaluate
        F_nom, eps1_rl, eps2_rl = evaluate_policy_on_device(
            model, env_res, dw1=0.0, dw2=0.0, dg=0.0
        )
        F_single, _, _ = evaluate_policy_on_device(
            model, env_res, dw1=noise_std_w, dw2=0.0, dg=0.0
        )
        F_ens_mean, F_ens_std, _ = evaluate_policy_ensemble(
            model, env_res, n_samples=100,
            noise_std_w=noise_std_w, noise_std_g=noise_std_g,
        )
        print(f"  {algo_name}: nominal={F_nom:.4f}, single={F_single:.4f}, "
              f"ensemble={F_ens_mean:.4f} ± {F_ens_std:.2e}")

        logs[algo_name] = dict(
            callback=cb, model=model,
            nominal=F_nom, single=F_single,
            ens_mean=F_ens_mean, ens_std=F_ens_std,
            eps1=eps1_rl, eps2=eps2_rl,
        )

    # ------------------ Plots & data ------------------
    plot_learning_curves_all(logs, F_OCT_ens_mean,
                             fname="learning_curves_all_algos.png")
    plot_ensemble_bar(logs, F_OCT_ens_mean, F_OCT_ens_std,
                      fname="ensemble_bar_all_algos.png")
    plot_eps1_pulses_all(logs, eps1_oct, fname="pulses_eps1_all_algos.png")

    save_stats_dat(F_avg_nom, F_OCT_single, F_OCT_ens_mean, F_OCT_ens_std, logs)
    save_pulses_dat(eps1_oct, eps2_oct, logs)

    print("\nAll done. Figures and .dat files saved.")


if __name__ == "__main__":
    main()
