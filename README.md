# Projects : Al-Amine Maouloud

**M2 Data & AI @ ECE Paris** · Exchange semester in Quantitative Finance @ University of Oslo (Autumn 2026)

Quantitative finance · Machine learning · Data engineering

I build things end-to-end: pricing engines in C++, ML pipelines in Python, and data platforms used in real research settings.

🔎 **Currently looking for an internship starting January 2027.**

![C++](https://img.shields.io/badge/C++17-00599C?logo=cplusplus&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?logo=scikitlearn&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?logo=pytorch&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-336791?logo=postgresql&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![C](https://img.shields.io/badge/C-A8B9CC?logo=c&logoColor=white)
![Java](https://img.shields.io/badge/Java-007396?logo=openjdk&logoColor=white)
![PHP](https://img.shields.io/badge/PHP-777BB4?logo=php&logoColor=white)

---

## 📈 Quantitative Finance

| Project | Stack | Highlights |
|---|---|---|
| [mcrisk · Monte Carlo Risk Engine · Black-Scholes · Limit Order Book](finance-quant/monte-carlo-risk-engine) | Python, C++17, pybind11 | Credit, market (FRTB IMA), counterparty (CVA, wrong-way risk) and market microstructure in one engine: C++ price-time priority order book simulating 15M events/s with Hawkes order flow; every model validated against closed-form results; 76 tests |
| [Real Estate Investment Analysis](finance-quant/real-estate-investment-analysis) | Python | <!-- TODO: one-line summary + key result --> |

## 🤖 Machine Learning & AI

| Project | Stack | Highlights |
|---|---|---|
| [Banking Fraud Detection](machine-learning/banking-anomaly-detection) | Python, pandas, scikit-learn, Streamlit | Card and payment fraud on a synthetic bank (557k transactions, 5 fraud typologies): leakage-tested behavioural features, rules vs Isolation Forest vs gradient boosting under a daily alert budget. PR-AUC 0.86 (0.02 for Isolation Forest on raw fields), 76% of fraud losses prevented reviewing 0.2% of transactions, reason codes per alert, investigation dashboard, 18 tests |
| [Federated Learning for Fraud Detection](machine-learning/federated-learning-fraud) | Python | Research internship at CSNET Lab: privacy-preserving fraud detection across institutions <!-- TODO: add key result --> |
| [AI-Driven Quantum Gate Calibration](machine-learning/quantum-gate-calibration) | Python, QuTiP, Stable-Baselines3 | AI calibration of a two-qubit CZ gate: deep RL agents (SAC, TD3, DDPG, PPO) correct GRAPE optimal-control pulses for device drift, benchmarked on 100 noisy devices |

## 🗄️ Data Engineering & Research Software

| Project | Stack | Highlights |
|---|---|---|
| [NICU Clinical Research Data Platform](data-engineering/nicu-research-data-platform) | Python, Streamlit, SQLite, DuckDB | Clinical research data platform: 71-field schema, 3-layer validation, de-identified exports, audit trail, local LLM (text-to-SQL + RAG) |
| [NICU Auditory Stimulation App (NeoRhythm)](data-engineering/nicu-auditory-stimulation-app) | Python, tkinter, pygame | Desktop app delivering randomized auditory protocols for NICU research |
| [qEEG Pipeline](data-engineering/qeeg-pipeline) | Python | <!-- TODO: one-line summary --> |

## 💻 Software & Web

| Project | Stack | Highlights |
|---|---|---|
| [Quoridor](software-web/quoridor) | C, CMake | Full board game implementation: rules, move validation, game logic |
| [Fashion Store](software-web/fashion-store) | Java, MVC, SQL | E-commerce app with MVC architecture: catalog, cart, payment, client and admin areas |
| [Mini LinkedIn](software-web/mini-linkedin) | PHP, HTML/CSS, SQL | Professional social network: profiles, connection requests, messaging, job offers |

## 📚 Learning

| Project | Stack | Highlights |
|---|---|---|
| [Titanic Survival Prediction](learning/titanic) | Python, scikit-learn | Classic classification exercise: feature engineering and model comparison |

---

## 📬 Contact

- Email: maouloudalamines@outlook.fr
- GitHub: [@alamine-maouloud](https://github.com/alamine-maouloud)
- LinkedIn: [Al-Amine Maouloud](https://www.linkedin.com/in/al-amine-maouloud-412a89249)
