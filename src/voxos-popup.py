#!/usr/bin/env python3

import os
import signal
import subprocess
import sys
import tempfile

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QMenu,
    QSystemTrayIcon,
    QWidget,
)


HOME = os.path.expanduser("~")

DRAFT = os.path.join(
    HOME,
    ".cache",
    "voxos-draft.txt"
)

HISTORY = os.path.join(
    HOME,
    ".cache",
    "voxos-history.txt"
)

VOLUME = os.path.join(
    HOME,
    ".cache",
    "voxos-volume.txt"
)

PIDFILE = "/tmp/voxos-prompt.pid"

EDGE_TTS = [sys.executable, "-m", "edge_tts"]

VOXOS_SINK = "voxos_output"
MAX_PULSE_VOLUME = 65_536

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESKTOP_ICON_PATH = os.path.join(
    PROJECT_ROOT,
    "assets",
    "voxos.svg",
)
TRAY_ICON_PATH = os.path.join(
    PROJECT_ROOT,
    "assets",
    "voxos-tray.svg",
)

toggle_requested = False


def remove_pidfile():
    try:
        os.remove(PIDFILE)
    except FileNotFoundError:
        pass


def get_default_sink():
    result = subprocess.run(
        ["pactl", "get-default-sink"],
        check=True,
        capture_output=True,
        text=True,
    )
    sink = result.stdout.strip()

    if not sink:
        raise RuntimeError("pactl did not report a default audio output sink")

    return sink


def signal_toggle(signum, frame):
    global toggle_requested
    toggle_requested = True


class FocusOverlay(QWidget):
    def __init__(self, popup):
        super().__init__()
        self.popup = popup

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

    def show_for_screen(self, screen):
        self.setGeometry(screen.geometry())
        self.show()
        self.raise_()

    def mousePressEvent(self, event):
        self.popup.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 160))


class TTSPopup(QLineEdit):
    def __init__(self):
        super().__init__()

        self.volume = self.load_volume()
        self.submitted = False
        self.history = []
        self.history_index = 0
        self.current_draft = ""
        self.focus_overlay = None

        self.setWindowTitle("Voxos")
        self.setWindowIcon(QIcon(DESKTOP_ICON_PATH))
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setPlaceholderText("Type what you want to say...")
        self.resize(640, 60)
        self.setStyleSheet(
            """
            QLineEdit {
                background-color: #111827;
                border: 1px solid #3b82a0;
                border-radius: 18px;
                color: #f8fafc;
                font-size: 16px;
                padding: 0 20px;
                selection-background-color: #0e7490;
            }
            QLineEdit:focus {
                border: 2px solid #22b8c9;
            }
            QLineEdit::placeholder {
                color: #94a3b8;
            }
            """
        )

        self.load_history()

        # Restore previous unfinished text
        try:
            with open(DRAFT, "r", encoding="utf-8") as f:
                saved_text = f.read()
                self.setText(saved_text)
                self.setCursorPosition(len(saved_text))
                self.current_draft = saved_text
        except FileNotFoundError:
            pass

        self.returnPressed.connect(self.submit)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_toggle)
        self.timer.start(50)

    def load_volume(self):
        try:
            with open(VOLUME, "r", encoding="utf-8") as f:
                volume = int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return 100

        return max(0, min(volume, 100))

    def save_volume(self, volume):
        self.volume = volume
        os.makedirs(
            os.path.dirname(VOLUME),
            exist_ok=True
        )

        with open(VOLUME, "w", encoding="utf-8") as f:
            f.write(f"{volume}\n")

    def load_history(self):
        try:
            with open(HISTORY, "r", encoding="utf-8") as f:
                self.history = [
                    line.rstrip("\n")
                    for line in f
                    if line.strip()
                ]
        except FileNotFoundError:
            self.history = []

        self.history_index = len(self.history)

    def save_history_entry(self, text):
        os.makedirs(
            os.path.dirname(HISTORY),
            exist_ok=True
        )

        # Avoid immediately duplicating the same prompt
        if self.history and self.history[-1] == text:
            return

        self.history.append(text)

        # Keep only the most recent 100 prompts
        self.history = self.history[-100:]

        with open(HISTORY, "w", encoding="utf-8") as f:
            for entry in self.history:
                f.write(entry.replace("\n", " ") + "\n")

        self.history_index = len(self.history)

    def save_draft(self):
        os.makedirs(
            os.path.dirname(DRAFT),
            exist_ok=True
        )

        with open(DRAFT, "w", encoding="utf-8") as f:
            f.write(self.text())

    def check_toggle(self):
        global toggle_requested

        if toggle_requested:
            toggle_requested = False
            self.toggle_visibility()

    def show_popup(self):
        self.submitted = False
        screen = QApplication.primaryScreen()

        if self.focus_overlay:
            self.focus_overlay.show_for_screen(screen)

        self.move(
            screen.availableGeometry().center() - self.rect().center()
        )
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_popup(self):
        if self.focus_overlay:
            self.focus_overlay.hide()

        self.hide()

    def toggle_visibility(self):
        if self.isVisible():
            self.close()
        else:
            self.show_popup()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return

        if event.key() == Qt.Key_Up:
            self.history_up()
            return

        if event.key() == Qt.Key_Down:
            self.history_down()
            return

        super().keyPressEvent(event)

    def history_up(self):
        if not self.history:
            return

        # Save what you're currently typing before entering history
        if self.history_index == len(self.history):
            self.current_draft = self.text()

        if self.history_index > 0:
            self.history_index -= 1
            text = self.history[self.history_index]
            self.setText(text)
            self.setCursorPosition(len(text))

    def history_down(self):
        if not self.history:
            return

        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            text = self.history[self.history_index]
            self.setText(text)
            self.setCursorPosition(len(text))

        elif self.history_index == len(self.history) - 1:
            self.history_index = len(self.history)
            self.setText(self.current_draft)
            self.setCursorPosition(len(self.current_draft))

    def submit(self):
        text = self.text().strip()

        if not text:
            return

        self.submitted = True

        self.save_history_entry(text)

        try:
            os.remove(DRAFT)
        except FileNotFoundError:
            pass

        self.clear()
        self.current_draft = ""
        self.hide_popup()
        QApplication.processEvents()

        mp3 = tempfile.NamedTemporaryFile(
            suffix=".mp3",
            delete=False
        )

        wav = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        )

        mp3.close()
        wav.close()

        try:
            subprocess.run(
                [
                    *EDGE_TTS,
                    "--voice",
                    "pt-PT-DuarteNeural",
                    "--rate=+5%",
                    "--pitch=-18Hz",
                    "--text",
                    text,
                    "--write-media",
                    mp3.name,
                ],
                check=True,
            )

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    mp3.name,
                    wav.name,
                ],
                check=True,
            )

            default_sink = get_default_sink()

            discord_audio = subprocess.Popen(
                [
                    "paplay",
                    f"--device={VOXOS_SINK}",
                    f"--volume={self.volume * MAX_PULSE_VOLUME // 100}",
                    wav.name,
                ]
            )

            headphone_audio = subprocess.Popen(
                [
                    "paplay",
                    f"--device={default_sink}",
                    f"--volume={self.volume * MAX_PULSE_VOLUME // 100}",
                    wav.name,
                ]
            )

            discord_audio.wait()
            headphone_audio.wait()

        finally:
            for path in (mp3.name, wav.name):
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

    def closeEvent(self, event):
        if not self.submitted:
            self.save_draft()

        self.hide_popup()
        event.ignore()


signal.signal(
    signal.SIGUSR1,
    signal_toggle
)

app = QApplication([])
app.setDesktopFileName("voxos")
app.setQuitOnLastWindowClosed(False)

popup = TTSPopup()
focus_overlay = FocusOverlay(popup)
popup.focus_overlay = focus_overlay

tray = QSystemTrayIcon(QIcon(TRAY_ICON_PATH), app)
tray.setToolTip("Voxos")

tray_menu = QMenu()
show_action = QAction("Show Voxos", tray_menu)
show_action.triggered.connect(popup.show_popup)
volume_menu = QMenu(
    f"Playback volume ({popup.volume}%)",
    tray_menu
)
volume_group = QActionGroup(volume_menu)
volume_group.setExclusive(True)


def set_volume(volume):
    popup.save_volume(volume)
    volume_menu.setTitle(f"Playback volume ({volume}%)")


for volume in range(0, 101, 5):
    volume_action = QAction(f"{volume}%", volume_menu)
    volume_action.setCheckable(True)
    volume_action.setChecked(volume == popup.volume)
    volume_action.triggered.connect(
        lambda checked=False, value=volume: set_volume(value)
    )
    volume_group.addAction(volume_action)
    volume_menu.addAction(volume_action)

quit_action = QAction("Quit Voxos", tray_menu)
quit_action.triggered.connect(app.quit)
tray_menu.addAction(show_action)
tray_menu.addMenu(volume_menu)
tray_menu.addAction(quit_action)

tray.setContextMenu(tray_menu)
tray.show()

app.aboutToQuit.connect(remove_pidfile)

popup.show_popup()

sys.exit(app.exec())
