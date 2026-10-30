#!/usr/bin/env python3
"""Install this local plugin and add its icon to the Omarchy bar."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ID = 'local.monitor-layout'
SOURCE = Path(__file__).resolve().parent
FILES = ['manifest.json', 'WidgetV2.qml', 'EditorV2.qml', 'Layout.js', 'backend.py', 'README.md', 'LICENSE']


def run(*args):
    subprocess.run(args, check=True)


def main():
    run('omarchy', 'plugin', 'validate', str(SOURCE))
    run('omarchy-shell', 'shell', 'ping')
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config'))) / 'omarchy'
    plugins = config / 'plugins'
    target = plugins / ID
    if target.is_symlink():
        raise RuntimeError('The plugin directory is a symlink; refusing to replace it.')
    state = config / 'monitor-layout-backups'
    backup = state / ('install-' + str(time.time_ns()))
    backup.mkdir(parents=True)
    if (config/'shell.json').exists():
        shutil.copy2(config/'shell.json', backup/'shell.json')
    if target.exists():
        shutil.copytree(target, backup/ID)
    plugins.mkdir(parents=True, exist_ok=True)
    # Stage outside the discovery directory so hot reload never loads half a plugin.
    with tempfile.TemporaryDirectory(prefix='.monitor-layout-install-', dir=config) as temp:
        staging=Path(temp)/ID
        staging.mkdir()
        for name in FILES:
            shutil.copy2(SOURCE/name,staging/name)
        run('omarchy','plugin','validate',str(staging))
        if target.exists(): shutil.rmtree(target)
        try:
            os.replace(staging,target)
        except Exception:
            if (backup/ID).exists(): shutil.copytree(backup/ID,target)
            raise
    run('omarchy-shell','shell','rescanPlugins')
    run('omarchy','bar','put',ID,'--before','omarchy.bluetooth')
    # Omarchy's live reload cannot reliably invalidate Qt's compiled dependencies.
    run('omarchy','restart','shell')
    print(f'Installed {target}\nBackup: {backup}\nClick the dual-monitor icon in your bar to open Monitor Layout.')


if __name__=='__main__': main()
