#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATV Cleaner: очистка телевизоров и приставок на Android TV / Google TV
от предустановленного мусора через ADB. Сейчас подробнее всего описаны
устройства Xiaomi (PatchWall, Mi Box). Другие марки добавляются пакетами
в каталоги ниже (JUNK, APPS, FEATURES) и шаблонами в VENDOR_HINT.

Что делает скрипт:
  * сам скачивает ADB, если его нет, и спрашивает IP телевизора;
  * предлагает заменить PatchWall штатным лаунчером;
  * находит лишние пакеты и показывает их по группам, в том числе
    приложения, которые давно или ни разу не запускались;
  * до удаления проверяет, не сломает ли это загрузку: лаунчер, клавиатура,
    persistent- и системные пакеты, администраторы устройства;
  * отключает (или, по выбору, удаляет) только то, что вы подтвердили,
    и сохраняет бэкап: список пакетов и APK сторонних приложений;
  * по желанию перезагружает устройство и проверяет, что оно загрузилось
    до главного экрана. Если нет, возвращает всё назад.

По умолчанию пакеты отключаются (`pm disable-user --user 0`): приложение
остаётся на месте, но не запускается. Так советуют делать на 4PDA и XDA,
это полностью обратимо. Режим --uninstall удаляет пакеты для пользователя
(`pm uninstall -k --user 0`). Вернуть всё можно так:
    python atv_cleaner.py --restore <файл removed.txt>
После режима «удалить» не делайте сброс к заводским настройкам, пока не
восстановите пакеты: на некоторых Xiaomi TV это, по сообщениям
пользователей, приводило к циклической перезагрузке.

Подготовка ТВ: Настройки -> Об устройстве -> 7 раз нажать на «Сборка»,
затем в «Для разработчиков» включить «Отладка по USB» и «Отладка по сети»
(названия пунктов зависят от модели).

На Windows проще всего запускать файл «Запустить ATV Cleaner.bat».
    python atv_cleaner.py                       # спросит IP сам
    python atv_cleaner.py --connect 192.168.1.50
    python atv_cleaner.py --dry-run             # только показать
"""

__version__ = "1.2.0"

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# В собранной программе (.exe) бэкапы и ADB лежат рядом с exe.
if getattr(sys, "frozen", False):
    HERE = os.path.dirname(sys.executable)
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
ADB = "adb"
SERIAL = None
CONNECT_ADDR = None

OK, WARN, BLOCK = "ok", "warn", "block"
DISABLE, UNINSTALL = "disable", "uninstall"

# Чтобы в оконной программе на каждый вызов adb не мигала консоль.
NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# ---------------------------------------------------------------------------
# Каталог. Пакеты, которых нет на устройстве, просто не показываются.
# Пакеты новых марок добавляются сюда же.
# ---------------------------------------------------------------------------

JUNK = {
    "com.miui.tv.analytics": "Аналитика и телеметрия Xiaomi",
    "com.xiaomi.statistic": "Сбор статистики Xiaomi",
    "com.xiaomi.mitv.tvmanager": "TV Manager («ускоритель», очистка памяти)",
    "com.xiaomi.mitv.appstore": "Магазин приложений Xiaomi",
    "com.xiaomi.mitv.payment": "Платёжный сервис Xiaomi",
    "com.xiaomi.mitv.care": "Обратная связь Xiaomi",
    "com.xiaomi.mitv.osstatistic": "Сбор статистики Xiaomi",
    "com.miui.systemAdSolution": "Рекламный сервис Xiaomi",
    "com.xiaomi.mitv.advertise": "Рекламный сервис Xiaomi",
    "com.xiaomi.mitv.tvpush.tvpushservice": "Push-уведомления и реклама Xiaomi",
    "com.xiaomi.floatingframe": "Всплывающие промо-окна Xiaomi",
    "com.xm.webcontent": "Рекламный веб-контент Xiaomi",
    "com.mitv.tvhome.mitvplus": "Рекламный ряд рекомендаций PatchWall",
    "com.mitv.tvhome.michannel": "Каналы-рекомендации PatchWall",
    "com.google.android.leanbacklauncher.recommendations": "Рекламный ряд рекомендаций лаунчера",
    "com.google.android.tv.bugreportsender": "Отправка отчётов об ошибках в Google",
    "com.xiaomi.mitv.shop": "Магазин Xiaomi",
    "com.xiaomi.mitv.shop.mihome": "Магазин Mi Home",
    "com.xiaomi.mitv.shop.tvshop": "ТВ-магазин Xiaomi",
    "com.google.android.feedback": "Отправка отзывов в Google",
    "com.android.printspooler": "Служба печати (на ТВ не нужна)",
    "com.android.dreams.basic": "Заставка «Цвета»",
    "com.android.egg": "Пасхалка Android",
}

APPS = {
    "com.netflix.ninja": "Netflix",
    "com.amazon.amazonvideo.livingroom": "Prime Video",
    "com.disney.disneyplus": "Disney+",
    "com.spotify.tv.android": "Spotify",
    "com.google.android.youtube.tv": "YouTube",
    "com.google.android.youtube.tvmusic": "YouTube Music",
    "com.google.android.videos": "Google Play Фильмы / Google TV",
    "com.google.android.play.games": "Google Play Игры",
    "com.google.android.music": "Google Play Музыка (сервис закрыт)",
    "com.google.android.backdrop": "Заставка Ambient (фото от Google)",
    "com.mitv.gallery": "Галерея Xiaomi",
    "com.mitv.videoplayer": "Видеоплеер Xiaomi (файлы с USB)",
    "com.xiaomi.mitv.mediaexplorer": "Медиапроводник Xiaomi",
    "com.xiaomi.tv.gallery": "Галерея Xiaomi",
    "com.xiaomi.mimusic": "Xiaomi Music",
    "com.xiaomi.mimusic2": "Xiaomi Music",
    "com.mitv.dream": "Заставка Xiaomi",
    "com.xiaomi.tweather": "Погода Xiaomi",
    "com.xiaomi.smarthome.tv": "Умный дом Xiaomi",
    "com.xiaomi.mibox.gamecenter": "Игровой центр Xiaomi",
    "com.hulu.livingroomplus": "Hulu",
    "com.sling": "Sling TV",
    "com.pandora.android.atv": "Pandora",
    "com.cbs.ott": "Paramount+ (CBS)",
    "com.showtime.standalone": "Showtime",
    "com.nousguide.android.rbtv": "Red Bull TV",
    "air.com.vudu.air.DownloaderTablet": "Vudu",
}

FEATURES = {
    "com.google.android.apps.mediashell": "Chromecast built-in (трансляция с телефона)",
    "com.google.android.tvrecommendations": "Рекомендации на главном экране",
    "com.google.android.marvin.talkback": "TalkBack (озвучивание экрана)",
    "com.android.tv": "Live Channels (на ТВ с эфирным тюнером не трогать)",
    "com.xiaomi.mitv.upgrade": "Обновления прошивки Xiaomi (OTA)",
    "com.xiaomi.mitv.updateservice": "Служба обновлений Xiaomi",
    "com.xiaomi.tv.appupgrade": "Обновление приложений Xiaomi",
    "com.mitv.tvlock": "Родительский замок Xiaomi",
}

# Пакеты из каталога, которые требуют отдельного подтверждения.
CAUTION = {
    "com.xiaomi.mitv.upgrade": "перестанут приходить обновления прошивки",
    "com.xiaomi.mitv.updateservice": "перестанут приходить обновления прошивки",
    "com.xiaomi.tv.appupgrade": "системные приложения Xiaomi перестанут обновляться",
    "com.google.android.apps.mediashell": "не будет работать трансляция с телефона "
                                          "(Chromecast)",
    "com.android.tv": "на ТВ с антенной пропадут эфирные каналы",
    "com.mitv.tvlock": "если на ТВ стоит родительский PIN-код, он перестанет действовать",
    "com.google.android.tvrecommendations": "главный экран может стать пустым",
}

GROUPS = [
    ("Мусор, реклама и телеметрия", JUNK),
    ("Предустановленные приложения", APPS),
    ("Функции системы (убирать осознанно)", FEATURES),
]

PATCHWALL = ("com.mitv.tvhome.atv", "com.mitv.tvhome")
# Штатные лаунчеры в порядке предпочтения. Их скрипт не предлагает удалять.
STOCK_LAUNCHERS = {
    "com.google.android.apps.tv.launcherx": "лаунчер Google TV",
    "com.google.android.tvlauncher": "штатный лаунчер Android TV",
    "com.google.android.leanbacklauncher": "старый лаунчер Android TV",
}

# Сюда скрипт не лезет никогда: без этого ТВ не загрузится или потеряет
# изображение, звук, пульт, HDMI, сеть или Play Маркет.
PROTECTED = [re.compile(p) for p in (
    r"^android$",
    r"^(android|vendor)\.",
    r"^com\.android\.(systemui|settings|shell|phone|bluetooth|nfc|keychain|"
    r"externalstorage|packageinstaller|permissioncontroller|inputdevices|"
    r"location\.fused|server\..*|networkstack.*|wifi.*|tethering|webview|"
    r"certinstaller|proxyhandler|statementservice|sharedstoragebackup|"
    r"backupconfirm|defcontainer|mtp|wallpaperbackup|localtransport|"
    r"dynsystem|modulemetadata|vending)$",
    r"^com\.android\.(providers|ext|media|tv)\.",
    r"^com\.google\.android\.(gms|gsf|gsf\.login|ext\..*|packageinstaller|"
    r"permissioncontroller|webview|modulemetadata|configupdater|"
    r"partnersetup|onetimeinitializer|tungsten\..*|tvsetup.*|sss.*|"
    r"networkstack.*|media\..*|tv\.frameworkpackagestubs|"
    r"apps\.tv\.launcherx\.coreservices)$",
    r"^com\.(droidlogic|amlogic|mediatek|mstar|realtek|rtk|novatek|"
    r"cvte|hisilicon)\.",
    r"overlay",
    r"setupwizard|setupwraith|provision|partnercustomizer",
    r"settings|systemui|framework|permission|provider|keystore|keychain",
    r"inputmethod|\.ime$|\.ime\.|keyboard",
    r"tvinput|hdmi|\bcec\b|tuner|dtv|tvplayer|tvserver|tvservice|"
    r"bluetooth|wifi|network|remotecontrol|\.rc$|irservice|tv\.remote",
    r"webview|chrome",
    # Голосовой поиск: на Android TV это katniss, на Google TV и в прошивках
    # Xiaomi свои пакеты, поэтому защищаем всё, что похоже на голос и поиск.
    r"katniss|voice|speech|pumpkin|hotword|assistant|search|\.tts$|"
    r"tvsearch|googlequicksearchbox|velvet",
)]

VENDOR_HINT = re.compile(r"xiaomi|mitv|miui|^com\.mi\.")

# Приложения, которые работают без запуска вручную: трансляция, фон.
BACKGROUND_HINT = re.compile(r"cast|miracast|airplay|airscreen|dlna|mirror|"
                             r"share|remote|vpn|wallpaper|dream|saver|sync")

# FallbackHome из «Настроек» показывается только пока система загружается.
# Если, кроме него, лаунчеров не осталось, ТВ висит на «Android запускается».
FALLBACK_HOME = {"android", "com.android.settings", "com.android.tv.settings"}

SYSTEM_UIDS = {"android.uid.system", "android.uid.phone",
               "android.uid.bluetooth", "android.uid.nfc", "android.uid.shell",
               "android.media", "android.uid.networkstack"}

GOOGLE_TV_ADS_TIP = """
Совет для Google TV. Вкладку с рекомендациями и рекламой удалением пакетов не
убрать: её показывает сам лаунчер Google TV. Её отключает режим «Только
приложения»: Настройки -> Аккаунты и вход -> ваш аккаунт -> «Только
приложения». На главном экране останутся только ваши приложения. Голосовой
поиск при этом не удаляется, но рекомендации и подсказки Ассистента станут
беднее. Убрать рекламу полностью можно другим лаунчером (например, Projectivy
или FLauncher из Play Маркета). Если он установлен, скрипт предложит сделать
его домашним."""

DATE_RE = r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d"


# ---------------------------------------------------------------------------
# ADB и подключение
# ---------------------------------------------------------------------------

def run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           stdin=subprocess.DEVNULL, timeout=timeout,
                           creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        return 124, ""
    return r.returncode, r.stdout.decode("utf-8", "replace").strip()


def adb(*args, timeout=60):
    return run([ADB] + (["-s", SERIAL] if SERIAL else []) + list(args), timeout)


def sh(command, timeout=60):
    return adb("shell", command, timeout=timeout)[1]


def ask(prompt):
    try:
        return input(prompt).strip().lower()
    except EOFError:
        return ""


def yes(prompt):
    return ask(prompt + " [y/N]: ") in ("y", "yes", "д", "да")


def die(msg):
    print("\n[!] " + msg)
    sys.exit(1)


def ensure_adb():
    """Находит adb, а если его нет, скачивает Platform Tools рядом со скриптом."""
    global ADB
    if os.path.isfile(ADB) or shutil.which(ADB):
        return
    local = os.path.join(HERE, "platform-tools",
                         "adb.exe" if os.name == "nt" else "adb")
    bundled = os.path.join(getattr(sys, "_MEIPASS", ""), "platform-tools")
    if not os.path.isfile(local) and os.path.isdir(bundled):
        # ADB, вшитый в exe, копируем рядом: из временной папки его не запустить
        # как постоянный сервер.
        shutil.copytree(bundled, os.path.dirname(local), dirs_exist_ok=True)
    if not os.path.isfile(local):
        plat = {"win32": "windows", "darwin": "darwin"}.get(sys.platform, "linux")
        url = ("https://dl.google.com/android/repository/"
               f"platform-tools-latest-{plat}.zip")
        print("ADB не найден, скачиваю Android Platform Tools с сайта Google...")
        zpath = os.path.join(HERE, "platform-tools.zip")
        try:
            urllib.request.urlretrieve(url, zpath)
            with zipfile.ZipFile(zpath) as z:
                z.extractall(HERE)
        except Exception as e:
            die(f"Не удалось скачать ADB ({e}). Скачайте вручную: {url} "
                f"и распакуйте в папку {HERE}")
        finally:
            if os.path.exists(zpath):
                os.remove(zpath)
        if os.name != "nt":
            os.chmod(local, 0o755)
        print("ADB установлен.")
    ADB = local


def adb_devices():
    devices = {}
    for line in run([ADB, "devices"])[1].splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            devices[parts[0]] = parts[1]
    return devices


def adb_connect(addr):
    return run([ADB, "connect", addr], timeout=20)[1]


def try_connect(addr):
    global SERIAL, CONNECT_ADDR
    if ":" not in addr:
        addr += ":5555"
    print(f"Подключаюсь к {addr}...")
    out = adb_connect(addr)
    if "connected" in out:
        SERIAL = CONNECT_ADDR = addr
        return True
    print(f"Не удалось подключиться: {out or 'нет ответа'}")
    if "refused" in out.lower():
        print("Телевизор отклонил подключение: включите на нём «Отладку по сети».")
    else:
        print("Проверьте IP и что компьютер и ТВ в одной сети.")
    return False


def ask_ip():
    last_file = os.path.join(HERE, "last_ip.txt")
    last = ""
    if os.path.isfile(last_file):
        with open(last_file, encoding="utf-8") as f:
            last = f.read().strip()
    print("\nТелевизор пока не подключён.\n"
          "IP можно посмотреть на ТВ: Настройки -> Сеть и Интернет -> "
          "ваша сеть Wi-Fi\n(или Об устройстве -> Статус). На ТВ должна быть "
          "включена отладка\n(Настройки -> Для разработчиков).")
    hint = f" [Enter = {last}]" if last else ""
    while True:
        try:
            ip = input(f"IP телевизора{hint}, или q для выхода: ").strip()
        except EOFError:
            ip = "q"
        if ip.lower() in ("q", "й"):
            sys.exit(0)
        ip = ip or last
        if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}(:\d+)?", ip):
            with open(last_file, "w", encoding="utf-8") as f:
                f.write(ip)
            return ip
        print("Это не похоже на IP-адрес, пример: 192.168.1.50")


def pick_device(args):
    global SERIAL
    ensure_adb()
    run([ADB, "start-server"], timeout=30)
    if args.serial:
        SERIAL = args.serial
    if args.connect:
        try_connect(args.connect)

    while True:
        devs = adb_devices()
        if SERIAL:
            devs = {k: v for k, v in devs.items() if k == SERIAL}
        ready = [k for k, v in devs.items() if v == "device"]
        if len(ready) == 1:
            SERIAL = ready[0]
            return
        if len(ready) > 1:
            print("Найдено несколько устройств:")
            for i, s in enumerate(ready, 1):
                print(f"  {i}. {s}")
            n = ask("Номер устройства: ")
            if n.isdigit() and 1 <= int(n) <= len(ready):
                SERIAL = ready[int(n) - 1]
                return
            continue
        if any(v == "unauthorized" for v in devs.values()):
            print("\nНа экране ТВ должно появиться окно «Разрешить отладку?».\n"
                  "Отметьте «Всегда разрешать с этого компьютера» и нажмите OK.")
            ask("Затем нажмите Enter здесь...")
            continue
        try_connect(ask_ip())


def list_packages(extra=""):
    out = sh(f"pm list packages {extra} --user 0")
    return {l[8:].strip() for l in out.splitlines() if l.startswith("package:")}


def full_components(text):
    return re.findall(r"^\s*([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)", text, re.M)


def components(text):
    return [c.split("/")[0] for c in full_components(text)]


def query(category):
    return sh("cmd package query-activities --brief "
              f"-a android.intent.action.MAIN -c android.intent.category.{category}")


def home_components():
    return [c for c in full_components(query("HOME"))
            if c.split("/")[0] not in FALLBACK_HOME]


def home_packages(installed):
    found = {c.split("/")[0] for c in home_components()}
    if not found:
        # Старые прошивки без query-activities: берём известные лаунчеры.
        found = (set(PATCHWALL) | set(STOCK_LAUNCHERS)) & installed
    return found


def default_home():
    out = sh("cmd package resolve-activity --brief "
             "-a android.intent.action.MAIN -c android.intent.category.HOME")
    comps = components(out)
    return comps[-1] if comps else None


def set_home(pkg):
    """Делает pkg домашним экраном. Возвращает True, если получилось."""
    sh(f"cmd role add-role-holder --user 0 android.app.role.HOME {pkg}")
    comp = next((c for c in home_components() if c.startswith(pkg + "/")), None)
    if comp:
        sh(f"cmd package set-home-activity --user 0 {comp}")
    return default_home() == pkg


def gather_context():
    everything = list_packages()
    if not everything:
        die("Не удалось получить список пакетов с устройства.")
    disabled = list_packages("-d")
    # Уже отключённые пакеты не предлагаем ещё раз.
    installed = everything - disabled
    ctx = {
        "installed": installed,
        "disabled": disabled,
        "third_party": list_packages("-3"),
        "home": home_packages(installed),
        "default_home": default_home(),
        "new_home": None,
    }
    ime = sh("settings get secure default_input_method")
    ctx["ime_current"] = ime.split("/")[0] if "/" in ime else None
    ctx["imes"] = set(components(sh("ime list -s")))
    if ctx["ime_current"]:
        ctx["imes"].add(ctx["ime_current"])
    ctx["admins"] = set(re.findall(r"ComponentInfo\{([\w.]+)/",
                                   sh("dumpsys device_policy")))
    acc = sh("settings get secure enabled_accessibility_services")
    ctx["accessibility"] = {a.split("/")[0] for a in acc.split(":") if "/" in a}
    return ctx


def is_protected(pkg):
    return any(p.search(pkg) for p in PROTECTED)


def assess(pkg, ctx):
    """Проверка влияния на загрузку. Возвращает (уровень, причины)."""
    if is_protected(pkg):
        return BLOCK, ["системный компонент, нужен для работы ТВ"]
    level, reasons = OK, []

    def warn(msg):
        nonlocal level
        if level == OK:
            level = WARN
        reasons.append(msg)

    if pkg in ctx["admins"]:
        return BLOCK, ["администратор устройства"]

    info = sh(f"dumpsys package {pkg}", timeout=30)
    if re.search(r"flags=\[[^\]]*\bPERSISTENT\b", info):
        return BLOCK, ["persistent: система держит его запущенным всегда"]
    m = re.search(r"sharedUser=SharedUserSetting\{\w+ ([\w.]+)/", info)
    if m and m.group(1) in SYSTEM_UIDS:
        return BLOCK, [f"работает с правами системы ({m.group(1)})"]

    if pkg in ctx["home"]:
        others = ctx["home"] - {pkg}
        if not others:
            return BLOCK, ["единственный лаунчер: без него ТВ зависнет "
                           "на «Android запускается»"]
        cur = (ctx["default_home"] or "").split("/")[0]
        warn("это лаунчер (главный экран)" +
             (", и он сейчас используется" if cur == pkg else "") +
             f"; останется: {', '.join(sorted(others))}")
    if pkg in ctx["imes"]:
        if not ctx["imes"] - {pkg}:
            return BLOCK, ["единственная экранная клавиатура"]
        if pkg == ctx["ime_current"]:
            warn("текущая клавиатура, система переключится на другую")
    if pkg in ctx["accessibility"]:
        warn("включён как служба специальных возможностей")
    if pkg in CAUTION:
        warn(CAUTION[pkg])
    if pkg in ctx["third_party"]:
        reasons.append("не системное: при удалении удалится полностью, "
                       "APK сохраню в бэкап")
    return level, reasons


# ---------------------------------------------------------------------------
# Статистика запусков
# ---------------------------------------------------------------------------

def usage_stats():
    """Последний запуск каждого приложения и дата начала статистики."""
    out = sh("dumpsys usagestats", timeout=180)
    last = {}

    def seen(pkg, date):
        if date > "1971" and date > last.get(pkg, ""):
            last[pkg] = date

    for m in re.finditer(r"package=([\w.]+)([^\n]*)", out):
        for d in re.findall(r'lastTime\w*="(' + DATE_RE + ')"', m.group(2)):
            seen(m.group(1), d)
    for m in re.finditer(r'time="(' + DATE_RE + r')" type=(?:MOVE_TO_FOREGROUND|'
                         r'ACTIVITY_RESUMED)[^\n]*?package=([\w.]+)', out):
        seen(m.group(2), m.group(1))
    starts = [s for s in re.findall(r'timeRange="(' + DATE_RE + ')', out)
              if s > "1971"]
    since = min(starts) if starts else (min(last.values()) if last else None)
    return last, since


def parse_date(s):
    return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def unused_apps(ctx, days, skip):
    """Приложения с иконкой в меню, которые давно или ни разу не запускались."""
    last, since = usage_stats()
    if not last:
        print("\nСтатистика запусков на этом устройстве недоступна, "
              "этот шаг пропускаю.")
        return []
    try:
        now = parse_date(sh("date '+%Y-%m-%d %H:%M:%S'"))
    except ValueError:
        now = datetime.datetime.now()
    tracked = (now - parse_date(since)).days if since else 0
    print(f"\nСтатистика запусков ведётся с {since[:10]} "
          f"(примерно {tracked} дн.).")
    if tracked < 14:
        print("Это слишком мало, чтобы судить, что не используется: "
              "шаг пропускаю.")
        return []

    # Только приложения с иконкой в меню: фоновые сервисы «не запускаются»
    # по определению, и по ним статистика ничего не говорит.
    launchable = set(components(query("LEANBACK_LAUNCHER"))) | \
        set(components(query("LAUNCHER")))
    candidates = []
    for pkg in sorted(launchable & ctx["installed"]):
        if pkg in skip or pkg in ctx["home"] or is_protected(pkg):
            continue
        used = last.get(pkg)
        if used and (now - parse_date(used)).days < days:
            continue
        candidates.append((pkg, used))
    candidates.sort(key=lambda c: c[1] or "")

    items = []
    for pkg, used in candidates:
        if used:
            desc = (f"последний запуск {used[:10]} "
                    f"({(now - parse_date(used)).days} дн. назад)")
        else:
            desc = "ни разу не запускалось"
        level, reasons = assess(pkg, ctx)
        if level != BLOCK and BACKGROUND_HINT.search(pkg):
            level = WARN if level == OK else level
            reasons.append("может работать без запуска (трансляция или фон), "
                           "проверьте, что вы им не пользуетесь")
        items.append((pkg, desc, level, reasons))
    return items


# ---------------------------------------------------------------------------
# Выбор
# ---------------------------------------------------------------------------

MARK = {OK: "  ", WARN: "⚠ ", BLOCK: "✖ "}


def choose(title, items, allow_all=True):
    print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)
    for i, (pkg, desc, level, reasons) in enumerate(items, 1):
        print(f"{i:>3}. {MARK[level]}{pkg}\n       {desc}")
        for r in reasons:
            print(f"       {'нельзя: ' if level == BLOCK else '· '}{r}")
    selectable = [it for it in items if it[2] != BLOCK]
    if not selectable:
        print("   Удалять здесь нечего.")
        return []

    hint = "[a] все доступные, " if allow_all else ""
    while True:
        ans = ask(f"\nЧто убрать? {hint}номера через пробел, Enter: пропустить: ")
        if not ans:
            return []
        if allow_all and ans in ("a", "а", "all", "все"):
            picked = selectable
        else:
            nums = re.split(r"[\s,;]+", ans)
            if not all(n.isdigit() and 1 <= int(n) <= len(items) for n in nums):
                print("   Не понял ввод, повторите.")
                continue
            picked = [items[int(n) - 1] for n in dict.fromkeys(nums)]
            blocked = [p[0] for p in picked if p[2] == BLOCK]
            if blocked:
                print("   Эти пакеты удалять нельзя: " + ", ".join(blocked))
                picked = [p for p in picked if p[2] != BLOCK]

        result = []
        for pkg, desc, level, reasons in picked:
            if level == WARN and not yes(f"   {pkg}: {'; '.join(reasons)}. "
                                         "Всё равно убрать?"):
                continue
            result.append(pkg)
        return result


def choose_launcher(ctx):
    """Предлагает другой домашний экран и удаление PatchWall."""
    pw = [p for p in PATCHWALL if p in ctx["installed"]]
    stock = [p for p in STOCK_LAUNCHERS if p in ctx["home"]]
    custom = sorted(ctx["home"] - set(PATCHWALL) - set(STOCK_LAUNCHERS))
    cur = (ctx["default_home"] or "").split("/")[0]
    if not pw and not custom:
        return []
    print("\n" + "=" * 70 + "\nЛаунчер (главный экран)\n" + "=" * 70)
    print(f"Сейчас домашний: {cur or 'не определён'}")

    for p in custom:
        if p != cur and yes(f"Найден сторонний лаунчер {p}. Сделать его домашним?"):
            ctx["new_home"] = p
            note = home_button_warning(ctx, p)
            if note:
                print(note)
            break
    if not pw:
        return []

    target = ctx["new_home"] or (stock[0] if stock else None)
    if not target:
        print("Других лаунчеров на этом устройстве нет, PatchWall здесь "
              "единственный главный экран.\nУдалять его нельзя, оставляю.")
        return []
    blocked = [(p, r) for p in pw for lvl, r in [assess(p, ctx)] if lvl == BLOCK
               and "единственный лаунчер" not in r[0]]
    if blocked:
        for p, r in blocked:
            print(f"PatchWall ({p}) удалить нельзя: {r[0]}.")
        return []
    name = STOCK_LAUNCHERS.get(target, target)
    if not yes(f"Удалить PatchWall" + ("" if ctx["new_home"] else
               f" и сделать домашним {name} ({target})") + "?"):
        return []
    ctx["new_home"] = target
    return pw


def validate_plan(plan, ctx):
    """Финальная проверка плана целиком: лаунчер и клавиатура должны остаться."""
    plan = list(plan)
    if ctx["home"] and not ctx["home"] - set(plan):
        dropped = [p for p in plan if p in ctx["home"]]
        print("\n[!] После удаления не останется ни одного лаунчера. "
              "Оставляю: " + ", ".join(dropped))
        plan = [p for p in plan if p not in ctx["home"]]
    if ctx["imes"] and not ctx["imes"] - set(plan):
        dropped = [p for p in plan if p in ctx["imes"]]
        print("\n[!] Не останется ни одной клавиатуры. Оставляю: " +
              ", ".join(dropped))
        plan = [p for p in plan if p not in ctx["imes"]]
    cur = (ctx["default_home"] or "").split("/")[0]
    if cur in plan and not ctx["new_home"]:
        left = [p for p in STOCK_LAUNCHERS if p in ctx["home"] and p not in plan]
        left += sorted(ctx["home"] - set(plan) - set(left))
        ctx["new_home"] = left[0]
    return plan


# ---------------------------------------------------------------------------
# Удаление, бэкап, восстановление
# ---------------------------------------------------------------------------

def backup(plan, ctx, model, method=DISABLE):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_serial = re.sub(r"[^\w.-]", "_", SERIAL or "device")
    folder = os.path.join(HERE, f"backup_{safe_serial}_{stamp}")
    n = 2
    while os.path.exists(folder):  # две операции в одну секунду
        folder = os.path.join(HERE, f"backup_{safe_serial}_{stamp}-{n}")
        n += 1
    os.makedirs(folder)
    listfile = os.path.join(folder, "removed.txt")
    with open(listfile, "w", encoding="utf-8") as f:
        f.write(f"# {model}, {SERIAL}, {stamp}\n")
        f.write(f"# Домашний экран до очистки: {ctx['default_home']}\n")
        f.write("# Восстановление: python atv_cleaner.py --restore "
                f"\"{listfile}\"\n")
        for pkg in plan:
            kind = "user" if pkg in ctx["third_party"] else "system"
            f.write(f"{pkg}\t{kind}\t{method}\n")
    for pkg in plan:
        # Отключённое приложение остаётся на ТВ, его APK сохранять незачем.
        if method == DISABLE or pkg not in ctx["third_party"]:
            continue
        dst = os.path.join(folder, pkg)
        os.makedirs(dst, exist_ok=True)
        for line in sh(f"pm path {pkg}").splitlines():
            if line.startswith("package:"):
                adb("pull", line[8:].strip(), dst, timeout=300)
    return listfile


def disable(pkg):
    out = sh(f"pm disable-user --user 0 {pkg}")
    if "disabled" in out.lower():
        return True, ""
    return False, (out or "нет ответа") + " (можно попробовать режим «удалить»)"


def enable(pkg):
    out = sh(f"pm enable --user 0 {pkg}")
    if "enabled" in out.lower():
        return True, ""
    return False, out or "нет ответа"


def uninstall(pkg, full=False):
    """full=True для сторонних приложений: удалить совсем, а не для пользователя."""
    out = sh(f"pm uninstall {pkg}" if full else f"pm uninstall -k --user 0 {pkg}")
    if "Success" in out:
        return True, ""
    # Некоторые прошивки не дают удалить, но позволяют отключить.
    ok, _ = disable(pkg)
    if ok:
        return True, "не удалился, но отключён"
    return False, out


def restore_packages(entries, folder):
    ok = 0
    for pkg, kind, method in entries:
        if method == DISABLE:
            out = sh(f"pm enable --user 0 {pkg}")
            good = "enabled" in out.lower()
            ok += good
            print(f"  {'✔' if good else '✖'} {pkg}" + ("" if good else f": {out}"))
            continue
        if kind == "user":
            apks = []
            d = os.path.join(folder, pkg)
            if os.path.isdir(d):
                apks = sorted(os.path.join(d, a) for a in os.listdir(d)
                              if a.endswith(".apk"))
            if not apks:
                print(f"  ✖ {pkg}: нет APK в бэкапе")
                continue
            rc, out = adb("install-multiple", "-r", *apks, timeout=600) \
                if len(apks) > 1 else adb("install", "-r", apks[0], timeout=600)
        else:
            out = sh(f"cmd package install-existing --user 0 {pkg}")
            if "installed" not in out.lower():
                out = sh(f"pm install-existing {pkg}")
            sh(f"pm enable --user 0 {pkg}")
        good = "success" in out.lower() or "installed" in out.lower()
        ok += good
        print(f"  {'✔' if good else '✖'} {pkg}" + ("" if good else f": {out}"))
    return ok


def read_backup(path):
    entries, old_home = [], None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            m = re.match(r"# Домашний экран до очистки: ([\w.]+)", line)
            if m and m.group(1) != "None":
                old_home = m.group(1)
            if line and not line.startswith("#"):
                # Старые бэкапы (1.0) без способа: тогда всё удалялось.
                pkg, kind, method = (line.split("\t") + ["system", UNINSTALL])[:3]
                entries.append((pkg, kind or "system", method or UNINSTALL))
    return entries, old_home


# ---------------------------------------------------------------------------
# Проверка загрузки
# ---------------------------------------------------------------------------

def check_boot(timeout=300):
    print("\nПерезагружаю устройство и жду загрузки (до "
          f"{timeout // 60} мин)...")
    adb("reboot", timeout=20)
    time.sleep(15)
    deadline = time.time() + timeout
    booted = False
    while time.time() < deadline:
        if CONNECT_ADDR:
            adb_connect(CONNECT_ADDR)
        rc, out = adb("shell", "getprop sys.boot_completed", timeout=10)
        if out.strip() == "1":
            booted = True
            break
        print("  ...ещё загружается")
        time.sleep(5)
    if not booted:
        return False, "система не сообщила о завершении загрузки"

    # Ждём, пока FallbackHome («Android запускается») сменится лаунчером.
    end = time.time() + 90
    while time.time() < end:
        top = sh("dumpsys activity activities | grep -E "
                 "'mResumedActivity|ResumedActivity'")
        if top and "FallbackHome" not in top:
            home = default_home() or "?"
            return True, f"главный экран: {home}"
        time.sleep(5)
    return False, "застрял на экране «Android запускается» (нет лаунчера)"


# ---------------------------------------------------------------------------
# Общие шаги для консольной и оконной версий
# ---------------------------------------------------------------------------

def device_info():
    model = " ".join(filter(None, [sh("getprop ro.product.manufacturer"),
                                   sh("getprop ro.product.model")]))
    return model, sh("getprop ro.build.version.release")


UNKNOWN_DESC = "неизвестный пакет Xiaomi: удаляйте, только если знаете, что это"


def scan(ctx, days, include_patchwall=True, skip=()):
    """Все кандидаты на удаление: [(заголовок, [(пакет, описание, уровень, причины)])]."""
    groups = []
    seen = set(PATCHWALL) | set(STOCK_LAUNCHERS) | set(skip)
    pw = [p for p in PATCHWALL if p in ctx["installed"]]
    if include_patchwall and pw:
        groups.append(("Лаунчер PatchWall",
                       [(p, "PatchWall, лаунчер Xiaomi. Домашним станет штатный",
                         *assess(p, ctx)) for p in pw]))
    for title, catalog in GROUPS:
        found = [p for p in catalog if p in ctx["installed"]]
        seen.update(catalog)
        if found:
            groups.append((title, [(p, catalog[p], *assess(p, ctx)) for p in found]))

    print("Анализирую, какие приложения давно не запускались...")
    items = unused_apps(ctx, days, seen)
    if items:
        groups.append((f"Не запускались больше {days} дней или ни разу", items))
        seen.update(p[0] for p in items)

    unknown = sorted(p for p in ctx["installed"]
                     if VENDOR_HINT.search(p) and p not in seen
                     and not is_protected(p))
    if unknown:
        groups.append(("Прочие пакеты Xiaomi (не из списка)",
                       [(p, UNKNOWN_DESC, *assess(p, ctx)) for p in unknown]))
    return groups


def perform_removal(plan, ctx, model, method=DISABLE):
    """Бэкап, смена лаунчера и отключение/удаление. -> (бэкап, обработанные)."""
    listfile = backup(plan, ctx, model, method)
    if method == DISABLE:
        action = disable
    else:
        def action(pkg):
            return uninstall(pkg, full=pkg in ctx["third_party"])
    print(f"Бэкап: {listfile}")
    if ctx["new_home"]:
        set_home(ctx["new_home"])
    removed = []
    for pkg in plan:
        good, note = action(pkg)
        print(f"  {'✔' if good else '✖'} {pkg}" + (f": {note}" if note else ""))
        if good:
            removed.append(pkg)
    print(f"{'Отключено' if method == DISABLE else 'Удалено'}: "
          f"{len(removed)} из {len(plan)}.")
    if removed and ctx["new_home"]:
        ok = set_home(ctx["new_home"])
        print(f"Домашний экран: {ctx['new_home']}" + ("" if ok else
              " (система может один раз спросить, какой лаунчер использовать)"))
    return listfile, removed


def list_apps(ctx, include_system=False):
    """Установленные приложения для вкладки «Установленные приложения»."""
    last, _ = usage_stats()
    apps = []
    for pkg in sorted(ctx["installed"] | ctx["disabled"]):
        user = pkg in ctx["third_party"]
        if not user and not include_system:
            continue
        level, reasons = assess(pkg, ctx)
        apps.append({"pkg": pkg, "user": user, "enabled": pkg not in ctx["disabled"],
                     "last": last.get(pkg), "level": level, "reasons": reasons})
    return apps


def home_button_warning(ctx, pkg):
    """На Xiaomi кнопка Home зашита на PatchWall, пока он включён."""
    if pkg in PATCHWALL:
        return None
    if any(p in ctx["installed"] for p in PATCHWALL):
        return ("На Xiaomi кнопка Home на пульте может по-прежнему открывать "
                "PatchWall. Чтобы она открывала новый лаунчер, отключите PatchWall.")
    return None


def rollback(listfile, only=None):
    """Возвращает пакеты из бэкапа и прежний домашний экран."""
    entries, old_home = read_backup(listfile)
    if only is not None:
        entries = [e for e in entries if e[0] in only]
    print(f"Восстанавливаю {len(entries)} пакетов...")
    n = restore_packages(entries, os.path.dirname(os.path.abspath(listfile)))
    if old_home:
        set_home(old_home.split("/")[0])
        print(f"Домашний экран возвращён: {old_home}")
    print(f"Готово: {n} из {len(entries)}.")
    return n


# ---------------------------------------------------------------------------
# Установка APK
# ---------------------------------------------------------------------------

INSTALL_ERRORS = {
    "INSTALL_FAILED_OLDER_SDK": "приложению нужна более новая версия Android",
    "INSTALL_FAILED_NO_MATCHING_ABIS": "сборка не для этого процессора, нужна "
                                       "версия для ARM (armeabi-v7a или arm64-v8a)",
    "INSTALL_FAILED_INSUFFICIENT_STORAGE": "на телевизоре не хватает места",
    "INSTALL_FAILED_UPDATE_INCOMPATIBLE": "уже установлена версия с другой "
                                          "подписью: сначала удалите её",
    "INSTALL_FAILED_VERSION_DOWNGRADE": "на телевизоре уже стоит более новая версия",
    "INSTALL_FAILED_ALREADY_EXISTS": "приложение уже установлено",
    "INSTALL_PARSE_FAILED": "файл повреждён или это не APK",
    "INSTALL_FAILED_INVALID_APK": "файл повреждён или это не APK",
    "INSTALL_FAILED_MISSING_SPLIT": "это часть приложения: нужен полный "
                                    "комплект (.apks или .xapk)",
    "INSTALL_FAILED_USER_RESTRICTED": "установку запретили на телевизоре",
    "INSTALL_FAILED_VERIFICATION_FAILURE": "установку заблокировала проверка "
                                           "Google Play Защиты",
}


def explain_install_error(out):
    for code, text in INSTALL_ERRORS.items():
        if code in out:
            return f"{text} ({code})"
    m = re.search(r"Failure \[([^\]]+)\]", out)
    return m.group(1) if m else (out.strip().splitlines() or ["нет ответа"])[-1]


def install_one(path):
    """Ставит .apk, .apks или .xapk. Возвращает (успех, сообщение)."""
    if not os.path.isfile(path):
        return False, "файл не найден"
    ext = os.path.splitext(path)[1].lower()
    if ext == ".apk":
        rc, out = adb("install", "-r", path, timeout=900)
    elif ext in (".apks", ".xapk", ".apkm", ".zip"):
        # Наборы из базового APK и частей: распаковываем и ставим вместе.
        with tempfile.TemporaryDirectory() as tmp:
            try:
                with zipfile.ZipFile(path) as z:
                    names = [n for n in z.namelist()
                             if n.lower().endswith(".apk") and "/" not in n.strip("/")]
                    for n in names:
                        z.extract(n, tmp)
            except zipfile.BadZipFile:
                return False, "архив повреждён"
            if not names:
                return False, "внутри нет APK-файлов"
            apks = [os.path.join(tmp, n) for n in names]
            rc, out = (adb("install-multiple", "-r", *apks, timeout=900)
                       if len(apks) > 1 else adb("install", "-r", apks[0], timeout=900))
    else:
        return False, "поддерживаются .apk, .apks и .xapk"
    if "Success" in out:
        return True, ""
    return False, explain_install_error(out)


def install_apks(paths):
    """Ставит файлы по очереди. Возвращает (сколько успешно, новые лаунчеры)."""
    before = list_packages()
    ok = 0
    for path in paths:
        print(f"Устанавливаю {os.path.basename(path)}...")
        good, msg = install_one(path)
        ok += good
        print(f"  {'✔ установлено' if good else '✖ ' + msg}")
    new = list_packages() - before
    if new:
        print("Новые приложения: " + ", ".join(sorted(new)))
    launchers = sorted(new & {c.split("/")[0] for c in home_components()})
    print(f"Установлено: {ok} из {len(paths)}.")
    return ok, launchers


def shutdown_adb():
    run([ADB, "kill-server"], timeout=15)


# ---------------------------------------------------------------------------

def main():
    global ADB
    ap = argparse.ArgumentParser(description="ATV Cleaner: очистка Android TV / Google TV от мусора через ADB")
    ap.add_argument("--connect", metavar="IP", help="подключиться к ТВ по сети")
    ap.add_argument("-s", "--serial", help="серийный номер устройства из `adb devices`")
    ap.add_argument("--adb", default="adb", help="путь к adb")
    ap.add_argument("--days", type=int, default=90,
                    help="считать неиспользуемым, если не запускалось столько дней (90)")
    ap.add_argument("--dry-run", action="store_true", help="только показать, ничего не удалять")
    ap.add_argument("--uninstall", action="store_true",
                    help="удалять пакеты (pm uninstall --user 0), а не отключать")
    ap.add_argument("--restore", metavar="FILE", help="вернуть пакеты из бэкапа removed.txt")
    ap.add_argument("--install", metavar="APK", nargs="+",
                    help="установить на ТВ файлы .apk / .apks / .xapk")
    args = ap.parse_args()
    ADB = args.adb

    pick_device(args)
    model, android = device_info()
    print(f"\nУстройство: {model} (Android {android}, {SERIAL})")

    if args.install:
        ok, launchers = install_apks(args.install)
        for p in launchers:
            if yes(f"{p} — это лаунчер. Сделать его домашним?"):
                set_home(p)
                break
        return

    if args.restore:
        rollback(args.restore)
        print("Перезагрузите устройство.")
        return

    print("Собираю сведения о системе...")
    ctx = gather_context()
    print(f"Пакетов: {len(ctx['installed'])}, лаунчеры: "
          f"{', '.join(sorted(ctx['home'])) or 'не определены'}, "
          f"клавиатура: {ctx['ime_current'] or 'не определена'}")

    plan = choose_launcher(ctx)
    for n, (title, items) in enumerate(scan(ctx, args.days, include_patchwall=False), 1):
        plan += choose(f"{n}. {title}", items,
                       allow_all=not all(i[1] == UNKNOWN_DESC for i in items))

    plan = validate_plan(list(dict.fromkeys(plan)), ctx)
    if not plan:
        if ctx["new_home"] and not args.dry_run:
            ok = set_home(ctx["new_home"])
            print(f"\nДомашний экран: {ctx['new_home']}" +
                  ("" if ok else " (не удалось, выберите его кнопкой Home)"))
        print("\nНичего не выбрано для удаления. Выход.")
        return

    if "com.google.android.apps.tv.launcherx" in ctx["installed"]:
        print(GOOGLE_TV_ADS_TIP)

    print("\nБудут " + ("удалены:" if args.uninstall else "отключены:"))
    for p in plan:
        print("  - " + p)
    if ctx["new_home"]:
        print(f"Домашним экраном станет: {ctx['new_home']}")
    if args.dry_run:
        print("\n--dry-run: ничего не удаляю.")
        return
    verb = "Удалить" if args.uninstall else "Отключить"
    if ask(f"\n{verb} {len(plan)} пакетов? Введите «да»: ") not in ("да", "yes"):
        print("Отменено.")
        return

    print()
    listfile, removed = perform_removal(plan, ctx, model,
                                       UNINSTALL if args.uninstall else DISABLE)
    if not removed:
        return

    if not yes("\nПерезагрузить и проверить, что ТВ нормально загружается? "
               "(рекомендуется)"):
        print(f"Если что-то пойдёт не так: python atv_cleaner.py "
              f"--restore \"{listfile}\"")
        return

    good, msg = check_boot()
    if good:
        print(f"\n✔ Устройство загрузилось нормально, {msg}.")
        return
    print(f"\n✖ Проблема с загрузкой: {msg}.")
    rollback(listfile, only=removed)
    adb("reboot", timeout=20)
    print("Устройство перезагружается.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nПрервано.")
