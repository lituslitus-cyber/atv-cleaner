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

__version__ = "1.5.0"

import argparse
import concurrent.futures
import datetime
import ipaddress
import os
import re
import shutil
import socket
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
    "com.android.hotspot2.osulogin": "Регистрация в сетях Passpoint (Hotspot 2.0)",
    "com.android.cts.ctsshim": "Заглушка для тестов совместимости Google (CTS)",
    "com.android.cts.priv.ctsshim": "Заглушка для тестов совместимости Google (CTS)",
    "com.google.android.syncadapters.calendar": "Синхронизация Google Календаря",
    "com.xiaomo.tv.milegal": "Юридические документы Xiaomi",
    "com.android.htmlviewer": "Просмотр HTML (раздел «Лицензии» в настройках)",
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
    "com.xiaomi.wfdsinkhelperservice": "перестанет работать трансляция экрана на ТВ",
    "com.mitv.milinkservice": "перестанут работать Mi Cast и пульт в телефоне",
    "com.xiaomi.mitv.smartshare": "перестанет работать Mi Cast",
    "com.xiaomi.mitv.tvmanager": "мнения расходятся: в одних списках отключают, "
                                 "в других оставляют",
    "com.xiaomo.tv.milegal": "может понадобиться, если ТВ снова покажет "
                             "соглашение после обновления",
    "com.android.htmlviewer": "в настройках перестанет открываться раздел лицензий",
    "com.google.android.apps.mediashell": "не будет работать трансляция с телефона "
                                          "(Chromecast)",
    "com.android.tv": "на ТВ с антенной пропадут эфирные каналы",
    "com.mitv.tvlock": "если на ТВ стоит родительский PIN-код, он перестанет действовать",
    "com.google.android.tvrecommendations": "главный экран может стать пустым",
}

# Пакеты из проверенных списков по 31 модели Xiaomi (cleanyourtv, free-my-tv).
JUNK.update({
    "com.mitv.shoplugin": "Плагин ТВ-магазина Taobao (Китай)",
    "com.xiaomi.tvqs": "Система качества Xiaomi: отправка отчётов о сбоях",
    "com.xiaomi.tvqs.overseas.y24": "Отправка статистики качества Xiaomi",
    "com.mitv.cloudcontrol": "Удалённая настройка ТВ командами из облака Xiaomi",
    "com.xiaomi.screenrecorder": "Запись экрана для отправки отзывов",
    "com.mitv.tvhome.oemtab": "Рекламный ряд и вкладка Xiaomi в лаунчере Google",
    "com.miui.analytics": "Аналитика Xiaomi (OneTrack)",
    "com.duokan.videodaily": "Короткие промо-видео с рекламным модулем",
    "com.mitv.screensaver": "Заставка Xiaomi с рекламным контентом",
    "com.xiaomi.mitv.hyper.screensaver": "Рекламная заставка HyperOS",
    "com.android.smspush": "Push-сообщения через SMS (на ТВ не нужны)",
    "com.xiaomi.mitv.csi": "Опросы удовлетворённости «помощника после продаж»",
    "tv.alphonso.alphonso_eula": "Alphonso: распознаёт, что вы смотрите, для рекламы",
    "co.sensara.tv.mitv": "Рекламный ТВ-гид Sensara",
    "com.glance.tv": "Новости и реклама Glance",
    "com.gitvdemo.video": "Демо-ролик GITV",
    "com.mitv.download.service": "Загрузчик контента PatchWall",
    "com.miui.misightservice": "Удалённая диагностика и выгрузка логов MiSight",
    "com.xiaomi.mitv.debug": "Сбор логов Xiaomi",
    "com.google.android.syncadapters.contacts": "Синхронизация контактов Google",
})
APPS.update({
    "com.xiaomi.gamecenter.sdk.service.mibox": "Модуль игрового центра Xiaomi",
    "com.xiaomi.mitv.handbook": "Руководство пользователя Xiaomi",
    "com.xiaomi.mitv.calendar": "Календарь Xiaomi",
    "com.xiaomi.mitv.karaoke.service": "Караоке Xiaomi",
    "com.xiaomi.mitv.healthdiagnosis": "Самодиагностика ТВ",
    "com.mitv.alarmcenter": "Будильники и напоминания Xiaomi",
    "com.xiaomi.mitv.health": "Mi Health",
    "com.xiaomi.mitv.tvvideocall": "Видеозвонки MiTime",
    "com.xiaomi.mitv.light": "Световые эффекты Xiaomi",
    "com.xiaomi.aitranslate": "ИИ-перевод субтитров (занимает ~117 МБ памяти)",
    "com.mitv.mivideoplayer": "Mi Video (китайский стриминг)",
    "com.google.android.youtube.tvkids": "YouTube Kids",
    "com.google.android.apps.tachyon": "Google Duo",
    "com.tcl.browser": "Предустановленный браузер",
    "com.emotn.browser": "Предустановленный браузер Emotn",
    "com.android.camera2": "Камера Android",
    "com.android.gallery3d": "Галерея Android",
    "com.netflix.tokenmanager": "Токен входа в Netflix",
    "com.dazn": "DAZN",
    "com.wbd.hbomax": "HBO Max",
    "com.wbd.stream": "Max",
    "com.apple.atve.androidtv.appletv": "Apple TV",
    "com.graymatrix.did": "ZEE5",
    "com.zee5.xiaomiTV": "ZEE5",
    "com.sonyliv": "SonyLIV",
    "com.xiaomitv.sonyliv": "SonyLIV",
    "com.newtv.cboxtv": "CCTV NewTV (Китай)",
    "com.jio.media.stb.ondemand": "JioCinema / JioTV (Индия)",
    "com.mxtech.videoplayer.television": "MX Player",
    "com.formulaone.production": "F1 TV",
    "com.fancode.tv": "FanCode (Индия)",
    "com.suntv.sunnxt.mitv": "Sun NXT (Индия)",
    "com.eros.mitv": "Eros Now (Индия)",
    "com.discoveryplus.mitv": "discovery+",
    "com.ddnational.prasarbharati": "DD National (Индия)",
    "net.aljazeera.english": "Al Jazeera",
    "com.aha.mitv": "aha (старая копия)",
})
FEATURES.update({
    "com.xiaomi.mitv.smartpanel": "Панель по долгому нажатию Menu",
    "com.google.android.tv": "Live Channels (эфирные каналы Google)",
    "com.xiaomi.amazon.alexa": "Связка с Amazon Alexa",
    "com.xiaomi.mi_connect_service": "Mi Connect: связь с телефоном Xiaomi",
    "com.xiaomi.wakeupservice": "Фраза пробуждения китайского голосового помощника",
    "com.xiaomi.mico.mqtt.service.application.tv": "Связь с колонкой Xiao AI",
    "com.duokan.airkan.tvbox": "Приём трансляции DLNA (AirKan)",
    "com.xiaomi.miplay": "MiPlay: трансляция с телефонов Xiaomi",
    "com.xiaomi.eetv.litehome": "Второй домашний экран («офисный режим»)",
    "com.xiaomi.account": "Аккаунт Xiaomi",
    "com.xiaomi.account.auth": "Вход в аккаунт Xiaomi",
    "com.mipay.wallet.tv": "Платежи Xiaomi (Китай)",
    "com.xiaomi.mitv.pay": "Платежи Xiaomi",
    "com.xiaomi.mibox.lockscreen": "Детский режим и блокировка",
    "com.miui.hybrid.tv": "Среда мини-приложений Xiaomi",
    "com.mitv.upgrader": "Обновление прошивки Xiaomi",
    "com.mitv.ABUpdateStatus": "Состояние обновления прошивки",
    "com.mitv.toolhouse": "Утилиты Xiaomi (Mi Home, очистка)",
    "com.xiaomi.tvqs.overseas": "Быстрые настройки или аналитика Xiaomi (источники расходятся)",
    "com.android.adservices.api": "Рекламная персонализация Android (Privacy Sandbox)",
    "com.android.ondevicepersonalization.services": "Персонализация рекламы на устройстве",
    "com.android.federatedcompute.services": "Федеративное обучение (персонализация)",
})
CAUTION.update({
    "com.xiaomi.mitv.smartpanel": "на некоторых моделях (MiTV-ASTR0, MFTR0) через неё "
                                 "переключаются источники, без неё не работает кнопка Menu",
    "com.google.android.tv": "на ТВ с антенной пропадут эфирные каналы",
    "com.xiaomi.wakeupservice": "перестанет откликаться китайский голосовой помощник",
    "com.xiaomi.eetv.litehome": "это второй домашний экран",
    "com.xiaomi.account": "нужен для платного контента и покупок Xiaomi",
    "com.xiaomi.account.auth": "нужен для платного контента и покупок Xiaomi",
    "com.mipay.wallet.tv": "перестанут работать покупки через Xiaomi",
    "com.xiaomi.mitv.pay": "перестанут работать покупки через Xiaomi",
    "com.xiaomi.mibox.lockscreen": "если стоит детский режим или PIN-код, он перестанет действовать",
    "com.miui.hybrid.tv": "могут перестать открываться мини-приложения Xiaomi",
    "com.mitv.upgrader": "перестанут приходить обновления прошивки",
    "com.mitv.ABUpdateStatus": "перестанут приходить обновления прошивки",
    "com.mitv.toolhouse": "мнения расходятся: на 5 моделях отключали, на остальных не трогали",
    "com.xiaomi.tvqs.overseas": "в одних списках это панель быстрых настроек, в других "
                                "отправка аналитики; после отключения проверьте быстрые настройки",
    "com.android.adservices.api": "модуль системы Android, отключали только на двух моделях",
    "com.android.ondevicepersonalization.services": "модуль системы Android, отключали "
                                                    "только на двух моделях",
    "com.android.federatedcompute.services": "модуль системы Android, отключали только на "
                                             "двух моделях",
    "com.netflix.tokenmanager": "нужен для входа в Netflix",
    "com.netflix.ninja": "на некоторых моделях прошивка включает Netflix обратно при загрузке",
    "com.xiaomi.mitv.mediaexplorer": "через него открываются фото и видео с флешки",
    "com.mitv.videoplayer": "через него открываются видео с флешки и Mi Cast",
})

FEATURES.update({
    "com.xiaomi.wfdsinkhelperservice": "Приём трансляции экрана (Miracast)",
    "com.mitv.milinkservice": "Mi Cast и управление с телефона (приложение Mi Remote)",
    "com.xiaomi.mitv.smartshare": "Mi Cast, трансляция с телефона",
})
APPS.update({
    "com.xiaomi.mitv.manualhelp": "Руководство пользователя Xiaomi",
})

# Не трогать ни при каких условиях: что пакет делает по данным сообщества.
KEEP = {
    "com.mitv.livetv": "Live TV: через него работает переключение входов (HDMI, антенна)",
    "com.mitv.livetv.ci_mediatek": "Live TV для MediaTek: входы HDMI и антенна",
    "mitv.service": "основная системная служба Xiaomi",
    "com.mitv.overseaservice": "служба глобальной прошивки Xiaomi, кнопка Netflix на пульте",
    "com.mi.bluetooth": "сопряжение пульта",
    "com.xiaomi.android.tvsetup.partnercustomizer": "кнопки Netflix и Mi на пульте",
    "com.duokan.factorytest": "заводское тестовое меню Xiaomi, не мешает",
    "com.mediatek.tv.agent": "питание, таймеры и кнопки пульта (MediaTek)",
    "com.mediatek.hotkey.dispatcher": "кнопки пульта, в том числе выбор источника",
    "com.mediatek.wwtv.tvcenter": "Live TV MediaTek: через него идёт картинка с HDMI",
    "com.xiaomi.mitv.tvplayer": "Live TV и входы HDMI",
    "com.mstar.netflixobserver": "кнопка Netflix на пульте",
    "com.google.android.tungsten.setupwraith": "мастер настройки: сопряжение пульта и "
                                               "сохранённая сеть Wi-Fi",
}

# Описания системных пакетов, которые встречаются, но в каталог не входят.
DESCRIPTIONS = {
    "com.dolby.android.audio.service": "обработка звука Dolby",
    "com.android.vpndialogs": "окно разрешения для VPN-приложений",
    "com.android.pacprocessor": "автонастройка прокси (PAC)",
    "com.android.captiveportallogin": "вход в Wi-Fi сети с авторизацией через браузер",
    "com.android.companiondevicemanager": "сопряжение Bluetooth-устройств",
    "com.android.backupconfirm": "подтверждение резервного копирования",
    "com.android.sharedstoragebackup": "резервное копирование общей памяти",
    "com.android.settings.intelligence": "поиск в настройках",
    "com.android.soundpicker": "выбор звуков",
    "com.android.se": "защищённый элемент (Secure Element)",
    "com.android.statementservice": "проверка ссылок приложений",
    "com.android.wallpaperbackup": "резервная копия обоев",
    "com.android.dynsystem": "установка тестовых образов системы",
    "com.android.localtransport": "служба резервного копирования",
    "com.android.certinstaller": "установка сертификатов",
    "com.android.proxyhandler": "работа через прокси",
    "com.android.keychain": "хранилище ключей и сертификатов",
    "com.android.externalstorage": "доступ к флешкам и памяти",
    "com.android.inputdevices": "раскладки клавиатур и пультов",
    "com.android.location.fused": "определение местоположения; отключение "
                                  "вызывает циклическую перезагрузку",
    "com.android.vending": "Google Play Маркет",
    "com.google.android.gms": "сервисы Google Play",
    "com.google.android.gsf": "сервисы Google",
    "com.google.android.tts": "синтез речи Google",
    "com.google.android.katniss": "голосовой поиск Google",
    "com.google.android.tv.assistant": "Google Ассистент",
    "com.google.android.tungsten.setupwraith": "мастер первоначальной настройки",
    "com.google.android.partnersetup": "настройки производителя для сервисов Google",
    "com.google.android.onetimeinitializer": "первичная настройка Google",
    "com.google.android.packageinstaller": "установка приложений",
    "com.google.android.permissioncontroller": "разрешения приложений",
    "com.google.android.webview": "встроенный браузерный движок",
    "com.google.android.inputmethod.latin": "экранная клавиатура",
    "com.google.android.tv.frameworkpackagestubs": "заглушки системных функций",
    "com.mediatek.tvinput": "входы HDMI и антенна (MediaTek)",
    "com.mediatek.tv.service": "основная ТВ-служба MediaTek",
    "com.mediatek.tv.agent": "ТВ-служба MediaTek",
    "com.mediatek.network": "сетевая служба MediaTek",
    "com.mediatek.wwtv.setupwizard": "мастер настройки каналов MediaTek",
    "com.mediatek.wwtv.webview": "встроенный браузер MediaTek",
    "com.mediatek.android.boot.appsplashscreen": "заставка при загрузке",
    "mediatek.factorymenu.ui": "заводское меню MediaTek",
    "com.mstar.android.tv.disclaimercustomization": "экран соглашения при настройке",
    "fusion.android.tv.demo": "демо-режим для магазинов (не подтверждено)",
    "com.mitv.toolhouse": "служебный пакет Xiaomi, назначение не описано",
    "com.mitv.upgrader": "служебный пакет Xiaomi, похоже на обновление (не подтверждено)",
    "com.xiaomi.mitv.scenemode": "режимы изображения Xiaomi (по названию, не подтверждено)",
}

# ---------------------------------------------------------------------------
# TCL (по 62 спискам cleanyourtv и защитному списку free-my-tv)
# ---------------------------------------------------------------------------

JUNK.update({
    "com.tcl.esticker": "Наклейки демо-режима магазина (энергоэтикетка)",
    "com.tcl.messagebox": "Промо-сообщения TCL",
    "com.tcl.logkit": "Сбор и отправка логов TCL",
    "com.tcl.bi": "Аналитика TCL (BI, Firebase)",
    "com.tcl.interactive": "Фоновая аналитика TCL (TIAS)",
    "com.tcl.exhibit": "Демо-режим магазина",
    "com.tcl.hotelmenu": "Гостиничный режим",
    "com.tcl.overseasappshow": "Витрина рекламируемых приложений",
    "com.tcl.waterfall.overseas": "Лента контента TCL Channel",
    "com.tcl.bootadservice": "Полноэкранная реклама при включении",
    "com.tcl.smartlink.core": "Тихая установка приложений TCL",
    "com.esaba.downloader": "Фоновая загрузка приложений и контента",
    "com.tcl.cyberui": "Контент-сервис TCL",
    "com.tcl.appreciate.art": "Заставка-галерея с платной подпиской",
    "com.tcl.tvweishi": "Очистка «TV Guard»",
    "com.tcl.tv.tclhome_passive": "Контент TCL на главном экране при загрузке",
    "com.tcl.guard": "Менеджер приложений и очистка TCL",
    "com.tcl.xian.StartandroidService": "Фоновая служба отчётов TCL",
})
APPS.update({
    "com.tcl.channelplus": "TCL Channel: бесплатные каналы с рекламой",
    "com.tcl.tv.plus": "TCL TV+: бесплатные каналы",
    "com.tcl.ocean.instructions": "Руководство пользователя TCL",
    "com.tcl.repairguide": "Справка по ремонту и самодиагностика",
    "com.tcl.playskill": "Советы по использованию",
    "com.tcl.copydatatotv": "Перенос данных с телефона на ТВ",
    "com.tcl.notereminder": "Заметки и напоминания",
    "com.tcl.browser": "Браузер TCL BrowseHere",
    "com.tcl.appmarket2": "Магазин приложений TCL",
    "com.tcl.ffkaraoke": "Караоке",
    "com.tcl.ffeducation": "Детский и обучающий контент",
    "com.tcl.ui_mediaCenter": "Медиацентр: фото и видео с флешки и DLNA",
    "com.tcl.gallery": "Галерея TCL",
    "com.tcl.audioplayer": "Аудиоплеер TCL",
    "com.tcl.imageplayer": "Просмотр фото TCL",
    "com.tcl.videoplayer": "Видеоплеер TCL",
    "com.tcl.magiconnectfree": "Реклама приложения MagiConnect (T-Cast)",
    "com.google.android.apps.tv.dreamx": "Заставка Google TV Ambient (с промо)",
    "com.tubitv": "Tubi",
    "tv.twitch.android.app": "Twitch",
    "tv.wuaki.apptv": "Rakuten TV",
    "au.com.stan.and": "Stan (Австралия)",
    "air.ITVMobilePlayer": "ITVX (Великобритания)",
    "com.channel5.my5": "My5 (Великобритания)",
    "br.com.claro.now.smarttvclient": "Claro TV+ (Бразилия)",
    "com.mercadolibre.android.mplay_tv": "Mercado Play",
    "com.rma.speedtesttv": "Speedtest",
    "com.google.android.youtube.tvunplugged": "YouTube TV",
})
FEATURES.update({
    "com.tcl.ttvs": "Служба TCL: отслеживание просмотров Samba TV, аналитика, обновления",
    "com.tcl.smartalexa": "Связка с Amazon Alexa",
    "com.tcl.usercenter": "Аккаунт TCL",
    "com.tcl.dashboard": "Панель «TCL Home»: промо и подарки",
    "com.tcl.partnercustomizer": "Промо-плитки T-Channel на главном экране",
    "com.tcl.t_solo": "T-Solo: звук в Bluetooth-наушники",
    "com.tcl.UpdatePeripheral": "Обновление прошивки саундбара TCL",
    "com.tcl.gamebar": "Игровая панель и режим VRR",
    "com.tcl.hearaid": "Проверка слуха и подстройка громкости",
    "com.tcl.miracast": "Приём трансляции экрана (Miracast)",
    "com.tcl.airplay2": "AirPlay",
    "com.tcl.MultiScreenInteraction_TV": "MagiConnect: связь с телефоном и трансляция",
    "com.tcl.versionUpdateApp": "Обновление прошивки TCL",
    "com.tcl.useragreement": "Экраны соглашений TCL",
    "com.tcl.android.webview": "Встроенный браузерный движок TCL",
    "com.tcl.keyhelp": "Подсказки по кнопкам пульта",
    "com.tcl.eva": "Голосовой слой TCL",
})
CAUTION.update({
    "com.tcl.ttvs": "на C7K и других G08 это ещё и обновление прошивки: без него обновления "
                    "не приходят (включите его, чтобы проверить обновление); на части старых "
                    "моделей free-my-tv держит его под защитой",
    "com.tcl.tv.tclhome_passive": "мнения расходятся: в 36 списках отключали, free-my-tv "
                                  "держит под защитой",
    "com.tcl.guard": "мнения расходятся: в 38 списках отключали, free-my-tv держит под защитой",
    "com.tcl.dashboard": "мнения расходятся: в одних списках это реклама, в других панель, "
                         "которую нужно оставить",
    "com.tcl.partnercustomizer": "мнения расходятся: в 40 списках отключали, free-my-tv "
                                 "держит под защитой",
    "com.tcl.gamebar": "нужна для игрового режима и VRR с приставками",
    "com.tcl.hearaid": "мнения расходятся: на части моделей её оставляли",
    "com.tcl.usercenter": "нужен для аккаунта TCL; на некоторых прошивках включается обратно",
    "com.tcl.UpdatePeripheral": "перестанет обновляться прошивка саундбара TCL",
    "com.tcl.versionUpdateApp": "перестанут приходить обновления прошивки",
    "com.tcl.useragreement": "мнения расходятся: часть владельцев оставляла",
    "com.tcl.android.webview": "мнения расходятся; основным браузерным движком остаётся Google",
    "com.tcl.keyhelp": "мнения расходятся: на части моделей её оставляли",
    "com.tcl.eva": "мнения расходятся: голос работает через Google, но на части моделей "
                   "её оставляли",
    "com.tcl.miracast": "перестанет работать трансляция экрана на ТВ",
    "com.tcl.airplay2": "перестанет работать AirPlay с iPhone и Mac",
    "com.tcl.MultiScreenInteraction_TV": "перестанут работать MagiConnect и T-Cast",
    "com.tcl.ui_mediaCenter": "через него открываются фото и видео с флешки",
    "com.tcl.gallery": "через неё открываются фото с флешки",
    "com.tcl.videoplayer": "через него открываются видео с флешки",
    "com.google.android.apps.tv.dreamx": "сначала выберите другую заставку в настройках",
    "com.tcl.xian.StartandroidService": "мнения расходятся: на части моделей её оставляли",
})
KEEP.update({
    "com.tcl.tv": "Live TV и входы HDMI",
    "com.tcl.tvinput": "входы HDMI, AV и антенна",
    "com.tcl.tvpassthrough": "передача сигнала с HDMI",
    "com.tcl.sourcemananger": "переключение источников",
    "com.tcl.suspension": "панель источников, которую открывает кнопка Input на пульте",
    "com.tcl.autopair": "сопряжение пульта",
    "com.tcl.tcl_bt_rcu_service": "Bluetooth-пульт",
    "com.tcl.keycustomfunctionservice": "кнопки пульта",
    "com.tcl.globalkeyoverlay": "кнопки пульта",
    "com.tcl.systemserver": "системная служба TCL",
    "com.tcl.system.server": "системная служба TCL",
    "com.tcl.systemui.plugin": "системный интерфейс TCL",
    "com.tcl.providers.config": "настройки системы TCL",
    "com.tcl.initsetup": "первичная настройка TCL",
    "com.tcl.factory.view": "заводское меню TCL: не отключать и не запускать",
    "com.tcl.settings": "настройки TCL",
    "com.tcl.micmanager": "микрофон пульта",
    "com.tcl.common.shortcutmenu": "быстрое меню TCL",
    "com.tcl.framework.custom": "системная часть TCL",
    "com.tvos": "системная часть TCL, назначение не выяснено",
    "com.tpa.kb": "держит разрешения Live TV и каналов TCL, назначение не выяснено",
    "tv.mopa.ginga": "Ginga: эфирное ТВ в Бразилии",
})
# Пакеты, которые проверены по источникам и не должны блокироваться общими
# шаблонами защиты (у Xiaomi partnercustomizer нужен пульту, у TCL это промо).
REVIEWED = {"com.tcl.partnercustomizer", "com.tcl.android.webview"}

# ---------------------------------------------------------------------------
# База устройств
# ---------------------------------------------------------------------------

try:
    import device_db
    MODEL_DB = device_db.MODELS
except ImportError:
    MODEL_DB = {}

# Какие модели каждой марки отключали каждый пакет: COMMUNITY[марка][пакет].
COMMUNITY = {}
for _key, _m in MODEL_DB.items():
    for _p in _m["disabled"]:
        COMMUNITY.setdefault(_m["brand"], {}).setdefault(_p, []).append(_key)


def detect_brand(text):
    t = text.lower()
    if "xiaomi" in t or "redmi" in t:
        return "Xiaomi"
    if "tcl" in t:
        return "TCL"
    return ""


def find_models(ctx):
    """Подходящие записи базы. -> (точная модель или None, списки той же платформы).

    Xiaomi различаются по ro.product.model. У TCL модель всегда «Smart TV Pro»,
    поэтому берём все списки той же платформы (ro.product.device, product, Android).
    """
    brand, android = ctx.get("brand"), ctx.get("android")
    if brand == "Xiaomi":
        for field, value in (("ids", ctx.get("model_id")), ("codename", ctx.get("codename"))):
            if not value:
                continue
            hits = [k for k, m in MODEL_DB.items() if m["brand"] == "Xiaomi"
                    and (value in m["ids"] if field == "ids" else m["codename"] == value)]
            if hits:
                same = [k for k in hits if MODEL_DB[k]["android"] == android]
                key = (same or hits)[0]
                return key, [key]
        return None, []
    if brand == "TCL":
        device = ctx.get("codename") or ""
        product = (ctx.get("product") or "").split("_")[0]
        cands = [k for k, m in MODEL_DB.items() if m["brand"] == "TCL"
                 and device and (m["codename"] == device or m["codename"] == product)]
        same = [k for k in cands if MODEL_DB[k]["android"] == android] or cands
        # Одна платформа (BeyondTV4) бывает и на Android TV, и на Google TV.
        kind = "Google TV" if ctx.get("google_tv") else "Android TV"
        same = [k for k in same if MODEL_DB[k]["firmware"] == kind] or same
        if product:
            # Списки без указанного product тоже подходят: он просто не записан.
            exact = [k for k in same if MODEL_DB[k]["product"].split("_")[0] in (product, "")]
            same = exact or same
        return None, same
    return None, []


def community_note(pkg, ctx):
    """Что о пакете известно по спискам сообщества. -> (текст, нужно предупредить)."""
    brand = ctx.get("brand")
    here = ctx.get("db_lists") or []
    if here:
        off = [k for k in here if pkg in MODEL_DB[k]["disabled"]]
        kept = [k for k in here if pkg in MODEL_DB[k]["keep"]]
        where = ("на вашей модели" if ctx.get("db_model") else
                 f"на вашей платформе {ctx.get('platform')}")
        if kept and not off:
            return f"{where} этот пакет оставляли намеренно", True
        if kept and off:
            return (f"{where} мнения расходятся: отключали в {len(off)}, "
                    f"оставляли в {len(kept)} списках"), True
        if off:
            if ctx.get("db_model"):
                own = " (по личному выбору)" if pkg in MODEL_DB[here[0]]["personal"] else ""
                return f"★ отключали на вашей модели{own}", False
            return f"★ отключали {where}: в {len(off)} из {len(here)} списков", False
    models = COMMUNITY.get(brand, {}).get(pkg, [])
    if models:
        total = sum(m["brand"] == brand for m in MODEL_DB.values())
        return f"отключали на {len(models)} из {total} моделей {brand}", False
    return "", False


# Пакеты, которые сами ставят рекламируемые приложения после обновлений.
AUTOINSTALL = re.compile(r"^android\.autoinstalls\.config\.")

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
    # Звук (Dolby, DTS), VPN, прокси, вход в Wi-Fi сети, сопряжение устройств.
    r"dolby|dts|audio|vpndialogs|pacprocessor|captiveportal|companiondevice",
    # Голосовой поиск: на Android TV это katniss, на Google TV и в прошивках
    # Xiaomi свои пакеты, поэтому защищаем всё, что похоже на голос и поиск.
    r"katniss|voice|speech|pumpkin|hotword|assistant|search|\.tts$|"
    r"tvsearch|googlequicksearchbox|velvet",
)]

VENDOR_HINT = re.compile(r"xiaomi|mitv|miui|^com\.mi\.|^com\.duokan\.|^com\.tcl\.|"
                         r"^com\.tpa\.|^com\.tvos")

# Приложения, которые работают без запуска вручную: трансляция, фон.
BACKGROUND_HINT = re.compile(r"cast|miracast|airplay|airscreen|dlna|mirror|"
                             r"share|remote|vpn|wallpaper|dream|saver|sync")

# FallbackHome из «Настроек» показывается только пока система загружается.
# Если, кроме него, лаунчеров не осталось, ТВ висит на «Android запускается».
FALLBACK_HOME = {"android", "com.android.settings", "com.android.tv.settings"}

# Служебные пакеты, которые тоже объявляют себя «домашним экраном», но
# лаунчерами не являются: заводской тест Xiaomi (com.duokan.factorytest),
# мастер настройки, демо-режим магазина. Их нельзя считать запасным
# лаунчером и нельзя предлагать сделать домашним.
NOT_LAUNCHER = re.compile(r"factory|test|setup|provision|demo|retail", re.I)

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
        print("Телевизор отклонил подключение: включите на нём «Отладку по сети». "
              "На Android 11+ (например, TCL C7K) вместо неё бывает только «Беспроводная "
              "отладка»: нужна разовая привязка по коду («🔑 Сопряжение по коду»).")
    else:
        print("Проверьте IP и что компьютер и ТВ в одной сети.")
    return False


# ---------------------------------------------------------------------------
# Беспроводная отладка Android 11+: сопряжение по коду
# ---------------------------------------------------------------------------

def mdns_services():
    """ТВ, которые объявляют беспроводную отладку. -> {ip: {"connect": порт, "pair": порт}}."""
    found = {}
    for line in run([ADB, "mdns", "services"], timeout=15)[1].splitlines():
        m = re.search(r"(\d+\.\d+\.\d+\.\d+):(\d+)", line)
        if not m:
            continue
        kind = ("pair" if "_adb-tls-pairing" in line else
                "connect" if "_adb-tls-connect" in line else None)
        if kind:
            found.setdefault(m.group(1), {})[kind] = int(m.group(2))
    return found


def pair_and_connect(ip, pair_port, code, connect_port=None, progress=print):
    """Сопряжение по коду с экрана ТВ, подключение и перевод ТВ на порт 5555.

    После `adb tcpip 5555` ТВ дальше подключается просто по IP (до перезагрузки).
    Возвращает итоговый адрес или None.
    """
    global SERIAL, CONNECT_ADDR
    progress(f"Сопряжение с {ip}:{pair_port}...")
    out = run([ADB, "pair", f"{ip}:{pair_port}", code], timeout=40)[1]
    if "success" not in out.lower():
        progress(f"Сопряжение не удалось: {out or 'нет ответа'}. Проверьте код и порт: "
                 "они меняются при каждом открытии окна «Подключение с кодом».")
        return None
    progress("Сопряжение выполнено.")
    if not connect_port:
        # Порт подключения ТВ объявляет в сети сам; иначе его видно на экране
        # «Беспроводная отладка» рядом с IP.
        for _ in range(5):
            connect_port = mdns_services().get(ip, {}).get("connect")
            if connect_port:
                break
            time.sleep(1)
    if not connect_port:
        progress("Не нашёл порт подключения: введите его с экрана «Беспроводная отладка» "
                 "(число после двоеточия в строке «IP-адрес и порт»).")
        return None
    addr = f"{ip}:{connect_port}"
    out = adb_connect(addr)
    if "connected" not in out:
        progress(f"Не удалось подключиться к {addr}: {out or 'нет ответа'}")
        return None
    SERIAL = CONNECT_ADDR = addr
    # Постоянный порт: дальше хватит IP, без кода (держится до перезагрузки ТВ).
    run([ADB, "-s", addr, "tcpip", str(ADB_PORT)], timeout=20)
    time.sleep(2)
    fixed = f"{ip}:{ADB_PORT}"
    if "connected" in adb_connect(fixed):
        run([ADB, "disconnect", addr], timeout=10)
        SERIAL = CONNECT_ADDR = fixed
        progress(f"Подключено: {fixed}. До перезагрузки ТВ можно подключаться просто по IP.")
        return fixed
    progress(f"Подключено: {addr}. Порт 5555 не включился, после перезагрузки ТВ "
             "сопряжение по коду понадобится снова.")
    return addr


# ---------------------------------------------------------------------------
# Поиск ТВ в локальной сети
# ---------------------------------------------------------------------------

ADB_PORT = 5555
ATV_REMOTE_PORT = 6466  # служба пульта Android TV: есть только у ТВ и приставок
CAST_PORT = 8009        # Chromecast: ТВ, приставки, но и колонки Google


def read_last_ip():
    try:
        with open(os.path.join(HERE, "last_ip.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def local_networks(extra_ips=()):
    """Домашние подсети /24, в которых есть этот компьютер (и прошлый IP ТВ)."""
    ips = set()
    try:
        # Адрес, через который компьютер ходит наружу; пакет не отправляется.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as u:
            u.connect(("192.0.2.1", 9))
            ips.add(u.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    ips.update(ip.split(":")[0] for ip in extra_ips if ip)
    nets = []
    for ip in sorted(ips):
        try:
            addr = ipaddress.IPv4Address(ip)
        except ValueError:
            continue
        if addr.is_private and not addr.is_loopback and not addr.is_link_local:
            net = ipaddress.IPv4Network(f"{ip}/24", strict=False)
            if net not in nets:
                nets.append(net)
    return nets[:4]


def port_open(ip, port, timeout=0.6):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_adb(ip):
    """Подключается к ТВ по ADB и узнаёт модель. Не трогает текущее SERIAL."""
    addr = f"{ip}:{ADB_PORT}"
    was_connected = addr in adb_devices()
    out = adb_connect(addr)
    info = {"state": "нет ответа"}
    if "connected" not in out:
        return info
    for _ in range(3):
        state = adb_devices().get(addr, "")
        if state in ("device", "unauthorized"):
            break
        time.sleep(0.5)
    if state == "unauthorized":
        info["state"] = "нужно разрешить отладку на ТВ"
    elif state == "device":
        def q(cmd):
            return run([ADB, "-s", addr, "shell", cmd], timeout=10)[1].strip()
        info["state"] = "готов к подключению"
        info["model"] = " ".join(filter(None, [q("getprop ro.product.manufacturer"),
                                               q("getprop ro.product.model")]))
        info["android"] = q("getprop ro.build.version.release")
        features = q("pm list features")
        info["is_tv"] = ("android.software.leanback" in features
                         or "tv" in q("getprop ro.build.characteristics"))
    if not was_connected:
        run([ADB, "disconnect", addr], timeout=10)
    return info


def scan_network(extra_ips=(), progress=print):
    """Ищет Android TV и приставки. -> [{ip, name, adb, remote, cast, state, model, ...}]."""
    nets = local_networks(extra_ips)
    if not nets:
        progress("Не удалось определить домашнюю сеть компьютера.")
        return []
    progress("Проверяю сети: " + ", ".join(str(n) for n in nets))
    hosts = [str(h) for n in nets for h in n.hosts()]
    ports = (ADB_PORT, ATV_REMOTE_PORT, CAST_PORT)
    found = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=128) as pool:
        futures = {pool.submit(port_open, h, p): (h, p) for h in hosts for p in ports}
        for fut in concurrent.futures.as_completed(futures):
            if fut.result():
                h, p = futures[fut]
                found.setdefault(h, set()).add(p)

    # ТВ с беспроводной отладкой (Android 11+) слушают случайный порт и
    # объявляют себя в сети: так их видно, даже если 5555 закрыт.
    tls = mdns_services()
    for ip in tls:
        found.setdefault(ip, set()).add(ATV_REMOTE_PORT)

    devices = []
    for ip in sorted(found, key=lambda x: tuple(map(int, x.split(".")))):
        open_ports = found[ip]
        # Только то, что похоже на ТВ: ADB по сети или служба пульта Android TV.
        if ADB_PORT not in open_ports and ATV_REMOTE_PORT not in open_ports:
            continue
        try:
            name = socket.gethostbyaddr(ip)[0].split(".")[0]
        except OSError:
            name = ""
        dev = {"ip": ip, "name": name, "adb": ADB_PORT in open_ports,
               "remote": ATV_REMOTE_PORT in open_ports, "cast": CAST_PORT in open_ports,
               "model": "", "android": "", "is_tv": None}
        dev["tls"] = tls.get(ip, {})
        if dev["adb"]:
            progress(f"Опрашиваю {ip} по ADB...")
            dev.update(probe_adb(ip))
        elif dev["tls"]:
            dev["state"] = "беспроводная отладка: нужно сопряжение по коду"
        else:
            dev["state"] = "отладка по сети выключена"
        # Устройство с ADB, которое само сказало, что оно не ТВ (телефон), скрываем.
        if dev["is_tv"] is False and not dev["remote"]:
            continue
        devices.append(dev)
    progress(f"Найдено устройств: {len(devices)}.")
    return devices


def print_devices(devices):
    for i, d in enumerate(devices, 1):
        what = d["model"] or d["name"] or "Android TV"
        print(f"  {i}. {d['ip']:<15} {what:<28} {d['state']}")


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
            ip = input(f"IP телевизора{hint}, s — найти ТВ в сети, q — выход: ").strip()
        except EOFError:
            ip = "q"
        if ip.lower() in ("q", "й"):
            sys.exit(0)
        if ip.lower() in ("s", "ы"):
            devices = scan_network([last])
            print_devices(devices)
            if devices:
                n = input("Номер устройства (Enter — ввести IP вручную): ").strip()
                if n.isdigit() and 1 <= int(n) <= len(devices):
                    ip = devices[int(n) - 1]["ip"]
                    with open(last_file, "w", encoding="utf-8") as f:
                        f.write(ip)
                    return ip
            continue
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
            if c.split("/")[0] not in FALLBACK_HOME
            and not NOT_LAUNCHER.search(c.split("/")[0])]


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
    ctx["model_id"] = sh("getprop ro.product.model").strip()
    ctx["codename"] = sh("getprop ro.product.device").strip()
    ctx["product"] = sh("getprop ro.product.name").strip()
    ctx["android"] = sh("getprop ro.build.version.release").strip().split(".")[0]
    ctx["brand"] = detect_brand(sh("getprop ro.product.manufacturer") + " " +
                                sh("getprop ro.product.brand"))
    ctx["google_tv"] = "com.google.android.apps.tv.launcherx" in everything
    ctx["db_model"], ctx["db_lists"] = find_models(ctx)
    ctx["platform"] = (ctx["codename"] + (f" / {ctx['product']}" if ctx["product"] else "")
                       + f", Android {ctx['android']}")
    # На Google TV мастер настройки объявляет себя домашним экраном: без штатного
    # лаунчера система открывает его экран восстановления, а не новый лаунчер.
    ctx["setup_home"] = any(re.search(r"setupwraith|RecoveryActivity", c)
                            for c in full_components(query("HOME")))
    return ctx


def model_summary(ctx):
    brand = ctx.get("brand")
    key, lists = ctx.get("db_model"), ctx.get("db_lists") or []
    if key:
        m = MODEL_DB[key]
        return (f"Модель есть в базе: {m['title']}. Отмечено ★ то, что отключали "
                f"именно на ней ({len(m['disabled'])} пакетов).")
    if lists:
        names = ", ".join(sorted({re.split(r" \(|,| —", MODEL_DB[k]["title"])[0]
                                  for k in lists}))
        return (f"Платформа {ctx.get('platform')} есть в базе: {len(lists)} списков "
                f"({names}). Отмечено ★ то, что на ней отключали.")
    total = sum(m["brand"] == brand for m in MODEL_DB.values())
    if total:
        return (f"Модели {ctx.get('model_id') or '?'} ({ctx.get('platform')}) нет в "
                f"базе: рекомендации по {total} моделям {brand}.")
    return "Этой марки нет в базе: рекомендации только по общему каталогу."


def is_protected(pkg):
    if AUTOINSTALL.search(pkg) or pkg in REVIEWED:
        return False
    return pkg in KEEP or any(p.search(pkg) for p in PROTECTED)

def describe(pkg):
    for table in (JUNK, APPS, FEATURES, STOCK_LAUNCHERS):
        if pkg in table:
            return table[pkg]
    if pkg in PATCHWALL:
        return "PatchWall, лаунчер Xiaomi"
    if pkg in KEEP:
        return KEEP[pkg][:1].upper() + KEEP[pkg][1:]
    if AUTOINSTALL.search(pkg):
        return "Автоустановка рекламируемых приложений"
    return DESCRIPTIONS.get(pkg, "")



def assess(pkg, ctx):
    """Проверка влияния на загрузку. Возвращает (уровень, причины)."""
    if pkg in KEEP:
        return BLOCK, [KEEP[pkg]]
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
        # Пакеты из каталога сообщество отключало без проблем, остальные — нет.
        if not (pkg in JUNK or pkg in APPS or pkg in FEATURES or AUTOINSTALL.search(pkg)):
            return BLOCK, [f"работает с правами системы ({m.group(1)})"]
        warn(f"работает с правами системы ({m.group(1)}); в списках сообщества "
             "отключается без проблем, но обязательно проверьте загрузку")

    if ctx.get("setup_home") and pkg in STOCK_LAUNCHERS:
        return BLOCK, ["на этой прошивке без штатного лаунчера домашним становится экран "
                       "восстановления мастера настройки: ТВ уходит в перезагрузки, "
                       "на одной модели это закончилось сбросом настроек"]
    if pkg == "com.mitv.tvhome":
        warn("на китайских прошивках и HyperOS система принимает как домашний экран "
             "только лаунчеры из своего списка: без PatchWall может остаться чёрный "
             "экран. Программа проверит, что новый лаунчер принят, и иначе оставит PatchWall")
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
    elif AUTOINSTALL.search(pkg):
        warn("мнения расходятся: в одних списках отключают, в других оставляют")
    note, kept_here = community_note(pkg, ctx)
    if kept_here:
        warn(note)
    elif note:
        reasons.insert(0, note)
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

def device_label(model):
    """Модель ТВ для имени папки бэкапа.

    IP в имени не годится: роутер чаще всего выдаёт телевизору новый адрес.
    """
    name = model or sh("getprop ro.product.model").strip() or "TV"
    # Запрещённые в именах файлов Windows символы и пробелы -> «_».
    return re.sub(r'[<>:"/\\|?*\s]+', "_", name).strip("._") or "TV"


def backup(plan, ctx, model, method=DISABLE):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    label = device_label(model)
    folder = os.path.join(HERE, f"backup_{label}_{stamp}")
    n = 2
    while os.path.exists(folder):  # две операции в одну секунду
        folder = os.path.join(HERE, f"backup_{label}_{stamp}-{n}")
        n += 1
    os.makedirs(folder)
    listfile = os.path.join(folder, "removed.txt")
    serialno = sh("getprop ro.serialno").strip() or "неизвестен"
    with open(listfile, "w", encoding="utf-8") as f:
        f.write(f"# {model}, серийный номер {serialno}, адрес {SERIAL}, {stamp}\n")
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
    booted = reachable = False
    while time.time() < deadline:
        if CONNECT_ADDR:
            adb_connect(CONNECT_ADDR)
        rc, out = adb("shell", "getprop sys.boot_completed", timeout=10)
        if rc == 0:
            reachable = True
        if out.strip() == "1":
            booted = True
            break
        print("  ...ещё загружается" if reachable else "  ...ТВ пока не отвечает")
        time.sleep(5)
    if not reachable:
        # На многих Xiaomi отладка по сети выключается после перезагрузки:
        # это не значит, что ТВ не загрузился. Откатывать вслепую нельзя.
        return None, ("ТВ не ответил по сети. На многих Xiaomi отладка по сети "
                      "выключается после перезагрузки. Посмотрите на экран ТВ: "
                      "если главный экран открылся, всё в порядке. Чтобы "
                      "проверить и при необходимости вернуть пакеты, снова "
                      "включите отладку по сети и нажмите «Подключить»")
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


UNKNOWN_DESC = "неизвестный пакет производителя: трогайте, только если знаете, что это"


def scan(ctx, days, include_patchwall=True, skip=()):
    """Все кандидаты на удаление: [(заголовок, [(пакет, описание, уровень, причины)])]."""
    groups = []
    print(model_summary(ctx))
    seen = set(PATCHWALL) | set(STOCK_LAUNCHERS) | set(skip)
    pw = [p for p in PATCHWALL if p in ctx["installed"]]
    if include_patchwall and pw:
        groups.append(("Лаунчер PatchWall",
                       [(p, "PatchWall, лаунчер Xiaomi. Домашним станет штатный",
                         *assess(p, ctx)) for p in pw]))
    for title, catalog in GROUPS:
        found = [p for p in catalog if p in ctx["installed"]]
        if catalog is JUNK:
            found += sorted(p for p in ctx["installed"] if AUTOINSTALL.search(p))
        seen.update(catalog)
        seen.update(found)
        if found:
            groups.append((title, [(p, describe(p), *assess(p, ctx)) for p in found]))

    print("Анализирую, какие приложения давно не запускались...")
    items = unused_apps(ctx, days, seen)
    if items:
        groups.append((f"Не запускались больше {days} дней или ни разу", items))
        seen.update(p[0] for p in items)

    lists = ctx.get("db_lists") or []
    if lists:
        # Для платформы TCL — то, что отключали хотя бы в трети её списков.
        need = 1 if ctx.get("db_model") else max(1, len(lists) // 3)
        counts = {}
        for k in lists:
            for p in MODEL_DB[k]["disabled"]:
                counts[p] = counts.get(p, 0) + 1
        extra = sorted(p for p, n in counts.items() if n >= need
                       and p in ctx["installed"] and p not in seen and not is_protected(p))
        if extra:
            where = "модели" if ctx.get("db_model") else "платформе"
            groups.append((f"Отключали на вашей {where} (нет в каталоге)",
                           [(p, describe(p) or "без описания", *assess(p, ctx))
                            for p in extra]))
            seen.update(extra)

    unknown = sorted(p for p in ctx["installed"]
                     if VENDOR_HINT.search(p) and p not in seen
                     and not is_protected(p))
    if unknown:
        groups.append((f"Прочие пакеты {ctx.get('brand') or 'производителя'} (не из списка)",
                       [(p, describe(p) or UNKNOWN_DESC, *assess(p, ctx))
                        for p in unknown]))
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
    cur = (ctx["default_home"] or "").split("/")[0]
    accepted = False
    if ctx["new_home"]:
        accepted = set_home(ctx["new_home"])
        if not accepted and cur in plan:
            # Китайские прошивки, HyperOS и Google TV могут игнорировать выбор
            # домашнего экрана. Тогда текущий лаунчер отключать нельзя.
            plan = [p for p in plan if p != cur]
            print(f"  ! Система не приняла {ctx['new_home']} как домашний экран, "
                  f"поэтому {cur} оставлен включённым.")
    removed = []
    for pkg in plan:
        good, note = action(pkg)
        print(f"  {'✔' if good else '✖'} {pkg}" + (f": {note}" if note else ""))
        if good:
            removed.append(pkg)
    print(f"{'Отключено' if method == DISABLE else 'Удалено'}: "
          f"{len(removed)} из {len(plan)}.")
    if removed and ctx["new_home"] and accepted:
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
        known = pkg in JUNK or pkg in APPS or pkg in FEATURES or AUTOINSTALL.search(pkg)
        if not user and not known and level == OK:
            level = WARN
            reasons = ["о назначении этого системного пакета нет проверенных "
                       "сведений; отключайте, только если точно знаете, что это"] + reasons
        apps.append({"pkg": pkg, "user": user, "enabled": pkg not in ctx["disabled"],
                     "desc": describe(pkg),
                     "last": last.get(pkg), "level": level, "reasons": reasons})
    return apps


def home_button_warning(ctx, pkg):
    """На Xiaomi кнопка Home зашита на PatchWall, пока он включён."""
    if pkg in PATCHWALL:
        return None
    if any(p in ctx["installed"] for p in PATCHWALL):
        return ("На Xiaomi кнопка Home на пульте может по-прежнему открывать "
                "PatchWall. Чтобы она открывала новый лаунчер, отключите PatchWall.")
    stock = [p for p in STOCK_LAUNCHERS if p in ctx["installed"] and p != pkg]
    if pkg not in STOCK_LAUNCHERS and stock:
        return ("На некоторых Xiaomi кнопка Home открывает новый лаунчер, только "
                f"когда штатный ({stock[0]}) отключён. Если после нажатия Home "
                "открывается старый экран, отключите штатный лаунчер на вкладке "
                "«Установленные приложения».")
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
# Экран ТВ на компьютере (scrcpy, github.com/Genymobile/scrcpy, Apache 2.0)
# ---------------------------------------------------------------------------

SCREEN_HELP = """Экран ТВ открыт в отдельном окне. Управление:
  стрелки и Enter на клавиатуре — как на пульте; можно печатать текст;
  щелчок мышью — выбрать, правая кнопка — «Назад», средняя (колесо) — «Домой»;
  Alt+H — «Домой», Alt+B — «Назад», Alt+M — меню, Alt+↑/↓ — громкость.
Платное видео (Netflix, YouTube и т. п.), HDMI-входы и антенна в окне будут
чёрными: это защита от копирования в Android, на телевизоре всё показывается."""


def find_scrcpy():
    """Путь к scrcpy: рядом с программой, из exe (копируется рядом) или в PATH."""
    name = "scrcpy.exe" if os.name == "nt" else "scrcpy"
    local = os.path.join(HERE, "scrcpy", name)
    bundled = os.path.join(getattr(sys, "_MEIPASS", ""), "scrcpy")
    if not os.path.isfile(local) and os.path.isfile(os.path.join(bundled, name)):
        # Из временной папки exe scrcpy запускать нельзя: она исчезнет при выходе.
        shutil.copytree(bundled, os.path.dirname(local), dirs_exist_ok=True)
    if os.path.isfile(local):
        return local
    return shutil.which("scrcpy")


def start_screen(title="Экран ТВ"):
    """Открывает окно с экраном ТВ. -> запущенный процесс или None."""
    exe = find_scrcpy()
    if not exe:
        print("scrcpy не найден. В собранной программе он встроен; при запуске из "
              "исходников поставьте scrcpy (github.com/Genymobile/scrcpy).")
        return None
    if not SERIAL:
        print("Сначала подключитесь к телевизору.")
        return None
    env = dict(os.environ)
    env["ADB"] = ADB  # тот же adb, что у программы: иначе два сервера мешают друг другу
    cmd = [exe, "-s", SERIAL, "--window-title", title,
           "--no-audio",             # звук остаётся на телевизоре
           "--max-size", "1280",     # по Wi-Fi большое разрешение дёргается
           "--video-bit-rate", "6M", "--max-fps", "30"]
    print(f"Открываю экран ТВ ({os.path.basename(exe)})...")
    try:
        return subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                creationflags=NO_WINDOW)
    except OSError as e:
        print(f"Не удалось запустить scrcpy: {e}")
        return None


def explain_screen_error(output):
    """Понятная причина, если окно экрана закрылось с ошибкой."""
    low = output.lower()
    if "unauthorized" in low:
        return "ТВ не разрешил отладку с этого компьютера"
    if "not found" in low or "no devices" in low or "device offline" in low:
        return "ТВ не отвечает по ADB: переподключитесь"
    if "could not open video stream" in low or "encoder" in low:
        return "ТВ не смог начать трансляцию (видеокодер занят или не поддерживается)"
    return ""


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
    ap.add_argument("--pair", nargs=2, metavar=("IP:ПОРТ", "КОД"),
                    help="сопряжение по коду с экрана «Беспроводная отладка» (Android 11+)")
    ap.add_argument("--screen", action="store_true",
                    help="показать экран ТВ в окне (scrcpy)")
    ap.add_argument("--scan", action="store_true",
                    help="найти Android TV и приставки в локальной сети")
    ap.add_argument("--install", metavar="APK", nargs="+",
                    help="установить на ТВ файлы .apk / .apks / .xapk")
    args = ap.parse_args()
    ADB = args.adb

    if args.pair:
        ensure_adb()
        run([ADB, "start-server"], timeout=30)
        host, _, port = args.pair[0].partition(":")
        addr = pair_and_connect(host, port, args.pair[1])
        if addr:
            print(f"Дальше: python atv_cleaner.py --connect {addr.split(':')[0]}")
        return

    if args.scan:
        ensure_adb()
        run([ADB, "start-server"], timeout=30)
        print_devices(scan_network([read_last_ip()]))
        return

    pick_device(args)
    if args.screen:
        print(SCREEN_HELP)
        proc = start_screen()
        if proc:
            for line in proc.stdout:
                print("  " + line.decode("utf-8", "replace").rstrip())
            proc.wait()
        return
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
                       allow_all=not title.startswith("Прочие"))

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
    if good is None:
        print(f"\n{msg}. Вернуть пакеты: python atv_cleaner.py --restore "
              f"\"{listfile}\"")
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
