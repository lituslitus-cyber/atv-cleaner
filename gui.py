# -*- coding: utf-8 -*-
"""ATV Cleaner, оконная версия. Вся работа с ТВ живёт в atv_cleaner."""

import json
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

import atv_cleaner as core

APP_TITLE = f"ATV Cleaner {core.__version__}"
UNCHECKED, CHECKED, LOCKED = "☐", "☑", "✖"
HINT = ("Щелчок по пакету отмечает его, по группе отмечает всё безопасное "
        "в группе. ⚠ требует подтверждения, ✖ трогать нельзя.")
APPS_HINT = ("Отметьте приложения щелчком и выберите действие. Сторонние "
             "приложения удаляются полностью, их APK сохраняется в бэкап.")

PALETTES = {
    "light": dict(bg="#f3f3f3", fg="#1f1f1f", field="#ffffff", alt="#e6e6e6",
                  border="#c7c7c7", select="#cce4f7", selfg="#000000",
                  muted="#5f6368", warn="#b35c00", block="#9aa0a6",
                  good="#137333", bad="#c5221f", btn="#e3e3e3", hover="#d4d4d4",
                  accent="#1a73e8"),
    "dark": dict(bg="#1f2023", fg="#e8eaed", field="#2a2b2f", alt="#26272b",
                 border="#3c4043", select="#36507a", selfg="#ffffff",
                 muted="#9aa0a6", warn="#f6ad55", block="#6b6f75",
                 good="#81c995", bad="#f28b82", btn="#303136", hover="#3d3e43",
                 accent="#8ab4f8"),
}


def system_theme():
    """Тема Windows для приложений: светлая или тёмная."""
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft"
                                r"\Windows\CurrentVersion\Themes\Personalize") as k:
                return "light" if winreg.QueryValueEx(k, "AppsUseLightTheme")[0] else "dark"
        except OSError:
            pass
    return "light"


def set_titlebar(root, dark):
    """Тёмный заголовок окна на Windows 10/11."""
    if os.name != "nt":
        return
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE в разных сборках
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:  # noqa: BLE001 — не Windows 10+ или нет dwmapi
        pass


def apply_theme(root, name):
    c = PALETTES[name]
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=c["bg"], foreground=c["fg"], fieldbackground=c["field"],
                 bordercolor=c["border"], lightcolor=c["bg"], darkcolor=c["bg"],
                 troughcolor=c["alt"], selectbackground=c["select"],
                 selectforeground=c["selfg"], insertcolor=c["fg"], focuscolor=c["select"])
    st.map(".", foreground=[("disabled", c["block"])])
    st.configure("TButton", background=c["btn"], padding=(8, 4))
    st.map("TButton", background=[("disabled", c["bg"]), ("pressed", c["select"]),
                                  ("active", c["hover"])],
           foreground=[("disabled", c["block"])])
    st.configure("Treeview", background=c["field"], fieldbackground=c["field"],
                 foreground=c["fg"], rowheight=22, bordercolor=c["border"])
    st.map("Treeview", background=[("selected", c["select"])],
           foreground=[("selected", c["selfg"])])
    st.configure("Treeview.Heading", background=c["btn"], foreground=c["fg"],
                 relief="flat")
    st.map("Treeview.Heading", background=[("active", c["hover"])])
    st.configure("TNotebook", background=c["bg"], bordercolor=c["border"])
    st.configure("TNotebook.Tab", background=c["alt"], foreground=c["muted"],
                 padding=(14, 5), bordercolor=c["border"], lightcolor=c["alt"])
    # В clam выбранная вкладка получает свой отступ поменьше и выглядит ниже
    # остальных. Делаем наоборот: выбранная выше, светлее и жирным шрифтом.
    root._tab_font = tkfont.nametofont("TkDefaultFont").copy()
    root._tab_font.configure(weight="bold")
    st.map("TNotebook.Tab",
           background=[("selected", c["field"]), ("active", c["hover"])],
           foreground=[("selected", c["fg"])],
           padding=[("selected", (14, 7))],
           expand=[("selected", (1, 3, 1, 0))],
           font=[("selected", root._tab_font)])
    for w in ("TCombobox", "TSpinbox", "TEntry"):
        st.configure(w, fieldbackground=c["field"], foreground=c["fg"],
                     background=c["btn"], arrowcolor=c["fg"], bordercolor=c["border"],
                     insertcolor=c["fg"])
        st.map(w, fieldbackground=[("readonly", c["field"]), ("disabled", c["bg"])],
               foreground=[("readonly", c["fg"])],
               selectbackground=[("readonly", c["field"])],
               selectforeground=[("readonly", c["fg"])])
    for w in ("TCheckbutton", "TRadiobutton"):
        st.configure(w, background=c["bg"], indicatorbackground=c["field"],
                     indicatorforeground=c["fg"])
        st.map(w, background=[("active", c["bg"])],
               indicatorbackground=[("selected", c["select"]), ("active", c["hover"])])
    st.configure("TScrollbar", background=c["btn"], troughcolor=c["bg"],
                 arrowcolor=c["fg"], bordercolor=c["border"])
    st.map("TScrollbar", background=[("active", c["hover"])])
    st.configure("TLabelframe", background=c["bg"], bordercolor=c["border"])
    st.configure("TLabelframe.Label", background=c["bg"], foreground=c["fg"])
    st.configure("Muted.TLabel", foreground=c["muted"])
    for kind in ("good", "warn", "bad"):
        st.configure(f"{kind.title()}.TLabel", foreground=c[kind])
    # Выпадающий список комбобокса — обычный tk.Listbox.
    root.option_add("*TCombobox*Listbox.background", c["field"])
    root.option_add("*TCombobox*Listbox.foreground", c["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", c["select"])
    root.option_add("*TCombobox*Listbox.selectForeground", c["selfg"])
    root.configure(bg=c["bg"])
    set_titlebar(root, name == "dark")
    return c


class QueueWriter:
    """Перенаправляет print() из рабочего потока в журнал окна."""

    def __init__(self, q):
        self.q = q

    def write(self, text):
        if text:
            self.q.put(("log", text))

    def flush(self):
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1000x760")
        self.minsize(780, 560)

        self.q = queue.Queue()
        sys.stdout = sys.stderr = QueueWriter(self.q)

        self.ctx = None
        self.model = ""
        self.items = {}          # строка дерева очистки -> (пакет, описание, уровень, причины)
        self.checked = set()     # отмеченные на вкладке «Очистка»
        self.apps = {}           # пакет -> сведения для вкладки приложений
        self.app_checked = set()
        self.last_backup = None  # removed.txt последнего изменения
        self.last_removed = []
        self.busy = False

        self.settings = self._load_settings()
        self.theme = self.settings.get("theme") or system_theme()
        self.colors = apply_theme(self, self.theme)

        self._build()
        self._apply_widget_colors()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._load_last_ip()
        self.log("Включите на ТВ «Отладку по сети» (Настройки -> Для разработчиков),\n"
                 "введите IP телевизора и нажмите «Подключить».\n")

    # ---------------------------------------------------------------- настройки

    def _settings_file(self):
        return os.path.join(core.HERE, "settings.json")

    def _load_settings(self):
        try:
            with open(self._settings_file(), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save_settings(self):
        try:
            with open(self._settings_file(), "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.settings["theme"] = self.theme
        self._save_settings()
        self.colors = apply_theme(self, self.theme)
        self._apply_widget_colors()

    def _apply_widget_colors(self):
        """Цвета обычных tk-виджетов и тегов, которые ttk.Style не покрывает."""
        c = self.colors
        self.logbox.configure(background=c["field"], foreground=c["fg"],
                              insertbackground=c["fg"], selectbackground=c["select"],
                              highlightthickness=0, borderwidth=0)
        for tree in (self.tree, self.app_tree):
            tree.tag_configure("warn", foreground=c["warn"])
            tree.tag_configure("block", foreground=c["block"])
            tree.tag_configure("off", foreground=c["muted"])
        self.btn_theme.configure(text="☀ Светлая" if self.theme == "dark"
                                 else "🌙 Тёмная")

    # ---------------------------------------------------------------- интерфейс

    def _build(self):
        pad = {"padx": 6, "pady": 4}

        conn = ttk.LabelFrame(self, text="Телевизор")
        conn.pack(fill="x", **pad)
        ttk.Label(conn, text="IP:").pack(side="left", padx=(8, 2), pady=6)
        self.ip = tk.StringVar()
        ip_entry = ttk.Entry(conn, textvariable=self.ip, width=18)
        ip_entry.pack(side="left", pady=6)
        ip_entry.bind("<Return>", lambda e: self.connect())
        self.btn_connect = ttk.Button(conn, text="Подключить", command=self.connect)
        self.btn_connect.pack(side="left", padx=6)
        self.status = ttk.Label(conn, text="не подключено", style="Bad.TLabel")
        self.status.pack(side="left", padx=8)
        self.btn_theme = ttk.Button(conn, command=self.toggle_theme)
        self.btn_theme.pack(side="right", padx=(0, 8))
        self.btn_folder = ttk.Button(conn, text="📁 Бэкапы", command=self.open_folder)
        self.btn_folder.pack(side="right", padx=(0, 6))
        self.btn_install = ttk.Button(conn, text="📦 Установить APK",
                                      command=self.install)
        self.btn_install.pack(side="right", padx=6)

        pane = ttk.PanedWindow(self, orient="vertical")
        pane.pack(fill="both", expand=True, **pad)

        self.tabs = ttk.Notebook(pane)
        clean = ttk.Frame(self.tabs)
        apps = ttk.Frame(self.tabs)
        self.tabs.add(clean, text="🧹 Очистка")
        self.tabs.add(apps, text="📱 Установленные приложения")
        self.tabs.bind("<<NotebookTabChanged>>", self._on_tab)
        pane.add(self.tabs, weight=3)
        self._build_clean_tab(clean, pad)
        self._build_apps_tab(apps, pad)

        log_frame = ttk.Frame(pane)
        self.logbox = tk.Text(log_frame, height=9, wrap="word", state="disabled",
                              font=("Consolas", 9))
        lsb = ttk.Scrollbar(log_frame, orient="vertical", command=self.logbox.yview)
        self.logbox.configure(yscrollcommand=lsb.set)
        self.logbox.pack(side="left", fill="both", expand=True)
        lsb.pack(side="right", fill="y")
        pane.add(log_frame, weight=1)

        self.hint = ttk.Label(self, text=HINT, wraplength=960, justify="left",
                              style="Muted.TLabel")
        self.hint.pack(fill="x", padx=8, pady=(0, 6))
        self._update_buttons()

    def _build_clean_tab(self, tab, pad):
        actions = ttk.Frame(tab)
        actions.pack(fill="x", **pad)
        self.btn_scan = ttk.Button(actions, text="🔍 Найти мусор", command=self.scan)
        self.btn_remove = ttk.Button(actions, text="🧹 Отключить отмеченное",
                                     command=self.remove)
        self.btn_boot = ttk.Button(actions, text="🔄 Перезагрузить и проверить",
                                   command=self.check_boot)
        self.btn_restore = ttk.Button(actions, text="↩ Восстановить из бэкапа",
                                      command=self.restore)
        for b in (self.btn_scan, self.btn_remove, self.btn_boot, self.btn_restore):
            b.pack(side="left", padx=(0, 6))

        mode = ttk.Frame(tab)
        mode.pack(fill="x", **pad)
        ttk.Label(mode, text="Способ:").pack(side="left")
        self.method = tk.StringVar(value=core.DISABLE)
        ttk.Radiobutton(mode, text="Отключать (рекомендуется, легко вернуть)",
                        value=core.DISABLE, variable=self.method,
                        command=self._on_method).pack(side="left", padx=6)
        ttk.Radiobutton(mode, text="Удалять", value=core.UNINSTALL,
                        variable=self.method, command=self._on_method).pack(side="left")

        home = ttk.Frame(tab)
        home.pack(fill="x", **pad)
        ttk.Label(home, text="Домашний экран:").pack(side="left")
        self.home = tk.StringVar()
        self.home_box = ttk.Combobox(home, textvariable=self.home, state="readonly",
                                     width=45)
        self.home_box.pack(side="left", padx=6)
        self.btn_home = ttk.Button(home, text="Сделать домашним",
                                   command=self.apply_home)
        self.btn_home.pack(side="left")
        self.days = tk.IntVar(value=90)
        ttk.Spinbox(home, from_=14, to=730, increment=30, width=5,
                    textvariable=self.days).pack(side="right")
        ttk.Label(home, text="Неиспользуемые, дней:").pack(side="right", padx=(12, 4))

        frame = ttk.Frame(tab)
        frame.pack(fill="both", expand=True, **pad)
        self.tree = ttk.Treeview(frame, columns=("desc", "note"), selectmode="browse")
        self.tree.heading("#0", text="Пакет")
        self.tree.heading("desc", text="Что это")
        self.tree.heading("note", text="Проверка")
        self.tree.column("#0", width=330)
        self.tree.column("desc", width=280)
        self.tree.column("note", width=340)
        self.tree.tag_configure("group", font=("Segoe UI", 10, "bold"))
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<space>", lambda e: self._toggle(self.tree.focus()))
        self.tree.bind("<<TreeviewSelect>>", self._show_details)

    def _build_apps_tab(self, tab, pad):
        bar = ttk.Frame(tab)
        bar.pack(fill="x", **pad)
        self.btn_apps_load = ttk.Button(bar, text="🔄 Обновить список",
                                        command=self.load_apps)
        self.btn_apps_uninstall = ttk.Button(bar, text="🗑 Удалить",
                                             command=lambda: self.app_action(core.UNINSTALL))
        self.btn_apps_disable = ttk.Button(bar, text="⏸ Отключить",
                                           command=lambda: self.app_action(core.DISABLE))
        self.btn_apps_enable = ttk.Button(bar, text="▶ Включить",
                                          command=lambda: self.app_action("enable"))
        for b in (self.btn_apps_load, self.btn_apps_uninstall, self.btn_apps_disable,
                  self.btn_apps_enable):
            b.pack(side="left", padx=(0, 6))

        filt = ttk.Frame(tab)
        filt.pack(fill="x", **pad)
        ttk.Label(filt, text="Поиск:").pack(side="left")
        self.app_filter = tk.StringVar()
        self.app_filter.trace_add("write", lambda *a: self._fill_apps())
        ttk.Entry(filt, textvariable=self.app_filter, width=30).pack(side="left", padx=6)
        self.show_system = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="Показывать системные (проверка займёт до минуты)",
                        variable=self.show_system,
                        command=self.load_apps).pack(side="left", padx=12)

        frame = ttk.Frame(tab)
        frame.pack(fill="both", expand=True, **pad)
        cols = ("desc", "kind", "state", "last", "note")
        self.app_tree = ttk.Treeview(frame, columns=cols, selectmode="browse")
        for col, title, width in (("#0", "Приложение", 260), ("desc", "Что это", 190),
                                  ("kind", "Тип", 85), ("state", "Состояние", 90),
                                  ("last", "Запуск", 85),
                                  ("note", "Проверка", 240)):
            self.app_tree.heading(col, text=title)
            self.app_tree.column(col, width=width, stretch=col in ("#0", "desc", "note"))
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.app_tree.yview)
        self.app_tree.configure(yscrollcommand=sb.set)
        self.app_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.app_tree.bind("<Button-1>", self._on_app_click)
        self.app_tree.bind("<space>", lambda e: self._toggle_app(self.app_tree.focus()))
        self.app_tree.bind("<<TreeviewSelect>>", self._show_app_details)

    def _update_buttons(self):
        connected = core.SERIAL is not None
        scanned = self.ctx is not None

        def st(b, on):
            b.configure(state="normal" if on and not self.busy else "disabled")
        st(self.btn_connect, True)
        st(self.btn_scan, connected)
        st(self.btn_remove, scanned and bool(self.checked))
        st(self.btn_boot, connected)
        st(self.btn_install, connected)
        st(self.btn_restore, connected)
        st(self.btn_home, scanned)
        verb = "Удалить" if self.method.get() == core.UNINSTALL else "Отключить"
        self.btn_remove.configure(text=f"🧹 {verb} отмеченное ({len(self.checked)})")

        picked = [self.apps[p] for p in self.app_checked if p in self.apps]
        st(self.btn_apps_load, connected)
        st(self.btn_apps_uninstall, bool(picked))
        st(self.btn_apps_disable, any(a["enabled"] for a in picked))
        st(self.btn_apps_enable, any(not a["enabled"] for a in picked))
        n = f" ({len(picked)})" if picked else ""
        self.btn_apps_uninstall.configure(text=f"🗑 Удалить{n}")

    def _on_method(self):
        if self.method.get() == core.UNINSTALL and not messagebox.askyesno(
                APP_TITLE, "Удаление менее обратимо, чем отключение.\n\n"
                "После удаления не делайте сброс к заводским настройкам, пока не "
                "восстановите пакеты из бэкапа: на некоторых Xiaomi TV это, по "
                "сообщениям пользователей, приводило к циклической перезагрузке.\n\n"
                "Всё равно удалять, а не отключать?"):
            self.method.set(core.DISABLE)
        self._update_buttons()

    def _on_tab(self, event=None):
        on_apps = self.tabs.index("current") == 1
        self.hint.configure(text=APPS_HINT if on_apps else HINT)
        if on_apps and not self.apps and core.SERIAL and not self.busy:
            self.load_apps()

    # ---------------------------------------------------------------- журнал

    def log(self, text):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", text)
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.log(payload)
                elif kind == "call":
                    payload()
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def run_bg(self, work, done=None):
        """Запускает work() в фоне, done(результат) потом вызывается в окне."""
        if self.busy:
            return
        self.busy = True
        self.configure(cursor="watch")
        self._update_buttons()

        def target():
            try:
                result = work()
            except SystemExit as e:
                print(f"\nОшибка: {e}")
                result = None
            except Exception as e:  # noqa: BLE001 — показать любую ошибку в журнале
                print(f"\nОшибка: {e}")
                result = None

            def finish():
                self.busy = False
                self.configure(cursor="")
                if done:
                    done(result)
                self._update_buttons()
            self.q.put(("call", finish))

        threading.Thread(target=target, daemon=True).start()

    # ---------------------------------------------------------------- подключение

    def _ip_file(self):
        return os.path.join(core.HERE, "last_ip.txt")

    def _load_last_ip(self):
        try:
            with open(self._ip_file(), encoding="utf-8") as f:
                self.ip.set(f.read().strip())
        except OSError:
            pass

    def connect(self):
        ip = self.ip.get().strip()
        if ip and not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}(:\d+)?", ip):
            messagebox.showerror(APP_TITLE, "Это не похоже на IP-адрес.\n"
                                            "Пример: 192.168.1.50")
            return
        if ip:
            try:
                with open(self._ip_file(), "w", encoding="utf-8") as f:
                    f.write(ip)
            except OSError:
                pass

        def work():
            core.ensure_adb()
            core.run([core.ADB, "start-server"], timeout=30)
            core.SERIAL = None
            if ip:
                core.try_connect(ip)
            devs = core.adb_devices()
            if core.SERIAL:
                devs = {k: v for k, v in devs.items() if k == core.SERIAL}
            ready = [k for k, v in devs.items() if v == "device"]
            if ready:
                core.SERIAL = ready[0]
                return ("ok",) + core.device_info()
            core.SERIAL = None
            if any(v == "unauthorized" for v in devs.values()):
                return ("unauthorized",)
            return ("none",)

        def done(res):
            if not res:
                return
            if res[0] == "ok":
                self.model = res[1]
                self.status.configure(text=f"{res[1]}, Android {res[2]}",
                                      style="Good.TLabel")
                print(f"Подключено: {res[1]} (Android {res[2]}, {core.SERIAL})\n"
                      "Теперь нажмите «Найти мусор» или откройте вкладку "
                      "«Установленные приложения».")
                self.ctx = None
                self.apps.clear()
                self.app_checked.clear()
                if self.tabs.index("current") == 1:
                    self.after(50, self.load_apps)
            elif res[0] == "unauthorized":
                self.status.configure(text="ждёт разрешения на ТВ", style="Warn.TLabel")
                messagebox.showinfo(APP_TITLE,
                                    "На экране ТВ появилось окно «Разрешить отладку?».\n"
                                    "Отметьте «Всегда разрешать с этого компьютера», "
                                    "нажмите OK, затем снова «Подключить».")
            else:
                self.status.configure(text="не подключено", style="Bad.TLabel")
                messagebox.showwarning(APP_TITLE,
                                       "Телевизор не найден.\n\nПроверьте IP (Настройки -> "
                                       "Сеть и Интернет -> ваша сеть) и что на ТВ "
                                       "включена отладка по сети.")
        self.run_bg(work, done)

    # ---------------------------------------------------------------- очистка

    def scan(self):
        try:
            days = max(14, int(self.days.get()))
        except (tk.TclError, ValueError):
            days = 90

        def work():
            print("\nСобираю сведения о системе...")
            ctx = core.gather_context()
            print(f"Пакетов: {len(ctx['installed'])}, уже отключено: "
                  f"{len(ctx['disabled'])}, лаунчеры: "
                  f"{', '.join(sorted(ctx['home'])) or 'не определены'}")
            groups = core.scan(ctx, days)
            if "com.google.android.apps.tv.launcherx" in ctx["installed"]:
                print(core.GOOGLE_TV_ADS_TIP)
            return ctx, groups

        def done(res):
            if not res:
                return
            self.ctx, groups = res
            self._fill_tree(groups)
            self._fill_home()
            total = sum(len(i) for _, i in groups)
            print(f"\nНайдено кандидатов: {total}. Отметьте ненужное и нажмите "
                  "«Отключить отмеченное».")
        self.run_bg(work, done)

    def _fill_tree(self, groups):
        self.tree.delete(*self.tree.get_children())
        self.items.clear()
        self.checked.clear()
        for title, items in groups:
            gid = self.tree.insert("", "end", text=f"{UNCHECKED} {title}",
                                   open=True, tags=("group",))
            for pkg, desc, level, reasons in items:
                mark = LOCKED if level == core.BLOCK else UNCHECKED
                iid = self.tree.insert(gid, "end", text=f"{mark} {pkg}",
                                       values=(desc, self._note(level, reasons)),
                                       tags=(level,))
                self.items[iid] = (pkg, desc, level, reasons)
        self._update_buttons()

    @staticmethod
    def _note(level, reasons):
        return (("нельзя: " if level == core.BLOCK else
                 "⚠ " if level == core.WARN else "") + "; ".join(reasons)) or "ок"

    def _fill_home(self):
        cur = (self.ctx["default_home"] or "").split("/")[0]
        values = []
        for p in sorted(self.ctx["home"]):
            name = core.STOCK_LAUNCHERS.get(p) or (
                "PatchWall" if p in core.PATCHWALL else "сторонний лаунчер")
            values.append(f"{p}  ({name}{', сейчас' if p == cur else ''})")
        self.home_box["values"] = values
        for v in values:
            if v.startswith(cur + " "):
                self.home.set(v)

    def _show_details(self, event=None):
        it = self.items.get(self.tree.focus())
        if not it:
            self.hint.configure(text=HINT)
            return
        pkg, desc, level, reasons = it
        self.hint.configure(text=f"{pkg}: {desc}" +
                            "".join(f"\n• {r}" for r in reasons))

    def _on_click(self, event):
        iid = self.tree.identify_row(event.y)
        if "indicator" in self.tree.identify_element(event.x, event.y):
            return  # стрелка раскрытия группы
        if iid and self.tree.identify_region(event.x, event.y) in ("tree", "cell"):
            self._toggle(iid)

    def _set_mark(self, iid, on):
        pkg = self.items[iid][0]
        (self.checked.add if on else self.checked.discard)(pkg)
        self.tree.item(iid, text=f"{CHECKED if on else UNCHECKED} {pkg}")

    def _confirm_warn(self, pkg, level, reasons):
        """Отказ для ✖, подтверждение для ⚠. True — можно отмечать."""
        if level == core.BLOCK:
            messagebox.showinfo(APP_TITLE, f"{pkg} трогать нельзя:\n\n" +
                                "\n".join(reasons))
            return False
        if level == core.WARN:
            return messagebox.askyesno(
                APP_TITLE, f"{pkg}\n\n" + "\n".join("• " + r for r in reasons) +
                "\n\nВсё равно отметить?")
        return True

    def _toggle(self, iid):
        if not iid or self.busy:
            return
        if iid not in self.items:  # группа
            children = [c for c in self.tree.get_children(iid)
                        if self.items[c][2] == core.OK]
            on = not all(self.items[c][0] in self.checked for c in children)
            for c in children:
                self._set_mark(c, on)
            title = self.tree.item(iid, "text")[2:]
            self.tree.item(iid, text=f"{CHECKED if on and children else UNCHECKED} {title}")
        else:
            pkg, desc, level, reasons = self.items[iid]
            on = pkg not in self.checked
            if on and not self._confirm_warn(pkg, level, reasons):
                return
            self._set_mark(iid, on)
        self._update_buttons()

    def _selected_home(self):
        v = self.home.get()
        return v.split()[0] if v else None

    def apply_home(self):
        pkg = self._selected_home()
        if pkg:
            self._make_home(pkg)

    def remove(self):
        ctx = self.ctx
        ctx["new_home"] = None
        chosen_home = self._selected_home()
        cur = (ctx["default_home"] or "").split("/")[0]
        if chosen_home and chosen_home != cur and chosen_home not in self.checked:
            ctx["new_home"] = chosen_home
        # Убираем PatchWall: домашним станет выбранный или штатный лаунчер.
        if any(p in self.checked for p in core.PATCHWALL) and not ctx["new_home"]:
            stock = [p for p in core.STOCK_LAUNCHERS
                     if p in ctx["home"] and p not in self.checked]
            if stock:
                ctx["new_home"] = stock[0]
        self._apply_plan(list(self.checked), self.method.get())

    def _apply_plan(self, packages, method):
        """Общий путь для обеих вкладок: проверка, подтверждение, бэкап, действие."""
        ctx = self.ctx
        plan = core.validate_plan(packages, ctx)
        if not plan:
            messagebox.showinfo(APP_TITLE, "Ничего не отмечено.")
            return
        verb = "Удалить" if method == core.UNINSTALL else "Отключить"
        text = "\n".join("• " + p for p in plan[:25])
        if len(plan) > 25:
            text += f"\n… и ещё {len(plan) - 25}"
        if ctx["new_home"]:
            text += f"\n\nДомашним экраном станет:\n{ctx['new_home']}"
        if not messagebox.askyesno(APP_TITLE, f"{verb} {len(plan)} пакетов?\n\n{text}\n\n"
                                   "Перед этим будет сделан бэкап."):
            return

        def work():
            print()
            return core.perform_removal(plan, ctx, self.model, method)

        def done(res):
            if not res:
                return
            self.last_backup, self.last_removed = res
            self._forget(self.last_removed, method)
            # Сторонние приложения на загрузку не влияют, проверять незачем.
            touched_system = set(self.last_removed) - ctx["third_party"]
            if touched_system and messagebox.askyesno(
                    APP_TITLE, "Готово.\n\nПерезагрузить ТВ и проверить, что он "
                               "нормально загружается? (рекомендуется)\n\n"
                               "Если загрузка не пройдёт, всё вернётся само."):
                self.check_boot()
        self.run_bg(work, done)

    def _forget(self, packages, method):
        """Убирает обработанные пакеты из списков обеих вкладок."""
        done = set(packages)
        for iid, (pkg, *_rest) in list(self.items.items()):
            if pkg in done:
                self.tree.delete(iid)
                del self.items[iid]
                self.checked.discard(pkg)
        if self.ctx:
            if method == core.DISABLE:
                self.ctx["disabled"] |= done
            self.ctx["installed"] -= done
        for pkg in done:
            self.app_checked.discard(pkg)
            if pkg in self.apps:
                if method == core.DISABLE:
                    self.apps[pkg]["enabled"] = False
                else:
                    del self.apps[pkg]
        self._fill_apps()

    def check_boot(self):
        def done(res):
            if not res:
                return
            good, msg = res
            if good:
                print(f"\n✔ Устройство загрузилось нормально, {msg}.")
                messagebox.showinfo(APP_TITLE, f"Телевизор загрузился нормально.\n{msg}")
                return
            if good is None:
                core.SERIAL = None
                self.status.configure(text="нет связи после перезагрузки",
                                      style="Warn.TLabel")
                print(f"\n{msg}.")
                messagebox.showinfo(APP_TITLE, msg + ".")
                return
            print(f"\n✖ Проблема с загрузкой: {msg}.")
            if self.last_backup and messagebox.askyesno(
                    APP_TITLE, f"Проблема с загрузкой: {msg}.\n\n"
                               "Вернуть пакеты, отключённые или удалённые в этот раз?"):
                self._rollback(self.last_backup, self.last_removed, reboot=True)
        self.run_bg(core.check_boot, done)

    def _rollback(self, listfile, only=None, reboot=False):
        def work():
            core.rollback(listfile, only)
            if reboot:
                core.adb("reboot", timeout=20)
                print("Устройство перезагружается.")
            return True

        def done(r):
            if not r:
                return
            self.ctx = None
            self.apps.clear()
            self._fill_apps()
            messagebox.showinfo(APP_TITLE, "Пакеты возвращены. " +
                                ("ТВ перезагружается." if reboot else "Перезагрузите ТВ."))
        self.run_bg(work, done)

    def restore(self):
        path = filedialog.askopenfilename(
            title="Файл removed.txt из папки бэкапа", initialdir=core.HERE,
            filetypes=[("Бэкап", "removed.txt"), ("Все файлы", "*.*")])
        if not path:
            return
        entries, old_home = core.read_backup(path)
        if not entries:
            messagebox.showwarning(APP_TITLE, "В этом файле нет пакетов.")
            return
        if messagebox.askyesno(APP_TITLE, f"Вернуть {len(entries)} пакетов"
                               + (f" и домашний экран {old_home}" if old_home else "")
                               + "?"):
            self._rollback(path)

    # ---------------------------------------------------------------- приложения

    def load_apps(self):
        if not core.SERIAL:
            return
        include_system = self.show_system.get()

        def work():
            print("\nЗагружаю список приложений" +
                  (" вместе с системными, это займёт до минуты..." if include_system
                   else "..."))
            ctx = core.gather_context()
            apps = core.list_apps(ctx, include_system)
            print(f"Приложений в списке: {len(apps)}.")
            return ctx, apps

        def done(res):
            if not res:
                return
            self.ctx, apps = res
            self._fill_home()
            self.apps = {a["pkg"]: a for a in apps}
            self.app_checked &= set(self.apps)
            self._fill_apps()
        self.run_bg(work, done)

    def _fill_apps(self):
        tree = self.app_tree
        tree.delete(*tree.get_children())
        needle = self.app_filter.get().strip().lower()
        # Сначала сторонние, потом системные, в конце то, что трогать нельзя.
        order = sorted(self.apps.values(), key=lambda a: (
            a["level"] == core.BLOCK, not a["user"], a["pkg"]))
        for a in order:
            if needle and needle not in (a["pkg"] + " " + a["desc"]).lower():
                continue
            pkg, level = a["pkg"], a["level"]
            mark = (LOCKED if level == core.BLOCK else
                    CHECKED if pkg in self.app_checked else UNCHECKED)
            last = a["last"][:10] if a["last"] else "ни разу"
            tags = (level,) if a["enabled"] else ("off",)
            tree.insert("", "end", iid=pkg, text=f"{mark} {pkg}", tags=tags,
                        values=(a["desc"], "стороннее" if a["user"] else "системное",
                                "включено" if a["enabled"] else "отключено",
                                last, self._note(level, a["reasons"])))
        self._update_buttons()

    def _on_app_click(self, event):
        iid = self.app_tree.identify_row(event.y)
        if iid and self.app_tree.identify_region(event.x, event.y) in ("tree", "cell"):
            self._toggle_app(iid)

    def _toggle_app(self, pkg):
        if not pkg or self.busy or pkg not in self.apps:
            return
        a = self.apps[pkg]
        on = pkg not in self.app_checked
        if on and not self._confirm_warn(pkg, a["level"], a["reasons"]):
            return
        (self.app_checked.add if on else self.app_checked.discard)(pkg)
        self.app_tree.item(pkg, text=f"{CHECKED if on else UNCHECKED} {pkg}")
        self._update_buttons()

    def _show_app_details(self, event=None):
        a = self.apps.get(self.app_tree.focus())
        if not a:
            self.hint.configure(text=APPS_HINT)
            return
        kind = "стороннее приложение" if a["user"] else "системное приложение"
        self.hint.configure(text=f"{a['pkg']}: " + (f"{a['desc']}, " if a["desc"] else "") +
                            f"{kind}, "
                            f"{'включено' if a['enabled'] else 'отключено'}" +
                            "".join(f"\n• {r}" for r in a["reasons"]))

    def app_action(self, action):
        picked = [self.apps[p] for p in sorted(self.app_checked) if p in self.apps]
        if action == "enable":
            targets = [a["pkg"] for a in picked if not a["enabled"]]
            self._enable(targets)
            return
        if action == core.DISABLE:
            picked = [a for a in picked if a["enabled"]]
        system = [a["pkg"] for a in picked if not a["user"]]
        if action == core.UNINSTALL and system and not messagebox.askyesno(
                APP_TITLE, "Среди выбранных есть системные приложения:\n\n" +
                "\n".join("• " + p for p in system[:15]) +
                "\n\nИх надёжнее отключать, а не удалять. После удаления не делайте "
                "сброс к заводским настройкам, пока не восстановите их из бэкапа.\n\n"
                "Всё равно удалить?"):
            return
        self.ctx["new_home"] = None
        cur = (self.ctx["default_home"] or "").split("/")[0]
        if cur in {a["pkg"] for a in picked}:
            left = [p for p in core.STOCK_LAUNCHERS
                    if p in self.ctx["home"] and p not in self.app_checked]
            left += sorted(self.ctx["home"] - self.app_checked - set(left))
            if left:
                self.ctx["new_home"] = left[0]
        self._apply_plan([a["pkg"] for a in picked], action)

    def _enable(self, packages):
        if not packages:
            return

        def work():
            print()
            ok = []
            for pkg in packages:
                good, msg = core.enable(pkg)
                print(f"  {'✔' if good else '✖'} {pkg} включено" +
                      ("" if good else f": {msg}"))
                if good:
                    ok.append(pkg)
            return ok

        def done(ok):
            for pkg in ok or []:
                self.app_checked.discard(pkg)
                if pkg in self.apps:
                    self.apps[pkg]["enabled"] = True
                if self.ctx:
                    self.ctx["disabled"].discard(pkg)
                    self.ctx["installed"].add(pkg)
            self._fill_apps()
        self.run_bg(work, done)

    # ---------------------------------------------------------------- прочее

    def install(self):
        paths = filedialog.askopenfilenames(
            title="Выберите приложения для установки на ТВ",
            filetypes=[("Приложения Android", "*.apk *.apks *.xapk *.apkm"),
                       ("Все файлы", "*.*")])
        if not paths:
            return

        def work():
            print()
            ok, launchers = core.install_apks(list(paths))
            return ok, launchers

        def done(res):
            if not res:
                return
            ok, launchers = res
            if self.apps:
                self.after(50, self.load_apps)
            for p in launchers:
                if messagebox.askyesno(APP_TITLE, f"{p} — это лаунчер.\n\n"
                                       "Сделать его домашним экраном?"):
                    self._make_home(p)
                    break
            else:
                messagebox.showinfo(APP_TITLE, f"Установлено: {ok} из {len(paths)}."
                                    + ("" if ok == len(paths) else
                                       "\nПричины ошибок смотрите в журнале."))
        self.run_bg(work, done)

    def _make_home(self, pkg):
        note = self.ctx and core.home_button_warning(self.ctx, pkg)
        if note:
            messagebox.showinfo(APP_TITLE, note)

        def work():
            ok = core.set_home(pkg)
            print(f"\nДомашний экран: {pkg}" +
                  ("" if ok else " (система может спросить при нажатии Home)"))
            if self.ctx:
                self.ctx["home"] = core.home_packages(self.ctx["installed"] | {pkg})
                self.ctx["default_home"] = core.default_home()
        self.run_bg(work, lambda r: self.ctx and self._fill_home())

    def open_folder(self):
        if os.name == "nt":
            os.startfile(core.HERE)  # noqa: S606 — открыть папку в проводнике
        else:
            subprocess.Popen(["xdg-open", core.HERE])

    def _on_close(self):
        if self.busy and not messagebox.askyesno(
                APP_TITLE, "Операция ещё идёт. Всё равно закрыть?"):
            return
        try:
            core.shutdown_adb()
        except Exception:  # noqa: BLE001
            pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
