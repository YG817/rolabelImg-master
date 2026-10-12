"""Release metadata served as a public asset rather than a REST API query."""
import hashlib
import json
from pathlib import Path
from app_version import GITHUB_OWNER, GITHUB_REPO, installer_name


def write_update_manifest(directory, version, notes):
    directory = Path(directory)
    name = installer_name(version)
    installer = directory / name
    digest = hashlib.sha256()
    with installer.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    tag = 'v' + version
    data = dict(schema_version=1, repository=f'{GITHUB_OWNER}/{GITHUB_REPO}',
                tag_name=tag, draft=False, prerelease=False, body=notes,
                assets=[dict(name=name, state='uploaded', size=installer.stat().st_size,
                             digest='sha256:' + digest.hexdigest(),
                             browser_download_url=f'https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/{tag}/{name}')])
    path = directory / 'update.json'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return path
