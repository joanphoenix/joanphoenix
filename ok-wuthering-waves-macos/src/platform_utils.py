"""Small desktop actions shared by Windows and native macOS tasks."""

import os
import subprocess
import sys


def open_folder(path):
    """Open a local folder using the host's file browser."""
    path = os.path.abspath(path)
    if sys.platform == 'darwin':
        subprocess.run(['/usr/bin/open', path], check=True)
    elif sys.platform == 'win32':
        os.startfile(path)
    else:
        raise RuntimeError(f'Opening folders is not supported on {sys.platform}')
