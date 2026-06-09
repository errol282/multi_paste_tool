"""Multi Paste Tool.

A lightweight Windows clipboard helper that maps clipboard entries to global
hotkeys. Pressing a hotkey copies the assigned text to the clipboard and can
optionally trigger a paste into the active window.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import ctypes
import os
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import BooleanVar, END, IntVar, PhotoImage, StringVar, Text, Tk, Toplevel, messagebox, ttk
from typing import Callable

import keyboard
import pyperclip


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "multi_paste_config.json"
SETTINGS_PATH = APP_DIR / "multi_paste_settings.json"
ICON_PATH = APP_DIR / "multi_paste_tool.ico"
ERROR_LOG_PATH = APP_DIR / "error.log"
PINK_BG = "#fff0f7"
PINK_PANEL = "#ffe1ef"
PINK_ACCENT = "#ff74ad"
PINK_ACCENT_DARK = "#d6337a"
PINK_SOFT = "#ffd0e5"
PINK_TEXT = "#5b2340"
WHITE = "#ffffff"
DEFAULT_HOTKEYS = [
    "ctrl+v",
    "ctrl+b",
    "ctrl+n",
    "ctrl+m",
    "ctrl+j",
    "ctrl+k",
    "ctrl+l",
    "ctrl+u",
    "ctrl+i",
    "ctrl+o",
    "ctrl+p",
]
MIN_CYCLE_SIZE = 3
MAX_CYCLE_SIZE = 5


@dataclass
class ClipItem:
    """A clipboard entry and its assigned global hotkey."""

    text: str
    hotkey: str


class MultiPasteTool:
    """Tkinter UI and hotkey controller for assigned clipboard entries."""

    def __init__(self, root: Tk) -> None:
        """Create the tool and wire UI state.

        Args:
            root: Tk root window.
        """
        self.root = root
        self.items: list[ClipItem] = []
        self.hotkey_handles: list[object] = []
        self.event_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self.last_seen_clipboard = ""
        self.monitor_running = True
        self.is_closing = False
        self.sending_paste = False
        self.capture_slot_index = 0

        self.capture_enabled = BooleanVar(value=True)
        self.auto_paste_enabled = BooleanVar(value=True)
        self.app_enabled = BooleanVar(value=True)
        self.cycle_size = IntVar(value=MIN_CYCLE_SIZE)
        self.status_text = StringVar(value="Ready")
        self.app_icon = self.create_app_icon()

        self.root.title("Multi Paste")
        self.root.geometry("920x600")
        self.root.minsize(760, 500)
        self.root.configure(bg=PINK_BG)
        self.root.iconphoto(True, self.app_icon)
        if ICON_PATH.exists():
            try:
                self.root.iconbitmap(str(ICON_PATH))
            except Exception:
                pass
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.configure_styles()
        self.load_settings()
        self.build_ui()
        self.load_config()
        self.apply_cycle_size()
        self.refresh_list()
        self.register_hotkeys()
        self.start_clipboard_monitor()
        self.process_event_queue()

    def create_app_icon(self) -> PhotoImage:
        """Create a small pink bow app icon for the window and taskbar."""
        image = PhotoImage(width=64, height=64)

        for y in range(64):
            for x in range(64):
                color = PINK_ACCENT if (x + y) % 2 == 0 else "#ff8fbe"
                image.put(color, (x, y))

        center_x = 32
        center_y = 36
        for y in range(12, 58):
            for x in range(8, 56):
                face = ((x - center_x) / 22) ** 2 + ((y - center_y) / 19) ** 2 <= 1
                left_ear = y < 25 and 12 <= x <= 26 and y <= 42 - x
                right_ear = y < 25 and 38 <= x <= 52 and y <= x - 22
                if face or left_ear or right_ear:
                    image.put(WHITE, (x, y))

        for x in range(21, 26):
            for y in range(35, 40):
                image.put(PINK_TEXT, (x, y))
        for x in range(39, 44):
            for y in range(35, 40):
                image.put(PINK_TEXT, (x, y))
        for x in range(31, 35):
            for y in range(42, 46):
                image.put("#ff95bd", (x, y))

        for y in range(12, 30):
            for x in range(34, 58):
                left_loop = ((x - 40) / 9) ** 2 + ((y - 21) / 8) ** 2 <= 1
                right_loop = ((x - 52) / 9) ** 2 + ((y - 21) / 8) ** 2 <= 1
                knot = ((x - 46) / 5) ** 2 + ((y - 21) / 5) ** 2 <= 1
                if left_loop or right_loop or knot:
                    image.put(PINK_ACCENT_DARK, (x, y))

        return image

    def configure_styles(self) -> None:
        """Apply the app's pink themed ttk styles."""
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=PINK_BG, foreground=PINK_TEXT, font=("Segoe UI", 10))
        style.configure("Header.TFrame", background=PINK_ACCENT)
        style.configure("Toolbar.TFrame", background=PINK_PANEL)
        style.configure("Content.TFrame", background=PINK_BG)
        style.configure("Footer.TFrame", background=PINK_BG)
        style.configure("Title.TLabel", background=PINK_ACCENT, foreground=WHITE, font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel", background=PINK_ACCENT, foreground=WHITE, font=("Segoe UI", 10))
        style.configure("Status.TLabel", background=PINK_BG, foreground=PINK_ACCENT_DARK, font=("Segoe UI", 10, "bold"))
        style.configure("Toolbar.TLabel", background=PINK_PANEL, foreground=PINK_TEXT, font=("Segoe UI", 10, "bold"))
        style.configure("TButton", background=PINK_SOFT, foreground=PINK_TEXT, borderwidth=1, padding=(12, 7))
        style.map("TButton", background=[("active", "#ffc1db"), ("pressed", PINK_ACCENT)])
        style.configure("Accent.TButton", background=PINK_ACCENT, foreground=WHITE, padding=(14, 7))
        style.map("Accent.TButton", background=[("active", PINK_ACCENT_DARK), ("pressed", "#b91f63")])
        style.configure("SwitchOn.TButton", background=PINK_ACCENT_DARK, foreground=WHITE, padding=(12, 7))
        style.map("SwitchOn.TButton", background=[("active", "#b91f63"), ("pressed", PINK_ACCENT_DARK)])
        style.configure("SwitchOff.TButton", background="#f7c9dc", foreground=PINK_TEXT, padding=(12, 7))
        style.map("SwitchOff.TButton", background=[("active", PINK_SOFT), ("pressed", "#f7c9dc")])
        style.configure("TCheckbutton", background=PINK_PANEL, foreground=PINK_TEXT, padding=(4, 2))
        style.map("TCheckbutton", background=[("active", PINK_PANEL)])
        style.configure("Treeview", background=WHITE, foreground=PINK_TEXT, fieldbackground=WHITE, rowheight=34, borderwidth=0)
        style.configure("Treeview.Heading", background=PINK_SOFT, foreground=PINK_TEXT, font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", PINK_ACCENT)], foreground=[("selected", WHITE)])

    def build_ui(self) -> None:
        """Build the main application controls."""
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        header = ttk.Frame(self.root, padding=(18, 14, 18, 14), style="Header.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Multi Paste", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Assign clipboard snippets to global hotkeys", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))

        toolbar = ttk.Frame(self.root, padding=(14, 12, 14, 10), style="Toolbar.TFrame")
        toolbar.grid(row=1, column=0, sticky="ew")
        toolbar.columnconfigure(1, weight=1)

        cycle_frame = ttk.Frame(toolbar, style="Toolbar.TFrame")
        cycle_frame.grid(row=0, column=0, padx=(0, 6), sticky="w")
        ttk.Label(cycle_frame, text="Paste slots", style="Toolbar.TLabel").grid(row=0, column=0, padx=(0, 6))
        self.cycle_spinbox = ttk.Spinbox(
            cycle_frame,
            from_=MIN_CYCLE_SIZE,
            to=MAX_CYCLE_SIZE,
            width=4,
            textvariable=self.cycle_size,
            command=self.on_cycle_size_change,
        )
        self.cycle_spinbox.grid(row=0, column=1)
        self.cycle_spinbox.bind("<FocusOut>", lambda _event: self.on_cycle_size_change())
        self.cycle_spinbox.bind("<Return>", lambda _event: self.on_cycle_size_change())

        switch_frame = ttk.Frame(toolbar, style="Toolbar.TFrame")
        switch_frame.grid(row=0, column=2, sticky="e")
        self.master_toggle = ttk.Button(switch_frame, command=self.toggle_app)
        self.master_toggle.grid(row=0, column=0)
        self.refresh_toggles()

        content = ttk.Frame(self.root, padding=(14, 14, 14, 8), style="Content.TFrame")
        content.grid(row=2, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        self.item_table = ttk.Treeview(content, columns=("number", "hotkey", "preview"), show="headings", selectmode="browse")
        self.item_table.heading("number", text="#")
        self.item_table.heading("hotkey", text="Hotkey")
        self.item_table.heading("preview", text="Clipboard item")
        self.item_table.column("number", width=56, minwidth=48, stretch=False, anchor="center")
        self.item_table.column("hotkey", width=130, minwidth=110, stretch=False)
        self.item_table.column("preview", width=560, minwidth=260, stretch=True)
        self.item_table.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(content, orient="vertical", command=self.item_table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.item_table.configure(yscrollcommand=scrollbar.set)

        footer = ttk.Frame(self.root, padding=(14, 0, 14, 12), style="Footer.TFrame")
        footer.grid(row=3, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_text, style="Status.TLabel").grid(row=0, column=0, sticky="w")

    def load_config(self) -> None:
        """Load saved clipboard entries from disk."""
        if not CONFIG_PATH.exists():
            return

        try:
            raw_items = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            self.items = [
                ClipItem(text=str(item.get("text", "")), hotkey=str(item.get("hotkey", "")))
                for item in raw_items
                if item.get("text")
            ]
        except (OSError, json.JSONDecodeError) as error:
            messagebox.showwarning("Could not load config", str(error))

    def load_settings(self) -> None:
        """Load saved app settings from disk."""
        if not SETTINGS_PATH.exists():
            return

        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            cycle_size = int(settings.get("cycle_size", MIN_CYCLE_SIZE))
            self.cycle_size.set(max(MIN_CYCLE_SIZE, min(MAX_CYCLE_SIZE, cycle_size)))
            app_enabled = bool(settings.get("app_enabled", settings.get("capture_enabled", True)))
            self.app_enabled.set(app_enabled)
            self.capture_enabled.set(app_enabled)
            self.auto_paste_enabled.set(app_enabled)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.cycle_size.set(MIN_CYCLE_SIZE)

    def save_settings(self) -> None:
        """Persist app settings to disk."""
        settings = {
            "cycle_size": self.cycle_size.get(),
            "app_enabled": self.app_enabled.get(),
        }
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    def save_config(self) -> None:
        """Persist clipboard entries to disk."""
        CONFIG_PATH.write_text(
            json.dumps([asdict(item) for item in self.items], indent=2),
            encoding="utf-8",
        )

    def apply_cycle_size(self) -> None:
        """Resize paste slots and assign their default hotkeys."""
        requested_size = self.cycle_size.get()
        cycle_size = max(MIN_CYCLE_SIZE, min(MAX_CYCLE_SIZE, requested_size))
        self.cycle_size.set(cycle_size)

        while len(self.items) < cycle_size:
            self.items.append(ClipItem(text="", hotkey=DEFAULT_HOTKEYS[len(self.items)]))

        if len(self.items) > cycle_size:
            self.items = self.items[:cycle_size]

        for index, item in enumerate(self.items):
            item.hotkey = DEFAULT_HOTKEYS[index]

        self.capture_slot_index %= cycle_size
        self.save_config()
        self.save_settings()

    def on_cycle_size_change(self) -> None:
        """Handle paste slot count changes from the UI."""
        self.apply_cycle_size()
        self.refresh_list()
        self.register_hotkeys()

    def toggle_app(self) -> None:
        """Toggle clipboard capture and hotkey paste together."""
        enabled = not self.app_enabled.get()
        self.app_enabled.set(enabled)
        self.capture_enabled.set(enabled)
        self.auto_paste_enabled.set(enabled)
        self.refresh_toggles()
        self.save_settings()
        self.register_hotkeys()

    def refresh_toggles(self) -> None:
        """Refresh switch-style toggle button labels and styles."""
        enabled = self.app_enabled.get()
        self.master_toggle.configure(
            text=f"Capture and paste: {'ON' if enabled else 'OFF'}",
            style="SwitchOn.TButton" if enabled else "SwitchOff.TButton",
        )

    def refresh_list(self) -> None:
        """Refresh the visible item list."""
        selected_index = self.get_selected_index()
        existing_rows = self.item_table.get_children()
        if existing_rows:
            self.item_table.delete(*existing_rows)

        for index, item in enumerate(self.items, start=1):
            preview = " ".join(item.text.split())
            if not preview:
                preview = "(empty slot)"
            if len(preview) > 110:
                preview = f"{preview[:107]}..."
            self.item_table.insert("", END, iid=str(index - 1), values=(f"{index:02d}", item.hotkey, preview))

        if selected_index is not None and self.items:
            iid = str(min(selected_index, len(self.items) - 1))
            self.item_table.selection_set(iid)
            self.item_table.focus(iid)

    def register_hotkeys(self) -> None:
        """Register global hotkeys for each configured item."""
        self.unregister_hotkeys()
        if not self.app_enabled.get():
            self.status_text.set("Capture and paste paused")
            return

        self.apply_cycle_size()
        self.refresh_list()

        self.hotkey_handles = []
        seen_hotkeys: set[str] = set()
        skipped_hotkeys: list[str] = []

        for index, item in enumerate(self.items):
            hotkey = item.hotkey.strip().lower()
            if not hotkey or hotkey in seen_hotkeys or not item.text:
                continue

            seen_hotkeys.add(hotkey)
            try:
                handle = keyboard.add_hotkey(hotkey, self.queue_paste, args=(index,), suppress=True)
                self.hotkey_handles.append(handle)
            except ValueError:
                skipped_hotkeys.append(hotkey)

        status = f"Registered {len(self.hotkey_handles)} hotkey(s)"
        if skipped_hotkeys:
            status += f"; skipped invalid: {', '.join(skipped_hotkeys)}"
        self.status_text.set(status)

    def unregister_hotkeys(self) -> None:
        """Remove global hotkeys that were registered by the app."""
        for handle in self.hotkey_handles:
            try:
                keyboard.remove_hotkey(handle)
            except KeyError:
                pass

        self.hotkey_handles = []

    def queue_paste(self, index: int) -> None:
        """Queue a paste operation on the Tkinter thread.

        Args:
            index: Zero-based item index to paste.
        """
        if self.sending_paste:
            return

        self.event_queue.put(lambda: self.paste_item(index))

    def paste_item(self, index: int) -> None:
        """Copy an assigned item to the clipboard and optionally paste it.

        Args:
            index: Zero-based item index to paste.
        """
        if index < 0 or index >= len(self.items):
            return

        item = self.items[index]
        pyperclip.copy(item.text)
        self.last_seen_clipboard = item.text
        self.status_text.set(f"Copied item {index + 1} using {item.hotkey}")

        if self.auto_paste_enabled.get():
            self.sending_paste = True
            self.root.after(60, self.send_paste_shortcut)

    def send_paste_shortcut(self) -> None:
        """Send Ctrl+V without recursively triggering an assigned paste item."""
        try:
            self.unregister_hotkeys()
            keyboard.send("ctrl+v")
        finally:
            self.root.after(120, self.restore_hotkeys_after_paste)

    def restore_hotkeys_after_paste(self) -> None:
        """Allow global hotkeys to run after an app-generated paste."""
        self.sending_paste = False
        self.register_hotkeys()

    def start_clipboard_monitor(self) -> None:
        """Start a background thread that notices clipboard changes."""
        try:
            self.last_seen_clipboard = pyperclip.paste()
        except pyperclip.PyperclipException:
            self.last_seen_clipboard = ""

        thread = threading.Thread(target=self.monitor_clipboard, daemon=True)
        thread.start()

    def monitor_clipboard(self) -> None:
        """Detect new clipboard text and add it to the item list."""
        while self.monitor_running:
            time.sleep(0.6)
            if not self.capture_enabled.get():
                continue

            try:
                current = pyperclip.paste()
            except pyperclip.PyperclipException:
                continue

            if not current or current == self.last_seen_clipboard:
                continue

            self.last_seen_clipboard = current
            self.event_queue.put(lambda text=current: self.capture_item(text))

    def process_event_queue(self) -> None:
        """Run queued callbacks from background hotkey and monitor threads."""
        if self.is_closing:
            return

        while True:
            try:
                callback = self.event_queue.get_nowait()
            except queue.Empty:
                break
            callback()

        self.root.after(80, self.process_event_queue)

    def add_current_clipboard(self) -> None:
        """Add the current clipboard contents as a new item."""
        try:
            text = pyperclip.paste()
        except pyperclip.PyperclipException as error:
            messagebox.showerror("Clipboard unavailable", str(error))
            return

        if not text:
            self.status_text.set("Clipboard is empty")
            return

        self.capture_item(text)

    def add_item(self, text: str, hotkey: str | None = None) -> None:
        """Add an item with the next available hotkey.

        Args:
            text: Clipboard text to store.
            hotkey: Optional explicit hotkey.
        """
        if any(item.text == text for item in self.items):
            return

        assigned_hotkey = hotkey or self.get_next_hotkey()
        self.items.append(ClipItem(text=text, hotkey=assigned_hotkey))
        self.save_config()
        self.refresh_list()
        self.register_hotkeys()

    def capture_item(self, text: str) -> None:
        """Store copied text into the next paste slot and wrap at cycle end.

        Args:
            text: Clipboard text to store.
        """
        if not text:
            return

        self.apply_cycle_size()
        slot_index = self.capture_slot_index
        self.items[slot_index] = ClipItem(text=text, hotkey=DEFAULT_HOTKEYS[slot_index])
        self.capture_slot_index = (self.capture_slot_index + 1) % self.cycle_size.get()
        self.save_config()
        self.refresh_list()
        self.register_hotkeys()
        self.status_text.set(f"Captured slot {slot_index + 1}; next slot {self.capture_slot_index + 1}")

    def get_next_hotkey(self) -> str:
        """Return the next default hotkey that is not already in use."""
        used_hotkeys = {item.hotkey.lower() for item in self.items}
        for hotkey in DEFAULT_HOTKEYS:
            if hotkey not in used_hotkeys:
                return hotkey

        return f"ctrl+shift+{len(self.items) + 1}"

    def open_add_text_dialog(self) -> None:
        """Open a dialog for manually adding a text item."""
        next_hotkey = DEFAULT_HOTKEYS[self.capture_slot_index]
        self.open_item_dialog("Add text", "", next_hotkey, self.create_item_from_dialog)

    def edit_selected(self) -> None:
        """Open a dialog for editing the selected item."""
        index = self.get_selected_index()
        if index is None:
            self.status_text.set("Select an item to edit")
            return

        item = self.items[index]
        self.open_item_dialog("Edit item", item.text, item.hotkey, lambda text, hotkey: self.update_item(index, text, hotkey))

    def open_item_dialog(
        self,
        title: str,
        text: str,
        hotkey: str,
        on_save: Callable[[str, str], None],
    ) -> None:
        """Open an item editor dialog.

        Args:
            title: Dialog title.
            text: Existing item text.
            hotkey: Existing hotkey.
            on_save: Callback invoked with edited text and hotkey.
        """
        dialog = Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("620x420")
        dialog.configure(bg=PINK_BG)
        dialog.iconphoto(True, self.app_icon)
        if ICON_PATH.exists():
            try:
                dialog.iconbitmap(str(ICON_PATH))
            except Exception:
                pass
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        ttk.Label(dialog, text="Hotkey").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 2))
        hotkey_var = StringVar(value=hotkey)
        hotkey_entry = ttk.Entry(dialog, textvariable=hotkey_var, state="readonly")
        hotkey_entry.grid(row=0, column=0, sticky="ew", padx=(70, 10), pady=(10, 2))

        ttk.Label(dialog, text="Text").grid(row=1, column=0, sticky="nw", padx=10, pady=(8, 2))
        text_box = Text(
            dialog,
            background=WHITE,
            foreground=PINK_TEXT,
            insertbackground=PINK_ACCENT_DARK,
            font=("Consolas", 10),
            relief="flat",
            wrap="word",
            undo=True,
        )
        text_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(28, 8))
        text_box.insert("1.0", text)

        controls = ttk.Frame(dialog, padding=(10, 0, 10, 10))
        controls.grid(row=2, column=0, sticky="ew")
        controls.columnconfigure(0, weight=1)

        def save_dialog() -> None:
            edited_text = text_box.get("1.0", END).strip()
            edited_hotkey = hotkey_var.get().strip().lower()
            if not edited_text:
                messagebox.showerror("Missing text", "Enter text for this item.")
                return
            if not edited_hotkey:
                messagebox.showerror("Missing hotkey", "Enter a hotkey such as ctrl+b.")
                return

            on_save(edited_text, edited_hotkey)
            dialog.destroy()

        ttk.Button(controls, text="Save", command=save_dialog).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(controls, text="Cancel", command=dialog.destroy).grid(row=0, column=2, padx=(6, 0))

    def create_item_from_dialog(self, text: str, hotkey: str) -> None:
        """Create a new item from dialog input.

        Args:
            text: Item text.
            hotkey: Assigned hotkey.
        """
        self.capture_item(text)

    def update_item(self, index: int, text: str, hotkey: str) -> None:
        """Update an existing item.

        Args:
            index: Zero-based item index.
            text: New item text.
            hotkey: New item hotkey.
        """
        self.items[index] = ClipItem(text=text, hotkey=DEFAULT_HOTKEYS[index])
        self.save_config()
        self.refresh_list()
        self.register_hotkeys()

    def remove_selected(self) -> None:
        """Remove the selected item."""
        index = self.get_selected_index()
        if index is None:
            self.status_text.set("Select an item to remove")
            return

        del self.items[index]
        self.save_config()
        self.refresh_list()
        self.register_hotkeys()

    def move_selected(self, offset: int) -> None:
        """Move the selected item up or down.

        Args:
            offset: -1 to move up, 1 to move down.
        """
        index = self.get_selected_index()
        if index is None:
            self.status_text.set("Select an item to move")
            return

        target_index = index + offset
        if target_index < 0 or target_index >= len(self.items):
            return

        self.items[index], self.items[target_index] = self.items[target_index], self.items[index]
        self.save_config()
        self.refresh_list()
        self.item_table.selection_set(str(target_index))
        self.item_table.focus(str(target_index))

    def get_selected_index(self) -> int | None:
        """Return the selected list index, if any."""
        selected = self.item_table.selection()
        if not selected:
            return None
        return int(selected[0])

    def close(self) -> None:
        """Stop background work and close the application."""
        if self.is_closing:
            return

        self.is_closing = True
        self.monitor_running = False
        self.capture_enabled.set(False)
        self.auto_paste_enabled.set(False)

        try:
            keyboard.unhook_all_hotkeys()
            keyboard.unhook_all()
        except Exception:
            pass

        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

        os._exit(0)


def main() -> None:
    """Run the Multi Paste Tool application."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Personal.MultiPasteTool")
    except Exception:
        pass

    root = Tk()
    MultiPasteTool(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        ERROR_LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")
        try:
            messagebox.showerror("Multi Paste failed to start", f"{error}\n\nDetails were written to:\n{ERROR_LOG_PATH}")
        except Exception:
            pass
        raise
