"""Publisher validation tests. No network calls and no release writes."""
import io
import json
import unittest
import zipfile
import publish_release as pub

SHA = '0' * 40
VERSION = '0.5.0'
RUN = 10


def zip_bytes(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return out.getvalue()


def fixture(platform='windows-x64', **changes):
    root = f'No-ide-v{VERSION}-{platform}'
    pe = bytearray(100)
    pe[:2] = b'MZ'
    pe[60:64] = (64).to_bytes(4, 'little')
    pe[64:70] = b'PE\0\0\x64\x86'
    if platform == 'linux-x64':
        pe = bytearray(100);pe[:5] = b'\x7fELF\x02';pe[18:20] = b'\x3e\0'
    elif platform.startswith('macos'):
        pe = bytearray(100);pe[:4] = b'\xcf\xfa\xed\xfe'
        cpu = 0x0100000c if platform == 'macos-arm64' else 0x01000007
        pe[4:8] = cpu.to_bytes(4, 'little')
    exe = 'no-ide.exe' if platform == 'windows-x64' else 'no-ide'
    files = {exe: bytes(pe), pub.PLATFORMS[platform][1]: 'start',
             'web/index.html': '<html></html>', 'README.txt': 'Read me',
             'THIRD_PARTY_NOTICES.md': 'Licenses', 'agent/no-ide-agent.jar': b'fixture',
             'build.json': json.dumps({'version': VERSION, 'platform': platform, 'commit': SHA, 'run': str(RUN)})}
    files.update(changes)
    inner = zip_bytes({root+'/'+k: v for k, v in files.items() if v is not None})
    return zip_bytes({root+'.zip': inner})


class ValidationTests(unittest.TestCase):
    def unpack(self, data, platform='windows-x64', **kwargs):
        return pub.unpack_verified_package(data, kwargs.get('version', VERSION), platform,
                                           kwargs.get('commit', SHA), kwargs.get('run', RUN))

    def test_valid_windows(self): self.assertTrue(self.unpack(fixture())[0].endswith('windows-x64.zip'))
    def test_valid_linux(self): self.unpack(fixture('linux-x64'), 'linux-x64')
    def test_valid_arm_mac(self): self.unpack(fixture('macos-arm64'), 'macos-arm64')
    def test_valid_intel_mac(self): self.unpack(fixture('macos-x64'), 'macos-x64')
    def test_wrong_commit(self):
        with self.assertRaises(ValueError): self.unpack(fixture(), commit='1'*40)
    def test_wrong_run(self):
        with self.assertRaises(ValueError): self.unpack(fixture(), run=11)
    def test_wrong_version(self):
        with self.assertRaises(ValueError): self.unpack(fixture(), version='0.4.4')
    def test_wrong_architecture(self):
        with self.assertRaises(ValueError): self.unpack(fixture(**{'no-ide.exe': b'ELF'}))
    def test_missing_agent(self):
        with self.assertRaises(ValueError): self.unpack(fixture(**{'agent/no-ide-agent.jar': None}))
    def test_no_private_settings(self):
        with self.assertRaises(ValueError): self.unpack(fixture(**{'settings.json': '{}'}))
    def test_no_fonts(self):
        with self.assertRaises(ValueError): self.unpack(fixture(**{'web/font.woff2': b'font'}))
    def test_no_traversal(self):
        with self.assertRaises(ValueError): self.unpack(fixture(**{'../token': b'secret'}))
    def test_no_extra_artifact(self):
        with self.assertRaises(ValueError): self.unpack(zip_bytes({'source.zip': b'not-a-package'}))
    def test_no_duplicate_member(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as z:
            z.writestr('same', 'one');z.writestr('same', 'two')
        with zipfile.ZipFile(io.BytesIO(out.getvalue())) as z:
            with self.assertRaises(ValueError): pub.safe_members(z)


if __name__ == '__main__': unittest.main()
