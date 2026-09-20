# KickPresence

[English](README.md) | [Español](README.es.md)

Discord Rich Presence that automatically shows when your Kick channel is live.

- Real stream thumbnail as the large image
- Stream title, category and viewer count
- Elapsed time counter for the stream
- **Watch** button that links to the channel (only other users can see it, not you)
- Clickable title and image
- System tray icon with notifications when the stream starts and ends
- Settings window to pick your channel, no hand-editing files
- Single instance: it will not open twice

## Requirements

- Windows 10/11
- Discord desktop app running (presence is not published while it is closed)
- To build: Python 3.12 or newer

## Usage

1. Run `KickPresence.exe`
2. On first launch the settings window opens: type your Kick channel (you can paste `kick.com/your-channel`), click **Verify** and then **Save**
3. The tray icon stays. When you go live, the presence is published automatically

To change the channel: right-click the tray icon → **Configurar canal...** (Configure channel).

Settings are stored in `%APPDATA%\KickPresence\config.json`. If a `config.json` sits next to the `.exe`, that one is used instead (portable mode).

## Building

```powershell
.\compilar.bat
```

or

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Produces `dist\KickPresence.exe`. The script creates the virtual environment, installs the dependencies, regenerates the icon from `assets\rika-icon.jpg`, closes the app if it is running, and builds.

## Using your own Discord app

The `.exe` ships with a default Application ID so it works out of the box. If you want your own app (to change the name or the assets):

1. Create an application at https://discord.com/developers/applications
2. Copy the **Application ID** into `discord_client_id` in `config.json`
3. Under *Rich Presence → Art Assets* upload `kick-icon` (fallback large image) and `live_badge` (small badge), minimum 512x512, square

The app name is what shows up in the activity ("Playing ...").

## Configuration

| Key | Description |
|---|---|
| `discord_client_id` | Discord Application ID |
| `kick_channels` | Kick channels to monitor (the first one that is live wins) |
| `poll_interval_seconds` | How often the API is checked (minimum 15) |
| `refresh_interval_seconds` | How often the presence is re-sent |
| `show_viewers` / `show_category` / `show_elapsed_time` | Which fields to display |
| `notify_on_change` | Notifications when the stream starts and ends |
| `use_stream_thumbnail` | Use the real stream thumbnail |
| `clickable_urls` | Clickable title and image |
| `status_display_type` | `name`, `state` or `details`: text shown in the member list |
| `large_image_live` / `small_image_live` | Discord asset names |
| `button_label` | Button text |

## Project layout

| File | Role |
|---|---|
| `main.py` | Entry point, monitoring loop, system tray and CLI |
| `kick_api.py` | Kick API client |
| `presence.py` | Discord Rich Presence: reconnection, assets, error handling |
| `settings_ui.py` | Settings window (tkinter) |
| `config.py` | Configuration loading, validation and saving |
| `icon.py` | `.ico` and tray icon generation |
| `build.ps1` / `compilar.bat` | PyInstaller build |
| `instalar-autostart.ps1` | Start with Windows (`-Quitar` to disable) |

## Command line modes

| Command | What it does |
|---|---|
| `--setup` | Opens the settings window and exits |
| `--once` | Checks the channels once and prints the result |
| `--test` | Sends a test presence to Discord |
| `--dry-run` | Monitors without publishing anything to Discord |
| `--console` | Runs in console mode, without the tray icon |
| `--tray` | Forces tray mode |
| `-v`, `--verbose` | Verbose logging |

## Notes

- The **Watch** button does not appear on your own profile: that is a Discord limitation, only other users see it
- If an instance is already running, a second one shows a notice and exits
- Images in `assets/` belong to their respective authors; the code is free to use and modify
