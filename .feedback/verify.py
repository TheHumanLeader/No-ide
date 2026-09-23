from pathlib import Path
import hashlib,json
root=Path.cwd()
p=root/'.github/workflows/native.yml';s=p.read_text();s=s.replace('      - name: Real 150-file grouping and Maven startup regressions','      - name: Real build task progress and cancellation\n        if: runner.os == \'Linux\' || runner.os == \'Windows\'\n        run: python tests/build-feedback-051.py\n      - name: Real 150-file grouping and Maven startup regressions');p.write_text(s)
p=root/'package.json';d=json.loads(p.read_text());d['scripts']['check']+=' && node --check src/activity-model.js && node --check src/build-activity.js';d['scripts']['test']+=' tests/activity-model.test.js';p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
expected={
  '.github/workflows/native.yml':'2a7ef069b9626bd36d488dfe65d5040da9ff3141e46a7a7378f09baac79456e8',
  'backend/Cargo.toml':'e8b3609ef1f09504abc3cbe8d9dfe8e5fc02174f5df6e817d19b9c837b32c825',
  'backend/src/activity.rs':'4d00d91860102b81359065fac861891e98f1c5aca68343e802c08d64ea79fc79',
  'backend/src/incremental.rs':'68fb212f2f6852ed98605d87fd4ad8ea1078e6e304b7f7fd834a2e3d0c9e9d76',
  'backend/src/main.rs':'78ebec840bd767a73f375e0484aa026622d5fcc82eff413815e7d8ab4a81969d',
  'backend/src/runtime.rs':'2863830772dbccc220ddcb3cf3a9ff5a9bbac63152401b245dac5574e85df0d7',
  'package.json':'4aae773aca8cd5be4b7bacdd4f59997a28f3db15032957e7f11e7b47df869dcc',
  'prd/build-feedback-v0.5.1.md':'a1ceb00fe5d04769ce4f83a687f8662cb3915c4fdd0a5a93c1a69db2808f54d1',
  'src/activity-model.js':'3447b86efcced35b8a28d911faf95a8e10e324af2839962ad5fad7d4e2896a4e',
  'src/build-activity.css':'c1629bc093eecd9a27a5feaedc7d77d47f0222fea5f50a8be1caa5421f0a1680',
  'src/build-activity.js':'70c72ca03de40f48ffa5323b4d8f13bf943de04f508a365b8f4744c79b3c788e',
  'src/incremental-workbench.js':'ecd4f8d225e3019e0fc4dd1b84911d64e420562505793e4dd9c78907bce5aca2',
  'src/live-workbench.js':'94232d6870fda30036a0cf85ce824b71ffe237d49d6d04a60e7e423e6af2f5ef',
  'src/runtime-logs.js':'31e2ac02d0aae386458bb2bfef24ab67ed449f53c01ad9e8624030e760f80a3f',
  'tests/activity-model.test.js':'73db8b9ca9ed0efa5f4d2374a06d9e3831da843a5185555aee62687b86a36922',
  'tests/browser-v04.py':'d3cc5ae3e3d1a6ed9a1be348eeae8e49b8c939bf8334d3f89c0f25aa7d2e80e0',
  'tests/build-feedback-051.py':'7c128fc14aa848bec4cbc8f663d1615f5b933d5e87128643888c91c05a250feb',
  'tests/log-scroll.py':'adadad35c89b15a7cfb0c93f7156a8589df3213c08a27a72d117aa5a89fadfec',
  'tests/native-browser.py':'95a0da3882b4a84a25d32950838cfc1c2b11265877322815bf54aae877df09b6'
}
failed=[]
for name,wanted in expected.items():
 actual=hashlib.sha256((root/name).read_bytes()).hexdigest()
 print(name,actual,actual==wanted)
 if actual!=wanted:failed.append(name)
if failed:raise SystemExit('Refusing changed patch: '+', '.join(failed))
