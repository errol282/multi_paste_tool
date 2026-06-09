# Multi Paste Tool

A small themed Windows Python app for assigning global hotkeys to clipboard text items.

## Run

After install, open `Multi Paste` from the Windows Start Menu.

The Start Menu shortcut launches through `pythonw.exe`, so no command prompt
window opens.

The app uses `multi_paste_tool.ico` for its window and taskbar icon.

## Install

Double-click `install_multi_paste_tool.bat`.

The installer creates or refreshes the local `.venv`, installs dependencies,
copies the app into `%LOCALAPPDATA%\Programs\Multi Paste`, and creates a Start
Menu shortcut with the app icon.

Double-click `install_multi_paste_tool_startup.bat` instead if you also want
Multi Paste to run when you sign in to Windows.

## Uninstall

Double-click `uninstall_multi_paste_tool.bat` to remove the Start Menu and
startup shortcuts. The installed app folder and saved data are left in place at
`%LOCALAPPDATA%\Programs\Multi Paste`.

`run_multi_paste_tool.bat` is still available as a debug launcher because it
keeps terminal errors visible.

## Usage

- Choose the number of paste slots. The default is `3`, and the current maximum is `5`.
- Turn `Capture and paste` on to fill slots as you copy text and activate the slot hotkeys.
- The default slot hotkeys start with `ctrl+v`, `ctrl+b`, `ctrl+n`, then continue through the configured slot count.
- With 3 slots, the fourth copied value wraps back to slot 1.

## Windows Notes

Some applications run elevated and will only accept global hotkeys from elevated tools. If hotkeys do not fire in a specific app, run this tool as administrator.

Binding `ctrl+v` means this app intercepts the normal paste shortcut while capture and paste is on.
