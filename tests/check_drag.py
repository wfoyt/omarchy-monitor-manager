#!/usr/bin/env python3
"""Send real Qt mouse events through the editor inside Quickshell, offscreen."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

source=Path(__file__).resolve().parents[1]
shell=Path(os.environ.get('OMARCHY_PATH','/usr/share/omarchy'))/'shell'
with tempfile.TemporaryDirectory(prefix='monitor-layout-drag-') as temp:
    root=Path(temp)
    (root/'Commons').symlink_to(shell/'Commons',target_is_directory=True)
    (root/'Ui').symlink_to(shell/'Ui',target_is_directory=True)
    (root/'Plugin').mkdir()
    for name in ('EditorV2.qml','Layout.js'):
        shutil.copy2(source/name,root/'Plugin'/name)
    shutil.copy2(source/'tests/drag.qml',root/'shell.qml')
    (root/'runtime').mkdir(mode=0o700)
    native=os.environ.get('MONITOR_LAYOUT_NATIVE_TEST')=='1'
    display=os.environ.get('WAYLAND_DISPLAY','wayland-1')
    if not display.startswith('/'):
        display=str(Path(os.environ.get('XDG_RUNTIME_DIR','/run/user/'+str(os.getuid())))/display)
    env={**os.environ,'WAYLAND_DISPLAY':display,'QT_QPA_PLATFORM':'wayland' if native else 'offscreen','QT_QPA_PLATFORMTHEME':'basic',
         'QT_QUICK_CONTROLS_STYLE':'Basic','XDG_RUNTIME_DIR':str(root/'runtime')}
    result=subprocess.run(['quickshell','-p',str(root),'--no-color'],env=env,
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=20)
    if result.returncode or 'DRAG_TEST_PASS' not in result.stdout or 'DRAG_TEST_FAIL' in result.stdout:
        raise SystemExit(result.stdout)
    print('PASS ('+('native Wayland' if native else 'offscreen')+'): held horizontal/vertical drags with pauses, repeated grabs, stationary input surface and scrolling viewport.')
