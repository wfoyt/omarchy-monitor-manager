import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('backend', ROOT / 'backend.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

RAW = [dict(name='DP-1',description='Acer',width=2560,height=1440,refreshRate=144.0,
            x=0,y=0,scale=1.25,transform=0,vrr=False,currentFormat='XRGB8888',mirrorOf='none',
            availableModes=['2560x1440@144.00Hz','2560x1440@60.00Hz']),
       dict(name='HDMI-A-1',description='XEC',width=1920,height=1080,refreshRate=75.0,
            x=2048,y=0,scale=1.0,transform=0,vrr=False,currentFormat='XRGB8888',mirrorOf='none',
            availableModes=['1920x1080@75.00Hz','1920x1080@60.00Hz'])]

class Validation(unittest.TestCase):
    def setUp(self):
        self.live=b.normalize(copy.deepcopy(RAW)); self.draft=copy.deepcopy(self.live)
    def test_current_refresh_matches_advertised_dropdown_option(self):
        raw=copy.deepcopy(RAW);raw[0]['refreshRate']=143.99999
        self.assertEqual(b.normalize(raw)[0]['rate'],144.0)
    def test_accepts_supported_modes_negative_coordinates_and_fractional_scale(self):
        self.draft[0]['x']=-2048; self.draft[1]['x']=0
        self.assertEqual(b.validate(self.draft,self.live)[0]['scale'],1.25)
    def test_rejects_overlap(self):
        self.draft[1]['x']=100
        with self.assertRaisesRegex(ValueError,'overlap'): b.validate(self.draft,self.live)
    def test_rejects_unsupported_rate(self):
        self.draft[0]['rate']=240
        with self.assertRaisesRegex(ValueError,'Unsupported'): b.validate(self.draft,self.live)
    def test_rejects_fractional_scale_with_non_integer_logical_pixels(self):
        self.draft[0]['scale']=1.5
        with self.assertRaisesRegex(ValueError,'incompatible'): b.validate(self.draft,self.live)
    def test_rejects_nan_and_lua_injection(self):
        self.draft[0]['x']=float('nan')
        with self.assertRaisesRegex(ValueError,'finite'): b.validate(self.draft,self.live)
        raw=copy.deepcopy(RAW); raw[0]['name']='DP-1");os.execute("bad")'
        with self.assertRaisesRegex(ValueError,'connector'): b.normalize(raw)
    def test_rejects_hotplug_and_duplicate_connectors(self):
        with self.assertRaisesRegex(ValueError,'changed'): b.validate(self.draft,self.live[:1])
        self.draft[1]=self.draft[0]
        with self.assertRaisesRegex(ValueError,'changed'): b.validate(self.draft,self.live)
    def test_preserves_rotation(self):
        self.live[0]['transform']=1; self.draft[0]['transform']=1
        self.draft[1]['x']=1152
        result=b.validate(self.draft,self.live)
        self.assertEqual(b.logical(result[0]),(1152,2048))
        self.assertIn('transform = 1',b.rule(result[0]))
    def test_rejects_mirrors(self):
        self.live[1]['mirror']='DP-1'
        with self.assertRaisesRegex(ValueError,'Mirrored'): b.validate(self.draft,self.live)
    def test_merge_retains_manual_rules_and_unplugged_display(self):
        old='-- My setup\nhl.env("GDK_SCALE", "1")\n'
        saved=b.merged_config(old,self.live)
        again=b.merged_config(saved,[{**self.live[0],'rate':60}])
        self.assertTrue(again.startswith(old))
        self.assertEqual(again.count(b.BEGIN),1)
        self.assertEqual(again.count('output = "HDMI-A-1"'),1)
        self.assertIn('@60"',again)
    def test_malformed_managed_block_is_not_silently_replaced(self):
        with self.assertRaisesRegex(ValueError,'markers'): b.merged_config(b.BEGIN+'\n',self.live)
    def test_failed_reload_restores_original_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'monitors.lua'; original='-- Existing user config\n';path.write_text(original)
            with patch.object(b,'config_path',return_value=path), patch.object(b,'hypr',side_effect=['','bad config','']):
                with self.assertRaisesRegex(RuntimeError,'configuration error'): b.save(self.live)
            self.assertEqual(path.read_text(),original)
            backups=list(path.parent.glob('*.before-monitor-layout-*'))
            self.assertEqual(len(backups),1)
            self.assertEqual(backups[0].read_text(),original)

# Emulates only the actual hyprctl boundary. Preview subprocesses, locks, pipes,
# watchdog lifetime and persistence execute normally in an isolated HOME.
FAKE = r'''#!/usr/bin/env python3
import json,os,re,sys
from pathlib import Path
state=Path(os.environ['FAKE_STATE'])
data=json.loads(state.read_text())
args=sys.argv[1:]
if args==['-j','monitors','all']:
 print(json.dumps(data));sys.exit()
if args[0]=='eval':
 for line in args[1].splitlines():
  name=re.search(r'output = "([^"]+)"',line)[1]
  m=next((v for v in data if v['name']==name),None)
  if m is None: continue
  w,h,r=re.search(r'mode = "(\d+)x(\d+)@([\d.]+)"',line).groups()
  x,y=re.search(r'position = "(-?\d+)x(-?\d+)"',line).groups()
  s=re.search(r'scale = ([\d.]+)',line)[1]
  m.update(width=int(w),height=int(h),refreshRate=float(r),x=int(x),y=int(y),scale=float(s))
 state.write_text(json.dumps(data));print('ok')
elif args[0]=='reload': print('ok')
elif args[0]=='configerrors': print('')
else: sys.exit(2)
'''

class Transactions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.home=Path(self.tmp.name)
        binary=self.home/'hyprctl';binary.write_text(FAKE);binary.chmod(0o755)
        self.state=self.home/'displays.json';self.state.write_text(json.dumps(RAW))
        self.env={**os.environ,'PATH':str(self.home)+os.pathsep+os.environ['PATH'],
                  'XDG_STATE_HOME':str(self.home/'state'),'XDG_CONFIG_HOME':str(self.home/'config'),'FAKE_STATE':str(self.state)}
        self.proc=None
    def tearDown(self):
        if self.proc:
            if self.proc.poll() is None:
                try: self.proc.stdin.write('revert\n'); self.proc.stdin.flush()
                except (BrokenPipeError,ValueError): pass
                self.proc.wait(timeout=10)
            for pipe in (self.proc.stdin,self.proc.stdout,self.proc.stderr):
                if pipe and not pipe.closed: pipe.close()
        self.tmp.cleanup()
    def start(self):
        self.proc=subprocess.Popen([sys.executable,str(ROOT/'backend.py'),'preview'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=self.env)
        draft=b.normalize(copy.deepcopy(RAW));draft[0]['rate']=60
        self.proc.stdin.write(json.dumps(draft)+'\n');self.proc.stdin.flush()
        self.assertEqual(self.event()['event'],'preview')
        self.assertEqual(json.loads(self.state.read_text())[0]['refreshRate'],60)
    def event(self,timeout=10):
        ready,_,_=select.select([self.proc.stdout],[],[],timeout)
        self.assertTrue(ready,'Backend did not produce a response')
        line=self.proc.stdout.readline()
        if not line: self.fail('Backend exited unexpectedly: '+self.proc.stderr.read())
        return json.loads(line)
    def restored(self):
        self.assertEqual(json.loads(self.state.read_text())[0]['refreshRate'],144)
    def test_explicit_revert_does_not_write_config(self):
        self.start();self.proc.stdin.write('revert\n');self.proc.stdin.flush()
        self.proc.wait(timeout=10);self.restored()
        self.assertFalse((self.home/'config/hypr/monitors.lua').exists())
    def test_confirmation_persists_only_after_keep(self):
        self.start();self.assertFalse((self.home/'config/hypr/monitors.lua').exists())
        self.proc.stdin.write('keep\n');self.proc.stdin.flush();self.proc.wait(timeout=10)
        self.assertEqual(self.proc.returncode,0)
        config=(self.home/'config/hypr/monitors.lua').read_text()
        self.assertIn('@60"',config);self.assertIn(b.BEGIN,config)
    def test_eof_reverts(self):
        self.start();self.proc.stdin.close();self.proc.wait(timeout=10);self.restored()
    def test_shell_reload_killing_parent_leaves_watchdog_to_restore(self):
        self.start();self.proc.kill();self.proc.wait(timeout=10)
        self.proc.stdin.close()
        # Detached worker owns stdout until it finishes its rollback.
        self.proc.stdout.read();self.restored()
    def test_twenty_second_timeout_reverts(self):
        self.start();self.proc.wait(timeout=27);self.restored()
        self.assertFalse((self.home/'config/hypr/monitors.lua').exists())

if __name__=='__main__': unittest.main()
