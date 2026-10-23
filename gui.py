# -*- coding: utf-8 -*-
"""ATV Cleaner, оконная версия. Вся работа с ТВ живёт в atv_cleaner."""

import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import atv_cleaner as core

APP_TITLE = "ATV Cleaner"
UNCHECKED, CHECKED, LOCKED = "☐", "☑", "✖"
HINT = ("Щелчок по пакету отмечает его, по группе отмечает всё безопасное "
        "в группе. ⚠ требует подтверждения, ✖ удалять нельзя.")


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
        self.geometry("980x720")
        self.minsize(760, 520)

        self.q = queue.Queue()
        sys.stdout = sys.stderr = QueueWriter(self.q)

        self.ctx = None
        self.model = ""
        self.items = {}          # id строки -> (пакет, описание, уровень, причины)
        self.checked = set()     # отмеченные пакеты
        self.last_backup = None  # removed.txt последнего удаления
        self.last_removed = []
        self.busy = False

        self._build()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._load_last_ip()
        self.log("Включите на ТВ «Отладку по сети» (Настройки -> Для разработчиков),\n"
                 "введите IP телевизора и нажмите «Подключить».\n")

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
        self.status = ttk.Label(conn, text="не подключено", foreground="#a00")
        self.status.pack(side="left", padx=8)

        actions = ttk.Frame(self)
        actions.pack(fill="x", **pad)
        self.btn_scan = ttk.Button(actions, text="🔍 Найти мусор", command=self.scan)
        self.btn_remove = ttk.Button(actions, text="🗑 Удалить отмеченное",
                                     command=self.remove)
        self.btn_boot = ttk.Button(actions, text="🔄 Перезагрузить и проверить",
                                   command=self.check_boot)
        self.btn_restore = ttk.Button(actions, text="↩ Восстановить из бэкапа",
                                      command=self.restore)
        for b in (self.btn_scan, self.btn_remove, self.btn_boot, self.btn_restore):
            b.pack(side="left", padx=(0, 6))
        self.btn_folder = ttk.Button(conn, text="📁 Папка бэкапов",
                                     command=self.open_folder)
        self.btn_folder.pack(side="right", padx=(0, 8))
        self.btn_install = ttk.Button(conn, text="📦 Установить APK на ТВ",
                                      command=self.install)
        self.btn_install.pack(side="right", padx=6)

        home = ttk.Frame(self)
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
        ttk.Label(home, text="Неиспользуемые, дней:").pack(
            side="right", padx=(12, 4))

        pane = ttk.PanedWindow(self, orient="vertical")
        pane.pack(fill="both", expand=True, **pad)

        tree_frame = ttk.Frame(pane)
        self.tree = ttk.Treeview(tree_frame, columns=("desc", "note"),
                                 selectmode="browse")
        self.tree.heading("#0", text="Пакет")
        self.tree.heading("desc", text="Что это")
        self.tree.heading("note", text="Проверка")
        self.tree.column("#0", width=330)
        self.tree.column("desc", width=280)
        self.tree.column("note", width=340)
        self.tree.tag_configure("group", font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("warn", foreground="#b35c00")
        self.tree.tag_configure("block", foreground="#999")
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<space>", lambda e: self._toggle(self.tree.focus()))
        pane.add(tree_frame, weight=3)

        log_frame = ttk.Frame(pane)
        self.logbox = tk.Text(log_frame, height=10, wrap="word", state="disabled",
                              font=("Consolas", 9))
        lsb = ttk.Scrollbar(log_frame, orient="vertical", command=self.logbox.yview)
        self.logbox.configure(yscrollcommand=lsb.set)
        self.logbox.pack(side="left", fill="both", expand=True)
        lsb.pack(side="right", fill="y")
        pane.add(log_frame, weight=1)

        self.hint = ttk.Label(self, foreground="#555", text=HINT, wraplength=940,
                              justify="left")
        self.hint.pack(fill="x", padx=8, pady=(0, 6))
        self.tree.bind("<<TreeviewSelect>>", self._show_details)
        self._update_buttons()

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
        self.btn_remove.configure(text=f"🗑 Удалить отмеченное ({len(self.checked)})")

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
                                      foreground="#070")
                print(f"Подключено: {res[1]} (Android {res[2]}, {core.SERIAL})\n"
                      "Теперь нажмите «Найти мусор».")
            elif res[0] == "unauthorized":
                self.status.configure(text="ждёт разрешения на ТВ", foreground="#b35c00")
                messagebox.showinfo(APP_TITLE,
                                    "На экране ТВ появилось окно «Разрешить отладку?».\n"
                                    "Отметьте «Всегда разрешать с этого компьютера», "
                                    "нажмите OK, затем снова «Подключить».")
            else:
                self.status.configure(text="не подключено", foreground="#a00")
                messagebox.showwarning(APP_TITLE,
                                       "Телевизор не найден.\n\nПроверьте IP (Настройки -> "
                                       "Сеть и Интернет -> ваша сеть) и что на ТВ "
                                       "включена отладка по сети.")
        self.run_bg(work, done)

    # ---------------------------------------------------------------- поиск

    def scan(self):
        try:
            days = max(14, int(self.days.get()))
        except (tk.TclError, ValueError):
            days = 90

        def work():
            print("\nСобираю сведения о системе...")
            ctx = core.gather_context()
            print(f"Пакетов: {len(ctx['installed'])}, лаунчеры: "
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
                  "«Удалить отмеченное».")
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
                note = ("нельзя: " if level == core.BLOCK else
                        "⚠ " if level == core.WARN else "") + "; ".join(reasons)
                iid = self.tree.insert(gid, "end", text=f"{mark} {pkg}",
                                       values=(desc, note or "ок"),
                                       tags=(level,))
                self.items[iid] = (pkg, desc, level, reasons)
        self._update_buttons()

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
            if level == core.BLOCK:
                messagebox.showinfo(APP_TITLE, f"{pkg} удалять нельзя:\n\n" +
                                    "\n".join(reasons))
                return
            on = pkg not in self.checked
            if on and level == core.WARN and not messagebox.askyesno(
                    APP_TITLE, f"{pkg}\n\n" + "\n".join("• " + r for r in reasons) +
                    "\n\nВсё равно отметить для удаления?"):
                return
            self._set_mark(iid, on)
        self._update_buttons()

    # ---------------------------------------------------------------- действия

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

        plan = core.validate_plan(list(self.checked), ctx)
        if not plan:
            messagebox.showinfo(APP_TITLE, "Нечего удалять.")
            return
        text = "\n".join("• " + p for p in plan)
        if ctx["new_home"]:
            text += f"\n\nДомашним экраном станет:\n{ctx['new_home']}"
        if not messagebox.askyesno(APP_TITLE, f"Удалить {len(plan)} пакетов?\n\n{text}\n\n"
                                   "Перед удалением будет сделан бэкап."):
            return

        def work():
            print()
            return core.perform_removal(plan, ctx, self.model)

        def done(res):
            if not res:
                return
            self.last_backup, self.last_removed = res
            for iid, (pkg, *_rest) in list(self.items.items()):
                if pkg in self.last_removed:
                    self.tree.delete(iid)
                    del self.items[iid]
                    self.checked.discard(pkg)
            if self.last_removed and messagebox.askyesno(
                    APP_TITLE, "Готово.\n\nПерезагрузить ТВ и проверить, что он "
                               "нормально загружается? (рекомендуется)\n\n"
                               "Если загрузка не пройдёт, удалённое вернётся само."):
                self.check_boot()
        self.run_bg(work, done)

    def check_boot(self):
        def done(res):
            if not res:
                return
            good, msg = res
            if good:
                print(f"\n✔ Устройство загрузилось нормально, {msg}.")
                messagebox.showinfo(APP_TITLE, f"Телевизор загрузился нормально.\n{msg}")
                return
            print(f"\n✖ Проблема с загрузкой: {msg}.")
            if self.last_backup and messagebox.askyesno(
                    APP_TITLE, f"Проблема с загрузкой: {msg}.\n\n"
                               "Вернуть пакеты, удалённые в этот раз?"):
                self._rollback(self.last_backup, self.last_removed, reboot=True)
        self.run_bg(core.check_boot, done)

    def _rollback(self, listfile, only=None, reboot=False):
        def work():
            core.rollback(listfile, only)
            if reboot:
                core.adb("reboot", timeout=20)
                print("Устройство перезагружается.")
            return True
        self.run_bg(work, lambda r: r and messagebox.showinfo(
            APP_TITLE, "Пакеты возвращены. " +
            ("ТВ перезагружается." if reboot else "Перезагрузите ТВ.")))

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
