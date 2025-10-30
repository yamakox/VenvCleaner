# Venv Cleaner

A simple GUI tool for cleaning up old or unused Python virtual environments (`venv` directories).

## How to Use

The easiest way to run Venv Cleaner is with [uvx](https://docs.astral.sh/uv/guides/tools/):

```bash
uvx venvcleaner
```

You can also specify a target directory:

```bash
uvx venvcleaner /path/to/target-directory
```

![screenshot](https://raw.githubusercontent.com/yamakox/VenvCleaner/main/screenshot.png)

## Features

- Scans the target directory for virtual environments (`.venv` folders containing a `pyvenv.cfg` file).
- You can change or refresh the target directory with the __Select...__ or __Refresh__ buttons.
- Choose which venvs to clean using the selection list.
  - __Select All__ selects all detected venvs.
  - __Select None__ clears the selection.
- __Copy Paths__ copies the paths of selected venvs to your clipboard.
You can paste them into a terminal to run shell commands manually. For example:

```bash
ls /path/to/project-1/.venv "/path/to/project 2/.venv"
rm -r /path/to/project-1/.venv "/path/to/project 2/.venv"
```

- __Cleanup Venvs__ deletes the selected venv directories.
Before using this button, you must check the agreement box:

> I agree to take responsibility for my actions.

## License

This software is distributed under the terms of the [MIT License](./LICENSE).
