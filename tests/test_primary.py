import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('backend',Path(__file__).resolve().parents[1]/'backend.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
POLICY='-- Custom policy\nlocal primary = "DP-1"\nlocal secondary = "HDMI-A-1"\n-- preserve all shortcuts\n'
class PrimaryTests(unittest.TestCase):
 def test_swap_preserves_policy_and_assigns_other_output(self):
  updated,secondary=b.primary_config(POLICY,'HDMI-A-1',['DP-1','HDMI-A-1'])
  self.assertIn('local primary = "HDMI-A-1"',updated)
  self.assertIn('local secondary = "DP-1"',updated)
  self.assertTrue(updated.endswith('-- preserve all shortcuts\n'))
  self.assertEqual(secondary,'DP-1')
 def test_reject_disconnected_and_injection(self):
  for name in ('DP-9','DP-1";bad()'):
   with self.assertRaises(ValueError):b.primary_config(POLICY,name,['DP-1','HDMI-A-1'])
 def test_failed_reload_restores_policy(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'dual-monitor.lua';path.write_text(POLICY)
   with patch.object(b,'primary_policy',return_value=path),patch.object(b,'monitors',return_value=[]),patch.object(b,'normalize',return_value=[{'name':'DP-1'},{'name':'HDMI-A-1'}]),patch.object(b,'hypr',side_effect=['[]','','broken config','']):
    with self.assertRaises(RuntimeError):b.set_primary('HDMI-A-1')
   self.assertEqual(path.read_text(),POLICY)
   self.assertEqual(len(list(Path(temp).glob('*.before-monitor-layout-*'))),1)
