# AI-Driven Quantum Gate Calibration — Two-Qubit CZ Gate

Robust calibration of a two-qubit CZ gate under device parameter drift, combining **optimal control (GRAPE)** with **residual reinforcement learning**.

## Problem

Real superconducting qubits never match their nominal parameters exactly: qubit frequencies (ω₁, ω₂) and coupling strength (g) drift from device to device. Pulses optimized on the nominal Hamiltonian lose fidelity on real hardware.

## Approach

1. **Optimal control baseline (GRAPE)**: pulses are optimized on the nominal two-qubit Hamiltonian (transmon-like, 2-level truncation) with QuTiP.
2. **Residual RL**: an agent observes the device's parameter deviations and outputs small corrections to the GRAPE pulses, expressed in a 20-mode cosine basis to keep pulses smooth. Reward = fidelity gain over the GRAPE baseline on that device.
3. **Algorithm benchmark**: SAC, TD3, DDPG and PPO (Stable-Baselines3), trained on randomly sampled noisy devices.
4. **Control experiment**: RL alone (no GRAPE baseline) on the nominal Hamiltonian, to show why the hybrid approach is needed.

## Evaluation

- Average gate fidelity on the nominal device, on a single detuned device, and over an ensemble of 100 noisy devices.
- Comparison of every RL algorithm against GRAPE alone.

## Stack

Python · QuTiP / qutip-qtrl (GRAPE) · Gymnasium · Stable-Baselines3 · NumPy · Matplotlib

## Run it

```bash
pip install -r requirements.txt
python agentRL_2qubits.py
```

Outputs: learning curves, ensemble fidelity bar chart, pulse shapes (`.png`), and raw data (`.dat`).
