import click
import os
import sys
from importlib.util import find_spec
from .version import version_number


# MARK: Determine GUI mode
def determineGUImode():
    if find_spec('wx') is None:
        return False
    if sys.platform == 'linux':
        if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
            return False
    return True


# MARK: Main Function
@click.command()
@click.argument('dir_path', nargs=1, default='.', type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option('--version', is_flag=True, help='Show the version of Venv Cleaner.')
@click.option('--no-gui', default=False, is_flag=True, help='Run Venv Cleaner in the TUI mode.')
def main(dir_path, version, no_gui):
    if version:
        click.echo(f'Venv Cleaner v{version_number}')
        return
    if not no_gui and determineGUImode():
        from . import gui as module
    else:
        from . import tui as module
    module.main(dir_path)
