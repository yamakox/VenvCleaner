import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Protocol

GLOB_PATTERN = 'pyvenv.cfg'

logger = logging.getLogger('venvcleaner')
debug = os.environ.get('DEBUG')
logger.setLevel(logging.DEBUG if debug else logging.INFO)
if not logging.getLogger().handlers:
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
    )


def compute_dir_size(dir_path: Path) -> int:
    dir_size = 0
    for path in dir_path.rglob('*'):
        if path.is_file():
            dir_size += path.stat().st_size
    return dir_size


def format_size(size: int) -> str:
    if size < 1024:
        return f'{size} B'
    if size < 1024 * 1024:
        return f'{size / 1024:.2f} KB'
    if size < 1024 * 1024 * 1024:
        return f'{size / 1024 / 1024:.2f} MB'
    return f'{size / 1024 / 1024 / 1024:.2f} GB'


def timestamp_to_local_str(timestamp: float) -> str:
    return str(datetime.fromtimestamp(int(timestamp)))


def quote_path(path: Path | str) -> str:
    _path = str(path)
    return f'"{_path}"' if ' ' in _path else _path


def venv_sort_values(venv_info: dict, sort_column: int) -> tuple:
    if sort_column == 0:
        return (venv_info['path'].name.lower(),)
    if sort_column == 1:
        return (str(venv_info['path'].parent).lower(),)
    if sort_column == 2:
        return (venv_info['size'],)
    if sort_column == 3:
        return (venv_info['t'],)
    return (0,)


def compare_venvs(venv_info1: dict, venv_info2: dict, sort_column: int, sort_ascending: bool) -> int:
    val1 = venv_sort_values(venv_info1, sort_column)[0]
    val2 = venv_sort_values(venv_info2, sort_column)[0]
    if sort_ascending:
        return (val1 > val2) - (val1 < val2)
    return (val1 < val2) - (val1 > val2)


def sort_venv_ids(venvs_cache: dict, sort_column: int, sort_ascending: bool) -> list[int]:
    ids = list(venvs_cache.keys())
    ids.sort(key=lambda item_id: venv_sort_values(venvs_cache[item_id], sort_column))
    if not sort_ascending:
        ids.reverse()
    return ids


class FindVenvsCallbacks(Protocol):
    def on_venv_found(self, venv_path: Path) -> None: ...

    def on_venv_size_computed(self, venv_path: Path, venv_size: int) -> None: ...

    def on_find_venvs_completed(self) -> None: ...

    def should_stop(self) -> bool: ...


def find_venvs_worker(dir_path: Path, callbacks: FindVenvsCallbacks) -> None:
    venv_paths: list[Path] = []
    try:
        for path in dir_path.rglob(GLOB_PATTERN):
            if callbacks.should_stop():
                return
            if path.is_file():
                venv_path = path.parent
                venv_paths.append(venv_path)
                callbacks.on_venv_found(venv_path)
        callbacks.on_find_venvs_completed()
        for venv_path in venv_paths:
            if callbacks.should_stop():
                return
            venv_size = compute_dir_size(venv_path)
            callbacks.on_venv_size_computed(venv_path, venv_size)
    except Exception as e:
        logger.error(f'Failed to find venvs: {e}')
        callbacks.on_find_venvs_completed()


def copy_text_to_clipboard(text: str) -> bool:
    try:
        if sys.platform == 'darwin':
            subprocess.run(['pbcopy'], input=text.encode(), check=True)
            return True
        if sys.platform == 'win32':
            subprocess.run(['clip'], input=text.encode('utf-16le'), check=True)
            return True
        for cmd in (['xclip', '-selection', 'clipboard'], ['xsel', '--clipboard', '--input']):
            try:
                subprocess.run(cmd, input=text.encode(), check=True)
                return True
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        return False
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return False


def format_status_text(count: int, total_size: int, prefix: str = 'Found') -> str:
    return f'{prefix} {count} venvs. Total size: {format_size(total_size)}'
