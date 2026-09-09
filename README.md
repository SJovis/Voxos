# Voxos

Voxos is a text-to-speech utility for Linux. It provides a focused prompt, 
local playback through the active audio output, and a PipeWire 
virtual microphone that Discord can use.

## AI Assistance

This project was developed with assistance from AI tools.

## Features

- Launches from a KDE desktop entry, Favorites, or a global shortcut.
- Stays available in the system tray after the prompt is dismissed.
- Uses a rounded, padded prompt with a dimmed backdrop.
- Saves unfinished drafts and keeps the latest 100 prompts as history.
- Dismisses the prompt with Escape, the global shortcut, or a backdrop click.
- Sends generated speech to both the active local audio output and Discord.
- Selects the local output dynamically with `pactl get-default-sink`.

The default voice configuration is:

```text
Voice: pt-PT-DuarteNeural
Rate:  +5%
Pitch: -18Hz
```

## Requirements

- Nobara Linux with KDE Plasma, Wayland/KWin, and PipeWire PulseAudio support
- Python 3, PySide6, and edge-tts
- ffmpeg, paplay, pactl, and systemd

## Project Layout

```text
~/Projects/Voxos/
├── assets/
│   ├── voxos.svg
│   └── voxos-tray.svg
├── scripts/
│   └── voxos-audio
├── src/
│   ├── voxos-popup.py
│   └── voxos.sh
├── systemd/
│   └── voxos-audio.service
├── requirements.txt
├── voxos.desktop
└── README.md
```

## Setup

Create the development environment:

```bash
cd ~/Projects/Voxos
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Install the desktop entry, PipeWire helper, and user service:

```bash
install -Dm644 ~/Projects/Voxos/voxos.desktop \
  ~/.local/share/applications/voxos.desktop
install -Dm755 ~/Projects/Voxos/scripts/voxos-audio \
  ~/.local/bin/voxos-audio
install -Dm644 ~/Projects/Voxos/systemd/voxos-audio.service \
  ~/.config/systemd/user/voxos-audio.service
systemctl --user daemon-reload
systemctl --user enable --now voxos-audio.service
```

Search for **Voxos** in the KDE application launcher and select **Add to
Favorites** to pin it. If the project is moved, update the absolute `Exec` and
`Icon` paths in `voxos.desktop`, then reinstall the desktop entry.

The launcher uses `.venv/bin/python` when available. It falls back to the
legacy environment at `~/.local/share/voxos/edge-tts/bin/python`.

## Using Voxos

Launch Voxos:

```bash
~/Projects/Voxos/src/voxos.sh
```

Configure a KDE global shortcut, such as Ctrl+Enter, to run that command.
Running it while Voxos is already open toggles the prompt.

| Control | Action |
|---|---|
| Enter | Generate and speak the prompt |
| Escape | Dismiss the prompt and save its draft |
| Up Arrow | Show an older prompt |
| Down Arrow | Show a newer prompt |
| Click backdrop | Dismiss the prompt and save its draft |

The tray menu includes **Show Voxos** and **Quit Voxos**. Quitting is required
to stop the tray application completely.

## Discord Audio Routing

Voxos creates the following PipeWire PulseAudio-compatible devices:

```text
voxos_output
voxos_output.monitor
voxos_mic
```

Speech is played twice:

```text
Voxos text -> edge-tts -> temporary WAV
                       -> voxos_output -> voxos_output.monitor -> voxos_mic -> Discord
                       -> current PipeWire default output -> local monitoring
```

In Discord, choose **Voxos Microphone** as the input device. If it is missing,
start the service and then reopen Discord's audio settings:

```bash
systemctl --user start voxos-audio.service
pactl list short sources | grep voxos
```

To stop the virtual microphone service:

```bash
systemctl --user stop voxos-audio.service
```

## Local Data

| Data | Location |
|---|---|
| Prompt history | `~/.cache/voxos-history.txt` |
| Unfinished draft | `~/.cache/voxos-draft.txt` |
| Launcher PID | `/tmp/voxos-prompt.pid` |
| PipeWire module IDs | `$XDG_RUNTIME_DIR/voxos-audio.modules` |

## Privacy

The UI, history, audio conversion, and PipeWire routing are local. Prompt text
is sent to Microsoft's Edge TTS service to generate speech. Discord receives
the generated audio through the Voxos virtual microphone, not the original
prompt text.

## Current Limitations

- Speech generation and playback run on the GUI thread.
- There is no speech queue.
- Microsoft Edge TTS requires an internet connection.
- Failures from edge-tts, ffmpeg, PipeWire, and paplay have limited GUI
  feedback.
- Voice, rate, pitch, and history behavior are not configurable yet.

## License

This project is licensed under the [MIT License](LICENSE).
