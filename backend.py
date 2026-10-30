#!/usr/bin/env python3
"""Hyprland Lua display transactions. No shell interpolation or third-party deps."""
import fcntl
import json
import math
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import tempfile
import time

BEGIN = '-- BEGIN local.monitor-layout (managed)'
END = '-- END local.monitor-layout (managed)'
BLOCK = re.compile(re.escape(BEGIN) + r'\n(.*?)' + re.escape(END) + r'\n?', re.S)
MODE = re.compile(r'^(\d+)x(\d+)@([\d.]+)(?:Hz)?$')
NAME = re.compile(r'^[A-Za-z0-9._-]+$')


def emit(**data):
    try:
        print(json.dumps(data), flush=True)
    except BrokenPipeError:
        pass


def hypr(*args):
    p = subprocess.run(['hyprctl', *args], text=True, capture_output=True, timeout=8)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout).strip() or 'Hyprland is unavailable')
    result = p.stdout.strip()
    if any(s in result.lower() for s in ('error', 'invalid', 'failed')):
        raise RuntimeError(result)
    return result


def monitors():
    data = json.loads(hypr('-j', 'monitors', 'all'))
    if not isinstance(data, list):
        raise ValueError('Unexpected monitor response')
    return data


def normalize(raw):
    result = []
    for m in raw:
        if m.get('disabled') or not m.get('width') or not m.get('height'):
            continue
        if not NAME.fullmatch(m['name']):
            raise ValueError('Unsupported connector name')
        modes = []
        for value in m.get('availableModes', []):
            match = MODE.fullmatch(value)
            if match:
                w, h, hz = match.groups()
                item = dict(width=int(w), height=int(h), rate=float(hz))
                if item not in modes:
                    modes.append(item)
        current = dict(width=m['width'], height=m['height'], rate=m['refreshRate'])
        matched = next((x for x in modes if x['width'] == current['width'] and x['height'] == current['height'] and abs(x['rate'] - current['rate']) < .02), None)
        if matched:
            current['rate'] = matched['rate']
        else:
            modes.insert(0, current)
        result.append(dict(name=m['name'], description=m.get('description', m['name']),
                           width=m['width'], height=m['height'], rate=current['rate'],
                           x=m['x'], y=m['y'], scale=m['scale'], transform=m.get('transform', 0),
                           mirror=m.get('mirrorOf', 'none'), vrr=int(bool(m.get('vrr', False))),
                           bitdepth=10 if '2101010' in m.get('currentFormat', '') else 8,
                           modes=modes))
    return result


def valid_scales(width, height):
    # Hyprland represents scale in 1/120 steps and requires whole logical pixels.
    divisor = math.gcd(int(width) * 120, int(height) * 120)
    values = [k / 120 for k in range(60, 481) if divisor % k == 0]
    return values


def logical(m):
    w, h = m['width'], m['height']
    if m.get('transform', 0) % 2:
        w, h = h, w
    return w / m['scale'], h / m['scale']


def validate(draft, live):
    if not isinstance(draft, list) or not draft:
        raise ValueError('No displays selected')
    current = {m['name']: m for m in live}
    if len(draft) != len(current) or {m.get('name') for m in draft} != set(current):
        raise ValueError('Displays changed. Reload the connected displays and try again.')
    clean = []
    for d in draft:
        old = current[d['name']]
        if old.get('mirror') not in (None, '', 'none'):
            raise ValueError('Mirrored displays are not supported. Extend the displays first.')
        values = [d.get(k) for k in ('width', 'height', 'rate', 'scale', 'x', 'y')]
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise ValueError('Display values must be finite numbers')
        if any(d[k] != int(d[k]) for k in ('width', 'height', 'x', 'y')):
            raise ValueError('Resolution and position must be whole pixels')
        if max(abs(d['x']), abs(d['y'])) > 32768:
            raise ValueError('Position is outside the supported layout area')
        if not any(m['width'] == d['width'] and m['height'] == d['height'] and abs(m['rate'] - d['rate']) < .02 for m in old['modes']):
            raise ValueError(f"Unsupported resolution or refresh rate for {d['name']}")
        # Permit the current scale as well as clean values, to preserve existing setups.
        if not (d['width'] == old['width'] and d['height'] == old['height'] and abs(d['scale'] - old['scale']) < .00001) and not any(abs(d['scale'] - s) < .00001 for s in valid_scales(d['width'], d['height'])):
            raise ValueError(f"Scale is incompatible with {d['width']} × {d['height']}")
        if not .25 <= d['scale'] <= 4:
            raise ValueError('Scale must be between 25% and 400%')
        clean.append({**old, **{k: d[k] for k in ('width', 'height', 'rate', 'scale', 'x', 'y')}})
    for i, a in enumerate(clean):
        aw, ah = logical(a)
        for b in clean[i+1:]:
            bw, bh = logical(b)
            if min(a['x']+aw, b['x']+bw) - max(a['x'], b['x']) > 1 and min(a['y']+ah, b['y']+bh) - max(a['y'], b['y']) > 1:
                raise ValueError('Displays overlap. Drag them apart or use Arrange in a row.')
    return clean


def rule(m):
    # Connector names were validated above; strings are encoded as Lua literals.
    return ('hl.monitor({ output = "%s", mode = "%dx%d@%g", position = "%dx%d", '
            'scale = %.8g, transform = %d, vrr = %d, bitdepth = %d })' %
            (m['name'], m['width'], m['height'], m['rate'], m['x'], m['y'],
             m['scale'], m.get('transform', 0), m.get('vrr', 0), m.get('bitdepth', 8)))


def apply(displays):
    hypr('eval', '\n'.join(rule(m) for m in displays))


def verify(displays):
    actual = {m['name']: m for m in normalize(monitors())}
    for d in displays:
        a = actual.get(d['name'])
        if not a or any(a[k] != d[k] for k in ('width', 'height', 'x', 'y', 'transform')) or abs(a['scale'] - d['scale']) > .01 or abs(a['rate'] - d['rate']) > 1:
            raise RuntimeError('Hyprland did not accept the requested layout. Previous settings restored.')


def merged_config(original, displays):
    matches = list(BLOCK.finditer(original))
    if original.count(BEGIN) != len(matches) or original.count(END) != len(matches) or len(matches) > 1:
        raise ValueError('The managed monitor block was edited. Repair its markers before saving.')
    lines = {}
    if matches:
        for line in matches[0].group(1).splitlines():
            m = re.match(r'hl\.monitor\(\{ output = "([A-Za-z0-9._-]+)"', line)
            if m:
                lines[m[1]] = line
    for d in displays:
        lines[d['name']] = rule(d)
    base = BLOCK.sub('', original).rstrip()
    return base + '\n\n' + BEGIN + '\n' + '\n'.join(lines.values()) + '\n' + END + '\n'


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        if path.exists():
            os.chmod(tmp, path.stat().st_mode & 0o777)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def config_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'hypr/monitors.lua'


def save(displays):
    path = config_path()
    if path.is_symlink():
        raise ValueError('monitors.lua is a symlink. Resolve it before using persistent saves.')
    original = path.read_text() if path.exists() else ''
    updated = merged_config(original, displays)
    backup = path.with_name(path.name + '.before-monitor-layout-' + str(time.time_ns()))
    atomic_write(backup, original)
    try:
        atomic_write(path, updated)
        hypr('reload')
        errors = hypr('configerrors')
        if errors:
            raise RuntimeError('Hyprland configuration error: ' + errors)
        verify(displays)
    except Exception:
        atomic_write(path, original)
        hypr('reload')
        raise
    return str(backup)


def transaction():
    # Held across preview and confirmation, preventing two bars/editors racing.
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'omarchy/monitor-layout'
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'preview.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another display preview is already running')
        line = sys.stdin.readline()
        if not line:
            return
        draft = json.loads(line)
        before = normalize(monitors())
        target = validate(draft, before)
        committed = False
        try:
            apply(target)
            verify(target)
            deadline = time.monotonic() + 20
            emit(event='preview', seconds=20)
            while time.monotonic() < deadline:
                ready, _, _ = select.select([sys.stdin], [], [], min(1, max(0, deadline-time.monotonic())))
                if ready:
                    command = sys.stdin.readline().strip()
                    if command == 'keep':
                        # Hotplug invalidates the transaction, including while confirming.
                        validate(target, normalize(monitors()))
                        backup = save(target)
                        committed = True
                        emit(event='kept', backup=backup)
                        return
                    if command in ('revert', ''):
                        break  # EOF (shell crash/reload) also restores the layout.
                emit(event='tick', seconds=max(0, math.ceil(deadline-time.monotonic())))
        finally:
            if not committed:
                try:
                    apply(before)
                    emit(event='reverted')
                except Exception as e:
                    emit(event='error', message='Could not restore displays: ' + str(e))


def primary_policy():
    return config_path().with_name('dual-monitor.lua')


def read_primary():
    path = primary_policy()
    if not path.exists(): return ''
    match = re.search(r'^local primary = "([A-Za-z0-9._-]+)"$', path.read_text(), re.M)
    return match[1] if match else ''


def primary_config(original, name, connected):
    if not NAME.fullmatch(name) or name not in connected:
        raise ValueError('Choose a connected display')
    first = re.search(r'^local primary = "([A-Za-z0-9._-]+)"$', original, re.M)
    second = re.search(r'^local secondary = "([A-Za-z0-9._-]+)"$', original, re.M)
    if not first or not second:
        raise ValueError('The workspace policy is not compatible with primary monitor selection')
    other = first[1] if name != first[1] else second[1]
    if other == name or other not in connected:
        other = next((n for n in connected if n != name), '')
    if not other: raise ValueError('This workspace policy requires two connected displays')
    updated = re.sub(r'^local primary = "[A-Za-z0-9._-]+"$', 'local primary = "'+name+'"', original, flags=re.M)
    updated = re.sub(r'^local secondary = "[A-Za-z0-9._-]+"$', 'local secondary = "'+other+'"', updated, flags=re.M)
    return updated, other


def set_primary(name):
    path = primary_policy()
    if not path.exists() or path.is_symlink():
        raise ValueError('A regular dual-monitor.lua workspace policy is required')
    connected = [m['name'] for m in normalize(monitors())]
    original = path.read_text()
    updated, secondary = primary_config(original, name, connected)
    previous = json.loads(hypr('-j', 'workspaces'))
    backup = path.with_name(path.name+'.before-monitor-layout-'+str(time.time_ns()))
    atomic_write(backup, original)
    try:
        atomic_write(path, updated)
        hypr('reload')
        errors = hypr('configerrors')
        if errors: raise RuntimeError(errors)
        for workspace in previous:
            wid = workspace['id']
            if 1 <= wid <= 10:
                hypr('dispatch', 'moveworkspacetomonitor', str(wid)+' '+name)
            elif workspace['name'] == 'dedicated':
                hypr('dispatch', 'moveworkspacetomonitor', 'name:dedicated '+secondary)
        hypr('eval', 'hl.dispatch(hl.dsp.focus({ monitor = "'+name+'" }))')
    except Exception:
        atomic_write(path, original)
        hypr('reload')
        for workspace in previous:
            if workspace['monitor'] in connected:
                selector = str(workspace['id']) if workspace['id'] > 0 else 'name:'+workspace['name']
                hypr('dispatch', 'moveworkspacetomonitor', selector+' '+workspace['monitor'])
        raise
    emit(event='primarySaved', primary=name, backup=str(backup))


def main():
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    try:
        if len(sys.argv) != 2:
            raise ValueError('Expected read or preview')
        if sys.argv[1] == 'read':
            emit(event='displays', displays=normalize(monitors()), primary=read_primary())
        elif sys.argv[1] == 'primary':
            set_primary(sys.stdin.readline().strip())
        elif sys.argv[1] == 'preview':
            # Detached worker survives QProcess destruction/SIGKILL on a shell reload.
            # It keeps the pipe descriptors; shell EOF triggers rollback in transaction().
            worker = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker'],
                                      start_new_session=True)
            return worker.wait()
        elif sys.argv[1] == 'worker':
            transaction()
        else:
            raise ValueError('Unknown command')
    except Exception as e:
        emit(event='error', message=str(e))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
