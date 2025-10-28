from typing import Any
import click
from pathlib import Path
import shutil
import sys
import logging
import os
from datetime import datetime
import wx
import threading
from importlib.metadata import version, metadata

package_name = metadata(__package__).get('Name') # type: ignore
version_number = version(package_name)

# MARK: logger "venvcleaner"

logger: logging.Logger|None = logging.getLogger('venvcleaner')
debug = os.environ.get('DEBUG')
logger.setLevel(logging.DEBUG if debug else logging.INFO)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s", 
)

# MARK: Constants

GLOB_PATTERN = 'pyvenv.cfg'

# MARK subroutines

def _compute_dir_size(dir_path):
    dir_size = 0
    for path in dir_path.rglob('*'):
        if path.is_file():
            dir_size += path.stat().st_size
    return dir_size

def _format_size(size):
    if size < 1024:
        return f'{size} B'
    elif size < 1024 * 1024:
        return f'{size / 1024:.2f} KB'
    elif size < 1024 * 1024 * 1024:
        return f'{size / 1024 / 1024:.2f} MB'
    else:
        return f'{size / 1024 / 1024 / 1024:.2f} GB'

def _timestamp_to_local_str(timestamp):
    return str(datetime.fromtimestamp(int(timestamp)))

# MARK: Events

myEVT_VENV_FOUND = wx.NewEventType()
EVT_VENV_FOUND = wx.PyEventBinder(myEVT_VENV_FOUND)

class VenvFoundEvent(wx.ThreadEvent):
    def __init__(self, venv_path):
        super().__init__(myEVT_VENV_FOUND)
        self.venv_path = venv_path

myEVT_VENV_SIZE_COMPUTED = wx.NewEventType()
EVT_VENV_SIZE_COMPUTED = wx.PyEventBinder(myEVT_VENV_SIZE_COMPUTED)

class VenvSizeComputedEvent(wx.ThreadEvent):
    def __init__(self, venv_path, venv_size):
        super().__init__(myEVT_VENV_SIZE_COMPUTED)
        self.venv_path = venv_path
        self.venv_size = venv_size

myEVT_FIND_VENVS_COMPLETED = wx.NewEventType()
EVT_FIND_VENVS_COMPLETED = wx.PyEventBinder(myEVT_FIND_VENVS_COMPLETED)

class FindVenvsCompletedEvent(wx.ThreadEvent):
    def __init__(self):
        super().__init__(myEVT_FIND_VENVS_COMPLETED)

# MARK: Main Frame

class VenvCleanerFrame(wx.Frame):
    def __init__(self, dir_path):
        super().__init__(None, title=f'venv cleaner v{version_number}', size=(800, 600))
        self.dir_path = Path(dir_path)

        self.venvs_cache = {}
        self.venvs_cache_inv = {}
        self.total_size = 0
        self.find_venvs_thread = None
        self.Bind(EVT_VENV_FOUND, self.__on_venv_found)
        self.Bind(EVT_VENV_SIZE_COMPUTED, self.__on_venv_size_computed)
        self.Bind(EVT_FIND_VENVS_COMPLETED, self.__on_find_venvs_completed)
        self.Bind(wx.EVT_CLOSE, self.__on_close)

        if sys.platform == 'darwin':
            menu_bar = wx.MenuBar()
            file_menu = wx.Menu()
            file_menu_close = file_menu.Append(wx.ID_CLOSE, 'Close Window\tCtrl+W')
            menu_bar.Append(file_menu, 'File')
            self.SetMenuBar(menu_bar)
            self.Bind(wx.EVT_MENU, self.__on_close_menu, file_menu_close)
        
        self.__setup_main_panel()
        self.__start_find_venvs_thread()

    def __setup_main_panel(self):
        frame_sizer = wx.GridSizer(rows=1, cols=1, gap=wx.Size(0, 0))
        panel = wx.Panel(self)
        sizer = wx.FlexGridSizer(rows=3, cols=1, gap=wx.Size(8, 8))
        sizer.AddGrowableCol(0)
        sizer.AddGrowableRow(1)

        dir_path_panel = self.__setup_dir_path_panel(panel)
        sizer.Add(dir_path_panel, flag=wx.EXPAND)

        self.venv_list = wx.ListCtrl(panel, style=wx.LC_REPORT|wx.LC_HRULES|wx.LC_VRULES|wx.LC_SORT_ASCENDING)
        self.venv_list.InsertColumn(0, 'Name', width=100)
        self.venv_list.InsertColumn(1, 'Location', width=350)
        self.venv_list.InsertColumn(2, 'Size', wx.LIST_FORMAT_RIGHT, width=120)
        self.venv_list.InsertColumn(3, 'Last Modified', width=180)
        sizer.Add(self.venv_list, flag=wx.EXPAND|wx.ALL, border=2)

        control_panel = self.__setup_control_panel(panel)
        sizer.Add(control_panel, flag=wx.EXPAND)

        panel.SetSizer(sizer)
        self.SetSizer(frame_sizer)
        frame_sizer.Add(panel, flag=wx.EXPAND|wx.ALL, border=8)

    def __setup_dir_path_panel(self, parent_panel):
        panel = wx.Panel(parent_panel)
        sizer = wx.FlexGridSizer(rows=1, cols=3, gap=wx.Size(4, 0))
        sizer.AddGrowableCol(0)

        self.dir_path_input = wx.TextCtrl(panel, style=wx.TE_READONLY)
        self.dir_path_input.SetValue(str(self.dir_path))
        sizer.Add(self.dir_path_input, flag=wx.EXPAND|wx.ALL, border=2)

        dir_path_button = wx.Button(panel, label='Select...')
        def on_dir_path_button_click(event):
            dialog = wx.DirDialog(self, 'Please select a directory.', style=wx.DD_DEFAULT_STYLE|wx.DD_DIR_MUST_EXIST)
            if dialog.ShowModal() == wx.ID_OK:
                self.dir_path = Path(dialog.GetPath())
                self.dir_path_input.SetValue(str(self.dir_path))
                self.__start_find_venvs_thread()
        dir_path_button.Bind(wx.EVT_BUTTON, on_dir_path_button_click)
        sizer.Add(dir_path_button, flag=wx.EXPAND|wx.ALL, border=2)

        refresh_button = wx.Button(panel, label='Refresh')
        def on_refresh_button_click(event):
            self.__start_find_venvs_thread()
        refresh_button.Bind(wx.EVT_BUTTON, on_refresh_button_click)
        sizer.Add(refresh_button, flag=wx.EXPAND|wx.ALL, border=2)

        panel.SetSizer(sizer)
        return panel

    def __setup_control_panel(self, parent_panel):
        self.control_panel = wx.Panel(parent_panel)
        sizer = wx.FlexGridSizer(rows=1, cols=4, gap=wx.Size(4, 0))
        sizer.AddGrowableCol(2)

        select_all_button = wx.Button(self.control_panel, label='Select All')
        def on_select_all_button_click(event):
            for row in range(self.venv_list.GetItemCount()):
                self.venv_list.Select(row, on=True)
        select_all_button.Bind(wx.EVT_BUTTON, on_select_all_button_click)
        sizer.Add(select_all_button, flag=wx.EXPAND|wx.ALL, border=2)

        select_none_button = wx.Button(self.control_panel, label='Select None')
        def on_select_none_button_click(event):
            for row in range(self.venv_list.GetItemCount()):
                self.venv_list.Select(row, on=False)
        select_none_button.Bind(wx.EVT_BUTTON, on_select_none_button_click)
        sizer.Add(select_none_button, flag=wx.EXPAND|wx.ALL, border=2)

        self.status_text = wx.StaticText(self.control_panel, label='', style=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.status_text, flag=wx.EXPAND|wx.ALL, border=2)

        clean_button = wx.Button(self.control_panel, label='Cleanup')
        def on_clean_button_click(event):
            self.__clean_venvs()
        clean_button.Bind(wx.EVT_BUTTON, on_clean_button_click)
        sizer.Add(clean_button, flag=wx.EXPAND|wx.ALL, border=2)

        self.control_panel.SetSizer(sizer)
        return self.control_panel

    def __start_find_venvs_thread(self):
        self.__ensure_stop_thread()
        self.venvs_cache.clear()
        self.venvs_cache_inv.clear()
        self.total_size = 0
        self.venv_list.DeleteAllItems()
        self.status_text.SetLabel('Finding venvs...')
        self.Layout()
        self.find_venvs_thread = threading.Thread(
            target=self.__find_venvs_worker,
            args=(self.dir_path,), 
            daemon=True,
        )
        self.find_venvs_thread.start()

    def __ensure_stop_thread(self):
        th = self.find_venvs_thread
        if th is not None:
            self.find_venvs_thread = None
            th.join()

    def __find_venvs_worker(self, dir_path):
        venv_paths = []
        try:
            for path in dir_path.rglob(GLOB_PATTERN):
                if self.find_venvs_thread is None:
                    return
                if path.is_file():
                    venv_path = path.parent
                    venv_paths.append(venv_path)
                    wx.QueueEvent(self, VenvFoundEvent(venv_path))
            wx.QueueEvent(self, FindVenvsCompletedEvent())
            for venv_path in venv_paths:
                if self.find_venvs_thread is None:
                    return
                venv_size = _compute_dir_size(venv_path)
                wx.QueueEvent(self, VenvSizeComputedEvent(venv_path, venv_size))
                wx.QueueEvent(self, FindVenvsCompletedEvent())
        except Exception as e:
            logger.error(f'Failed to find venvs: {e}')
        finally:
            self.find_venvs_thread = None

    def __on_venv_found(self, event):
        self.venv_list.Append([
            event.venv_path.name, 
            str(event.venv_path.relative_to(self.dir_path).parent), 
            '...', 
            _timestamp_to_local_str(event.venv_path.stat().st_mtime),
        ])
        id = self.venv_list.GetItemCount()
        venv_info = {'path': event.venv_path, 'size': 0, 'id': id}
        self.venvs_cache[id] = venv_info
        self.venvs_cache_inv[event.venv_path] = venv_info
        self.venv_list.SetItemData(id - 1, id)

    def __on_venv_size_computed(self, event):
        if event.venv_path not in self.venvs_cache_inv:
            return
        venv_info = self.venvs_cache_inv[event.venv_path]
        index = self.venv_list.FindItem(-1, venv_info['id'])
        if index >= 0:
            venv_info['size'] = event.venv_size
            self.total_size += event.venv_size
            self.venv_list.SetItem(index, 2, _format_size(event.venv_size))

    def __on_find_venvs_completed(self, event):
        n = self.venv_list.GetItemCount()
        self.status_text.SetLabel(f'Found {n} venvs. Total size: {_format_size(self.total_size)}')
        self.control_panel.Layout()
        self.venv_list.SortItems(self.__sort_venvs)

    def __sort_venvs(self, item1, item2):
        venv1 = str(self.venvs_cache[item1]['path']).lower()
        venv2 = str(self.venvs_cache[item2]['path']).lower()
        return (venv1 > venv2) - (venv1 < venv2)

    def __clean_venvs(self):
        selected_count = self.venv_list.GetSelectedItemCount()
        if selected_count == 0:
            wx.MessageBox('Please select at least one venv to clean up.', 'Warning', wx.OK|wx.ICON_WARNING)
            return
        answer = wx.MessageBox(
            f'Are you sure you want to clean up {selected_count} venv(s)?', 
            'Confirm', 
            wx.OK|wx.CANCEL|wx.CANCEL_DEFAULT|wx.ICON_QUESTION
        )
        if answer != wx.OK:
            return
        self.__ensure_stop_thread()
        cleaned_count = 0
        error_count = 0
        row = 0
        while row < self.venv_list.GetItemCount():
            try:
                id = self.venv_list.GetItemData(row)
                venv_info = self.venvs_cache[id]
                venv_path = venv_info['path']
                if self.venv_list.IsSelected(row):
                    logger.info(f'Cleaned up: {venv_path}')
                    shutil.rmtree(venv_path)
                    self.venv_list.DeleteItem(row)
                    cleaned_count += 1
                    self.total_size -= venv_info['size']
                    continue
            except Exception:
                error_count += 1
                logger.error(f'Failed to clean up: {venv_path}')
            row += 1
        n = self.venv_list.GetItemCount()
        self.status_text.SetLabel(f'{n} venv(s) remaining. Total size: {_format_size(self.total_size)}')
        self.control_panel.Layout()
        self.venv_list.Update()
        if error_count > 0:
            wx.MessageBox(
                (
                    f'Failed to clean up {error_count} of {cleaned_count + error_count} venv(s). '
                    'Please check the permissions and try again.'
                ), 
                'Error',
                wx.OK|wx.ICON_ERROR
            )
        else:
            wx.MessageBox(
                f'Cleaned up {cleaned_count} venv(s).',
                'Success',
                wx.OK|wx.ICON_INFORMATION
            )

    def __on_close_menu(self, event):
        self.Close()
        event.Skip()

    def __on_close(self, event):
        self.__ensure_stop_thread()
        event.Skip()

# MARK: Main App

class VenvCleanerApp(wx.App):
    def __init__(self, dir_path):
        super().__init__()

        # wxPythonのcontrolをシステム言語で表示できるようにする
        # NOTE: ただし、ファイル選択ダイアログは英語のまま
        lang_code = wx.Locale().GetSystemLanguage()
        locale = wx.Locale(lang_code)

        self.dir_path = Path(dir_path)
        self.frame = VenvCleanerFrame(self.dir_path)
        self.frame.Show()
        self.frame.venv_list.SetFocus()

# MARK: Main Function

@click.command()
@click.argument('dir_path', nargs=1, default='.', type=click.Path(exists=True, file_okay=False, resolve_path=True))
def main(dir_path):
    app = VenvCleanerApp(dir_path)
    app.MainLoop()
