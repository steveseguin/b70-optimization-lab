"""Unit names come from the actual lanequeue builder; unrelated packets refuse."""
import unittest
import window as W
from launch_identity import unit_name


def cgroup(unit, user=True):
    return '0::/' + ('user.slice/user-1000.slice/user@1000.service/app.slice/' if user else 'system.slice/') + unit + '\n'


class LaunchUnit(unittest.TestCase):
    def test_both_proposed_units(self):
        for name in ('packet58ab-smoke-A', 'packet58ab-v5-A'):
            W.user_unit_gate(cgroup(unit_name(dict(name=name, lane='A', argv=[]))))

    def test_coordinator_chain(self):
        W.user_unit_gate(cgroup('packet58-coordinator.service'))

    def test_other_units_refused(self):
        for name in ('packet58r-smoke-A', 'packet58t-v5-A', 'packet58p-WS128-A',
                     'packet58xv-smoke-A', 'unrelated', 'packet58-smoke-A'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                W.user_unit_gate(cgroup(unit_name(dict(name=name, lane='A', argv=[]))))

    def test_user_service_required(self):
        unit = unit_name(dict(name='packet58ab-smoke-A', lane='A', argv=[]))
        for group in (cgroup(unit, user=False), cgroup(unit.replace('.service', '.scope')),
                      cgroup(unit + '/child'), '0::/\n'):
            with self.subTest(group=group), self.assertRaises(ValueError):
                W.user_unit_gate(group)
