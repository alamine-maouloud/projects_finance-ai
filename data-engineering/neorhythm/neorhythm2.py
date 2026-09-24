from __future__ import annotations

import csv
import io
import json
import math
import os
import random
import struct
import sys
import threading
import time
import wave
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import tkinter as tk
from tkinter import ttk, messagebox

try:
    import pygame
except ImportError:
    raise SystemExit("Missing dependency: pygame. Install with 'pip install pygame'")

# Try to import pyttsx3 for TTS; fall back gracefully
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

APP_NAME = "NeoRhythm"
VERSION = "2.0"

# ---------------------------------------------------------------------------
# Fixed directory structure
# ---------------------------------------------------------------------------
# Place audio files here (relative to the script's directory):
#   stimuli/classical/   – any .wav/.mp3/.ogg
#   stimuli/lullabies/   – any .wav/.mp3/.ogg
#   stimuli/whitenoise/  – any .wav/.mp3/.ogg
# When packaged with PyInstaller as a .app, sys.executable sits inside
# NeoRhythm.app/Contents/MacOS/. We want stimuli/ to live NEXT TO the .app,
# so we walk up until we find the .app bundle and go one level above it.
def _find_base_dir() -> Path:
    exe = Path(sys.executable).resolve()

    # macOS: walk up until we find the .app bundle, then go one level above
    for parent in exe.parents:
        if parent.suffix == ".app":
            return parent.parent

    # Windows (PyInstaller one-folder build): the exe sits inside
    # dist/NeoRhythm/NeoRhythm.exe — stimuli/ lives next to the exe
    if getattr(sys, "frozen", False):
        return exe.parent

    # Fallback for running as plain script
    return Path(__file__).parent

SCRIPT_DIR = _find_base_dir()
STIMULI_ROOT = SCRIPT_DIR / "stimuli"
STIMULI_DIRS: Dict[str, Path] = {
    "Classical":  STIMULI_ROOT / "classical",
    "Lullabies":  STIMULI_ROOT / "lullabies",
    "WhiteNoise": STIMULI_ROOT / "whitenoise",
}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac"}


def find_first_audio(folder: Path) -> Optional[Path]:
    """Return the first audio file found in *folder*, or None."""
    if not folder.is_dir():
        return None
    for p in sorted(folder.iterdir()):
        if p.suffix.lower() in AUDIO_EXTENSIONS:
            return p
    return None


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Timings:
    pre_silence_before_start_beep: float = 10.0
    wait_after_start_beep: float = 5.0

    block_play_seconds: float = 5 * 60.0
    inter_block_silence_seconds: float = 60.0

    transfer_silence_seconds: float = 3 * 60.0
    skin_to_skin_seconds: float = 5 * 60.0

    first_stop_beep_pause_seconds: float = 10.0
    fade_ms: int = 3000
    sim_scale: float = 1.0

    def scaled(self, x: float) -> float:
        return x * self.sim_scale


# ---------------------------------------------------------------------------
# Audio Engine
# ---------------------------------------------------------------------------

class AudioEngine:
    LOW_FREQ  = 660.0   # Hz – first two beeps
    HIGH_FREQ = 880.0   # Hz – third beep

    def __init__(self, stop_event: threading.Event):
        self._stop = stop_event
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=1024)
        pygame.init()
        self.channel = pygame.mixer.Channel(0)
        self._low_beep  = self._make_beep(self.LOW_FREQ,  duration_s=0.5, volume=0.8)
        self._high_beep = self._make_beep(self.HIGH_FREQ, duration_s=0.5, volume=0.8)

        # TTS engine (optional)
        self._tts_lock = threading.Lock()
        if TTS_AVAILABLE:
            try:
                self._tts = pyttsx3.init()
                self._tts.setProperty("rate", 150)
                # Force an English voice
                voices = self._tts.getProperty("voices")
                english_voice = None
                for v in voices:
                    vid = (v.id or "").lower()
                    vname = (v.name or "").lower()
                    if "en" in vid or "english" in vname or "samantha" in vname or "alex" in vname or "daniel" in vname:
                        english_voice = v.id
                        break
                if english_voice:
                    self._tts.setProperty("voice", english_voice)
            except Exception:
                self._tts = None
        else:
            self._tts = None

    # ------------------------------------------------------------------
    # Beep helpers
    # ------------------------------------------------------------------

    def _make_beep(self, freq: float, duration_s: float = 0.5,
                   volume: float = 0.8) -> pygame.mixer.Sound:
        sample_rate = 44100
        n_samples = int(duration_s * sample_rate)
        max_amp = 32767
        raw = bytearray()
        for i in range(n_samples):
            t = i / sample_rate
            # simple sine with short linear fade-in/out to avoid clicks
            fade = min(i, n_samples - i, 1000) / 1000.0
            val = int(max_amp * fade * math.sin(2 * math.pi * freq * t))
            raw += struct.pack('<hh', val, val)
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, 'wb') as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(bytes(raw))
        wav_buf.seek(0)
        sound = pygame.mixer.Sound(file=wav_buf)
        sound.set_volume(volume)
        return sound

    def _play_sound_blocking(self, sound: pygame.mixer.Sound):
        """Play a sound on channel 0 and block until done or stop requested."""
        self.channel.play(sound)
        while self.channel.get_busy():
            if self._stop.is_set():
                self.channel.stop()
                return
            pygame.time.wait(10)

    def play_triple_beep(self):
        """Two low beeps then one higher beep (with 1s gap between each)."""
        for _ in range(2):
            if self._stop.is_set():
                return
            self._play_sound_blocking(self._low_beep)
            self._interruptible_sleep(1.0)
        if self._stop.is_set():
            return
        self._play_sound_blocking(self._high_beep)

    # ------------------------------------------------------------------
    # TTS / speech
    # ------------------------------------------------------------------

    def speak(self, text: str):
        """Speak *text* via TTS (blocking). Falls back to console print."""
        if self._stop.is_set():
            return
        if self._tts is not None:
            try:
                with self._tts_lock:
                    self._tts.say(text)
                    self._tts.runAndWait()
            except Exception:
                pass
        else:
            print(f"[SPEECH] {text}")

    # ------------------------------------------------------------------
    # Music playback
    # ------------------------------------------------------------------

    def load_sound(self, path: Path) -> pygame.mixer.Sound:
        s = pygame.mixer.Sound(path.as_posix())
        s.set_volume(1.0)
        return s

    def play_for_duration(self, sound: pygame.mixer.Sound, seconds: float,
                          fade_ms: int = 0, on_progress=None):
        """Play *sound* for *seconds* with fade-in and fade-out.
        on_progress(elapsed, total) is called ~20 Hz for progress bar updates."""
        if self._stop.is_set():
            return
        start_time = time.time()
        end_time   = start_time + seconds
        fade_s     = fade_ms / 1000.0

        def _tick():
            if on_progress:
                on_progress(time.time() - start_time, seconds)

        # Fade-in: start at volume 0, ramp up over fade_ms
        self.channel.play(sound, loops=-1)
        ramp_steps = max(1, fade_ms // 50)
        for step in range(ramp_steps + 1):
            if self._stop.is_set():
                self.channel.stop()
                return
            vol = step / ramp_steps
            self.channel.set_volume(vol)
            _tick()
            time.sleep(0.05)

        # Sustain
        sustain_end = end_time - fade_s
        while time.time() < sustain_end:
            if self._stop.is_set():
                self.channel.stop()
                return
            _tick()
            time.sleep(0.05)

        # Fade-out
        fade_steps = max(1, fade_ms // 50)
        for step in range(fade_steps, -1, -1):
            if self._stop.is_set():
                self.channel.stop()
                return
            vol = step / fade_steps
            self.channel.set_volume(vol)
            _tick()
            time.sleep(0.05)

        self.channel.stop()
        self.channel.set_volume(1.0)

    # ------------------------------------------------------------------
    # Silence / sleep
    # ------------------------------------------------------------------

    def silence(self, seconds: float):
        self._interruptible_sleep(seconds)

    def _interruptible_sleep(self, seconds: float):
        end = time.time() + seconds
        while time.time() < end:
            if self._stop.is_set():
                return
            time.sleep(0.05)


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

@dataclass
class BlockLog:
    block_index: int
    condition: str
    start_time: str
    end_time: str
    duration_sec: float


@dataclass
class NoteLog:
    label: str
    start_time: str
    end_time: str
    duration_sec: float


@dataclass
class SessionLog:
    subject_id: str
    datetime_started: str
    random_seed: int
    randomized_order: List[str]
    with_skin_to_skin: bool
    notes: List[NoteLog]
    blocks: List[BlockLog]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


# ---------------------------------------------------------------------------
# GUI Application
# ---------------------------------------------------------------------------

class NeoRhythmApp(tk.Tk):
    CONDITIONS = ["Classical", "Lullabies", "WhiteNoise", "Silence"]

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("860x660")
        self.eval('tk::PlaceWindow . center')
        self.resizable(False, False)

        self._stop_event = threading.Event()
        self.audio: Optional[AudioEngine] = None
        self.session_thread: Optional[threading.Thread] = None
        self.timings = Timings()

        # UI vars
        self.subject_var       = tk.StringVar()
        self.seed_var          = tk.StringVar(value=str(random.randint(1, 999999)))
        self.sim_scale_var     = tk.DoubleVar(value=1.0)
        self.skin_to_skin_var  = tk.BooleanVar(value=True)

        self._build_ui()
        self._check_stimuli_dirs()

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}
        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True, **pad)

        row = 0

        # ── Session ID & seed ──────────────────────────────────────────
        ttk.Label(frm, text="Session ID:").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.subject_var, width=28).grid(
            row=row, column=1, sticky="w")
        ttk.Label(frm, text="Random Seed:").grid(row=row, column=2, sticky="e")
        ttk.Entry(frm, textvariable=self.seed_var, width=12).grid(
            row=row, column=3, sticky="w")
        row += 1

        # ── Stimuli directory status ───────────────────────────────────
        self.stimuli_status_var = tk.StringVar(value="Checking stimuli folders…")
        ttk.Label(frm, textvariable=self.stimuli_status_var,
                  foreground="gray").grid(
            row=row, column=0, columnspan=4, sticky="w")
        row += 1

        # ── Separator ─────────────────────────────────────────────────
        ttk.Separator(frm).grid(
            row=row, column=0, columnspan=4, sticky="we", pady=(8, 4))
        row += 1

        # ── Timing spinboxes ──────────────────────────────────────────
        def spin(label, attr, default, step, col=0):
            nonlocal row
            ttk.Label(frm, text=label).grid(row=row, column=col, sticky="w")
            var = tk.DoubleVar(value=default)
            ttk.Spinbox(frm, from_=0, to=3600, increment=step,
                        textvariable=var, width=8).grid(
                row=row, column=col + 1, sticky="w")
            setattr(self, attr, var)

        spin("Pre-silence before start beeps (s):", "pre_silence_var",
             self.timings.pre_silence_before_start_beep, 1)
        spin("Pause after start beeps (s):", "post_start_beep_var",
             self.timings.wait_after_start_beep, 1, col=2)
        row += 1
        spin("Block duration (s):", "block_sec_var",
             self.timings.block_play_seconds, 5)
        spin("Inter-block silence (s):", "inter_silence_var",
             self.timings.inter_block_silence_seconds, 1, col=2)
        row += 1
        spin("Transfer silence (s):", "transfer_sec_var",
             self.timings.transfer_silence_seconds, 5)
        spin("Skin-to-skin duration (s):", "skin_sec_var",
             self.timings.skin_to_skin_seconds, 5, col=2)
        row += 1
        spin("Pause between final beeps (s):", "stop_beeps_pause_var",
             self.timings.first_stop_beep_pause_seconds, 1)
        ttk.Label(frm, text="Fade (ms):").grid(row=row, column=2, sticky="w")
        self.fade_var = tk.IntVar(value=self.timings.fade_ms)
        ttk.Spinbox(frm, from_=0, to=10000, increment=250,
                    textvariable=self.fade_var, width=8).grid(
            row=row, column=3, sticky="w")
        row += 1

        ttk.Label(frm, text="Simulation scale:").grid(
            row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.sim_scale_var, width=10).grid(
            row=row, column=1, sticky="w")
        ttk.Label(frm, text="1.0 = real time").grid(
            row=row, column=2, sticky="w")
        row += 1

        # ── Skin-to-skin toggle ───────────────────────────────────────
        ttk.Separator(frm).grid(
            row=row, column=0, columnspan=4, sticky="we", pady=(8, 4))
        row += 1
        ttk.Checkbutton(
            frm,
            text="Include skin-to-skin transfer phase at the end",
            variable=self.skin_to_skin_var,
        ).grid(row=row, column=0, columnspan=4, sticky="w")
        row += 1

        # ── TTS notice ────────────────────────────────────────────────
        tts_msg = ("✔ pyttsx3 found – spoken prompts enabled."
                   if TTS_AVAILABLE else
                   "⚠ pyttsx3 not found – spoken prompts will be skipped. "
                   "Install with: pip install pyttsx3")
        ttk.Label(frm, text=tts_msg,
                  foreground="green" if TTS_AVAILABLE else "orange").grid(
            row=row, column=0, columnspan=4, sticky="w")
        row += 1

        # ── Separator + buttons ───────────────────────────────────────
        ttk.Separator(frm).grid(
            row=row, column=0, columnspan=4, sticky="we", pady=(8, 4))
        row += 1

        self.start_btn = ttk.Button(
            frm, text="▶  Start Protocol", command=self.start_protocol)
        self.start_btn.grid(row=row, column=0, sticky="we", padx=(0, 6))
        self.stop_btn = ttk.Button(
            frm, text="■  Abort (immediate)",
            command=self.abort_protocol, state=tk.DISABLED)
        self.stop_btn.grid(row=row, column=1, sticky="we")
        row += 1

        # ── Status + progress ─────────────────────────────────────────
        self.status_var = tk.StringVar(value="Idle.")
        ttk.Label(frm, textvariable=self.status_var,
                  font=("Segoe UI", 11)).grid(
            row=row, column=0, columnspan=4, sticky="w")
        row += 1

        self.progress = ttk.Progressbar(
            frm, mode="determinate", length=800)
        self.progress.grid(row=row, column=0, columnspan=4, sticky="we")
        row += 1

        self.order_var = tk.StringVar(value="Order: —")
        ttk.Label(frm, textvariable=self.order_var).grid(
            row=row, column=0, columnspan=4, sticky="w")

    # ------------------------------------------------------------------
    # Stimuli directory check
    # ------------------------------------------------------------------

    def _check_stimuli_dirs(self):
        lines = []
        ok = True
        for name, folder in STIMULI_DIRS.items():
            f = find_first_audio(folder)
            if f:
                lines.append(f"✔ {name}: {f.name}")
            else:
                lines.append(f"✘ {name}: no audio file found in {folder}")
                ok = False
        colour = "green" if ok else "red"
        self.stimuli_status_var.set("  |  ".join(lines))
        # re-colour label (need to walk widget tree)
        for w in self.winfo_children():
            self._recolour_label(w, self.stimuli_status_var, colour)

    def _recolour_label(self, widget, var, colour):
        if isinstance(widget, ttk.Label):
            try:
                if widget.cget("textvariable") == str(var):
                    widget.configure(foreground=colour)
            except Exception:
                pass
        for child in widget.winfo_children():
            self._recolour_label(child, var, colour)

    # ------------------------------------------------------------------
    # Protocol control
    # ------------------------------------------------------------------

    def start_protocol(self):
        if self.session_thread and self.session_thread.is_alive():
            return

        subj = self.subject_var.get().strip()
        if not subj:
            messagebox.showwarning(APP_NAME, "Please enter a Session ID.")
            return
        try:
            seed = int(self.seed_var.get().strip())
        except ValueError:
            messagebox.showwarning(APP_NAME, "Seed must be an integer.")
            return

        # Resolve stimuli files
        files: Dict[str, Path] = {}
        missing = []
        for name, folder in STIMULI_DIRS.items():
            p = find_first_audio(folder)
            if p:
                files[name] = p
            else:
                missing.append(name)
        if missing:
            messagebox.showwarning(
                APP_NAME,
                f"Missing audio in folder(s): {', '.join(missing)}\n\n"
                f"Expected subfolders inside:\n{STIMULI_ROOT}"
            )
            return

        # Build timings
        t = Timings(
            pre_silence_before_start_beep=float(self.pre_silence_var.get()),
            wait_after_start_beep=float(self.post_start_beep_var.get()),
            block_play_seconds=float(self.block_sec_var.get()),
            inter_block_silence_seconds=float(self.inter_silence_var.get()),
            transfer_silence_seconds=float(self.transfer_sec_var.get()),
            skin_to_skin_seconds=float(self.skin_sec_var.get()),
            first_stop_beep_pause_seconds=float(self.stop_beeps_pause_var.get()),
            fade_ms=int(self.fade_var.get()),
            sim_scale=float(self.sim_scale_var.get()),
        )
        self.timings = t
        with_sts = self.skin_to_skin_var.get()

        # Randomise order
        random.seed(seed)
        order = self.CONDITIONS.copy()
        random.shuffle(order)
        self.order_var.set("Order: " + " → ".join(order))

        # Session log
        self.session_log = SessionLog(
            subject_id=subj,
            datetime_started=datetime.now().isoformat(timespec='seconds'),
            random_seed=seed,
            randomized_order=order,
            with_skin_to_skin=with_sts,
            notes=[],
            blocks=[],
        )

        self._stop_event.clear()
        self.audio = AudioEngine(self._stop_event)

        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)

        self.session_thread = threading.Thread(
            target=self._run_protocol,
            args=(files, order, with_sts),
            daemon=True,
        )
        self.session_thread.start()

    def abort_protocol(self):
        """Immediately signal the audio engine and background thread to stop."""
        self._stop_event.set()
        if self.audio:
            self.audio.channel.stop()   # cut audio right now
        self._ui_safe(lambda: self.status_var.set(
            "Abort requested — stopping immediately…"))

    # ------------------------------------------------------------------
    # Protocol engine
    # ------------------------------------------------------------------

    def _run_protocol(self, files: Dict[str, Path], order: List[str],
                      with_skin_to_skin: bool):
        try:
            self._protocol_impl(files, order, with_skin_to_skin)
            aborted = self._stop_event.is_set()
            self._finalize_logs(success=not aborted)
        except Exception as e:
            self._finalize_logs(success=False)
            self._ui_safe(lambda: messagebox.showerror(
                APP_NAME, f"Unexpected error:\n{e}"))
        finally:
            self._ui_safe(lambda: (
                self.start_btn.configure(state=tk.NORMAL),
                self.stop_btn.configure(state=tk.DISABLED),
            ))

    def _protocol_impl(self, files: Dict[str, Path], order: List[str],
                       with_skin_to_skin: bool):
        t   = self.timings
        ae  = self.audio

        def log_note(label: str, start: str, end: str, duration: float):
            self.session_log.notes.append(NoteLog(label, start, end, duration))

        # ── 1. Pre-start silence ──────────────────────────────────────
        self._stage("Preparation silence before start beeps…")
        self._progress_run(t.scaled(t.pre_silence_before_start_beep))
        if self._stop_event.is_set(): return

        # ── 2. Triple beep (EEG marker) ───────────────────────────────
        self._stage("Start beeps — nurse presses EEG marker on third beep")
        t0 = datetime.now().isoformat(timespec='seconds')
        ae.play_triple_beep()
        t1 = datetime.now().isoformat(timespec='seconds')
        log_note("Triple start beep", t0, t1, 0.0)
        if self._stop_event.is_set(): return

        # ── 3. Relaxation pause ───────────────────────────────────────
        self._stage("Relaxation pause after start beeps…")
        self._progress_run(t.scaled(t.wait_after_start_beep))
        if self._stop_event.is_set(): return

        # ── 4. Load sounds ────────────────────────────────────────────
        sounds = {name: ae.load_sound(path) for name, path in files.items()}

        # ── 5. Randomised stimulus blocks ─────────────────────────────
        for idx, cond in enumerate(order, start=1):
            if self._stop_event.is_set(): break

            start = datetime.now().isoformat(timespec='seconds')
            dur = t.scaled(t.block_play_seconds)
            if cond == "Silence":
                self._stage(f"Block {idx}/4 — Silence")
                self._progress_run(dur)
            else:
                self._stage(f"Block {idx}/4 — Playing {cond}…")
                self._ui_safe(lambda d=dur: self.progress.configure(
                    maximum=max(1.0, d), value=0))
                ae.play_for_duration(
                    sounds[cond],
                    seconds=dur,
                    fade_ms=t.fade_ms,
                    on_progress=lambda e, d: self._ui_safe(
                        lambda e=e, d=d: self.progress.configure(value=min(e, d))),
                )
                self._ui_safe(lambda d=dur: self.progress.configure(value=d))
            end = datetime.now().isoformat(timespec='seconds')
            self.session_log.blocks.append(
                BlockLog(idx, cond, start, end, dur))

            if idx < 4 and not self._stop_event.is_set():
                self._stage("Inter-block silence…")
                self._progress_run(t.scaled(t.inter_block_silence_seconds))

        if self._stop_event.is_set():
            self._stage("Aborted by user.")
            return

        # ── 6. Acoustic protocol end: triple beep ─────────────────────
        self._stage("End of acoustic protocol — triple beep")
        t0 = datetime.now().isoformat(timespec='seconds')
        ae.play_triple_beep()
        t1 = datetime.now().isoformat(timespec='seconds')
        log_note("Triple end beep (acoustic protocol complete)", t0, t1, 0.0)
        if self._stop_event.is_set(): return

        # ── 7. Optional skin-to-skin transfer phase ───────────────────
        if with_skin_to_skin:
            # Spoken prompt to nurse
            self._stage("Spoken prompt: transfer baby to mother")
            t0 = datetime.now().isoformat(timespec='seconds')
            ae.speak("Now transfer the baby to the mother for skin-to-skin.")
            t1 = datetime.now().isoformat(timespec='seconds')
            log_note("Spoken: transfer to mother", t0, t1, 0.0)
            if self._stop_event.is_set(): return

            # Transfer silence
            self._stage("Transfer silence (baby being moved to mother)…")
            t0 = datetime.now().isoformat(timespec='seconds')
            dur = t.scaled(t.transfer_silence_seconds)
            self._progress_run(dur)
            t1 = datetime.now().isoformat(timespec='seconds')
            log_note("Transfer silence", t0, t1, dur)
            if self._stop_event.is_set(): return

            # Spoken prompt: EEG measurement starts
            self._stage("Spoken prompt: EEG measurement starts")
            t0 = datetime.now().isoformat(timespec='seconds')
            ae.speak("Now the EEG measurement starts.")
            t1 = datetime.now().isoformat(timespec='seconds')
            log_note("Spoken: EEG measurement starts", t0, t1, 0.0)
            if self._stop_event.is_set(): return

            # Skin-to-skin period
            self._stage("Skin-to-skin period…")
            t0 = datetime.now().isoformat(timespec='seconds')
            dur = t.scaled(t.skin_to_skin_seconds)
            self._progress_run(dur)
            t1 = datetime.now().isoformat(timespec='seconds')
            log_note("Skin-to-skin silence", t0, t1, dur)
            if self._stop_event.is_set(): return

        # ── 8. Closing message ────────────────────────────────────────
        self._stage("Closing spoken message")
        t0 = datetime.now().isoformat(timespec='seconds')
        ae.speak("We have concluded the experiment. Thank you very much.")
        t1 = datetime.now().isoformat(timespec='seconds')
        log_note("Spoken: closing message", t0, t1, 0.0)

        self._stage("Protocol completed. Saving logs…")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _stage(self, text: str):
        self._ui_safe(lambda: self.status_var.set(text))

    def _progress_run(self, total: float):
        start = time.time()
        end   = start + max(0.0, total)
        self._ui_safe(lambda: self.progress.configure(
            maximum=max(1.0, total), value=0))
        while time.time() < end:
            if self._stop_event.is_set():
                break
            elapsed = time.time() - start
            self._ui_safe(lambda e=elapsed: self.progress.configure(value=e))
            time.sleep(0.05)
        self._ui_safe(lambda: self.progress.configure(value=max(1.0, total)))

    def _finalize_logs(self, success: bool):
        outdir = SCRIPT_DIR / "logs"
        outdir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base  = f"{self.session_log.subject_id}_{stamp}"

        csv_path  = outdir / f"{base}.csv"
        json_path = outdir / f"{base}.json"

        # ── CSV ──────────────────────────────────────────────────────
        try:
            dt = datetime.fromisoformat(self.session_log.datetime_started)
            date_str = dt.strftime("%Y - %m - %d")
            time_str = dt.strftime("%H:%M:%S")
            order_str = " -> ".join(self.session_log.randomized_order)

            with csv_path.open("w", newline='', encoding="utf-8") as f:
                w = csv.writer(f)

                # ── Header block ──────────────────────────────────────
                w.writerow(["SubjectID",  self.session_log.subject_id])
                w.writerow(["Date",       date_str])
                w.writerow(["Time",       time_str])
                w.writerow(["RandomSeed", self.session_log.random_seed])
                w.writerow(["Order",      order_str])
                w.writerow([])

                # ── Stimulus blocks ───────────────────────────────────
                w.writerow(["BlockIndex", "Condition",
                             "StartTime", "EndTime", "DurationSec"])
                for b in self.session_log.blocks:
                    # keep only HH:MM:SS for readability
                    st = b.start_time[11:] if "T" in b.start_time else b.start_time
                    et = b.end_time[11:]   if "T" in b.end_time   else b.end_time
                    w.writerow([b.block_index, b.condition,
                                st, et, f"{b.duration_sec:.3f}"])
                w.writerow([])

                # ── Notes / events ────────────────────────────────────
                w.writerow(["Notes", "", "StartTime", "EndTime", "DurationSec"])
                for n in self.session_log.notes:
                    st = n.start_time[11:] if "T" in n.start_time else n.start_time
                    et = n.end_time[11:]   if "T" in n.end_time   else n.end_time
                    dur = f"{n.duration_sec:.3f}" if n.duration_sec > 0 else ""
                    w.writerow([n.label, "", st, et, dur])

        except Exception as e:
            self._ui_safe(lambda: messagebox.showerror(
                APP_NAME, f"Could not write CSV log:\n{e}"))
            return

        # ── JSON ──────────────────────────────────────────────────────
        try:
            with json_path.open("w", encoding="utf-8") as f:
                f.write(self.session_log.to_json())
        except Exception as e:
            self._ui_safe(lambda: messagebox.showerror(
                APP_NAME, f"Could not write JSON log:\n{e}"))
            return

        def _done():
            if not self._stop_event.is_set() and success:
                self.status_var.set("Done ✔  Logs saved.")
            else:
                self.status_var.set("Finished (aborted/error). Partial logs saved.")
            messagebox.showinfo(
                APP_NAME,
                f"Session summary saved.\n\nCSV:  {csv_path}\nJSON: {json_path}",
            )

        self._ui_safe(_done)

    def _ui_safe(self, fn):
        self.after(0, fn)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Create expected stimuli folders if they don't exist yet (first run)
    for folder in STIMULI_DIRS.values():
        folder.mkdir(parents=True, exist_ok=True)
    app = NeoRhythmApp()
    app.mainloop()


if __name__ == "__main__":
    main()
