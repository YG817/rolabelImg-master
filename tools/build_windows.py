"""Build, frozen-test and package a Windows x64 release using the active Python."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONFIG = runpy.run_path(str(ROOT / 'app_version.py'))
VERSION = CONFIG['APP_VERSION']


def run(*args):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iscc', help='Absolute path to Inno Setup 6/7 ISCC.exe')
    stages = parser.add_mutually_exclusive_group()
    stages.add_argument('--exe-only', action='store_true', help='Build and smoke-test the client only')
    stages.add_argument('--installer-only', action='store_true', help='Package an existing client of the current version')
    args = parser.parse_args()
    if sys.platform != 'win32' or platform.architecture()[0] != '64bit':
        parser.error('Run with a 64-bit Python on Windows')
    if sys.version_info[:3] == (3, 10, 0):
        parser.error('PyInstaller does not support Python 3.10.0; use Python 3.12')
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct)
    version = tuple(map(int, VERSION.split('.'))) + (0,)
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    info = VSVersionInfo(ffi=FixedFileInfo(filevers=version, prodvers=version, mask=0x3f,
        flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)), kids=[
        StringFileInfo([StringTable('040904B0', [StringStruct('FileDescription', 'roLabelImg'),
            StringStruct('FileVersion', VERSION), StringStruct('ProductVersion', VERSION),
            StringStruct('ProductName', 'roLabelImg'), StringStruct('OriginalFilename', 'roLabelImg.exe')])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])])])
    (build / 'windows-version.txt').write_text(str(info), encoding='utf-8')
    if not args.installer_only:
        run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
            '--distpath', ROOT / 'dist', '--workpath', build / 'pyinstaller', ROOT / 'packaging' / 'roLabelImg.spec')
    executable = ROOT / 'dist' / 'roLabelImg' / 'roLabelImg.exe'
    if not executable.is_file():
        raise RuntimeError('Client missing; build it with --exe-only first')
    report = build / 'frozen-smoke.json'
    run(executable, '--smoke-test', report)
    smoke = json.loads(report.read_text(encoding='utf-8'))
    if not smoke['ok']:
        raise RuntimeError('Frozen smoke test failed: ' + str(report))
    if smoke.get('version') != VERSION:
        raise RuntimeError('Existing client version does not match APP_VERSION; rebuild the client first')
    if args.exe_only:
        print('Client executable:', executable)
        return
    compiler = args.iscc or shutil.which('ISCC') or str(
        Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Inno Setup 6' / 'ISCC.exe')
    if not Path(compiler).is_file():
        raise RuntimeError('Install Inno Setup 6/7 or pass --iscc "...\\ISCC.exe"')
    release = ROOT / 'release'
    release.mkdir(exist_ok=True)
    run(compiler, '/DAppVersion=' + VERSION, '/DSourceDir=' + str(executable.parent),
        '/DOutputDir=' + str(release), ROOT / 'packaging' / 'installer.iss')
    archive = shutil.make_archive(str(release / f'roLabelImg-{VERSION}-win-x64-portable'),
                                  'zip', root_dir=ROOT / 'dist', base_dir='roLabelImg')
    installer = release / CONFIG['installer_name'](VERSION)
    paths = [installer, Path(archive)]
    hashes = []
    for path in paths:
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        hashes.append(digest.hexdigest() + '  ' + path.name)
    (release / 'SHA256SUMS.txt').write_text('\n'.join(hashes) + '\n', encoding='utf-8')
    freeze = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    (release / 'build-info.json').write_text(json.dumps(dict(version=VERSION, python=sys.version,
        platform=platform.platform(), dependencies=freeze.splitlines(), smoke=json.loads(report.read_text())),
        ensure_ascii=False, indent=2), encoding='utf-8')
    print('Release artifacts:', release)


if __name__ == '__main__':
    main()
