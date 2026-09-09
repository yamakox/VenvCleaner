# Venv Cleaner

A simple TUI/GUI tool for cleaning up old or unused Python virtual environments (`venv` directories).

## How to Use

The easiest way to run the **TUI mode** of Venv Cleaner is using [uvx](https://docs.astral.sh/uv/guides/tools/):

```bash
uvx venvcleaner
```

![TUI mode](https://raw.githubusercontent.com/yamakox/VenvCleaner/main/tui-mode.png)

You can also run the **GUI mode** of Venv Cleaner:

```bash
uvx --with wxpython venvcleaner
```

![GUI mode](https://raw.githubusercontent.com/yamakox/VenvCleaner/main/gui-mode.png)

You can specify a target directory:

```bash
uvx venvcleaner /path/to/target-directory
```

### Using GUI mode on Linux

If you want to use GUI mode on Linux, you will need to build wxPython via pip. Please see [Building wxPython for Linux via Pip](https://wxpython.org/blog/2017-08-17-builds-for-linux-with-pip/) and [wxWidgets for GTK installation](https://docs.wxwidgets.org/3.2/plat_gtk_install.html).

Alternatively, on [some Linux systems](https://wxpython.org/pages/downloads/index.html), you can use the `-f` (`--find-links`) option to specify [the download URL of wxPython package](https://extras.wxpython.org/wxPython4/extras/linux/):

```bash
# for Ubuntu 24.04
uvx -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04 venvcleaner
```

If you want to install it into a persistent environment:

```bash
uv tool install venvcleaner[gui]@latest

# for Ubuntu 24.04
uv tool install -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04 venvcleaner@latest

# run Venv Cleaner
venvcleaner

# run the TUI mode of Venv Cleaner
venvcleaner --no-gui
```

## Features

- Scans the target directory for virtual environments (`.venv` directories containing a `pyvenv.cfg` file).
- In TUI mode, you can change the target directory by editing the path field and pressing Enter, or refresh the scan with the **Refresh** button.
- In GUI mode, you can change or refresh the target directory with the **Select...** or **Refresh** buttons.
- Choose which venvs to clean using the selection list.
  - **Select All** selects all detected venvs.
  - **Select None** clears the selection.
- **Copy Paths** (GUI) copies the paths of selected venvs to your clipboard.
You can paste them into a terminal to run shell commands manually. For example:

```bash
ls /path/to/project-1/.venv "/path/to/project 2/.venv"
rm -r /path/to/project-1/.venv "/path/to/project 2/.venv"
```

- **Dump Paths** (TUI) prints the full paths of selected venvs to stdout, one per line, and exits.
This is useful on SSH or other remote sessions where clipboard access is unavailable. For example:

```bash
venvcleaner --no-gui /path/to/scan  # select venvs, then press Dump Paths
# /path/to/project-1/.venv
# /path/to/project-2/.venv
```

- **Cleanup Venvs** deletes the selected venv directories.

## TUI Key Bindings

|Key|Action|
|---|---|
|`↑` / `↓`|Move within the venv list|
|`Space`|Toggle selection of the current row|
|`Tab` / `Shift+Tab`|Move focus between widgets|
|`Enter`|Activate the focused button / confirm path input|
|`a`|Select All|
|`n`|Select None|
|`r`|Refresh|
|`d`|Dump Paths|
|`Esc` / `q`|Quit|

In modal dialogs, press `Esc` to close, or use the buttons.

## Environment Variables

TUI mode reads optional settings from:

```text
~/.config/venvcleaner/.env
```

|Variable|Description|
|---|---|
|`TEXTUAL_THEME`|Textual theme name (for example `textual-light`, `textual-dark`, or `ansi-dark`). If unset or empty, the Textual default theme is used.|

Example:

```bash
mkdir -p ~/.config/venvcleaner
echo 'TEXTUAL_THEME=textual-light' > ~/.config/venvcleaner/.env
```

You can also set `TEXTUAL_THEME` in your shell environment. Existing environment variables take precedence over values in `.env`.

## License

This software is distributed under the terms of the [MIT License](https://raw.githubusercontent.com/yamakox/VenvCleaner/main/LICENSE).
