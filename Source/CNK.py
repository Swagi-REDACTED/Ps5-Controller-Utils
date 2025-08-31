import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import threading
import sys
import os
import time
import math
from queue import Queue, Empty
import ctypes
import platform

# --- Third-party library imports ---
# This script offers multiple backends for input simulation to maximize game compatibility.
#
# 1. pynput (Default): Uses the Win32 SendInput function. This is a high-level,
#    reliable method for most applications and games. However, some aggressive
#    anti-cheat systems can detect and block this type of API-based input.
#
# 2. ctypes (Win32 API): A more direct, lower-level way of calling the same
#    Windows input functions as pynput. It's provided as a compatibility option
#    for legacy games or applications that might not respond to pynput's wrapper.
#
# 3. pydirectinput (DirectInput): This library sends keyboard scancodes, which
#    is different from the virtual-key codes used by SendInput. Many DirectX games
#    are designed to listen for scancodes, making this method more effective for
#    games that ignore other input simulation techniques.
#
# The enhancements in this file focus on making the behavior and style of the input match that of a real keyboard and mouse
# as such theres some compatibility options built in to help it work with you're preferred game 
# if it doesnt work i suggest attempting to fix it yourself also please report any issues or incompatibilities to the github and ensure you post any fixes
# it will likely not work on games with aggressive ac scanning I.E. Valorant/Siege you'll have to test it yourself
from pystray import MenuItem as item, Icon
from PIL import Image, ImageTk, ImageDraw, ImageFont
from pynput import keyboard
from pynput import mouse
from pynput.mouse import Controller as MouseController

# --- Alternative Input Libraries ---
try:
    import pydirectinput
    # Configure pydirectinput for minimal delay
    pydirectinput.PAUSE = 0.001
    pydirectinput.FAILSAFE = False
except ImportError:
    pydirectinput = None


# --- DualSense Library ---
try:
    from dualsense_controller import DualSenseController, Mapping
except ImportError:
    DualSenseController = None
    Mapping = None

# --- Configuration ---
CONFIG_FILE = 'utility_app_config.json'

# --- Key Mapping for String to pynput object ---
SPECIAL_KEYS = {k.name: k for k in keyboard.Key}

# --- Message Box Flags ---
MB_OK = 0x00000000
MB_OKCANCEL = 0x00000001
MB_ICONEXCLAMATION = 0x00000030   # warning icon
MB_ICONINFORMATION = 0x00000040
MB_SYSTEMMODAL = 0x00001000       # topmost, blocks all windows
MB_SETFOREGROUND = 0x00010000     # bring to foreground
IDOK = 1
IDCANCEL = 2


# --- New Unified Keybinding Dialog ---
class KeyBindDialog(simpledialog.Dialog):
    """A custom dialog to capture up to two keystrokes, including system keys."""
    def __init__(self, parent, title=None, button_name=""):
        self.pressed_keys = []
        self.result = "" # Start with empty string, None indicates cancel
        self.button_name = button_name
        self.listener = None
        super().__init__(parent, title)

    def body(self, master):
        self.grab_set() # Capture all input, swallowing system keys
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        ttk.Label(master, text=f"Press up to two keys for '{self.button_name}'.\nSystem keys like Alt, Ctrl, and Win are captured.").pack(pady=10)
        
        self.key_display_var = tk.StringVar(value="Press a key...")
        ttk.Label(master, textvariable=self.key_display_var, font=('Segoe UI', 12, 'bold'), style='Active.TLabel', anchor='center').pack(pady=10, padx=20, fill='x')
        
        self.start_listener()
        return None

    def start_listener(self):
        # start both keyboard and mouse listeners (non-blocking)
        if getattr(self, 'klistener', None) is None or not getattr(self, 'klistener').is_alive():
            self.klistener = keyboard.Listener(on_press=self.on_key_press)
            self.klistener.start()
        if getattr(self, 'mlistener', None) is None or not getattr(self, 'mlistener').is_alive():
            self.mlistener = mouse.Listener(on_click=self.on_click)
            self.mlistener.start()


    def stop_listener(self):
        # stop both listeners if present
        for L in (getattr(self, 'klistener', None), getattr(self, 'mlistener', None)):
            if L:
                try:
                    L.stop()
                except Exception:
                    pass
        self.klistener = None
        self.mlistener = None

    def format_key(self, key):
        """Formats a pynput key object into a readable string."""
        try:
            # printable character (letters/numbers)
            if hasattr(key, 'char') and key.char is not None:
                return key.char
            # special keys (Esc, Ctrl, Alt, F1, etc.)
            if hasattr(key, 'name') and key.name:
                # normalize a few common names
                nm = key.name
                if nm.lower() in ('esc', 'escape'):
                    return 'Escape'
                if nm.lower() == 'space':
                    return 'Space'
                if nm.lower() == 'return':
                    return 'Enter'
                return nm
        except Exception:
            pass
        return None

    def on_key_press(self, key):
        try:
            key_str = self.format_key(key)
            if key_str and key_str not in self.pressed_keys:
                if len(self.pressed_keys) < 2:
                    self.pressed_keys.append(key_str)
                    # Schedule the GUI update on the main Tkinter thread for safety
                    self.after(0, self.update_display)
        except Exception as e:
            print(f"Error processing key: {e}")

    def _click_within_dialog(self, x, y):
        """Return True if screen coords (x,y) are inside this dialog window."""
        try:
            # ensure geometry is up-to-date
            self.update_idletasks()
            x0 = self.winfo_rootx()
            y0 = self.winfo_rooty()
            x1 = x0 + self.winfo_width()
            y1 = y0 + self.winfo_height()
            return x0 <= x <= x1 and y0 <= y <= y1
        except Exception:
            return False

    def on_click(self, x, y, button, pressed):
        # ignore releases
        if not pressed:
            return
        # IGNORE clicks that happened inside the dialog (so pressing OK/Clear/Cancel
        # doesn't get captured as MouseLeft)
        if self._click_within_dialog(x, y):
            return

        try:
            name = getattr(button, 'name', None) or str(button).split('.')[-1]
            key_str = {
                'left': 'MouseLeft',
                'right': 'MouseRight',
                'middle': 'MouseMiddle',
                'x1': 'MouseX1',
                'x2': 'MouseX2'
            }.get(name.lower(), f"Mouse{name}")
            if key_str not in self.pressed_keys and len(self.pressed_keys) < 2:
                self.pressed_keys.append(key_str)
                self.after(0, self.update_display)
        except Exception as e:
            print(f"Error processing mouse: {e}")

    def update_display(self):
        # Sort modifiers first for consistency (e.g., 'alt+f4' not 'f4+alt')
        modifiers = sorted([k for k in self.pressed_keys if 'alt' in k or 'ctrl' in k or 'shift' in k or 'cmd' in k])
        others = sorted([k for k in self.pressed_keys if k not in modifiers])
        display_text = "+".join(modifiers + others)
        self.key_display_var.set(display_text if display_text else "Press a key...")

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="Clear", width=10, command=self._on_clear).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="Cancel", width=10, command=self.cancel).pack(side=tk.LEFT, padx=5, pady=5)
        box.pack()

    def _on_clear(self):
        self.pressed_keys.clear()
        self.after(0, self.update_display)
        
    def _on_cancel(self):
        self.cancel()

    def ok(self, event=None):
        self.result = self.key_display_var.get()
        if self.result == "Press a key...": self.result = ""
        self.stop_listener()
        self.withdraw()
        self.update_idletasks()
        self.parent.focus_set()
        self.destroy()

    def cancel(self, event=None):
        self.result = None # Use None to indicate cancellation
        self.stop_listener()
        self.withdraw()
        self.update_idletasks()
        self.parent.focus_set()
        self.destroy()

class UtilityApp:
    """
    Main application class to manage state, GUI, and background listeners.
    """
    def __init__(self):
        # --- App State ---
        self.current_index = 0
        self.cycle_keys = []
        self.settings = {"profiles": {}, "active_profile": ""}
        self.settings_window = None
        self.icon = None
        self.active_tab_name = ""

        # --- Input Controllers ---
        self.keyboard_controller_pynput = keyboard.Controller()
        self.mouse_controller_pynput = MouseController()

        # Default to pynput
        self.active_key_presser   = self._press_key_pynput
        self.active_key_releaser  = self._release_key_pynput
        self.active_mouse_presser = self._press_mouse_pynput
        self.active_mouse_releaser= self._release_mouse_pynput
        self.active_mouse_mover   = self._move_mouse_pynput

        # --- DualSense Controller State ---
        self.controller = None
        self.controller_thread = None
        self.is_running = threading.Event()
        self.update_queue = Queue()
        self.last_stick_move_time = 0
        self.last_delta_x = 0
        self.last_delta_y = 0
        # --- NEW: State for Adaptive Mouse Mode ---
        self.last_confinement_check = 0
        self.confinement_check_interval = 0.1  # Check every 100ms
        self.is_mouse_confined = False
        self.adaptive_mode_active = False
        self.last_controller_status = ("Initializing...", "#E0E0E0")
        
        # --- Robust Input Handling State ---
        self.key_press_requests = {} # {'source': {'key1', 'key2'}}
        self.currently_pressed_keys = set()
        self.stick_active_direction = None

        # --- UI State for Tester, Keys & Mapper Tabs ---
        self.base_resized_tester_image = None
        self.working_tester_image = None
        self.controller_tester_photoimage = None
        self.image_on_canvas = None
        self.keys_canvas_photoimage = None 
        self.keys_image_on_canvas = None
        self.mapper_canvas_photoimage = None
        self.mapper_image_on_canvas = None
        self.base_resized_mapper_image = None
        self.key_mapping_labels = {}
        self.key_mapping_label_vars = {}

        self.button_states = {btn: False for btn in [
            'L1', 'L2', 'L3', 'R1', 'R2', 'R3',
            'Triangle', 'Circle', 'Cross', 'Square',
            'D-Pad Up', 'D-Pad Right', 'D-Pad Down', 'D-Pad Left',
            'Create', 'Options', 'PS', 'Touchpad', 'Mic'
        ]}
        self.analog_states = {
            'left_stick': (127.5, 127.5),
            'right_stick': (127.5, 127.5),
            'left_trigger': 0,
            'right_trigger': 0
        }
        self.touchpad_state = {
            'finger1': {'active': False, 'x': 0, 'y': 0},
            'finger2': {'active': False, 'x': 0, 'y': 0}
        }
        self.trigger_effects = {}
        self.font = None

        # --- Setup the main Tkinter window but keep it hidden ---
        self.root = tk.Tk()
        self.root.withdraw()

        # --- Load settings and initialize ---
        self.load_settings()
        self.update_cycle_keys_from_settings()
        self._initialize_controllers()

    @staticmethod
    def show_windows_ok_cancel(title: str, message: str, warning: bool = True) -> bool:
        """
        Show a native Windows MessageBoxW with OK / Cancel.
        Returns True if user clicked OK, False if user clicked Cancel.
        On non-Windows platforms uses tkinter.messagebox.askokcancel.
        """
        # Platform fallback: tkinter askokcancel returns True for OK, False for Cancel
        if platform.system() != "Windows":
            root = tk.Tk()
            root.withdraw()
            result = messagebox.askokcancel(title, message, icon='warning' if warning else 'info')
            root.destroy()
            return result

        flags = MB_OKCANCEL | MB_SETFOREGROUND | MB_SYSTEMMODAL
        flags |= (MB_ICONEXCLAMATION if warning else MB_ICONINFORMATION)
        # MessageBoxW returns IDOK or IDCANCEL (integers)
        res = ctypes.windll.user32.MessageBoxW(0, message, title, flags)
        return int(res) == IDOK

    def resource_path(self, relative_path):
        """
        Return an absolute path to a resource.

        Priority:
        1) Folder where the running EXE/script lives (preferred for 'next-to-exe' files)
        2) Current working directory
        3) PyInstaller _MEIPASS (bundled files when using --add-data)
        4) Fallback: path relative to the source file
        """
        # 1) Folder of the running exe (if frozen) or the script directory
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable) or os.getcwd()
        else:
            exe_dir = os.path.dirname(os.path.abspath(__file__))

        candidates = [
            os.path.join(exe_dir, relative_path),
            os.path.join(os.getcwd(), relative_path),
        ]

        # 3) MEIPASS (PyInstaller onefile bundles get extracted here)
        try:
            meipass = sys._MEIPASS  # type: ignore[attr-defined]
        except Exception:
            meipass = None
        if meipass:
            candidates.append(os.path.join(meipass, relative_path))

        # 4) final fallback: script-relative
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path))

        # return the first that exists; otherwise return the last candidate so caller can see attempted path
        for p in candidates:
            if os.path.exists(p):
                return p
        return candidates[-1]

    # --- NEW: Profile and Settings Management ---
    def get_active_settings(self):
        """Returns the settings dictionary for the currently active profile."""
        return self.settings["profiles"].get(self.settings.get("active_profile"), {})

    def _ensure_default_settings(self, settings_dict):
        """Ensures a given settings dictionary has all necessary default values."""
        # Key Cycler settings
        settings_dict.setdefault('key_cycler_enabled', False)
        settings_dict.setdefault('mode', 'default')
        settings_dict.setdefault('default_start', '1')
        settings_dict.setdefault('default_end', '0')
        settings_dict.setdefault('custom_keys', ['1', '2', '3', 'q', 'w', 'e'])

        # DualSense Mouse Control settings
        settings_dict.setdefault('dualsense_mouse_enabled', False)
        settings_dict.setdefault('dualsense_mouse_mode', 'Browser')
        settings_dict.setdefault('adaptive_game_mode', False)
        settings_dict.setdefault('dualsense_sensitivity', 15.0)
        
        # --- MODIFIED: Handle migration from old deadzone settings to new independent ones ---
        old_inner_dz = settings_dict.get('dualsense_inner_deadzone', 0.08)
        old_outer_dz = settings_dict.get('dualsense_outer_deadzone', 0.95)
        
        settings_dict.setdefault('dualsense_left_inner_deadzone', old_inner_dz)
        settings_dict.setdefault('dualsense_left_outer_deadzone', old_outer_dz)
        settings_dict.setdefault('dualsense_right_inner_deadzone', old_inner_dz)
        settings_dict.setdefault('dualsense_right_outer_deadzone', old_outer_dz)
        
        settings_dict.setdefault('dualsense_invert_mouse_x', False)
        settings_dict.setdefault('dualsense_invert_mouse_y', False)
        settings_dict.setdefault('hide_hid_device', False)
        
        settings_dict.setdefault('browser_exponent_enabled', True)
        settings_dict.setdefault('browser_exponent', 2.0)
        settings_dict.setdefault('browser_acceleration_enabled', False)
        settings_dict.setdefault('browser_acceleration_rate', 0.1)

        settings_dict.setdefault('game_exponent_enabled', True)
        settings_dict.setdefault('game_exponent', 2.4)
        settings_dict.setdefault('game_acceleration_enabled', False)
        settings_dict.setdefault('game_acceleration_rate', 0.1)
        settings_dict.setdefault('game_sensitivity_multiplier', 1.5)

        settings_dict.setdefault('selected_controller_index', 0)
        settings_dict.setdefault('keep_thread_running', False)
        
        # DualSense Keys settings
        settings_dict.setdefault('dualsense_keys_enabled', False)
        settings_dict.setdefault('dualsense_swap_sticks', False)
        settings_dict.setdefault('dualsense_keys_mappings', {
            'n': 'w', 'ne': 'w+d', 'e': 'd', 'se': 's+d', 
            's': 's', 'sw': 's+a', 'w': 'a', 'nw': 'w+a'
        })
        
        # New Key Mapper settings
        settings_dict.setdefault('dualsense_custom_mappings_enabled', False)
        settings_dict.setdefault('dualsense_custom_mappings', {})

        # Compatibility settings
        settings_dict.setdefault('mouse_compatibility_mode', 'pynput')
        settings_dict.setdefault('keyboard_compatibility_mode', 'pynput')

    def load_settings(self):
        """Loads settings from a JSON file, or creates default settings with profile support."""
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
            if "profiles" not in data or "active_profile" not in data: # Migration for old config
                print("Old config format found, migrating to new profile system...")
                self.settings = {
                    "profiles": {"Default": data},
                    "active_profile": "Default"
                }
                self.save_settings_to_file()
            else:
                self.settings = data
        except (FileNotFoundError, json.JSONDecodeError):
            self.settings = {
                "profiles": {"Default": {}},
                "active_profile": "Default"
            }
        
        # Ensure the active profile exists, otherwise reset it
        if self.settings.get("active_profile") not in self.settings.get("profiles", {}):
            self.settings["active_profile"] = next(iter(self.settings.get("profiles", {"Default": {}})), "Default")

        # Ensure all profiles have the latest default values
        for profile_name, profile_settings in self.settings["profiles"].items():
            self._ensure_default_settings(profile_settings)
        
        print(f"Settings loaded. Active profile: '{self.settings['active_profile']}'")

    def _initialize_controllers(self):
        """Sets the active input functions based on current settings."""
        active_settings = self.get_active_settings()

        # --- Mouse Mode ---
        mouse_mode = active_settings.get('mouse_compatibility_mode', 'pynput')
        if mouse_mode == 'ctypes':
            self.active_mouse_mover   = self._move_mouse_ctypes
            self.active_mouse_presser = self._press_mouse_ctypes
            self.active_mouse_releaser= self._release_mouse_ctypes
            print("Mouse Compatibility Layer: Win32 API (ctypes)")
        elif mouse_mode == 'pydirectinput' and pydirectinput:
            self.active_mouse_mover   = self._move_mouse_pynput  # pydirectinput has no move
            self.active_mouse_presser = self._press_mouse_pydirectinput
            self.active_mouse_releaser= self._release_mouse_pydirectinput
            print("Mouse Compatibility Layer: DirectInput")
        else:
            if mouse_mode == 'pydirectinput' and not pydirectinput:
                print("Warning: pydirectinput not found. Falling back to pynput.")
                self.get_active_settings()['mouse_compatibility_mode'] = 'pynput'
            self.active_mouse_mover   = self._move_mouse_pynput
            self.active_mouse_presser = self._press_mouse_pynput
            self.active_mouse_releaser= self._release_mouse_pynput
            print("Mouse Compatibility Layer: pynput (Default)")

        # --- Keyboard Mode ---
        keyboard_mode = active_settings.get('keyboard_compatibility_mode', 'pynput')
        if keyboard_mode == 'pydirectinput' and pydirectinput:
            self.active_key_presser  = self._press_key_pydirectinput
            self.active_key_releaser = self._release_key_pydirectinput
            print("Keyboard Compatibility Layer: DirectInput")
        else:
            if keyboard_mode == 'pydirectinput' and not pydirectinput:
                print("Warning: pydirectinput not found. Falling back to pynput.")
                self.get_active_settings()['keyboard_compatibility_mode'] = 'pynput'
            self.active_key_presser  = self._press_key_pynput
            self.active_key_releaser = self._release_key_pynput
            print("Keyboard Compatibility Layer: pynput (Default)")


    def save_settings_to_file(self):
        """Saves the current settings structure (including all profiles) to the JSON file."""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.settings, f, indent=4)
            print("Settings saved to file.")
        except IOError as e:
            print(f"Error saving settings: {e}")
            if self.settings_window and self.settings_window.winfo_exists():
                messagebox.showerror("Save Error", f"Could not write settings to file:\n{e}")

    def update_cycle_keys_from_settings(self):
        """Updates the active list of keys to cycle through based on current settings."""
        active_settings = self.get_active_settings()
        if active_settings.get('mode') == 'custom':
            self.cycle_keys = active_settings.get('custom_keys', [])
        else:
            start_char = active_settings.get('default_start', '1')
            end_char = active_settings.get('default_end', '0')
            all_nums = [str(i) for i in range(1, 10)] + ['0']
            try:
                start_index, end_index = all_nums.index(start_char), all_nums.index(end_char)
                if start_index <= end_index:
                    self.cycle_keys = all_nums[start_index:end_index + 1]
                else:
                    self.cycle_keys = all_nums[start_index:] + all_nums[:end_index + 1]
            except ValueError:
                self.cycle_keys = all_nums
        self.current_index = 0
        print(f"Active cycle keys: {self.cycle_keys}")
        if not self.cycle_keys:
            print("Warning: Cycle key list is empty.")

    def cycle_forward(self):
        active_settings = self.get_active_settings()
        if not active_settings.get('key_cycler_enabled', False) or not self.cycle_keys: return
        self.current_index = (self.current_index + 1) % len(self.cycle_keys)
        self.press_current_key()

    def cycle_backward(self):
        active_settings = self.get_active_settings()
        if not active_settings.get('key_cycler_enabled', False) or not self.cycle_keys: return
        self.current_index = (self.current_index - 1 + len(self.cycle_keys)) % len(self.cycle_keys)
        self.press_current_key()

# --- Methods for pressing/releasing keys, unified wrappers ---
    def press_key_from_string(self, key_str):
        if not key_str or not key_str.strip():
            return
        key_str = key_str.strip()
        
        # Make mouse button detection case-insensitive
        if key_str.lower().startswith("mouse"):
            # Normalize mouse button names to proper case
            key_str = self._normalize_mouse_button_name(key_str)
            self.active_mouse_presser(key_str)
        else:
            self.active_key_presser(key_str)

    def release_key_from_string(self, key_str):
        if not key_str or not key_str.strip():
            return
        key_str = key_str.strip()
        
        # Make mouse button detection case-insensitive
        if key_str.lower().startswith("mouse"):
            # Normalize mouse button names to proper case
            key_str = self._normalize_mouse_button_name(key_str)
            self.active_mouse_releaser(key_str)
        else:
            self.active_key_releaser(key_str)

    def _normalize_mouse_button_name(self, key_str):
        """Normalize mouse button names to proper case format."""
        lower_key = key_str.lower()
        mapping = {
            "mouseleft": "MouseLeft",
            "mouseright": "MouseRight", 
            "mousemiddle": "MouseMiddle",
            "mousex1": "MouseX1",
            "mousex2": "MouseX2"
        }
        return mapping.get(lower_key, key_str)

    # --- Pynput Implementation ---
    def _press_key_pynput(self, key_str):
        key_str = key_str.strip()
        if not key_str: 
            return
        try:
            if key_str in SPECIAL_KEYS:
                self.keyboard_controller_pynput.press(SPECIAL_KEYS[key_str])
            elif len(key_str) == 1:
                self.keyboard_controller_pynput.press(key_str)
            else:
                print(f"Warning (pynput): Cannot press unknown key string '{key_str}'")
        except Exception as e:
            print(f"Error (pynput) pressing key '{key_str}': {e}")

    def _release_key_pynput(self, key_str):
        key_str = key_str.strip()
        if not key_str: 
            return
        try:
            if key_str in SPECIAL_KEYS:
                self.keyboard_controller_pynput.release(SPECIAL_KEYS[key_str])
            elif len(key_str) == 1:
                self.keyboard_controller_pynput.release(key_str)
            else:
                print(f"Warning (pynput): Cannot release unknown key string '{key_str}'")
        except Exception as e:
            print(f"Error (pynput) releasing key '{key_str}': {e}")

    # --- PyDirectInput Implementation ---
    def _press_key_pydirectinput(self, key_str):
        key_str = key_str.strip()
        if not key_str: 
            return
        try:
            pydirectinput.keyDown(key_str)
        except Exception as e:
            print(f"Error (pydirectinput) pressing key '{key_str}': {e}")
            
    def _release_key_pydirectinput(self, key_str):
        key_str = key_str.strip()
        if not key_str: 
            return
        try:
            pydirectinput.keyUp(key_str)
        except Exception as e:
            print(f"Error (pydirectinput) releasing key '{key_str}': {e}")

    # --- Mouse Button Implementations (raw backends) ---
    def _press_mouse_pynput(self, key_str):
        try:
            mapping = {
                "MouseLeft": mouse.Button.left,
                "MouseRight": mouse.Button.right,
                "MouseMiddle": mouse.Button.middle,
                "MouseX1": mouse.Button.x1,
                "MouseX2": mouse.Button.x2,
            }
            btn = mapping.get(key_str)
            if btn:
                print(f"Debug: Pressing mouse button {key_str} with pynput")
                self.mouse_controller_pynput.press(btn)
            else:
                print(f"Warning: Unknown mouse button '{key_str}'")
        except Exception as e:
            print(f"Error (pynput) pressing mouse '{key_str}': {e}")

    def _release_mouse_pynput(self, key_str):
        try:
            mapping = {
                "MouseLeft": mouse.Button.left,
                "MouseRight": mouse.Button.right,
                "MouseMiddle": mouse.Button.middle,
                "MouseX1": mouse.Button.x1,
                "MouseX2": mouse.Button.x2,
            }
            btn = mapping.get(key_str)
            if btn:
                print(f"Debug: Releasing mouse button {key_str} with pynput")
                self.mouse_controller_pynput.release(btn)
            else:
                print(f"Warning: Unknown mouse button '{key_str}'")
        except Exception as e:
            print(f"Error (pynput) releasing mouse '{key_str}': {e}")

    def _press_mouse_pydirectinput(self, key_str):
        try:
            mapping = {
                "MouseLeft": "left",
                "MouseRight": "right",
                "MouseMiddle": "middle",
                "MouseX1": "x1",
                "MouseX2": "x2",
            }
            btn = mapping.get(key_str)
            if btn:
                print(f"Debug: Pressing mouse button {key_str} with pydirectinput")
                pydirectinput.mouseDown(button=btn)
            else:
                print(f"Warning: Unknown mouse button '{key_str}'")
        except Exception as e:
            print(f"Error (pydirectinput) pressing mouse '{key_str}': {e}")

    def _release_mouse_pydirectinput(self, key_str):
        try:
            mapping = {
                "MouseLeft": "left",
                "MouseRight": "right",
                "MouseMiddle": "middle",
                "MouseX1": "x1",
                "MouseX2": "x2",
            }
            btn = mapping.get(key_str)
            if btn:
                print(f"Debug: Releasing mouse button {key_str} with pydirectinput")
                pydirectinput.mouseUp(button=btn)
            else:
                print(f"Warning: Unknown mouse button '{key_str}'")
        except Exception as e:
            print(f"Error (pydirectinput) releasing mouse '{key_str}': {e}")

    def _press_mouse_ctypes(self, key_str):
        mapping = {
            "MouseLeft": 0x0002,   # MOUSEEVENTF_LEFTDOWN
            "MouseRight": 0x0008,  # MOUSEEVENTF_RIGHTDOWN
            "MouseMiddle": 0x0020, # MOUSEEVENTF_MIDDLEDOWN
            "MouseX1": 0x0080,     # MOUSEEVENTF_XDOWN
            "MouseX2": 0x0080,     # MOUSEEVENTF_XDOWN
        }
        flag = mapping.get(key_str)
        if flag:
            extra = 1 if key_str == "MouseX1" else (2 if key_str == "MouseX2" else 0)
            print(f"Debug: Pressing mouse button {key_str} with ctypes (flag: {hex(flag)}, extra: {extra})")
            ctypes.windll.user32.mouse_event(flag, 0, 0, extra, 0)
        else:
            print(f"Warning: Unknown mouse button '{key_str}'")

    def _release_mouse_ctypes(self, key_str):
        mapping = {
            "MouseLeft": 0x0004,   # MOUSEEVENTF_LEFTUP
            "MouseRight": 0x0010,  # MOUSEEVENTF_RIGHTUP
            "MouseMiddle": 0x0040, # MOUSEEVENTF_MIDDLEUP
            "MouseX1": 0x0100,     # MOUSEEVENTF_XUP (FIXED)
            "MouseX2": 0x0100,     # MOUSEEVENTF_XUP (FIXED)
        }
        flag = mapping.get(key_str)
        if flag:
            extra = 1 if key_str == "MouseX1" else (2 if key_str == "MouseX2" else 0)
            print(f"Debug: Releasing mouse button {key_str} with ctypes (flag: {hex(flag)}, extra: {extra})")
            ctypes.windll.user32.mouse_event(flag, 0, 0, extra, 0)
        else:
            print(f"Warning: Unknown mouse button '{key_str}'")

    # --- Mouse Movement Implementations ---
    def _move_mouse_pynput(self, dx, dy):
        self.mouse_controller_pynput.move(dx, dy)
        
    def _move_mouse_ctypes(self, dx, dy):
        # MOUSEEVENTF_MOVE = 0x0001
        ctypes.windll.user32.mouse_event(0x0001, int(dx), int(dy), 0, 0)

    def press_current_key(self):
        if not self.cycle_keys:
            return
        key_to_press = self.cycle_keys[self.current_index]
        print(f"Debug: Attempting to press key: '{key_to_press}'")
        self.press_key_from_string(key_to_press)
        self.release_key_from_string(key_to_press)

    def _process_stick_input_for_mouse(self, x, y, effective_mode=None):
        """
        Unified mouse processing logic with a hard deadzone cutoff and 360-division quantization.
        """
        active_settings = self.get_active_settings()
        mouse_mode = effective_mode or active_settings.get('dualsense_mouse_mode', 'Browser')
        
        # Determine which stick is being used for the mouse
        swap_sticks = active_settings.get('dualsense_swap_sticks', False)
        # If sticks are swapped, the left stick is for the mouse. Otherwise, it's the right.
        stick_prefix = 'left' if swap_sticks else 'right'
        
        # Use the inner deadzone setting
        inner_deadzone = float(active_settings.get(f'dualsense_{stick_prefix}_inner_deadzone', 0.08))
        sensitivity = active_settings.get('dualsense_sensitivity', 15.0)

        # Apply sensitivity multiplier for game mode
        if mouse_mode == 'Game':
            multiplier = active_settings.get('game_sensitivity_multiplier', 1.5)
            sensitivity *= multiplier

        # --- Modified Deadzone and Speed Calculation ---
        # Increased NUM_DIVISIONS for finer, smoother mouse control.
        NUM_DIVISIONS = 360
        magnitude = math.sqrt(x**2 + y**2)

        # If inside the inner deadzone, do nothing. This is the simple cutoff.
        if magnitude < inner_deadzone:
            return 0, 0

        # --- MODIFIED LOGIC ---
        # The original code rescaled the input range to start from 0 at the deadzone edge.
        # This new logic uses the raw magnitude for speed calculation, creating a "hard"
        # deadzone that matches the behavior of _process_stick_input_for_keys.
        
        # Clamp magnitude to 1.0 to handle potential out-of-bounds controller values
        clamped_magnitude = min(magnitude, 1.0)
        final_speed = clamped_magnitude * sensitivity

        # --- Angle Quantization Logic (Unchanged) ---
        # Get angle in radians
        angle_rad = math.atan2(y, x)
        
        # Convert angle to degrees [0, 360]
        angle_deg = math.degrees(angle_rad)
        if angle_deg < 0:
            angle_deg += 360

        # Calculate which discrete division the angle falls into
        division_size_deg = 360.0 / NUM_DIVISIONS
        division_index = round(angle_deg / division_size_deg) % NUM_DIVISIONS
        
        # Get the precise, quantized angle for the center of that division
        quantized_angle_rad = math.radians(division_index * division_size_deg)

        # Calculate final mouse delta (dx, dy)
        final_x = math.cos(quantized_angle_rad) * final_speed
        final_y = math.sin(quantized_angle_rad) * final_speed
        
        return final_x, final_y

    def _apply_mouse_acceleration(self, delta_x, delta_y, effective_mode=None):
        """Applies acceleration with optional mode override."""
        active_settings = self.get_active_settings()
        mouse_mode = effective_mode or active_settings.get('dualsense_mouse_mode', 'Browser')
        accel_rate = active_settings.get(f'{mouse_mode.lower()}_acceleration_rate', 0.1)
        
        current_time = time.time()
        time_diff = current_time - self.last_stick_move_time
        self.last_stick_move_time = current_time

        if time_diff < 0.001 or time_diff > 0.1:
            self.last_delta_x, self.last_delta_y = 0, 0
            return delta_x, delta_y

        accel_factor_x = 1.0 + abs(delta_x - self.last_delta_x) * accel_rate
        accel_factor_y = 1.0 + abs(delta_y - self.last_delta_y) * accel_rate
        
        self.last_delta_x, self.last_delta_y = delta_x, delta_y
        return delta_x * accel_factor_x, delta_y * accel_factor_y

    def _perform_natural_mouse_move(self, dx, dy, effective_mode=None):
        """Enhanced mouse movement with optional mode override."""
        active_settings = self.get_active_settings()
        mouse_mode = effective_mode or active_settings.get('dualsense_mouse_mode', 'Browser')

        if mouse_mode == 'Game':
            self.active_mouse_mover(dx, dy)
            return

        # Original logic for Browser mode
        magnitude = math.sqrt(dx**2 + dy**2)
        steps = max(2, int(magnitude / 4))

        if steps > 0:
            step_dx = dx / steps
            step_dy = dy / steps
            for _ in range(steps):
                self.active_mouse_mover(step_dx, step_dy)

    # --- REFINED: Adaptive Mouse Mode Logic ---
    def _is_mouse_cursor_confined(self):
        """
        Detects if the mouse cursor is confined/captured by checking the system's
        cursor clipping rectangle. This method avoids any mouse movement,
        preventing visual jitter.
        Returns True if confined, False if free to move.
        """
        try:
            # Get the dimensions of the entire screen
            screen_width = ctypes.windll.user32.GetSystemMetrics(0) # SM_CXSCREEN
            screen_height = ctypes.windll.user32.GetSystemMetrics(1) # SM_CYSCREEN

            # Define the RECT structure for the GetClipCursor function
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long),
                            ("top", ctypes.c_long),
                            ("right", ctypes.c_long),
                            ("bottom", ctypes.c_long)]

            clip_rect = RECT()
            
            # Call the Win32 API function to get the current clipping rectangle
            ctypes.windll.user32.GetClipCursor(ctypes.byref(clip_rect))

            # Check if the clipping rectangle is smaller than the full screen.
            # If it is, the cursor is confined.
            is_confined = (clip_rect.left > 0 or
                           clip_rect.top > 0 or
                           clip_rect.right < screen_width or
                           clip_rect.bottom < screen_height)

            return is_confined

        except Exception as e:
            print(f"Error checking mouse confinement via GetClipCursor: {e}")
            # Fallback to a safe default if the API call fails
            return False

    def _get_effective_mouse_mode(self, active_settings):
        """
        Determines the effective mouse mode based on adaptive settings and cursor confinement.
        """
        base_mode = active_settings.get('dualsense_mouse_mode', 'Browser')
        adaptive_enabled = active_settings.get('adaptive_game_mode', False)
        
        # Adaptive mode is only relevant if the base mode is "Game" and the toggle is on
        if not adaptive_enabled or base_mode != 'Game':
            return base_mode
        
        # If adaptive mode is active, check mouse confinement periodically
        current_time = time.time()
        if current_time - self.last_confinement_check > self.confinement_check_interval:
            self.is_mouse_confined = self._is_mouse_cursor_confined()
            self.last_confinement_check = current_time
            
            # Log when the adaptive mode state changes
            new_adaptive_status = self.is_mouse_confined
            if new_adaptive_status != self.adaptive_mode_active:
                self.adaptive_mode_active = new_adaptive_status
                mode_text = "Game" if self.adaptive_mode_active else "Browser"
                print(f"Adaptive mode: Switched to {mode_text} (Mouse {'confined' if self.is_mouse_confined else 'free'})")
        
        # Return Game mode if the mouse is confined, otherwise fall back to Browser mode
        return 'Game' if self.is_mouse_confined else 'Browser'
    
    def _update_keyboard_state(self):
        """
        Reconciles all key press requests from various sources (stick, buttons)
        and updates the actual keyboard state to match. This prevents conflicts
        and ensures keys are released correctly.
        """
        all_requested_keys = set()
        for source, keys in self.key_press_requests.items():
            all_requested_keys.update(keys)

        keys_to_release = self.currently_pressed_keys - all_requested_keys
        for key in keys_to_release:
            self.release_key_from_string(key)

        keys_to_press = all_requested_keys - self.currently_pressed_keys
        for key in keys_to_press:
            self.press_key_from_string(key)
            
        self.currently_pressed_keys = all_requested_keys

    def _process_stick_input_for_keys(self, x, y):
        """
        Processes left stick input to determine which keys should be held down.
        """
        # --- MODIFIED: Use configurable inner deadzone from settings ---
        active_settings = self.get_active_settings()
        swap_sticks = active_settings.get('dualsense_swap_sticks', False)
        # Keys are on the left stick by default, so if sticks are swapped, use right stick settings
        stick_prefix = 'right' if swap_sticks else 'left'
        deadzone = float(active_settings.get(f'dualsense_{stick_prefix}_inner_deadzone', 0.2)) # Use a slightly larger default for keys
        
        magnitude = math.sqrt(x**2 + y**2)

        new_direction = None
        if magnitude > deadzone:
            angle = math.degrees(math.atan2(y, x))
            if angle < 0: angle += 360

            if 337.5 <= angle or angle < 22.5: new_direction = 'E'
            elif 22.5 <= angle < 67.5: new_direction = 'SE'
            elif 67.5 <= angle < 112.5: new_direction = 'S'
            elif 112.5 <= angle < 157.5: new_direction = 'SW'
            elif 157.5 <= angle < 202.5: new_direction = 'W'
            elif 202.5 <= angle < 247.5: new_direction = 'NW'
            elif 247.5 <= angle < 292.5: new_direction = 'N'
            elif 292.5 <= angle < 337.5: new_direction = 'NE'

        mappings = {k.upper(): v for k, v in active_settings['dualsense_keys_mappings'].items()}
        keys_str = mappings.get(new_direction, '') if new_direction else ''
        current_target_keys = set(key for key in keys_str.split('+') if key)

        self.key_press_requests['stick'] = current_target_keys
        
        if new_direction != self.stick_active_direction:
            self.stick_active_direction = new_direction
            self.queue_update('keys_direction_update', new_direction)

    def controller_loop(self):
        """Main loop for handling controller inputs and reconciling keyboard/mouse state."""
        print("Controller thread started.")
        while self.is_running.is_set():
            try:
                if self.controller:
                    active_settings = self.get_active_settings()
                    
                    # --- Determine which stick is for mouse and which is for keys ---
                    swap_sticks = active_settings.get('dualsense_swap_sticks', False)
                    if swap_sticks:
                        mouse_stick_value = self.controller.left_stick.value
                        keys_stick_value = self.controller.right_stick.value
                    else:
                        mouse_stick_value = self.controller.right_stick.value
                        keys_stick_value = self.controller.left_stick.value
                    
                    # --- Process Mouse ---
                    if active_settings.get('dualsense_mouse_enabled'):
                        rx_raw, ry_raw = mouse_stick_value.x, mouse_stick_value.y
                        norm_x = (rx_raw - 127.5) / 127.5
                        norm_y = (ry_raw - 127.5) / 127.5
                        
                        effective_mouse_mode = self._get_effective_mouse_mode(active_settings)
                        delta_x, delta_y = self._process_stick_input_for_mouse(norm_x, norm_y, effective_mode=effective_mouse_mode)

                        if active_settings.get(f'{effective_mouse_mode.lower()}_acceleration_enabled', False):
                            delta_x, delta_y = self._apply_mouse_acceleration(delta_x, delta_y, effective_mode=effective_mouse_mode)
                        
                        if active_settings.get('dualsense_invert_mouse_x', False): delta_x = -delta_x
                        if active_settings.get('dualsense_invert_mouse_y', False): delta_y = -delta_y
                        
                        if abs(delta_x) > 0.01 or abs(delta_y) > 0.01:
                            self._perform_natural_mouse_move(delta_x, delta_y, effective_mode=effective_mouse_mode)

                    # --- Process Keys ---
                    if active_settings.get('dualsense_keys_enabled'):
                        lx_raw, ly_raw = keys_stick_value.x, keys_stick_value.y
                        norm_x = (lx_raw - 127.5) / 127.5
                        norm_y = (ly_raw - 127.5) / 127.5
                        self._process_stick_input_for_keys(norm_x, norm_y)
                    else:
                        if 'stick' in self.key_press_requests:
                            self.key_press_requests['stick'] = set()
                    
                    # --- Process Button Mappings ---
                    if not active_settings.get('dualsense_custom_mappings_enabled'):
                        keys_to_delete = [key for key in self.key_press_requests if key.startswith('button_')]
                        for key in keys_to_delete:
                            del self.key_press_requests[key]

                    # --- Reconcile Keyboard State ---
                    self._update_keyboard_state()

                time.sleep(0.005)
            except Exception as e:
                print(f"Error in controller loop (likely disconnected): {e}")
                self.handle_disconnection()
                time.sleep(1) 
        print("Controller thread stopped.")
    
    def handle_disconnection(self):
        """Gracefully handles controller disconnection."""
        if self.controller:
            try:
                self.controller.deactivate()
            except: pass
        self.controller = None
        # Clean up keyboard state on disconnect
        self.key_press_requests.clear()
        self._update_keyboard_state()
        self.queue_update('status', "Controller Disconnected", '#F44336')

    def start_controller_thread(self):
        """Initializes controller and starts the connection management thread."""
        if self.controller_thread and self.controller_thread.is_alive():
            return
        
        self.is_running.set()
        self.controller_thread = threading.Thread(target=self.connection_manager_loop, daemon=True)
        self.controller_thread.start()

    def connection_manager_loop(self):
        """A loop to manage the controller's connection state and the mouse loop."""
        mouse_thread = None
        while self.is_running.is_set():
            if self.controller is None:
                if self.try_connect_controller():
                    time.sleep(0.1)
                    mouse_thread = threading.Thread(target=self.controller_loop, daemon=True)
                    mouse_thread.start()
            else:
                if mouse_thread is None or not mouse_thread.is_alive():
                     self.handle_disconnection()
            time.sleep(2)

    def _register_controller_callbacks(self):
        """Centralized function to register all controller event handlers."""
        
        def create_button_handler(button_name):
            request_source = f"button_{button_name}"

            def on_down():
                self.queue_update('tester_button_update', button_name, True)
                
                active_settings = self.get_active_settings()
                if active_settings.get('key_cycler_enabled', False):
                    if button_name == 'R1': self.cycle_forward()
                    if button_name == 'L1': self.cycle_backward()

                if active_settings.get('dualsense_custom_mappings_enabled', False):
                    mapped_key_str = active_settings.get('dualsense_custom_mappings', {}).get(button_name)
                    if mapped_key_str:
                        keys_to_press = set(key for key in mapped_key_str.split('+') if key)
                        self.key_press_requests[request_source] = keys_to_press
            
            def on_up():
                self.queue_update('tester_button_update', button_name, False)
                if self.get_active_settings().get('dualsense_custom_mappings_enabled', False):
                    self.key_press_requests.pop(request_source, None)
            
            return on_down, on_up

        buttons_to_register = {
            'Cross': self.controller.btn_cross, 'Circle': self.controller.btn_circle, 'Square': self.controller.btn_square, 'Triangle': self.controller.btn_triangle,
            'L1': self.controller.btn_l1, 'R1': self.controller.btn_r1, 'L2': self.controller.btn_l2, 'R2': self.controller.btn_r2, 
            'L3': self.controller.btn_l3, 'R3': self.controller.btn_r3, 'D-Pad Up': self.controller.btn_up, 'D-Pad Down': self.controller.btn_down, 
            'D-Pad Left': self.controller.btn_left, 'D-Pad Right': self.controller.btn_right, 'Create': self.controller.btn_create, 'Options': self.controller.btn_options, 
            'PS': self.controller.btn_ps, 'Touchpad': self.controller.btn_touchpad, 'Mic': self.controller.btn_mute
        }
        for name, btn_prop in buttons_to_register.items():
            down_handler, up_handler = create_button_handler(name)
            btn_prop.on_down(down_handler)
            btn_prop.on_up(up_handler)

        self.controller.left_stick.on_change(lambda val: self.queue_update('tester_analog_update', 'left_stick', (val.x, val.y)))
        self.controller.right_stick.on_change(lambda val: self.queue_update('tester_analog_update', 'right_stick', (val.x, val.y)))
        self.controller.left_trigger.on_change(lambda val: self.queue_update('tester_analog_update', 'left_trigger', val))
        self.controller.right_trigger.on_change(lambda val: self.queue_update('tester_analog_update', 'right_trigger', val))
        
        def on_touch(finger, name):
            self.queue_update('tester_touchpad_update', name, {'active': finger.active, 'x': finger.x, 'y': finger.y})
        self.controller.touch_finger_1.on_change(lambda f: on_touch(f, 'finger1'))
        self.controller.touch_finger_2.on_change(lambda f: on_touch(f, 'finger2'))

        self.controller.battery.on_change(lambda b: self.queue_update('tester_battery_update', (b.level_percentage, b.charging, b.full)))


    def try_connect_controller(self):
        """Attempts to find and activate a DualSense controller."""
        self.queue_update('status', "Searching...", '#FFC107')
        try:
            if DualSenseController:
                device_infos = DualSenseController.enumerate_devices()
                if device_infos:
                    active_settings = self.get_active_settings()
                    device_index = active_settings.get('selected_controller_index', 0)
                    if device_index >= len(device_infos):
                        device_index = 0
                        active_settings['selected_controller_index'] = 0
                        self.save_settings_to_file()

                    self.controller = DualSenseController(device_index_or_device_info=device_index, mapping=Mapping.RAW)
                    self.controller.on_error(lambda err: self.queue_update('error', err))
                    self._register_controller_callbacks()
                    self.controller.activate()
                    self.queue_update('status', f"Connected to Device {device_index}", '#4CAF50')
                    return True
                else:
                    self.queue_update('status', "No Controllers Found", '#F44336')
            else:
                 self.queue_update('status', "dualsense-controller not installed", '#F44336')
        except Exception as e:
            error_message = f"Connection Error: {e}"
            print(f"Failed to connect: {e}")
            self.controller = None
            self.queue_update('status', error_message, '#F44336')
        return False


    def stop_controller_thread(self):
        """Stops and cleans up the controller connection and threads."""
        self.is_running.clear()
        
        self.handle_disconnection()
        
        if self.controller_thread and self.controller_thread.is_alive():
            self.controller_thread.join(timeout=1)
        self.controller_thread = None
        
        self.stick_active_direction = None


    def _on_tab_changed(self, event):
        """Callback for when the notebook tab is changed."""
        try:
            notebook = event.widget
            self.active_tab_name = notebook.tab(notebook.select(), "text")
            if self.active_tab_name == 'Controller Tester':
                self.refresh_controller_list()
                self.settings_window.after(50, self.redraw_tester_image)
            elif self.active_tab_name == 'DualSense Keys':
                self.settings_window.after(50, self.redraw_keys_canvas)
            elif self.active_tab_name == 'Key Mapper':
                self.settings_window.after(50, lambda: self._update_mapper_canvas_size(self.mapper_canvas.winfo_width(), self.mapper_canvas.winfo_height()))
            print(f"Active tab changed to: {self.active_tab_name}")
        except tk.TclError:
            pass

    def create_settings_window(self):
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
            
        win = tk.Toplevel(self.root)
        win.title("Utility Settings")
        win.geometry("1920x1040")
        win.minsize(800, 700) # Increased min height for profiles
        win.configure(bg='#2E2E2E')
        self.settings_window = win
        
        try:
            self.font = ImageFont.truetype("arial.ttf", 15)
        except IOError:
            self.font = ImageFont.load_default()
        
        style = ttk.Style(win)
        style.theme_use('clam')
        self.configure_styles(style)

        # --- NEW: Profile Management Frame ---
        profile_frame = ttk.LabelFrame(win, text="Settings Profile", style='TLabelframe', padding="10")
        profile_frame.pack(pady=(10,0), padx=15, fill="x")
        
        ttk.Label(profile_frame, text="Current Profile:").pack(side="left", padx=(0,5))
        
        self.profile_var = tk.StringVar()
        self.profile_combobox = ttk.Combobox(profile_frame, textvariable=self.profile_var, state='readonly', width=30)
        self.profile_combobox.pack(side="left", padx=5)
        self.profile_combobox.bind("<<ComboboxSelected>>", self._on_profile_selected)
        
        ttk.Button(profile_frame, text="Create New", command=self._create_profile, style='Save.TButton').pack(side="left", padx=5)
        ttk.Button(profile_frame, text="Delete", command=self._delete_profile, style='Save.TButton').pack(side="left", padx=5)
        
        notebook = ttk.Notebook(win, style='TNotebook')
        notebook.pack(pady=15, padx=15, expand=True, fill="both")
        notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        cycler_frame = ttk.Frame(notebook, style='TFrame', padding="15")
        dualsense_frame = ttk.Frame(notebook, style='TFrame', padding="15")
        dualsense_keys_frame = ttk.Frame(notebook, style='TFrame', padding="15")
        mapper_frame = ttk.Frame(notebook, style='TFrame', padding="15")
        tester_frame = ttk.Frame(notebook, style='TFrame', padding="15")
        compatibility_frame = ttk.Frame(notebook, style='TFrame', padding="15")
        
        notebook.add(cycler_frame, text='Key Cycler')
        notebook.add(dualsense_frame, text='DualSense Mouse')
        notebook.add(dualsense_keys_frame, text='DualSense Keys')
        notebook.add(mapper_frame, text='Key Mapper')
        notebook.add(compatibility_frame, text='Compatibility')
        notebook.add(tester_frame, text='Controller Tester')
        
        self.active_tab_name = 'Key Cycler'
        
        self.populate_key_cycler_tab(cycler_frame)
        self.populate_dualsense_mouse_tab(dualsense_frame)
        self.populate_dualsense_keys_tab(dualsense_keys_frame)
        self.populate_key_mapper_tab(mapper_frame)
        self.populate_compatibility_tab(compatibility_frame)
        self.populate_controller_tester_tab(tester_frame)
        
        # Load current profile data into UI and update profile list
        self._update_profile_dropdown()
        self._load_settings_into_ui()
        
        button_frame = ttk.Frame(win, style='TFrame')
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Save", command=lambda: self.on_save_only(win), style='Save.TButton').pack(side="left", padx=10)
        ttk.Button(button_frame, text="Save and Close", command=lambda: self.on_save_and_close(win), style='Save.TButton').pack(side="left", padx=10)

        win.protocol("WM_DELETE_WINDOW", lambda: self.on_close_settings(win))
        
        self.start_controller_thread()

        win.after(50, self._initial_tester_render)
        self.process_updates()

    def _initial_tester_render(self):
        """Forces the initial drawing of the controller tester canvas."""
        if self.settings_window and self.settings_window.winfo_exists() and hasattr(self, 'canvas') and self.canvas:
            self._update_tester_canvas_size(self.canvas.winfo_width(), self.canvas.winfo_height())


    def configure_styles(self, style):
        BG_COLOR, FG_COLOR, ACCENT_COLOR, ENTRY_BG = '#2E2E2E', '#E0E0E0', '#007ACC', '#3C3C3C'
        style.configure('TFrame', background=BG_COLOR)
        style.configure('TNotebook', background=BG_COLOR, borderwidth=0)
        style.configure('TNotebook.Tab', background='#3C3C3C', foreground=FG_COLOR, padding=[10, 5], borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', ACCENT_COLOR)])
        style.configure('TLabel', background=BG_COLOR, foreground=FG_COLOR, font=('Segoe UI', 10))
        style.configure('TLabelframe', background=BG_COLOR, bordercolor=ACCENT_COLOR)
        style.configure('TLabelframe.Label', background=BG_COLOR, foreground=ACCENT_COLOR, font=('Segoe UI', 11, 'bold'))
        style.configure('TRadiobutton', background=BG_COLOR, foreground=FG_COLOR, indicatorcolor=ENTRY_BG, font=('Segoe UI', 10))
        style.map('TRadiobutton', background=[('active', '#3C3C3C')])
        style.configure('TCheckbutton', background=BG_COLOR, foreground=FG_COLOR, font=('Segoe UI', 10))
        style.configure('TEntry', fieldbackground=ENTRY_BG, foreground=FG_COLOR, bordercolor=ACCENT_COLOR, insertcolor=FG_COLOR)
        style.configure('TCombobox', fieldbackground=ENTRY_BG, foreground=FG_COLOR, bordercolor=ACCENT_COLOR, arrowcolor=FG_COLOR)
        style.configure('Save.TButton', background=ACCENT_COLOR, foreground='white', font=('Segoe UI', 10, 'bold'), borderwidth=0, padding=10)
        style.map('Save.TButton', background=[('active', '#005f9e')])
        style.configure('Active.TEntry', fieldbackground=ACCENT_COLOR, foreground='white')
        style.configure('Active.TLabel', background=ACCENT_COLOR, foreground='white', padding=5)
        
    def on_close_settings(self, win):
        if not self.get_active_settings().get('keep_thread_running', False):
            self.stop_controller_thread()
        self.active_tab_name = ""
        win.destroy()
        self.settings_window = None

    def populate_key_cycler_tab(self, parent_frame):
        top_frame = ttk.Frame(parent_frame)
        top_frame.pack(fill='x', pady=5)
        
        self.key_cycler_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(top_frame, text="Enable Key Cycler (L1/R1 Hotkeys)", variable=self.key_cycler_enabled_var).pack(side='left', padx=5)

        self.mode_var = tk.StringVar()
        mode_frame = ttk.LabelFrame(parent_frame, text="Active Key Cycler Mode", padding="10")
        mode_frame.pack(padx=10, pady=10, fill="x")
        ttk.Radiobutton(mode_frame, text="Default (Number Range)", variable=self.mode_var, value="default").pack(side="left", padx=5)
        ttk.Radiobutton(mode_frame, text="Custom (Any Keys)", variable=self.mode_var, value="custom").pack(side="left", padx=5)
        
        default_frame = ttk.LabelFrame(parent_frame, text="Default Mode Settings", padding="10")
        default_frame.pack(padx=10, pady=10, fill="x")
        ttk.Label(default_frame, text="Cycle between two numbers (inclusive).").pack(pady=(0,10))
        range_frame = ttk.Frame(default_frame)
        range_frame.pack(pady=5)
        all_nums = [str(i) for i in range(1, 10)] + ['0']
        ttk.Label(range_frame, text="Start:").pack(side="left")
        self.default_start_var = tk.StringVar()
        ttk.Combobox(range_frame, textvariable=self.default_start_var, values=all_nums, width=5).pack(side="left", padx=5)
        ttk.Label(range_frame, text="End:").pack(side="left")
        self.default_end_var = tk.StringVar()
        ttk.Combobox(range_frame, textvariable=self.default_end_var, values=all_nums, width=5).pack(side="left", padx=5)

        custom_frame = ttk.LabelFrame(parent_frame, text="Custom Mode Settings", padding="10")
        custom_frame.pack(padx=10, pady=10, fill="both", expand=True)
        listbox_frame = ttk.Frame(custom_frame)
        listbox_frame.pack(pady=5, fill="both", expand=True)
        self.custom_keys_listbox = tk.Listbox(listbox_frame, height=8, bg='#3C3C3C', fg='#E0E0E0', selectbackground='#007ACC', borderwidth=0, highlightthickness=0)
        self.custom_keys_listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.custom_keys_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.custom_keys_listbox.config(yscrollcommand=scrollbar.set)

    def populate_dualsense_mouse_tab(self, parent_frame):
        # General Frame
        general_frame = ttk.LabelFrame(parent_frame, text="General Mouse Settings", padding=10)
        general_frame.pack(fill='x', pady=5)
        
        self.dualsense_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(general_frame, text="Enable DualSense Mouse Control", variable=self.dualsense_enabled_var).grid(row=0, column=0, columnspan=2, sticky='w', pady=5)
        
        self.keep_thread_var = tk.BooleanVar()
        ttk.Checkbutton(general_frame, text="Keep controller connected when settings are closed", variable=self.keep_thread_var).grid(row=1, column=0, columnspan=2, sticky='w', pady=5)
        
        self.hide_hid_var = tk.BooleanVar()
        ttk.Checkbutton(general_frame, text="Hide HID Device from Games (Requires 3rd party HidHide)", variable=self.hide_hid_var).grid(row=2, column=0, columnspan=2, sticky='w', pady=5)
        
        self.adapt_game_var = tk.BooleanVar()
        ttk.Checkbutton(general_frame, text="Adaptive game mode (Requires game mode to be active)", variable=self.adapt_game_var).grid(row=3, column=0, columnspan=2, sticky='w', pady=5)
        
        self.sensitivity_var = tk.StringVar()
        ttk.Label(general_frame, text="Sensitivity:").grid(row=4, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(general_frame, textvariable=self.sensitivity_var, width=10).grid(row=4, column=1, sticky='w', padx=5, pady=5)

        self.invert_x_var = tk.BooleanVar()
        self.invert_y_var = tk.BooleanVar()
        ttk.Checkbutton(general_frame, text="Invert Mouse X-Axis", variable=self.invert_x_var).grid(row=5, column=0, sticky='w', padx=5, pady=5)
        ttk.Checkbutton(general_frame, text="Invert Mouse Y-Axis", variable=self.invert_y_var).grid(row=5, column=1, sticky='w', padx=5, pady=5)

        # --- NEW: Independent Deadzone Settings Frame ---
        deadzone_frame = ttk.LabelFrame(parent_frame, text="Stick Deadzones (0-1)", padding=10)
        deadzone_frame.pack(fill='x', pady=5)
        deadzone_frame.grid_columnconfigure(1, weight=1)
        deadzone_frame.grid_columnconfigure(2, weight=1)

        ttk.Label(deadzone_frame, text="Left Stick").grid(row=0, column=1, pady=(0, 5))
        ttk.Label(deadzone_frame, text="Right Stick").grid(row=0, column=2, pady=(0, 5))

        self.left_inner_deadzone_var = tk.StringVar()
        self.left_outer_deadzone_var = tk.StringVar()
        self.right_inner_deadzone_var = tk.StringVar()
        self.right_outer_deadzone_var = tk.StringVar()

        ttk.Label(deadzone_frame, text="Inner:").grid(row=1, column=0, sticky='e', padx=5)
        ttk.Entry(deadzone_frame, textvariable=self.left_inner_deadzone_var, width=8).grid(row=1, column=1)
        ttk.Entry(deadzone_frame, textvariable=self.right_inner_deadzone_var, width=8).grid(row=1, column=2)

        ttk.Label(deadzone_frame, text="Outer:").grid(row=2, column=0, sticky='e', padx=5)
        ttk.Entry(deadzone_frame, textvariable=self.left_outer_deadzone_var, width=8).grid(row=2, column=1, pady=5)
        ttk.Entry(deadzone_frame, textvariable=self.right_outer_deadzone_var, width=8).grid(row=2, column=2, pady=5)

        # Mouse Mode Frame
        mode_frame = ttk.LabelFrame(parent_frame, text="Mouse Mode", padding="10")
        mode_frame.pack(fill='x', pady=5)
        self.mouse_mode_var = tk.StringVar()
        ttk.Radiobutton(mode_frame, text="Browser Mode", variable=self.mouse_mode_var, value="Browser").pack(side='left', padx=10)
        ttk.Radiobutton(mode_frame, text="Game Mode", variable=self.mouse_mode_var, value="Game").pack(side='left', padx=10)

        # Browser Mode Settings
        browser_mode_frame = ttk.LabelFrame(parent_frame, text="Browser Mode Settings", padding="10")
        browser_mode_frame.pack(fill='x', pady=5)
        self.browser_exponent_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(browser_mode_frame, text="Enable Exponent Curve", variable=self.browser_exponent_enabled_var).grid(row=0, column=0, columnspan=2, sticky='w')
        self.browser_exponent_var = tk.StringVar()
        ttk.Label(browser_mode_frame, text="Exponent:").grid(row=1, column=0, sticky='w', padx=5, pady=2)
        ttk.Entry(browser_mode_frame, textvariable=self.browser_exponent_var, width=10).grid(row=1, column=1, sticky='w', padx=5)
        
        self.browser_accel_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(browser_mode_frame, text="Enable Acceleration", variable=self.browser_accel_enabled_var).grid(row=2, column=0, columnspan=2, sticky='w')
        self.browser_accel_rate_var = tk.StringVar()
        ttk.Label(browser_mode_frame, text="Acceleration Rate:").grid(row=3, column=0, sticky='w', padx=5, pady=2)
        ttk.Entry(browser_mode_frame, textvariable=self.browser_accel_rate_var, width=10).grid(row=3, column=1, sticky='w', padx=5)

        # Game Mode Settings
        game_mode_frame = ttk.LabelFrame(parent_frame, text="Game Mode Settings", padding="10")
        game_mode_frame.pack(fill='x', pady=5)
        self.game_exponent_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(game_mode_frame, text="Enable Exponent Curve", variable=self.game_exponent_enabled_var).grid(row=0, column=0, columnspan=2, sticky='w')
        self.game_exponent_var = tk.StringVar()
        ttk.Label(game_mode_frame, text="Exponent:").grid(row=1, column=0, sticky='w', padx=5, pady=2)
        ttk.Entry(game_mode_frame, textvariable=self.game_exponent_var, width=10).grid(row=1, column=1, sticky='w', padx=5)
        
        self.game_accel_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(game_mode_frame, text="Enable Acceleration", variable=self.game_accel_enabled_var).grid(row=2, column=0, columnspan=2, sticky='w')
        self.game_accel_rate_var = tk.StringVar()
        ttk.Label(game_mode_frame, text="Acceleration Rate:").grid(row=3, column=0, sticky='w', padx=5, pady=2)
        ttk.Entry(game_mode_frame, textvariable=self.game_accel_rate_var, width=10).grid(row=3, column=1, sticky='w', padx=5)

        self.game_sensitivity_multiplier_var = tk.StringVar()
        ttk.Label(game_mode_frame, text="Sensitivity Multiplier:").grid(row=4, column=0, sticky='w', padx=5, pady=2)
        ttk.Entry(game_mode_frame, textvariable=self.game_sensitivity_multiplier_var, width=10).grid(row=4, column=1, sticky='w', padx=5)


    def populate_dualsense_keys_tab(self, parent_frame):
        self.keys_image_on_canvas = None
        self.key_mapping_labels = {}
        self.key_mapping_label_vars = {}

        top_frame = ttk.Frame(parent_frame)
        top_frame.pack(fill='x', pady=5)

        self.dualsense_keys_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(top_frame, text="Enable Stick Key Mapping", variable=self.dualsense_keys_enabled_var).pack(side='left', padx=10)
        
        self.swap_sticks_var = tk.BooleanVar()
        ttk.Checkbutton(top_frame, text="Swap Left and Right Sticks", variable=self.swap_sticks_var).pack(side='left', padx=10)

        main_container = ttk.Frame(parent_frame)
        main_container.pack(expand=True, fill='both', pady=5, padx=5)

        self.keys_canvas = tk.Canvas(main_container, bg='#1E1E1E', highlightthickness=0, width=300)
        self.keys_canvas.pack(side='left', expand=True, fill='both', pady=5, padx=5)
        self.keys_canvas.bind('<Configure>', lambda e: self.redraw_keys_canvas())

        bindings_frame_container = ttk.LabelFrame(main_container, text="Key Bindings")
        bindings_frame_container.pack(side='right', fill='y', padx=10)

        bindings_grid = ttk.Frame(bindings_frame_container)
        bindings_grid.pack(padx=10, pady=10)

        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']

        for i, direction in enumerate(directions):
            ttk.Label(bindings_grid, text=f"{direction}:").grid(row=i, column=0, sticky='e', pady=3)
            
            label_var = tk.StringVar()
            self.key_mapping_label_vars[direction] = label_var
            
            label_widget = ttk.Label(bindings_grid, textvariable=label_var, width=12, anchor='center', 
                                     background='#3C3C3C', foreground='#E0E0E0', padding=(0, 2),
                                     font=('Segoe UI', 10))
            self.key_mapping_labels[direction] = label_widget
            label_widget.grid(row=i, column=1, padx=5)
            
            btn = ttk.Button(bindings_grid, text="Bind", command=lambda d=direction: self.open_stick_key_bind_dialog(d))
            btn.grid(row=i, column=2, padx=(0, 5))

    def open_stick_key_bind_dialog(self, direction):
        dialog = KeyBindDialog(self.settings_window, title="Set Stick Direction Bind", button_name=direction)
        new_key = dialog.result

        if new_key is not None:
            self.get_active_settings()['dualsense_keys_mappings'][direction.lower()] = new_key
            self.key_mapping_label_vars[direction].set(new_key)
            self.save_settings_to_file()

    def redraw_keys_canvas(self, *args):
        if not self.settings_window or not self.settings_window.winfo_exists() or not hasattr(self, 'keys_canvas'): return
        
        self.keys_canvas.delete("all")
        width = self.keys_canvas.winfo_width()
        height = self.keys_canvas.winfo_height()
        if width <= 1 or height <= 1: 
            self.settings_window.after(50, self.redraw_keys_canvas)
            return

        center_x, center_y = width / 2, height / 2
        
        active_settings = self.get_active_settings()
        swap_sticks = active_settings.get('dualsense_swap_sticks', False)
        
        stick_to_draw = 'right_stick' if swap_sticks else 'left_stick'
        stick_prefix = 'right' if swap_sticks else 'left'

        inner_dz = float(active_settings.get(f'dualsense_{stick_prefix}_inner_deadzone', 0.08))
        outer_dz = float(active_settings.get(f'dualsense_{stick_prefix}_outer_deadzone', 0.95))
        
        stick_obj = self.analog_states[stick_to_draw]
        x_val, y_val = stick_obj[0], stick_obj[1]
        x_offset_norm, y_offset_norm = (x_val - 127.5) / 127.5, (y_val - 127.5) / 127.5
        
        self.draw_stick_indicator_on_canvas(self.keys_canvas, center_x, center_y, x_offset_norm, y_offset_norm, inner_dz, outer_dz)

    def draw_stick_indicator_on_canvas(self, canvas, base_x, base_y, x_val, y_val, inner_deadzone, outer_deadzone):
        """
        Draws a stick indicator with deadzones on a tkinter canvas.
        base_x, base_y: center of the ring in canvas coords.
        x_val, y_val: normalized axis values in range [-1.0, 1.0].
        inner_deadzone, outer_deadzone: deadzone values in range [0.0, 1.0].
        """
        try:
            # Sizes
            width = canvas.winfo_width()
            height = canvas.winfo_height()
            ring_radius = min(width, height) * 0.35
            
            # Safety bounds for deadzones
            inner_deadzone = max(0.0, min(0.99, inner_deadzone))
            outer_deadzone = max(inner_deadzone + 0.001, min(1.0, outer_deadzone))

            # Draw outer boundary ring
            canvas.create_oval(base_x - ring_radius, base_y - ring_radius,
                               base_x + ring_radius, base_y + ring_radius,
                               outline='#007ACC', width=2)

            # Compute pixel radii for inner/outer deadzones
            inner_px = inner_deadzone * ring_radius
            outer_px = outer_deadzone * ring_radius

            # Draw inner deadzone ring (orange, dashed)
            canvas.create_oval(base_x - inner_px, base_y - inner_px,
                               base_x + inner_px, base_y + inner_px,
                               outline='#FF9800', width=2, dash=(3, 4))
            
            # Draw outer deadzone ring (orange, dashed)
            canvas.create_oval(base_x - outer_px, base_y - outer_px,
                               base_x + outer_px, base_y + outer_px,
                               outline='#FF9800', width=2, dash=(3, 4))

            # Compute vector magnitude
            vec = math.hypot(x_val, y_val)
            dot_x, dot_y = base_x, base_y

            # If inside inner deadzone, dot is at center
            if vec > inner_deadzone:
                # Clamp vector to outer_deadzone
                capped_vec = min(vec, outer_deadzone)
                
                # Scale magnitude to a 0-1 range between inner and outer deadzones
                deadzone_range = outer_deadzone - inner_deadzone
                scaled = (capped_vec - inner_deadzone) / deadzone_range if deadzone_range > 0 else 1.0
                scaled = max(0.0, min(1.0, scaled))

                # Compute direction unit vector
                if vec > 0:
                    ux = x_val / vec
                    uy = y_val / vec
                else: # Should not happen due to vec > inner_deadzone check, but as a fallback
                    ux, uy = 0, 0
                
                # Compute final pixel radius for the dot
                final_r = inner_px + scaled * (outer_px - inner_px)
                dot_x = base_x + ux * final_r
                dot_y = base_y + uy * final_r

            # Draw direction line from center to dot
            canvas.create_line(base_x, base_y, dot_x, dot_y, fill='#007ACC', width=2)
            
            # Draw the dot
            dot_radius = 8
            canvas.create_oval(dot_x - dot_radius, dot_y - dot_radius, dot_x + dot_radius, dot_y + dot_radius, fill='#007ACC', outline='white')

        except Exception as e:
            print(f"Error in draw_stick_indicator_on_canvas: {e}")
            try:
                canvas.create_text(base_x, base_y, text="ERR", fill="red")
            except Exception:
                pass


    def populate_key_mapper_tab(self, parent_frame):
        top_frame = ttk.Frame(parent_frame)
        top_frame.pack(fill='x', pady=5)
        
        self.custom_mappings_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(top_frame, text="Enable Custom Key Mapper", variable=self.custom_mappings_enabled_var).pack(side='left', padx=10)

        self.mapper_canvas = tk.Canvas(parent_frame, bg='#1E1E1E', highlightthickness=0)
        self.mapper_canvas.pack(expand=True, fill='both', pady=5, padx=5)
        
        self.mapper_canvas.bind('<Configure>', lambda e: self._update_mapper_canvas_size(e.width, e.height))
        self.mapper_canvas.bind('<Button-1>', self.on_mapper_canvas_click)

    def populate_compatibility_tab(self, parent_frame):
        # --- Mouse Compatibility ---
        mouse_frame = ttk.LabelFrame(parent_frame, text="Mouse Compatibility Layer", padding=10)
        mouse_frame.pack(fill='x', pady=5)
        
        self.mouse_compat_var = tk.StringVar()
        
        ttk.Radiobutton(mouse_frame, text="pynput (Default)", variable=self.mouse_compat_var, value="pynput").pack(anchor='w', padx=10, pady=2)
        ttk.Radiobutton(mouse_frame, text="Win32 API (ctypes, Recommended for compatibilty could cause errors)", variable=self.mouse_compat_var, value="ctypes").pack(anchor='w', padx=10, pady=2)

        # --- Keyboard Compatibility ---
        keyboard_frame = ttk.LabelFrame(parent_frame, text="Keyboard Compatibility Layer", padding=10)
        keyboard_frame.pack(fill='x', pady=5)
        
        self.keyboard_compat_var = tk.StringVar()

        ttk.Radiobutton(keyboard_frame, text="pynput (Default)", variable=self.keyboard_compat_var, value="pynput").pack(anchor='w', padx=10, pady=2)
        
        direct_input_rb = ttk.Radiobutton(keyboard_frame, text="DirectInput (for DirectX games, Recommended)", variable=self.keyboard_compat_var, value="pydirectinput")
        direct_input_rb.pack(anchor='w', padx=10, pady=2)
        
        if not pydirectinput:
            direct_input_rb.config(state='disabled')
            ttk.Label(keyboard_frame, text=" (pydirectinput library not found. Install with: pip install pydirectinput)", foreground="#FFA500").pack(anchor='w', padx=25)

    def _update_mapper_canvas_size(self, canvas_width, canvas_height):
        if not hasattr(self, 'original_tester_image') or not self.original_tester_image: return
        if canvas_width <= 1 or canvas_height <= 1: return
        
        img_ratio = self.original_tester_image.width / self.original_tester_image.height
        canvas_ratio = canvas_width / canvas_height
        
        new_width = canvas_width if canvas_ratio <= img_ratio else int(canvas_height * img_ratio)
        new_height = int(new_width / img_ratio) if canvas_ratio <= img_ratio else canvas_height
            
        self.base_resized_mapper_image = self.original_tester_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.redraw_mapper_canvas()

    def redraw_mapper_canvas(self):
        if not self.base_resized_mapper_image or not self.mapper_canvas.winfo_exists(): return
        
        active_settings = self.get_active_settings()
        working_image = self.base_resized_mapper_image.copy()
        draw = ImageDraw.Draw(working_image, 'RGBA')

        current_width, current_height = working_image.size
        scale_x, scale_y = current_width / 1200.0, current_height / 800.0

        for button_name, pos in self.get_button_positions().items():
            scaled_x, scaled_y = int(pos[0] * scale_x), int(pos[1] * scale_y)
            
            mapped_key = active_settings.get('dualsense_custom_mappings', {}).get(button_name)
            fill_color = (0, 255, 0, 100) if mapped_key else (255, 255, 0, 100)
            draw.ellipse([scaled_x-15, scaled_y-15, scaled_x+15, scaled_y+15], fill=fill_color)
            if mapped_key:
                try:
                    text_bbox = draw.textbbox((0,0), mapped_key, font=self.font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]
                    draw.text((scaled_x - text_width/2, scaled_y - text_height/2), mapped_key, font=self.font, fill="white")
                except: 
                    draw.text((scaled_x, scaled_y), mapped_key, font=self.font, fill="white", anchor="mm")


        self.mapper_canvas_photoimage = ImageTk.PhotoImage(working_image)
        
        canvas_width, canvas_height = self.mapper_canvas.winfo_width(), self.mapper_canvas.winfo_height()
        if self.mapper_image_on_canvas: self.mapper_canvas.itemconfig(self.mapper_image_on_canvas, image=self.mapper_canvas_photoimage)
        else: self.mapper_image_on_canvas = self.mapper_canvas.create_image(canvas_width / 2, canvas_height / 2, image=self.mapper_canvas_photoimage)
        self.mapper_canvas.coords(self.mapper_image_on_canvas, canvas_width / 2, canvas_height / 2)

    def get_button_positions(self):
        return {
            'L2': (298, 188), 'L1': (292, 235), 'R2': (907, 188), 'R1': (909, 235), 'Triangle': (901, 320), 'Circle': (971, 367), 'Cross': (901, 415), 'Square': (831, 368),
            'D-Pad Up': (311, 330), 'D-Pad Right': (354, 367), 'D-Pad Down': (311, 405), 'D-Pad Left': (267, 367), 'Create': (385, 295), 'Options': (827, 295), 'PS': (606, 450), 
            'L3': (456, 455), 'R3': (758, 455), 'Mic': (606, 485), 'Touchpad': (606, 325)
        }

    def on_mapper_canvas_click(self, event):
            if not self.base_resized_mapper_image: return
            
            canvas_width = self.mapper_canvas.winfo_width()
            canvas_height = self.mapper_canvas.winfo_height()
            img_width = self.base_resized_mapper_image.width
            img_height = self.base_resized_mapper_image.height
            
            img_x = event.x - (canvas_width - img_width) / 2
            img_y = event.y - (canvas_height - img_height) / 2

            scale_x = img_width / 1200.0
            scale_y = img_height / 800.0
            click_radius = 20

            for button_name, pos in self.get_button_positions().items():
                scaled_x, scaled_y = int(pos[0] * scale_x), int(pos[1] * scale_y)
                if math.sqrt((img_x - scaled_x)**2 + (img_y - scaled_y)**2) < click_radius:
                    dialog = KeyBindDialog(self.settings_window, title="Set Keybind", button_name=button_name)
                    new_key = dialog.result
                    if new_key is not None:
                        active_settings = self.get_active_settings()
                        if new_key.strip() == "":
                            if button_name in active_settings['dualsense_custom_mappings']:
                                del active_settings['dualsense_custom_mappings'][button_name]
                        else:
                            # FIXED: Don't convert mouse buttons to lowercase
                            if new_key.lower().startswith("mouse"):
                                # Keep mouse buttons in proper case
                                active_settings['dualsense_custom_mappings'][button_name] = new_key
                            else:
                                # Convert keyboard keys to lowercase
                                active_settings['dualsense_custom_mappings'][button_name] = new_key.lower()
                        self.save_settings_to_file()
                        self.redraw_mapper_canvas()
                    break

    def populate_controller_tester_tab(self, parent_frame):
        self.image_on_canvas = None
        top_frame = ttk.Frame(parent_frame)
        top_frame.pack(fill='x', pady=5)
        
        controller_frame = ttk.Frame(top_frame)
        controller_frame.pack(side='left', padx=10)
        ttk.Label(controller_frame, text="Select Controller:").pack(side='left')
        self.controller_var = tk.StringVar()
        self.controller_selector = ttk.Combobox(controller_frame, textvariable=self.controller_var, state='readonly', width=40)
        self.controller_selector.pack(side='left', padx=5)
        self.controller_selector.bind('<<ComboboxSelected>>', self.on_controller_selected)
        ttk.Button(controller_frame, text="Refresh", command=self.refresh_controller_list).pack(side='left')
        
        initial_status_text, initial_status_color = self.last_controller_status
        self.status_label = ttk.Label(top_frame, text=f"Controller Status: {initial_status_text}", foreground=initial_status_color, font=('Segoe UI', 12, 'bold'))
        self.status_label.pack(side='left', padx=10)
        self.battery_label = ttk.Label(top_frame, text="Battery: --", font=('Segoe UI', 10))
        self.battery_label.pack(side='left', padx=10)
        
        self.canvas = tk.Canvas(parent_frame, bg='#1E1E1E', highlightthickness=0)
        self.canvas.pack(expand=True, fill='both', pady=5, padx=5)
        try:
            self.original_tester_image = Image.open(self.resource_path("ps5_controller.png"))
            self.canvas.bind('<Configure>', self.resize_tester_image)
        except Exception as e:
            self.canvas.create_text(200, 100, text=f"Error loading image: {e}", fill="red", font=('Segoe UI', 12))
            self.original_tester_image = None

        trigger_frame = ttk.LabelFrame(parent_frame, text="Adaptive Trigger Effects", padding="10")
        trigger_frame.pack(fill='x', pady=5, padx=5)
        
        self.trigger_effects = {
            'Off': lambda trigger: trigger.effect.off(), 'Continuous Resistance': lambda trigger: trigger.effect.continuous_resistance(start_position=0, force=255),
            'Section Resistance': lambda trigger: trigger.effect.section_resistance(start_position=0, end_position=255, force=255),
            'Weapon': lambda trigger: trigger.effect.weapon(start_position=2, end_position=8, strength=8),
            'Bow': lambda trigger: trigger.effect.bow(start_position=0, end_position=8, strength=4, snap_force=4),
            'Machine': lambda trigger: trigger.effect.machine(start_position=0, end_position=9, amplitude_a=5, amplitude_b=7, frequency=30, period=1)
        }
        
        ttk.Label(trigger_frame, text="Effect:").pack(side='left', padx=5)
        self.trigger_mode_var = tk.StringVar(value='Off')
        ttk.Combobox(trigger_frame, textvariable=self.trigger_mode_var, values=list(self.trigger_effects.keys()), state='readonly', width=20).pack(side='left', padx=5)
        ttk.Button(trigger_frame, text="Apply Left", command=lambda: self.apply_trigger_effect('left')).pack(side='left', padx=5)
        ttk.Button(trigger_frame, text="Apply Right", command=lambda: self.apply_trigger_effect('right')).pack(side='left', padx=5)
        ttk.Button(trigger_frame, text="Reset Both", command=lambda: self.apply_trigger_effect('reset')).pack(side='left', padx=5)
        
        self.refresh_controller_list()
        
    def refresh_controller_list(self):
        """Scans for controllers and updates the dropdown."""
        if not self.settings_window or not self.settings_window.winfo_exists(): return
        try:
            if not DualSenseController: 
                self.controller_selector['values'] = []
                self.controller_selector.set('')
                return
            devices = DualSenseController.enumerate_devices()
            device_names = [f"Device {i}: {info.product_string}" for i, info in enumerate(devices)]
            self.controller_selector['values'] = device_names
            
            active_settings = self.get_active_settings()
            current_index = active_settings.get('selected_controller_index', 0)
            if device_names and current_index < len(device_names):
                self.controller_selector.set(device_names[current_index])
            elif device_names:
                 self.controller_selector.set(device_names[0])
            else:
                self.controller_selector.set('')
        except Exception as e:
            print(f"Error refreshing controller list: {e}")

    def on_controller_selected(self, event):
        """Handles changing the active controller."""
        try:
            selected_index = self.controller_selector.current()
            active_settings = self.get_active_settings()
            if selected_index != active_settings.get('selected_controller_index'):
                print(f"Switching to controller index {selected_index}")
                active_settings['selected_controller_index'] = selected_index
                self.stop_controller_thread() 
                self.start_controller_thread()
        except Exception as e:
            print(f"Error switching controller: {e}")

    def apply_trigger_effect(self, side):
        """Applies the selected adaptive trigger effect."""
        if not self.controller: return
        try:
            mode_name = self.trigger_mode_var.get()
            effect_func = self.trigger_effects.get(mode_name)
            
            if effect_func:
                if side == 'left': effect_func(self.controller.left_trigger)
                elif side == 'right': effect_func(self.controller.right_trigger)
                elif side == 'reset':
                    self.controller.left_trigger.effect.off()
                    self.controller.right_trigger.effect.off()
        except Exception as e:
            messagebox.showerror("Trigger Error", f"Could not apply trigger effect: {e}", parent=self.settings_window)

    def _save_settings_from_gui(self, win):
        """Helper to gather data from UI and save settings FOR THE ACTIVE PROFILE. Returns True on success."""
        try:
            active_settings = self.get_active_settings()
            # DualSense Mouse settings
            active_settings['dualsense_sensitivity'] = float(self.sensitivity_var.get())
            
            # --- MODIFIED: Save new independent deadzone settings ---
            active_settings['dualsense_left_inner_deadzone'] = float(self.left_inner_deadzone_var.get())
            active_settings['dualsense_left_outer_deadzone'] = float(self.left_outer_deadzone_var.get())
            active_settings['dualsense_right_inner_deadzone'] = float(self.right_inner_deadzone_var.get())
            active_settings['dualsense_right_outer_deadzone'] = float(self.right_outer_deadzone_var.get())

            active_settings['browser_exponent'] = float(self.browser_exponent_var.get())
            active_settings['browser_acceleration_rate'] = float(self.browser_accel_rate_var.get())
            active_settings['game_exponent'] = float(self.game_exponent_var.get())
            active_settings['game_acceleration_rate'] = float(self.game_accel_rate_var.get())
            active_settings['game_sensitivity_multiplier'] = float(self.game_sensitivity_multiplier_var.get())
            active_settings['dualsense_mouse_enabled'] = self.dualsense_enabled_var.get()
            active_settings['dualsense_mouse_mode'] = self.mouse_mode_var.get()
            active_settings['browser_exponent_enabled'] = self.browser_exponent_enabled_var.get()
            active_settings['browser_acceleration_enabled'] = self.browser_accel_enabled_var.get()
            active_settings['game_exponent_enabled'] = self.game_exponent_enabled_var.get()
            active_settings['game_acceleration_enabled'] = self.game_accel_enabled_var.get()
            active_settings['dualsense_invert_mouse_x'] = self.invert_x_var.get()
            active_settings['dualsense_invert_mouse_y'] = self.invert_y_var.get()
            active_settings['keep_thread_running'] = self.keep_thread_var.get()
            active_settings['hide_hid_device'] = self.hide_hid_var.get()
            active_settings['adaptive_game_mode'] = self.adapt_game_var.get()
            
            # Key Cycler settings
            active_settings['key_cycler_enabled'] = self.key_cycler_enabled_var.get()
            active_settings['mode'] = self.mode_var.get()
            active_settings['default_start'] = self.default_start_var.get()
            active_settings['default_end'] = self.default_end_var.get()
            active_settings['custom_keys'] = list(self.custom_keys_listbox.get(0, tk.END))

            # DualSense Keys settings
            active_settings['dualsense_keys_enabled'] = self.dualsense_keys_enabled_var.get()
            active_settings['dualsense_swap_sticks'] = self.swap_sticks_var.get()
            
            # Key Mapper settings
            active_settings['dualsense_custom_mappings_enabled'] = self.custom_mappings_enabled_var.get()

            # Compatibility settings
            active_settings['mouse_compatibility_mode'] = self.mouse_compat_var.get()
            active_settings['keyboard_compatibility_mode'] = self.keyboard_compat_var.get()

            self.save_settings_to_file()
            self.update_cycle_keys_from_settings()
            self._initialize_controllers() # Re-initialize to apply new settings
            
            if self.keep_thread_var.get() and (not self.controller_thread or not self.controller_thread.is_alive()):
                self.start_controller_thread()

            return True
        except ValueError:
            messagebox.showerror("Invalid Input", "Please ensure all numeric fields are valid numbers.", parent=win)
            return False
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}", parent=win)
            return False
    
    def on_save_only(self, win):
        """Saves settings without closing the window."""
        self._save_settings_from_gui(win)
        
    def on_save_and_close(self, win):
        """Saves settings and then closes the window."""
        if self._save_settings_from_gui(win):
            self.on_close_settings(win)

    def _load_settings_into_ui(self):
        """Loads all settings from the active profile into the UI variables."""
        if not self.settings_window or not self.settings_window.winfo_exists(): return
        
        active_settings = self.get_active_settings()
        
        # Key Cycler
        self.key_cycler_enabled_var.set(active_settings.get('key_cycler_enabled', False))
        self.mode_var.set(active_settings.get('mode', 'default'))
        self.default_start_var.set(active_settings.get('default_start'))
        self.default_end_var.set(active_settings.get('default_end'))
        self.custom_keys_listbox.delete(0, tk.END)
        for key in active_settings.get('custom_keys', []): self.custom_keys_listbox.insert(tk.END, key)

        # Dualsense Mouse
        self.dualsense_enabled_var.set(active_settings.get('dualsense_mouse_enabled'))
        self.keep_thread_var.set(active_settings.get('keep_thread_running'))
        self.hide_hid_var.set(active_settings.get('hide_hid_device'))
        self.sensitivity_var.set(str(active_settings.get('dualsense_sensitivity')))
        
        # --- MODIFIED: Load new independent deadzone settings ---
        self.left_inner_deadzone_var.set(str(active_settings.get('dualsense_left_inner_deadzone')))
        self.left_outer_deadzone_var.set(str(active_settings.get('dualsense_left_outer_deadzone')))
        self.right_inner_deadzone_var.set(str(active_settings.get('dualsense_right_inner_deadzone')))
        self.right_outer_deadzone_var.set(str(active_settings.get('dualsense_right_outer_deadzone')))
        
        self.invert_x_var.set(active_settings.get('dualsense_invert_mouse_x'))
        self.invert_y_var.set(active_settings.get('dualsense_invert_mouse_y'))
        self.mouse_mode_var.set(active_settings.get('dualsense_mouse_mode', 'Browser'))
        self.adapt_game_var.set(active_settings.get('adaptive_game_mode', False))
        
        self.browser_exponent_enabled_var.set(active_settings.get('browser_exponent_enabled'))
        self.browser_exponent_var.set(str(active_settings.get('browser_exponent')))
        self.browser_accel_enabled_var.set(active_settings.get('browser_acceleration_enabled'))
        self.browser_accel_rate_var.set(str(active_settings.get('browser_acceleration_rate')))
        
        self.game_exponent_enabled_var.set(active_settings.get('game_exponent_enabled'))
        self.game_exponent_var.set(str(active_settings.get('game_exponent')))
        self.game_accel_enabled_var.set(active_settings.get('game_acceleration_enabled'))
        self.game_accel_rate_var.set(str(active_settings.get('game_acceleration_rate')))
        self.game_sensitivity_multiplier_var.set(str(active_settings.get('game_sensitivity_multiplier')))

        # DualSense Keys
        self.dualsense_keys_enabled_var.set(active_settings.get('dualsense_keys_enabled'))
        self.swap_sticks_var.set(active_settings.get('dualsense_swap_sticks', False))
        mappings = active_settings.get('dualsense_keys_mappings', {})
        for direction, var in self.key_mapping_label_vars.items():
            var.set(mappings.get(direction.lower(), ''))
            
        # Key Mapper
        self.custom_mappings_enabled_var.set(active_settings.get('dualsense_custom_mappings_enabled'))

        # Compatibility
        self.mouse_compat_var.set(active_settings.get('mouse_compatibility_mode'))
        self.keyboard_compat_var.set(active_settings.get('keyboard_compatibility_mode'))

        # Redraw canvases that depend on settings
        self.redraw_mapper_canvas()
        self.redraw_keys_canvas()
        self.redraw_tester_image()
        print(f"UI updated with settings from profile '{self.settings['active_profile']}'")

    # --- NEW: Profile UI Handlers ---
    def _update_profile_dropdown(self):
        """Updates the profile combobox with the current list of profiles."""
        if not self.settings_window or not self.settings_window.winfo_exists(): return
        profiles = list(self.settings.get("profiles", {}).keys())
        self.profile_combobox['values'] = profiles
        self.profile_var.set(self.settings.get("active_profile", ""))

    def _on_profile_selected(self, event=None):
        """Handles switching the active profile."""
        selected_profile = self.profile_var.get()
        if selected_profile and selected_profile != self.settings.get("active_profile"):
            self.settings["active_profile"] = selected_profile
            self._load_settings_into_ui()
            self.update_cycle_keys_from_settings()
            self._initialize_controllers()
            # No need to save here, just switching view
    
    def _create_profile(self):
        """Creates a new profile by copying the current one."""
        new_name = simpledialog.askstring("Create Profile", "Enter new profile name:", parent=self.settings_window)
        if not new_name:
            return
        if new_name in self.settings["profiles"]:
            messagebox.showerror("Error", f"A profile named '{new_name}' already exists.", parent=self.settings_window)
            return
        
        # Create new profile by copying the currently active one
        current_settings = self.get_active_settings().copy()
        self.settings["profiles"][new_name] = current_settings
        self.settings["active_profile"] = new_name
        
        self._update_profile_dropdown()
        self._load_settings_into_ui() # Load the (copied) settings into the UI
        self.save_settings_to_file()
        
    def _delete_profile(self):
        """Deletes the currently active profile."""
        if len(self.settings["profiles"]) <= 1:
            messagebox.showerror("Error", "Cannot delete the last remaining profile.", parent=self.settings_window)
            return

        active_profile = self.settings["active_profile"]
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the profile '{active_profile}'?", parent=self.settings_window):
            del self.settings["profiles"][active_profile]
            self.settings["active_profile"] = next(iter(self.settings["profiles"]))
            
            self._update_profile_dropdown()
            self._load_settings_into_ui()
            self.save_settings_to_file()


    def queue_update(self, update_type, *data):
        self.update_queue.put((update_type, data))

    def process_updates(self):
        try:
            should_redraw_tester = False
            should_redraw_keys = False
            should_redraw_mapper = False
            while not self.update_queue.empty():
                if not self.settings_window or not self.settings_window.winfo_exists(): return
                
                update_type, data = self.update_queue.get_nowait()
                
                if update_type == 'status':
                    self.last_controller_status = (data[0], data[1])
                    if self.settings_window and self.settings_window.winfo_exists():
                        self.status_label.config(text=f"Controller Status: {data[0]}", foreground=data[1])
                elif update_type == 'error':
                     print(f"Controller error event: {data[0]}")
                     self.handle_disconnection()
                elif update_type == 'tester_button_update':
                    self.button_states[data[0]] = data[1]
                    should_redraw_tester = True
                elif update_type == 'tester_analog_update':
                    self.analog_states[data[0]] = data[1]
                    should_redraw_tester = True
                    if data[0] in ['left_stick', 'right_stick']: should_redraw_keys = True
                elif update_type == 'tester_touchpad_update':
                    self.touchpad_state[data[0]] = data[1]
                    should_redraw_tester = True
                elif update_type == 'tester_battery_update':
                    level, is_charging, is_full = data[0]
                    state_str = "Charging" if is_charging else ("Full" if is_full else "Discharging")
                    if self.battery_label.winfo_exists():
                        self.battery_label.config(text=f"Battery: {level:.0f}% ({state_str})")
                elif update_type == 'keys_direction_update':
                    new_direction = data[0]
                    should_redraw_keys = True
                    if self.active_tab_name == 'DualSense Keys' and hasattr(self, 'key_mapping_labels'):
                        ACCENT_COLOR, ENTRY_BG, FG_COLOR = '#007ACC', '#3C3C3C', '#E0E0E0'
                        for direction, label in self.key_mapping_labels.items():
                            if label.winfo_exists():
                                if direction == new_direction:
                                    label.config(background=ACCENT_COLOR, foreground='white')
                                else:
                                    label.config(background=ENTRY_BG, foreground=FG_COLOR)


        except Empty: pass
        except tk.TclError: pass
        finally:
            if self.settings_window and self.settings_window.winfo_exists():
                if should_redraw_tester and self.active_tab_name == 'Controller Tester': self.redraw_tester_image()
                if should_redraw_keys and self.active_tab_name == 'DualSense Keys': self.redraw_keys_canvas()
                if should_redraw_mapper and self.active_tab_name == 'Key Mapper': self.redraw_mapper_canvas()
                self.settings_window.after(16, self.process_updates)

    def resize_tester_image(self, event):
        self._update_tester_canvas_size(event.width, event.height)

    def _update_tester_canvas_size(self, canvas_width, canvas_height):
        if not hasattr(self, 'original_tester_image') or not self.original_tester_image: return
        if canvas_width <= 1 or canvas_height <= 1: return
        
        img_ratio = self.original_tester_image.width / self.original_tester_image.height
        canvas_ratio = canvas_width / canvas_height
        
        new_width = canvas_width if canvas_ratio <= img_ratio else int(canvas_height * img_ratio)
        new_height = int(new_width / img_ratio) if canvas_ratio <= img_ratio else canvas_height
            
        self.base_resized_tester_image = self.original_tester_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.redraw_tester_image()


    def redraw_tester_image(self):
        if not self.base_resized_tester_image or not self.canvas.winfo_exists(): return
            
        self.working_tester_image = self.base_resized_tester_image.copy()
        draw = ImageDraw.Draw(self.working_tester_image, 'RGBA')
        
        self.draw_buttons(draw)
        self.draw_touchpad(draw)
        self.draw_analog_sticks(draw)
        self.draw_triggers(draw)
        
        self.controller_tester_photoimage = ImageTk.PhotoImage(self.working_tester_image)
        
        canvas_width, canvas_height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if self.image_on_canvas: self.canvas.itemconfig(self.image_on_canvas, image=self.controller_tester_photoimage)
        else: self.image_on_canvas = self.canvas.create_image(canvas_width / 2, canvas_height / 2, image=self.controller_tester_photoimage)
        self.canvas.coords(self.image_on_canvas, canvas_width / 2, canvas_height / 2)

    def draw_buttons(self, draw):
        if not self.working_tester_image: return
        current_width, current_height = self.working_tester_image.size
        scale_x, scale_y = current_width / 1200.0, current_height / 800.0
        uniform_scale = min(scale_x, scale_y)
        base_radius = 15

        for button_name, is_pressed in self.button_states.items():
            if is_pressed and button_name in self.get_button_positions():
                original_x, original_y = self.get_button_positions()[button_name]
                scaled_x, scaled_y = int(original_x * scale_x), int(original_y * scale_y)
                scaled_radius = int(base_radius * uniform_scale)
                draw.ellipse([scaled_x - scaled_radius, scaled_y - scaled_radius, scaled_x + scaled_radius, scaled_y + scaled_radius], fill=(255, 0, 0, 200), outline='black')

    def draw_touchpad(self, draw):
        img_w, img_h = self.working_tester_image.size
        orig_w, orig_h = 1190, 720
        tp_box = {'x': 445, 'y': 230, 'w': 310, 'h': 120}
        
        scale_x, scale_y = img_w / orig_w, img_h / orig_h
        scaled_box = {
            'x': int(tp_box['x'] * scale_x), 'y': int(tp_box['y'] * scale_y),
            'w': int(tp_box['w'] * scale_x), 'h': int(tp_box['h'] * scale_y)
        }
        
        draw.rectangle([scaled_box['x'], scaled_box['y'], scaled_box['x'] + scaled_box['w'], scaled_box['y'] + scaled_box['h']], outline=(255, 255, 255, 100), width=2)

        for finger_data in self.touchpad_state.values():
            if finger_data['active']:
                norm_x, norm_y = finger_data['x'] / 1920.0, finger_data['y'] / 1080.0
                draw_x, draw_y = scaled_box['x'] + int(norm_x * scaled_box['w']), scaled_box['y'] + int(norm_y * scaled_box['h'])
                radius = int(10 * min(scale_x, scale_y))
                draw.ellipse([draw_x - radius, draw_y - radius, draw_x + radius, draw_y + radius], fill=(0, 255, 255, 200), outline='white')
                text = f"({finger_data['x']}, {finger_data['y']})"
                draw.text((draw_x + 15, draw_y - 10), text, font=self.font, fill="white")


    def draw_analog_sticks(self, draw):
        active_settings = self.get_active_settings()
        stick_positions = {'left_stick': (456, 455), 'right_stick': (758, 455)}
        
        for stick_name, base_pos in stick_positions.items():
            stick_obj = self.analog_states[stick_name]
            x_val, y_val = stick_obj[0], stick_obj[1]
            # Normalize stick values from [0, 255] to [-1.0, 1.0]
            x_offset_norm, y_offset_norm = (x_val - 127.5) / 127.5, (y_val - 127.5) / 127.5
            
            # Get correct deadzone settings for each stick
            stick_prefix = 'left' if stick_name == 'left_stick' else 'right'
            inner_deadzone = float(active_settings.get(f'dualsense_{stick_prefix}_inner_deadzone', 0.08))
            outer_deadzone = float(active_settings.get(f'dualsense_{stick_prefix}_outer_deadzone', 0.95))
            
            self.draw_stick_indicator(draw, base_pos, x_offset_norm, y_offset_norm, inner_deadzone, outer_deadzone)

    def draw_triggers(self, draw):
        img_w, img_h = self.working_tester_image.size
        scale_x, scale_y = img_w / 1200.0, img_h / 800.0
        bar_w, bar_h = int(25 * scale_x), int(100 * scale_y)
        
        l_val = self.analog_states['left_trigger'] / 255.0
        l_bar_x, l_bar_y = int(180 * scale_x), int(130 * scale_y)
        l_fill_h = int(bar_h * l_val)
        draw.rectangle([l_bar_x, l_bar_y, l_bar_x + bar_w, l_bar_y + bar_h], outline=(0, 255, 255, 150), width=2)
        if l_fill_h > 0: draw.rectangle([l_bar_x, l_bar_y + (bar_h - l_fill_h), l_bar_x + bar_w, l_bar_y + bar_h], fill=(0, 255, 255, 150))
        
        r_val = self.analog_states['right_trigger'] / 255.0
        r_bar_x, r_bar_y = int(1020 * scale_x), int(130 * scale_y)
        r_fill_h = int(bar_h * r_val)
        draw.rectangle([r_bar_x, r_bar_y, r_bar_x + bar_w, r_bar_y + bar_h], outline=(255, 0, 255, 150), width=2)
        if r_fill_h > 0: draw.rectangle([r_bar_x, r_bar_y + (bar_h - r_fill_h), r_bar_x + bar_w, r_bar_y + bar_h], fill=(255, 0, 255, 150))

    def draw_stick_indicator(self, draw, base_pos, x_val, y_val, inner_dz=0.0, outer_dz=1.0):
        scale_x, scale_y = self.working_tester_image.width / 1200.0, self.working_tester_image.height / 800.0
        uniform_scale = min(scale_x, scale_y)
        base_x, base_y = int(base_pos[0] * scale_x), int(base_pos[1] * scale_y)
        
        ring_radius = int(60 * uniform_scale)
        
        # Draw the main blue ring for the stick area boundary
        draw.ellipse([base_x - ring_radius, base_y - ring_radius, base_x + ring_radius, base_y + ring_radius], outline=(0, 255, 255, 200), width=int(2 * uniform_scale))

        # Draw inner deadzone (orange circle)
        if inner_dz > 0:
            inner_radius = ring_radius * inner_dz
            draw.ellipse([base_x - inner_radius, base_y - inner_radius, base_x + inner_radius, base_y + inner_radius], outline=(255, 152, 0, 200), width=int(1.5 * uniform_scale))

        # Draw outer deadzone (orange circle)
        if outer_dz < 1.0:
            outer_radius = ring_radius * outer_dz
            draw.ellipse([base_x - outer_radius, base_y - outer_radius, base_x + outer_radius, base_y + outer_radius], outline=(255, 152, 0, 200), width=int(1.5 * uniform_scale))
        
        # Calculate dot position based on raw input vector
        vec = math.hypot(x_val, y_val)
        dot_x, dot_y = base_x + x_val * ring_radius, base_y + y_val * ring_radius
        
        # Change color if outside inner deadzone
        dot_color = (0, 255, 255, 220) if vec > inner_dz else (255, 0, 0, 220)
        
        # Draw line from center to dot
        if vec > 0.05:
            draw.line([base_x, base_y, dot_x, dot_y], fill=dot_color, width=int(2 * uniform_scale))
        
        # Draw the dot indicator
        dot_radius = int(8 * uniform_scale)
        draw.ellipse([dot_x - dot_radius, dot_y - dot_radius, dot_x + dot_radius, dot_y + dot_radius], fill=dot_color, outline='white')


    def show_settings(self, icon, item):
        # First, check if the settings window already exists. If so, just bring it to the front.
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus_force()
            return

        # If the window doesn't exist, call your function to create it.
        self.create_settings_window()

        # After it's created, apply the maximization logic.
        if self.settings_window and self.settings_window.winfo_exists():
            try:
                # This works on most platforms including Windows
                self.settings_window.state('zoomed')
            except tk.TclError:
                # Fallback for other systems
                w, h = self.settings_window.winfo_screenwidth(), self.settings_window.winfo_screenheight()
                self.settings_window.geometry(f"{w}x{h}+0+0")

    def exit_app(self, icon=None, item=None):
        """Graceful shutdown that avoids joining the current thread and handles None controller."""
        print("Exiting application...")

        # 1) tell controller loops to stop
        try:
            self.is_running.clear()
        except Exception as e:
            print("Failed clearing is_running:", e)

        # 2) deactivate controller if present (defensive)
        try:
            if getattr(self, "controller", None):
                try:
                    # Some controller implementations may be partially initialized;
                    # wrap in try/except to avoid AttributeError inside their code.
                    self.controller.deactivate()
                except Exception as e:
                    print("Error deactivating controller:", e)
                finally:
                    self.controller = None
        except Exception as e:
            print("Controller cleanup error:", e)

        # 3) stop any keyboard/mouse listeners (KeyBindDialog listeners etc.)
        try:
            for name in ("klistener", "mlistener"):
                L = getattr(self, name, None)
                if L:
                    try:
                        L.stop()
                    except Exception as e:
                        print(f"Error stopping listener {name}:", e)
                    finally:
                        try:
                            setattr(self, name, None)
                        except Exception:
                            pass
        except Exception as e:
            print("Listener cleanup error:", e)

        # 4) stop pystray icon (safe) and join thread only if not current thread
        try:
            if getattr(self, "icon", None):
                try:
                    self.icon.stop()
                except Exception as e:
                    print("icon.stop() raised:", e)

                try:
                    self.icon.visible = False
                except Exception:
                    pass

            # join icon thread but DO NOT join if we're already on it
            icon_thread = getattr(self, "icon_thread", None)
            if isinstance(icon_thread, threading.Thread):
                if icon_thread.is_alive():
                    if threading.current_thread() is not icon_thread:
                        try:
                            icon_thread.join(timeout=2.0)
                        except Exception as e:
                            print("Failed joining icon_thread:", e)
                    else:
                        print("Skipping join of icon_thread because we're running on it.")
        except Exception as e:
            print("Tray cleanup error:", e)

        # 5) join controller thread(s)
        try:
            ct = getattr(self, "controller_thread", None)
            if isinstance(ct, threading.Thread) and ct.is_alive():
                try:
                    if threading.current_thread() is not ct:
                        ct.join(timeout=2.0)
                    else:
                        print("Skipping join of controller_thread because we're running on it.")
                except Exception as e:
                    print("Failed joining controller_thread:", e)

            mt = getattr(self, "mouse_thread", None)
            if isinstance(mt, threading.Thread) and mt.is_alive():
                try:
                    if threading.current_thread() is not mt:
                        mt.join(timeout=1.0)
                    else:
                        print("Skipping join of mouse_thread because we're running on it.")
                except Exception as e:
                    print("Failed joining mouse_thread:", e)
        except Exception as e:
            print("Thread join error:", e)

        # 6) destroy Tk root
        try:
            if getattr(self, "root", None):
                try:
                    self.root.quit()
                except Exception:
                    pass
                try:
                    time.sleep(0.03)
                    self.root.update_idletasks()
                except Exception:
                    pass
                try:
                    self.root.destroy()
                except Exception as e:
                    print("root.destroy() failed:", e)
        except Exception as e:
            print("Tk cleanup error:", e)

        # 7) final exit (normal first, then forced)
        try:
            print("Cleanup complete, exiting normally.")
            sys.exit(0)
        except SystemExit:
            # last resort hard exit if something is still hung
            try:
                time.sleep(0.05)
            finally:
                os._exit(0)

    def create_tray_icon(self):
        """Return a PIL Image for pystray; fallback to simple generated image on error."""
        try:
            # Open the ICO (ICO files can contain multiple sizes)
            img = Image.open(self.resource_path("icon.ico"))
            # Ensure a mode pystray likes (RGBA for transparency)
            return img.convert("RGBA")
        except Exception as e:
            # fallback (64x64 RGBA)
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            dc = ImageDraw.Draw(image)
            dc.rectangle((16, 16, 48, 48), fill=(255,255,255,255))
            return image

    def controllers_available(self):
        """
        Return True if any DualSenseController devices are present.
        Defensive: if DualSenseController not installed, return False.
        """
        try:
            if not DualSenseController:
                return False
            infos = DualSenseController.enumerate_devices()
            return bool(infos)
        except Exception as e:
            # If enumeration throws, treat as no devices and print for debugging
            print("controllers_available() error:", e)
            return False

    def run(self):
        if not DualSenseController:
            root = tk.Tk(); root.withdraw()
            messagebox.showerror(
                "Missing Library",
                "The required library `dualsense-controller` is not installed.\n\n"
                "Please install it using: pip install dualsense-controller"
            )
            return

        if not self.controllers_available():
            # --- MODIFIED: Call static method correctly ---
            user_ok = UtilityApp.show_windows_ok_cancel(
                "No Controller Found",
                "No DualSense controllers were detected.\n\n"
                "Please connect your controller and restart the application, "
                "or click OK to continue without one.",
                warning=True
            )
            if not user_ok:
                self.exit_app()
                return

        if self.get_active_settings().get('keep_thread_running', False):
            self.start_controller_thread()

        # Create the PIL image we'll use for the tray icon (and possibly for fallback)
        tray_image = self.create_tray_icon()

        # Try to set the .ico as the window/taskbar icon (preferred on Windows)
        try:
            self.root.iconbitmap(self.resource_path("icon.ico"))
        except Exception:
            # Fallback: convert the PIL image to a Tk PhotoImage and set via iconphoto
            try:
                # Ensure we have a PIL Image
                pil_img = tray_image
                if pil_img.mode != "RGBA":
                    pil_img = pil_img.convert("RGBA")

                # Resize to a reasonable size for a window/taskbar icon if needed
                # (optional; Windows uses .ico but this helps non-Windows platforms)
                try:
                    pil_img_for_tk = pil_img.resize((64, 64), Image.Resampling.LANCZOS)
                except Exception:
                    pil_img_for_tk = pil_img

                tk_img = ImageTk.PhotoImage(pil_img_for_tk)
                # Keep reference to prevent GC (very important)
                self._tk_icon_image = tk_img
                try:
                    # False = apply to this toplevel only
                    self.root.iconphoto(False, tk_img)
                except Exception:
                    # Some systems / Tk versions may not support iconphoto
                    pass
            except Exception:
                pass

        # Build tray menu and start pystray icon
        menu = (item('Settings', self.show_settings), item('Exit', self.exit_app))
        # Ensure tray image is in RGBA and a sensible size for pystray
        try:
            tray_img_for_pystray = tray_image.convert("RGBA")
            # pystray prefers 16..64 sizes; resize if huge
            if max(tray_img_for_pystray.size) > 256:
                tray_img_for_pystray = tray_img_for_pystray.resize((128, 128), Image.Resampling.LANCZOS)
        except Exception:
            tray_img_for_pystray = tray_image

        self.icon = Icon("UtilityApp", tray_img_for_pystray, "Controller & Key Utility", menu)

        # Start the tray in a background thread so Tk mainloop still runs
        self.icon_thread = threading.Thread(target=self.icon.run, daemon=True)
        self.icon_thread.start()

        print("System tray icon started. Right-click tray icon for options.")
        self.root.mainloop()

if __name__ == '__main__':
    app = UtilityApp()
    app.run()
