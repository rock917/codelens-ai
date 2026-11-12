"""Run interactively as root on the VM. Never prints or accepts a key as an argument."""
import getpass
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request
import urllib.error
import uuid


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo on the Azure VM.')
    target = Path('/etc/codelens/account-admin.env')
    if target.exists():
        raise SystemExit('Admin settings already exist. Nothing overwritten.')
    inspected = subprocess.run(['docker', 'inspect', 'codelens-backend-1'], capture_output=True, check=True)
    values = dict(item.split('=', 1) for item in json.loads(inspected.stdout)[0]['Config']['Env'])
    url = values['SUPABASE_URL'].rstrip('/')
    if url != 'https://vwzaovypruwjohmbugtm.supabase.co':
        raise SystemExit('Unexpected Supabase project; nothing saved.')
    key = getpass.getpass('Supabase server secret or legacy service_role key (hidden): ').strip()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{40,4096}', key):
        raise SystemExit('Invalid key format; nothing saved.')
    # A missing random user returns 404 only after the admin credential is checked.
    # No existing user data is retrieved, created or deleted.
    request = urllib.request.Request(url + '/auth/v1/admin/users/' + str(uuid.uuid4()),
        headers={'apikey': key, 'Authorization': 'Bearer ' + key})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            valid = response.status == 200
    except urllib.error.HTTPError as exc:
        valid = exc.code == 404
    if not valid:
        raise SystemExit('Admin credential was not accepted; nothing saved.')
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.umask(0o077)
    # Exclusive creation prevents replacing existing settings or following a symlink.
    with target.open('x') as output:
        output.write('SUPABASE_SERVICE_ROLE_KEY=' + key + '\n')
    print('Verified server-only admin settings saved with root-only permissions. No account was deleted.')
    print('Recreate the backend using the documented Compose command to activate deletion.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        raise SystemExit('Setup could not finish. No credentials were printed. Check the connection and try again.') from None
