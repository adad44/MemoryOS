# Phase 5 Mac Menu Bar App

Phase 5 adds a compact macOS menu bar app and launch-agent packaging for login startup.

## Build

Build the daemon:

```sh
scripts/build_daemon.sh
```

Build the menu bar app bundle:

```sh
scripts/build_menubar.sh
```

Output:

```text
menubar/dist/MemoryOS.app
```

## Run

Start the backend and web UI first:

```sh
scripts/run_backend.sh
cd web && npm run dev
```

Open the menu bar app:

```sh
open menubar/dist/MemoryOS.app
```

The normal installer builds and opens this app automatically:

```sh
scripts/install_memoryos.sh
```

## Menu Bar Controls

- Backend status.
- Capture count.
- Index readiness.
- Latest capture timestamp.
- Capture active/paused state.
- Compact hosted MemoryOS dropdown panel.
- Outline-only MemoryOS circuit-brain menu bar icon.
- Setup panel for macOS permissions, hidden by default until opened.
- Accessibility status and shortcut to the Accessibility privacy pane.
- Full Disk Access review shortcut for file capture.
- Screen Recording fallback status and request action.
- Open Search.
- Pause/Resume Capture.
- Refresh Index.
- Open backend API docs.
- Backend URL and web URL settings.
- Quit.

## Permission Onboarding

The menu bar app now includes a SwiftUI setup panel for local macOS permissions:

- Accessibility is required for `AXUIElement` active-window text capture. The setup panel checks `AXIsProcessTrusted()`, can trigger the macOS prompt, and opens the Accessibility privacy pane.
- Full Disk Access is recommended for broader file capture. macOS does not provide a public API to grant this automatically, so the setup panel opens the Full Disk Access privacy pane and performs a best-effort protected-folder read check.
- Screen Recording is listed as fallback-only. The current daemon does not use screenshot OCR for normal capture, but the setup panel can request/open the Screen Recording pane for future fallback work.

## Pause Capture

The menu bar app toggles:

```text
~/Library/Application Support/MemoryOS/capture.paused
```

The Swift daemon checks this flag before saving Accessibility and file captures. When the flag exists, capture is paused. Removing it resumes capture.

## Launch Agents

Install daemon launch at login:

```sh
scripts/install_daemon_launch_agent.sh
```

Install backend launch at login:

```sh
scripts/install_backend_launch_agent.sh
```

Uninstall daemon launch agent:

```sh
scripts/uninstall_daemon_launch_agent.sh
```

Uninstall backend launch agent:

```sh
scripts/uninstall_backend_launch_agent.sh
```

Install menu bar launch at login:

```sh
scripts/install_menubar_launch_agent.sh
```

Uninstall menu bar launch agent:

```sh
scripts/uninstall_menubar_launch_agent.sh
```

The plist files are written to:

```text
~/Library/LaunchAgents/com.memoryos.daemon.plist
~/Library/LaunchAgents/com.memoryos.backend.plist
~/Library/LaunchAgents/com.memoryos.menubar.plist
```

## Notes

The menu bar app is packaged with `LSUIElement=true`, so it runs as a menu bar utility instead of a normal Dock app.

`scripts/build_menubar.sh` uses direct `swiftc` compilation and copies `menubar/Assets/memoryos-menubar-logo.svg` into the app bundle so the menu bar icon matches the public MemoryOS brand mark without the dark square background.
