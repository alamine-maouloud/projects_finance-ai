# NeoRhythm — Auditory Protocol Delivery for NICU Research

Desktop application that delivers randomized auditory stimulation protocols to premature infants during EEG recording sessions. Built as Work Package 1 of the NeoRhythm research initiative on neonatal developmental care, during a research internship at the Canadian University of Dubai (School of Health Sciences and Psychology).

## What it does

- **Randomized protocol**: the order of the auditory conditions (lullabies, classical piano, white noise) is shuffled from a user-defined seed, so every session is reproducible.
- **Configurable timings**: pre-silence, start/stop beeps, block duration, inter-block silence, transfer and optional skin-to-skin phases, fade-in/out.
- **Session logging**: every session is exported to CSV and JSON (subject ID, seed, randomized order, block timestamps, notes).
- **Safe control**: the protocol runs in a background thread and can be aborted instantly.
- **Cross-platform builds**: packaged with PyInstaller for macOS and Windows.

## Stack

Python · tkinter (GUI) · pygame (audio engine) · PyInstaller (packaging)

## Run it

```bash
pip install -r requirements.txt
python neorhythm2.py
```

Audio stimuli are not included in this repository. Place one audio file in each folder before starting a session:

```
stimuli/
├── lullabies/
├── classical/
└── whitenoise/
```

## Build the desktop app

```bash
pyinstaller NeoRhythm.spec           # macOS
pyinstaller NeoRhythm_windows.spec   # Windows (run on a Windows machine)
```

## Note

Session logs and audio files are excluded from version control. No clinical data is stored in this repository.
