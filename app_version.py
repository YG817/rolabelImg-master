"""Single source for client, installer and GitHub release versions."""
APP_VERSION = '2.0.2'
GITHUB_OWNER = 'YG817'
GITHUB_REPO = 'rolabelImg-master'
REPOSITORY_URL = f'https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}'
LATEST_RELEASE_API = f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest'
LATEST_UPDATE_MANIFEST = f'{REPOSITORY_URL}/releases/latest/download/update.json'
INSTALLER_PREFIX = 'roLabelImg-Setup-'


def installer_name(version):
    return f'{INSTALLER_PREFIX}{version}-win-x64.exe'
