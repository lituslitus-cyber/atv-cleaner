# -*- coding: utf-8 -*-
"""Собирает xiaomi_db.py из списков проекта cleanyourtv (MIT, Gathin).

Запуск: python tools/build_xiaomi_db.py <путь к клону github.com/Gathin23/cleanyourtv>
Берутся папки examples/xiaomi-* и examples/redmi-*: модель, кодовое имя, версия
Android, отключённые на ней пакеты и пакеты, которые авторы оставили намеренно.
"""
import datetime
import os
import pprint
import re
import subprocess
import sys

PKG_LINE = re.compile(r"^([a-zA-Z][\w]*(?:\.[\w]+)+)\s*(?:#\s*(.*))?$")
PKG_ANY = re.compile(r"\b((?:com|mitv|android\.autoinstalls)\.[\w]+(?:\.[\w]+)*[\w])")
KEEP_HINT = re.compile(r"keep|kept|left alone|leave alone|do not disable|do not touch|"
                       r"don't touch|must stay|stay enabled|deliberately", re.I)


def parse(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    header = []
    for line in lines:
        if line.startswith("#"):
            header.append(line[1:].strip())
        elif line.strip():
            break
    title = header[0] if header else ""
    top = " ".join(header[:3])
    # Модель берём из первой строки: дальше в тексте упоминаются соседние модели.
    ids = re.findall(r"\b(MiTV-[A-Z0-9]+|MIBOX\d)\b", title) or \
        re.findall(r"\b(MiTV-[A-Z0-9]+|MIBOX\d)\b", top)[:1]
    codename = (re.search(r"codename (\w+)", top) or re.search(r"MiTV-\w+, (\w+)[,)]", top)
                or re.search(r"MiTV-\w+ \((\w+)[,)]", top))
    android = re.search(r"(?:Android|Google TV)(?: TV)?(?: on Android)? (\d+)", top)
    china = bool(re.search(r"China|CN firmware|HyperOS", top))
    if re.search(r"HyperOS(?: TV)? \d", top):
        firmware = "HyperOS"
    elif "Google TV" in top:
        firmware = "Google TV"
    elif "Android TV" in top or "Mi Box" in top:
        firmware = "Android TV"
    else:
        firmware = "Android"
    chip = next((c for c in ("Amlogic", "MediaTek") if c in top), "")
    disabled, personal, section = [], [], ""
    for line in lines[len(header):]:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            section = s.lstrip("# ").lower()
            continue
        m = PKG_LINE.match(s)
        if m:
            disabled.append(m.group(1))
            if "personal" in section or "choice" in section:
                personal.append(m.group(1))
    # «Оставлено намеренно»: пакеты из строк заголовка с такими словами и строк
    # сразу после них (списки в заголовках переносятся на несколько строк).
    keep, carry = set(), 0
    for h in header[1:]:
        if KEEP_HINT.search(h):
            carry = 4
        if carry:
            keep.update(PKG_ANY.findall(h))
            carry -= 1
    keep -= set(disabled)
    # Только полные имена пакетов (без обрывков вроде com.mediatek, mitv.gallery).
    keep = {p for p in keep if not p.startswith("com.gathin")
            and (p == "mitv.service" or (p.count(".") >= 2 and not p.startswith("mitv.")))}
    return {
        "title": title.rstrip("."),
        "ids": sorted(set(ids)),
        "codename": codename.group(1) if codename else "",
        "android": android.group(1) if android else "",
        "firmware": firmware,
        "china": china,
        "chip": chip,
        "disabled": disabled,
        "personal": personal,
        "keep": sorted(keep),
    }


def main(repo):
    base = os.path.join(repo, "examples")
    models = {}
    for d in sorted(os.listdir(base)):
        path = os.path.join(base, d, "debloat.txt")
        if re.match(r"(xiaomi|redmi)-", d) and os.path.isfile(path):
            models[d] = parse(path)
    commit = subprocess.run(["git", "-C", repo, "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "xiaomi_db.py")
    with open(out, "w", encoding="utf-8") as f:
        f.write('# -*- coding: utf-8 -*-\n"""База моделей Xiaomi: что сообщество отключало на каждой модели.\n\n')
        f.write("Создано tools/build_xiaomi_db.py из списков проекта cleanyourtv\n")
        f.write(f"(https://github.com/Gathin23/cleanyourtv, коммит {commit}, "
                f"{datetime.date.today()}).\n\n")
        f.write("Исходные данные: MIT License, Copyright (c) 2026 Gathin.\n")
        f.write("Не править вручную: перегенерировать скриптом.\n")
        f.write('"""\n\n')
        f.write("MODELS = ")
        f.write(pprint.pformat(models, width=100, sort_dicts=True))
        f.write("\n")
    print(f"{out}: {len(models)} моделей, коммит {commit}")
    update_readme(models)


def device_rows(models):
    """Строки таблицы устройств для README."""
    rows = []
    for m in models.values():
        t = m["title"]
        name = re.split(r" \(|, Android| on Android|, MiTV-", t)[0].strip()
        kind = m["firmware"] + (", Китай" if m["china"] else "")
        rows.append((name, ", ".join(m["ids"]) or "—", m["codename"] or "—",
                     m["android"] or "—", kind, m["chip"] or "—", len(m["disabled"])))
    rows.sort(key=lambda r: (not r[0].startswith(("Xiaomi Mi Box", "Xiaomi TV Box", "Xiaomi TV Stick")),
                             r[0], r[3]))
    head = ("| Устройство | Модель | Кодовое имя | Android | Прошивка | Чип | Пакетов |\n"
            "|---|---|---|---|---|---|---|\n")
    return head + "".join(f"| {' | '.join(str(x) for x in r)} |\n" for r in rows)


def update_readme(models):
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "README.md")
    text = open(path, encoding="utf-8").read()
    start, end = "<!-- devices:start -->", "<!-- devices:end -->"
    if start not in text:
        print("В README нет меток таблицы устройств, пропускаю.")
        return
    a, b = text.index(start) + len(start), text.index(end)
    text = text[:a] + "\n" + device_rows(models) + text[b:]
    open(path, "w", encoding="utf-8").write(text)
    print(f"README: таблица из {len(models)} устройств обновлена")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "cleanyourtv")
