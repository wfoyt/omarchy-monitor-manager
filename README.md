# Monitor Layout for Omarchy

A native Omarchy shell plugin for arranging monitors and setting each display's refresh rate, resolution and scale. Uses the active Omarchy shell palette, typography, spacing, borders and native controls. Theme changes apply live.

## Install

Requires Omarchy 4's Quickshell plugin system, Hyprland's Lua configuration API, and Python 3. No additional Python packages or privileged installation needed.

From this folder, in your Omarchy session:

```bash
python3 install.py
```

The installer backs up your shell configuration, installs the plugin in `~/.config/omarchy/plugins/local.monitor-layout/`, and adds a dual-monitor icon immediately before Bluetooth. Your brightness controls remain available. It restarts the shell to load the current plugin code and does not change your monitor layout.

Open it by clicking that icon, or run:

```bash
omarchy-shell local.monitor-layout open
```

## Using the editor

- Drag the numbered displays to match your desk. Edges snap together when you release.
- Select a display on the map or with the buttons below it.
- Choose its resolution, advertised refresh rate and scale. Larger scale makes content bigger. Only scale values compatible with whole logical pixels are offered.
- For precision, use Horizontal position and Vertical position. Coordinates use scaled pixels; negative positions are supported. Tab focuses controls. Arrow keys on a display move it 10 pixels; Shift + arrow moves it one pixel.
- **Arrange in a row** aligns displays side by side at their top edges.
- **Reset edits** discards local edits. **Reload** reads the current connected displays and discards edits.
- **Preview changes** temporarily applies your layout. **Keep changes** saves it. **Revert**, Escape during preview, or a 20-second timeout restores the previous layout.

Preview has an independent watchdog that also restores settings if the shell closes or reloads. No configuration file is changed until you keep the preview. Closing the panel leaves the watchdog running; reopen it to keep or revert.

Saved rules are placed in a clearly marked managed block at the end of `~/.config/hypr/monitors.lua`. Existing manual configuration outside that block stays intact. Previously managed rules for currently disconnected monitors are retained. Each save creates a timestamped copy beside `monitors.lua`, reloads Hyprland, checks config errors, and verifies the applied layout. On failure the original file and runtime settings are restored.

The plugin preserves current rotation, active VRR state and 8/10-bit pixel depth in its monitor rules. The panel is for active, extended displays; monitor disabling, mirroring, HDR/color-management editing, and workspace assignment are outside this version. Custom color profiles or other advanced monitor options should be reviewed before adopting generated rules. Hotplug during a preview cancels confirmation until you reload. Overlapping displays are rejected.

## Remove

```bash
omarchy plugin disable local.monitor-layout
```

Then remove its user plugin directory if desired. Saved monitor settings remain in `monitors.lua`. To remove those settings, delete the `BEGIN local.monitor-layout` / `END local.monitor-layout` block (or restore the timestamped backup), then run `hyprctl reload` and `hyprctl configerrors`.

## Verify

```bash
omarchy plugin validate .
python3 -m unittest discover -s tests -v
node tests/test_layout.cjs
python3 tests/check_drag.py
MONITOR_LAYOUT_NATIVE_TEST=1 python3 tests/check_drag.py
```

The Python suite exercises real preview subprocesses using an isolated fake compositor: explicit rollback, timeout, pipe closure, shell process death, confirmation, validation, and config recovery. It never changes the real displays.

Version 1.0.2 moves the arrangement canvas outside the scrolling settings and uses a stationary, exclusive DragHandler for sustained mouse and touch gestures. Regression checks hold the button through pauses, horizontal and vertical movements, repeated drags, and smaller windows. The native Wayland check opens a temporary test window.

## Primary monitor

Select a monitor and choose **Make primary**. This saves your existing dual-monitor workspace policy: workspaces 1–10 and their shortcuts follow the primary display; the other display keeps the dedicated workspace. The policy is backed up before applying, and failures restore it. Complete or discard layout edits before changing primary. This is a workspace preference, not a universal Wayland primary flag.
