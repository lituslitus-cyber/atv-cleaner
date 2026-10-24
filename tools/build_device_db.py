# -*- coding: utf-8 -*-
"""Собирает device_db.py из списков проекта cleanyourtv (MIT, Gathin).

Запуск: python tools/build_device_db.py <путь к клону github.com/Gathin23/cleanyourtv>
Берутся папки examples/<марка>-* для марок из BRANDS: модель, платформа, версия
Android, отключённые пакеты и пакеты, которые авторы оставили намеренно.
Заодно обновляется таблица устройств в README.md.
"""
import datetime
import os
import pprint
import re
import subprocess
import sys

# Папки cleanyourtv -> марка в базе.
BRANDS = {"xiaomi": "Xiaomi", "redmi": "Xiaomi", "tcl": "TCL"}

PKG_LINE = re.compile(r"^([a-zA-Z][\w]*(?:\.[\w]+)+)\s*(?:#\s*(.*))?$")
PKG_ANY = re.compile(r"\b((?:com|mitv|tv|org|android\.autoinstalls)\.[\w]+(?:\.[\w]+)*[\w])")
KEEP_HINT = re.compile(r"keep|kept|left alone|leave alone|left enabled|never disable|"
                       r"do not disable|do not touch|don't touch|must stay|stay enabled|"
                       r"deliberately|on purpose", re.I)


def header_of(lines):
    header = []
    for line in lines:
        if line.startswith("#"):
            header.append(line[1:].strip())
        elif line.strip():
            break
    return header


def xiaomi_ids(title, top):
    # Модель берём из первой строки: дальше в тексте упоминаются соседние модели.
    pat = r"\b(MiTV-[A-Z0-9]+|MIBOX\d)\b"
    ids = re.findall(pat, title) or re.findall(pat, top)[:1]
    codename = (re.search(r"codename (\w+)", top) or re.search(r"MiTV-\w+, (\w+)[,)]", top)
                or re.search(r"MiTV-\w+ \((\w+)[,)]", top))
    return sorted(set(ids)), codename.group(1) if codename else ""


def tcl_platform(top):
    """У TCL модель везде «Smart TV Pro»: различаем по платформе (ro.product.device)."""
    m = (re.search(r"\bdevice[: `]+([A-Za-z][\w]*)", top)
         or re.search(r"\b(BeyondTV\d?|UnionTV)\b", top)
         or re.search(r"\b(G\d\d)\b", top))
    device = m.group(1) if m else ""
    if device in ("and", "with"):  # «product/device and ro.product.model BeyondTV»
        m = re.search(r"(BeyondTV\d?|UnionTV)", top)
        device = m.group(1) if m else ""
    product = re.search(r"\bproduct[: `]+([A-Z][\w]*)", top)
    return device, product.group(1) if product else ""


def parse(path, brand):
    lines = open(path, encoding="utf-8").read().splitlines()
    header = header_of(lines)
    title = header[0] if header else ""
    top = " ".join(header[:4])
    if brand == "Xiaomi":
        ids, codename = xiaomi_ids(title, " ".join(header[:3]))
        product = ""
    else:
        ids = []
        codename, product = tcl_platform(top)
    android = re.search(r"(?:Android|Google TV)(?: TV)?(?: on Android)? (\d+)", top)
    china = bool(re.search(r"China|Chinese-market|CN firmware|HyperOS|_cn\b", top))
    if re.search(r"HyperOS(?: TV)? \d", top):
        firmware = "HyperOS"
    elif re.search(r"Fire TV", top):
        firmware = "Fire TV"
    elif "Google TV" in top or "launcherx" in top:
        firmware = "Google TV"
    elif "Android TV" in top or "Mi Box" in top:
        firmware = "Android TV"
    else:
        firmware = "Android"
    chip = next((c for c in ("Amlogic", "MediaTek", "Realtek") if c in top), "")
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
    # Имена экранов и служб внутри пакетов (com.tcl.player.TVActivity) — не пакеты.
    keep = {p for p in keep if not re.search(r"\.[A-Z]\w*(Activity|Service|Receiver|Provider)$", p)}
    keep = {p for p in keep if not p.startswith("com.gathin")
            and (p == "mitv.service" or (p.count(".") >= 2 and not p.startswith("mitv.")))}
    return {
        "brand": brand,
        "title": title.rstrip("."),
        "ids": ids,
        "codename": codename,
        "product": product,
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
        brand = BRANDS.get(d.split("-")[0])
        if brand and os.path.isfile(path):
            models[d] = parse(path, brand)
    commit = subprocess.run(["git", "-C", repo, "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "device_db.py")
    with open(out, "w", encoding="utf-8") as f:
        f.write('# -*- coding: utf-8 -*-\n"""База устройств: что сообщество отключало на каждой модели.\n\n')
        f.write("Создано tools/build_device_db.py из списков проекта cleanyourtv\n")
        f.write(f"(https://github.com/Gathin23/cleanyourtv, коммит {commit}, "
                f"{datetime.date.today()}).\n\n")
        f.write("Исходные данные: MIT License, Copyright (c) 2026 Gathin.\n")
        f.write("Не править вручную: перегенерировать скриптом.\n")
        f.write('"""\n\n')
        f.write("MODELS = ")
        f.write(pprint.pformat(models, width=100, sort_dicts=True))
        f.write("\n")
    counts = {b: sum(m["brand"] == b for m in models.values()) for b in set(BRANDS.values())}
    print(f"{out}: {len(models)} моделей {counts}, коммит {commit}")
    update_readme(models, root)


def short_name(t):
    return re.split(r" \(|, Android| on Android|, MiTV-| — |, reports| debloat", t)[0].strip()


def device_rows(models, brand):
    rows = []
    for m in models.values():
        if m["brand"] != brand:
            continue
        kind = m["firmware"] + (", Китай" if m["china"] else "")
        model = ", ".join(m["ids"]) or "—"
        platform = m["codename"] + (f" / {m['product']}" if m["product"] else "")
        rows.append((short_name(m["title"]), model, platform or "—", m["android"] or "—",
                     kind, m["chip"] or "—", len(m["disabled"])))
    rows.sort(key=lambda r: (not r[0].startswith(("Xiaomi Mi Box", "Xiaomi TV Box",
                                                  "Xiaomi TV Stick")), r[2], r[0], r[3]))
    if brand == "TCL":
        head = ("| Устройство | Платформа / product | Android | Прошивка | Чип | Пакетов |\n"
                "|---|---|---|---|---|---|\n")
        return head + "".join(f"| {r[0]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |\n"
                              for r in rows)
    head = ("| Устройство | Модель | Кодовое имя | Android | Прошивка | Чип | Пакетов |\n"
            "|---|---|---|---|---|---|---|\n")
    return head + "".join(f"| {' | '.join(str(x) for x in r)} |\n" for r in rows)


def update_readme(models, root):
    path = os.path.join(root, "README.md")
    text = open(path, encoding="utf-8").read()
    start, end = "<!-- devices:start -->", "<!-- devices:end -->"
    if start not in text:
        print("В README нет меток таблицы устройств, пропускаю.")
        return
    parts = []
    for brand, label in (("Xiaomi", "Xiaomi и Redmi"), ("TCL", "TCL")):
        n = sum(m["brand"] == brand for m in models.values())
        if not n:
            continue
        note = (" Модель у TCL всегда «Smart TV Pro», поэтому программа определяет "
                "платформу (ro.product.device, например G08) и даёт рекомендации по "
                "всем спискам этой платформы.") if brand == "TCL" else ""
        parts.append(f"\n#### {label} ({n})\n\n{note.strip()}\n\n" if note else
                     f"\n#### {label} ({n})\n\n")
        parts.append(device_rows(models, brand))
    a, b = text.index(start) + len(start), text.index(end)
    text = text[:a] + "".join(parts) + text[b:]
    open(path, "w", encoding="utf-8").write(text)
    print(f"README: таблица устройств обновлена ({len(models)})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "cleanyourtv")
