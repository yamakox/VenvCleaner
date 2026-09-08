import shutil
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, Label, Static

from .core import (
    copy_text_to_clipboard,
    find_venvs_worker,
    format_size,
    format_status_text,
    logger,
    quote_path,
    sort_venv_ids,
    timestamp_to_local_str,
)
from .version import version_number

SORT_COLUMNS = ('Venv Name', 'Location', 'Size', 'Last Modified')


class VenvFound(Message):
    def __init__(self, venv_path: Path) -> None:
        self.venv_path = venv_path
        super().__init__()


class VenvSizeComputed(Message):
    def __init__(self, venv_path: Path, venv_size: int) -> None:
        self.venv_path = venv_path
        self.venv_size = venv_size
        super().__init__()


class FindVenvsCompleted(Message):
    pass


class ConfirmDialog(ModalScreen[bool]):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical(id='confirm-dialog'):
            yield Static(self.message)
            with Horizontal():
                yield Button('Yes', id='yes', variant='primary')
                yield Button('No', id='no')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == 'yes')

    def key_y(self) -> None:
        self.dismiss(True)

    def key_n(self) -> None:
        self.dismiss(False)


class InfoDialog(ModalScreen[None]):
    def __init__(self, title: str, message: str) -> None:
        self.title = title
        self.message = message
        super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical(id='info-dialog'):
            yield Static(self.title, classes='dialog-title')
            yield Static(self.message)
            yield Button('OK', id='ok', variant='primary')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'ok':
            self.dismiss(None)

    def key_enter(self) -> None:
        self.dismiss(None)


class VenvCleanerApp(App[None]):
    TITLE = f'venv cleaner v{version_number}'
    BINDINGS = [
        Binding('escape', 'quit', 'Quit'),
        Binding('q', 'quit', 'Quit'),
        Binding('a', 'select_all', 'Select All', show=False),
        Binding('n', 'select_none', 'Select None', show=False),
        Binding('r', 'refresh', 'Refresh', show=False),
        Binding('c', 'copy_paths', 'Copy Paths', show=False),
        Binding('space', 'toggle_row', 'Toggle', show=False),
    ]

    CSS = """
    Screen {
        overflow: hidden;
    }

    Header {
        dock: top;
    }

    Footer {
        dock: bottom;
    }

    #path-row {
        dock: top;
        height: 3;
        padding: 0 1;
    }

    #path-row Label {
        width: auto;
        min-width: 11;
        height: 3;
        content-align: left middle;
    }

    #dir-path-input {
        width: 1fr;
        min-width: 1;
    }

    #refresh-button {
        width: auto;
        min-width: 9;
    }

    #bottom-panel {
        dock: bottom;
        height: auto;
    }

    #status-label {
        height: 1;
        padding: 0 1;
        text-align: center;
    }

    #control-row {
        height: 3;
        padding: 0 1;
    }

    #cleanup-row {
        height: 3;
        padding: 0 1;
    }

    #venv-table {
        height: 1fr;
        min-height: 3;
    }

    #confirm-dialog, #info-dialog {
        padding: 1 2;
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
    }

    .dialog-title {
        text-style: bold;
        padding-bottom: 1;
    }
    """

    def __init__(self, dir_path: str | Path) -> None:
        super().__init__()
        self.dir_path = Path(dir_path).resolve()
        self.venvs_cache: dict[int, dict] = {}
        self.venvs_cache_inv: dict[Path, dict] = {}
        self.selected_ids: set[int] = set()
        self.total_size = 0
        self.sort_column = 1
        self.sort_ascending = True
        self._stop_scan = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id='path-row'):
            yield Label('Directory:')
            yield Input(value=str(self.dir_path), id='dir-path-input')
            yield Button('Refresh', id='refresh-button', variant='default')
        yield DataTable(id='venv-table', cursor_type='row', zebra_stripes=True)
        with Vertical(id='bottom-panel'):
            yield Static('Venv Cleaner', id='status-label')
            with Horizontal(id='control-row'):
                yield Button('Select All', id='select-all-button')
                yield Button('Select None', id='select-none-button')
                yield Button('Copy Paths', id='copy-paths-button')
            with Horizontal(id='cleanup-row'):
                yield Checkbox('I agree to take responsibility for my actions.', id='agree-checkbox')
                yield Button('Cleanup Venvs', id='cleanup-button', variant='error', disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        #self.theme = 'textual-light'
        table = self.query_one('#venv-table', DataTable)
        table.add_columns('Sel', *SORT_COLUMNS)
        self._start_find_venvs()

    def _set_status_text(self, text: str) -> None:
        self.query_one('#status-label', Static).update(text)

    def _get_cleanup_button(self) -> Button:
        return self.query_one('#cleanup-button', Button)

    def _start_find_venvs(self) -> None:
        self._stop_scan = True
        self.venvs_cache.clear()
        self.venvs_cache_inv.clear()
        self.selected_ids.clear()
        self.total_size = 0
        table = self.query_one('#venv-table', DataTable)
        table.clear()
        self._set_status_text('Finding venvs...')
        self._stop_scan = False
        self._find_venvs_worker(self.dir_path)

    @work(thread=True)
    def _find_venvs_worker(self, dir_path: Path) -> None:
        app = self

        class Callbacks:
            @staticmethod
            def on_venv_found(venv_path: Path) -> None:
                app.post_message(VenvFound(venv_path))

            @staticmethod
            def on_venv_size_computed(venv_path: Path, venv_size: int) -> None:
                app.post_message(VenvSizeComputed(venv_path, venv_size))

            @staticmethod
            def on_find_venvs_completed() -> None:
                app.post_message(FindVenvsCompleted())

            @staticmethod
            def should_stop() -> bool:
                return app._stop_scan

        find_venvs_worker(dir_path, Callbacks)

    def _get_row_key(self, item_id: int):
        table = self.query_one('#venv-table', DataTable)
        target = str(item_id)
        for row in table.ordered_rows:
            if row.key.value == target:
                return row.key
        return None

    def _get_column_key(self, label: str):
        table = self.query_one('#venv-table', DataTable)
        for col_key, column in table.columns.items():
            if column.label.plain == label:
                return col_key
        return None

    def _selection_marker(self, item_id: int) -> str:
        return '*' if item_id in self.selected_ids else ' '

    def _location_text(self, venv_path: Path) -> str:
        try:
            return str(venv_path.relative_to(self.dir_path).parent)
        except ValueError:
            return str(venv_path.parent)

    def _size_text(self, venv_info: dict) -> str:
        return format_size(venv_info['size']) if venv_info['size'] else '...'

    def _add_venv_row(self, venv_info: dict) -> None:
        table = self.query_one('#venv-table', DataTable)
        row_key = str(venv_info['id'])
        table.add_row(
            self._selection_marker(venv_info['id']),
            venv_info['path'].name,
            self._location_text(venv_info['path']),
            self._size_text(venv_info),
            timestamp_to_local_str(venv_info['t']),
            key=row_key,
        )

    def _refresh_table_rows(self) -> None:
        table = self.query_one('#venv-table', DataTable)
        table.clear()
        sorted_ids = sort_venv_ids(self.venvs_cache, self.sort_column, self.sort_ascending)
        for item_id in sorted_ids:
            self._add_venv_row(self.venvs_cache[item_id])

    def _update_row_selection(self, item_id: int) -> None:
        table = self.query_one('#venv-table', DataTable)
        row_key = self._get_row_key(item_id)
        if row_key is None:
            return
        venv_info = self.venvs_cache[item_id]
        sel_key = self._get_column_key('Sel')
        size_key = self._get_column_key('Size')
        if sel_key is not None:
            table.update_cell(row_key, sel_key, self._selection_marker(item_id))
        if size_key is not None:
            table.update_cell(row_key, size_key, self._size_text(venv_info), update_width=True)

    @on(VenvFound)
    def on_venv_found(self, message: VenvFound) -> None:
        mtime = message.venv_path.stat().st_mtime
        item_id = len(self.venvs_cache) + 1
        venv_info = {'path': message.venv_path, 'size': 0, 'id': item_id, 't': mtime}
        self.venvs_cache[item_id] = venv_info
        self.venvs_cache_inv[message.venv_path] = venv_info
        self._add_venv_row(venv_info)

    @on(VenvSizeComputed)
    def on_venv_size_computed(self, message: VenvSizeComputed) -> None:
        if message.venv_path not in self.venvs_cache_inv:
            return
        venv_info = self.venvs_cache_inv[message.venv_path]
        venv_info['size'] = message.venv_size
        self.total_size += message.venv_size
        self._update_row_selection(venv_info['id'])
        if self.sort_column == 2:
            self._refresh_table_rows()
        count = len(self.venvs_cache)
        self._set_status_text(format_status_text(count, self.total_size))

    @on(FindVenvsCompleted)
    def on_find_venvs_completed(self, _message: FindVenvsCompleted) -> None:
        count = len(self.venvs_cache)
        self._set_status_text(format_status_text(count, self.total_size))
        self._refresh_table_rows()

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        column = event.column_index - 1
        if column < 0:
            return
        if column == self.sort_column:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column = column
            self.sort_ascending = True
        self._refresh_table_rows()

    def action_toggle_row(self) -> None:
        table = self.query_one('#venv-table', DataTable)
        if table.cursor_row is None or table.cursor_row >= len(table.ordered_rows):
            return
        row_key = table.ordered_rows[table.cursor_row].key
        item_id = int(row_key.value)
        if item_id in self.selected_ids:
            self.selected_ids.remove(item_id)
        else:
            self.selected_ids.add(item_id)
        self._update_row_selection(item_id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != 'dir-path-input':
            return
        path = Path(event.value).expanduser()
        if not path.is_dir():
            self._set_status_text('Invalid directory path.')
            return
        self.dir_path = path.resolve()
        event.input.value = str(self.dir_path)
        self._start_find_venvs()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == 'agree-checkbox':
            self._get_cleanup_button().disabled = not event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == 'refresh-button':
            self.action_refresh()
        elif button_id == 'select-all-button':
            self.action_select_all()
        elif button_id == 'select-none-button':
            self.action_select_none()
        elif button_id == 'copy-paths-button':
            self.action_copy_paths()
        elif button_id == 'cleanup-button':
            self.run_worker(self._clean_venvs(), exclusive=True)

    def action_select_all(self) -> None:
        self.selected_ids = set(self.venvs_cache.keys())
        self._refresh_table_rows()

    def action_select_none(self) -> None:
        self.selected_ids.clear()
        self._refresh_table_rows()

    def action_refresh(self) -> None:
        self._start_find_venvs()

    def action_copy_paths(self) -> None:
        if not self.selected_ids:
            self.push_screen(InfoDialog('Warning', 'Please select at least one venv to copy the paths.'))
            return
        paths = []
        for item_id in sorted(self.selected_ids):
            venv_info = self.venvs_cache[item_id]
            paths.append(quote_path(venv_info['path']))
        if copy_text_to_clipboard(' '.join(paths)):
            self.push_screen(
                InfoDialog('Success', f'{len(paths)} venv path(s) have been copied to the clipboard.')
            )
        else:
            self.push_screen(InfoDialog('Error', 'Failed to open the clipboard. Please try again.'))

    async def _clean_venvs(self) -> None:
        selected_count = len(self.selected_ids)
        if selected_count == 0:
            self.push_screen(InfoDialog('Warning', 'Please select at least one venv to clean up.'))
            return
        confirmed = await self.push_screen_wait(
            ConfirmDialog(f'Are you sure you want to clean up {selected_count} venv(s)?')
        )
        if not confirmed:
            return
        self._stop_scan = True
        cleaned_count = 0
        error_count = 0
        sorted_ids = sort_venv_ids(self.venvs_cache, self.sort_column, self.sort_ascending)
        remaining_ids: list[int] = []
        for item_id in sorted_ids:
            venv_info = self.venvs_cache[item_id]
            venv_path = venv_info['path']
            if item_id not in self.selected_ids:
                remaining_ids.append(item_id)
                continue
            try:
                logger.info(f'Cleaned up: {venv_path}')
                shutil.rmtree(venv_path)
                cleaned_count += 1
                self.total_size -= venv_info['size']
                del self.venvs_cache[item_id]
                if venv_path in self.venvs_cache_inv:
                    del self.venvs_cache_inv[venv_path]
            except Exception:
                error_count += 1
                logger.error(f'Failed to clean up: {venv_path}')
                remaining_ids.append(item_id)
        self.selected_ids = {item_id for item_id in remaining_ids if item_id in self.venvs_cache}
        self._refresh_table_rows()
        count = len(self.venvs_cache)
        self._set_status_text(f'{count} venv(s) remaining. Total size: {format_size(self.total_size)}')
        if error_count > 0:
            self.push_screen(
                InfoDialog(
                    'Error',
                    (
                        f'Failed to clean up {error_count} of {cleaned_count + error_count} venv(s). '
                        'Please check the permissions and try again.'
                    ),
                )
            )
        else:
            self.push_screen(InfoDialog('Success', f'Cleaned up {cleaned_count} venv(s).'))

    def on_unmount(self) -> None:
        self._stop_scan = True


def main(dir_path: str | Path) -> None:
    app = VenvCleanerApp(dir_path)
    app.run()
