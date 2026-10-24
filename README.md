# ATV Cleaner

Портативная программа для Windows: убирает предустановленный мусор с
телевизоров и приставок на Android TV и Google TV через ADB и ставит на них
приложения. Подробнее всего сейчас поддержаны Xiaomi (PatchWall, Mi Box),
остальные марки будут добавляться.
Устанавливать ничего не нужно, ADB уже внутри.

## Как пользоваться

1. Скачайте `ATVCleaner.exe` из раздела **Releases** и положите в любую
   папку: рядом с ним появятся бэкапы.
2. На телевизоре: Настройки → Об устройстве → 7 раз нажмите «Сборка». Затем
   в «Для разработчиков» включите «Отладку по USB» и «Отладку по сети».
3. Запустите программу, введите IP телевизора и нажмите **Подключить**.
   На ТВ разрешите отладку.
4. **Найти мусор** покажет кандидатов по группам. Отметьте ненужное
   и нажмите **Отключить отмеченное**.
5. Согласитесь на перезагрузку с проверкой: если ТВ не загрузится до главного
   экрана, всё вернётся само.

## Рекомендации по моделям Xiaomi и TCL

Программа определяет модель ТВ и сверяется с базой `device_db.py`: что
сообщество отключало на 32 моделях Xiaomi и Redmi (Mi Box 3, Mi Box S 1–3,
TV Stick 4K, Mi TV 4A/P1, серии MSSP, MOOQ, AXSO, Google TV и китайские прошивки)
и на 62 моделях TCL (C7K, C755, C745, C645, C725, P-, Q-, S-серии, Google TV
и Android TV). У TCL модель всегда «Smart TV Pro», поэтому программа определяет
платформу (например, G08 у C7K или BeyondTV4 / G03 у C645) и сводит вместе
все списки этой платформы: «отключали в 9 из 11 списков вашей платформы».
- ★ «отключали на вашей модели» — пакет проверен именно на такой модели;
- «отключали на N из 31 моделей» — опыт по другим моделям;
- ⚠ «на вашей модели оставляли намеренно» — на ней пакет оказался нужен.

Кроме этого, программа:
- не даёт отключить штатный лаунчер Google TV, если мастер настройки претендует
  на домашний экран (иначе ТВ уходит в перезагрузки);
- перед отключением текущего лаунчера проверяет, что система приняла новый
  домашний экран. Китайские прошивки и HyperOS принимают только лаунчеры из
  своего списка, и без этой проверки остался бы чёрный экран.

### Устройства в базе

Для этих устройств есть проверенный список: программа отметит ★ пакеты,
которые отключали именно на такой модели. Модель ТВ видна в
Настройки → Об устройстве → Модель, программа определяет её сама.
Для остальных Android TV рекомендации даются по всем моделям из базы.

<!-- devices:start -->
#### Xiaomi и Redmi (32)

| Устройство | Модель | Кодовое имя | Android | Прошивка | Чип | Пакетов |
|---|---|---|---|---|---|---|
| Xiaomi Mi Box S 2nd gen | MiTV-AFKR0 | jaws | 11 | Google TV | Amlogic | 16 |
| Xiaomi Mi Box 3 | MIBOX3 | once | 9 | Android TV | Amlogic | 24 |
| Xiaomi Mi Box S | MIBOX4 | oneday | 9 | Android TV | Amlogic | 22 |
| Xiaomi TV Stick 4K | MiTV-AYFR0 | soul | 14 | Android TV | Amlogic | 22 |
| Xiaomi TV Box S 3rd gen | MiTV-AFMU0 | twilight | 14 | Google TV | Amlogic | 25 |
| Xiaomi TV Stick 4K 2nd gen | MiTV-AFMU1 | twilight | 14 | Google TV | Amlogic | 24 |
| Redmi TV | MiTV-MFTP0 | alita | 9 | Android, Китай | MediaTek | 16 |
| Xiaomi MiTV-MSSP0 / Xiaomi Mi TV 4A 32 | MiTV-MSSP0 | amelie | 9 | Android TV | — | 11 |
| Xiaomi MiTV-AESP0 | MiTV-AESP0 | aquaman | 9 | Android TV | — | 43 |
| Xiaomi TV EA Pro 55" | MiTV-MTEQ0 | baymax | 10 | Android, Китай | MediaTek | 52 |
| Xiaomi Redmi Smart TV A Pro 55" 2025 Energy-saving | MiTV-ASTR0 | blueplanet | 14 | HyperOS, Китай | Amlogic | 26 |
| Xiaomi Mi TV | MiTV-MOOQ0 | croods | 10 | Android TV | MediaTek | 29 |
| Xiaomi Mi TV P1 43" | MiTV-MOOQ2 | croods | 11 | Android TV | MediaTek | 27 |
| Xiaomi MiTV-AXSO0 | MiTV-AXSO0 | dangal | 9 | Android TV | Amlogic | 33 |
| Xiaomi MiTV-AXSO2 | MiTV-AXSO2 | dangalUHD | 9 | Android TV | Amlogic | 32 |
| Xiaomi TV S Pro 100 Mini LED 2025 | MiTV-MFFU0 | finch | 14 | HyperOS, Китай | MediaTek | 14 |
| Xiaomi MiTV-MFTR0 | MiTV-MFTR0 | freeguy | 11 | HyperOS, Китай | MediaTek | 22 |
| Xiaomi MiTV-MOSR4 | MiTV-MOSR4 | irobot | 11 | Google TV | MediaTek | 27 |
| Xiaomi MiTV-ANSP0 | MiTV-ANSP0 | jobs | 9 | Android, Китай | Amlogic | 31 |
| Xiaomi TV S Mini LED 75 2025 | MiTV-MOEU0 | ladybird | 14 | Google TV | MediaTek | 19 |
| Xiaomi MiTV-MSSP3 | MiTV-MSSP3 | machuca | 11 | Android TV | MediaTek | 23 |
| Xiaomi MiTV-MSSP3 | MiTV-MSSP3 | machuca | 9 | Android TV | MediaTek | 18 |
| Xiaomi MiTV-ASTP1 | MiTV-ASTP1 | maverick | 9 | Android, Китай | Amlogic | 18 |
| Xiaomi MiTV-ASTP0 | MiTV-ASTP0 | mulan | 9 | Android, Китай | Amlogic | 38 |
| Xiaomi MiTV-MSSP1 | MiTV-MSSP1 | nino | 9 | Android TV | — | 8 |
| Xiaomi MiTV-AXFR0 | MiTV-AXFR0 | rango | 11 | Android TV | Amlogic | 16 |
| Xiaomi MiTV-AXFR1 | MiTV-AXFR1 | rango | 11 | Android TV | Amlogic | 25 |
| Xiaomi TV A Pro 75" 2026 | MiTV-MZTU0 | river | 14 | Google TV | MediaTek | 19 |
| Redmi TV | MiTV-ANTL0 | starwars | 5 | Android, Китай | Amlogic | 11 |
| Xiaomi Mi TV 4A | MiTV-MOOQ1 | tarzan | 10 | Android TV | — | 21 |
| Xiaomi MiTV-MOOR2 | MiTV-MOOR2 | venom | 11 | Google TV | MediaTek | 22 |
| Xiaomi MiTV-MSSP2 | MiTV-MSSP2 | volver | 9 | Android TV | MediaTek | 16 |

#### TCL (62)

Модель у TCL всегда «Smart TV Pro», поэтому программа определяет платформу (ro.product.device, например G08) и даёт рекомендации по всем спискам этой платформы.

| Устройство | Платформа / product | Android | Прошивка | Чип | Пакетов |
|---|---|---|---|---|---|
| TCL 43EP660, Europe | BeyondTV | 9 | Android TV | — | 27 |
| TCL 43P615 | BeyondTV | 11 | Android TV | — | 42 |
| TCL 50EP680 | BeyondTV | 11 | Android TV | Realtek | 47 |
| TCL 50P615, Greece | BeyondTV | 11 | Android TV | — | 29 |
| TCL 55C715 QLED | BeyondTV | 9 | Android TV | Realtek | 33 |
| TCL 55C815 | BeyondTV | 11 | Android TV | Realtek | 18 |
| TCL 55EP640, Greece | BeyondTV | 11 | Android TV | — | 29 |
| TCL 65EP640, Finland | BeyondTV | 9 | Android TV | — | 28 |
| TCL 65EP68 | BeyondTV | 11 | Android TV | Realtek | 37 |
| TCL BeyondTV | BeyondTV | 9 | Android TV | — | 12 |
| TCL BeyondTV, EU/Nordic unit | BeyondTV | 9 | Android TV | — | 27 |
| TCL BeyondTV, Poland unit | BeyondTV | 9 | Android TV | — | 26 |
| TCL BeyondTV2 | BeyondTV2 | 11 | Android TV | — | 19 |
| TCL BeyondTV2, Latin America / Brazil market | BeyondTV2 | 9 | Android TV | Realtek | 2 |
| TCL 50P735 BeyondTV4 | BeyondTV4 | 11 | Android | — | 30 |
| TCL 55P638 | BeyondTV4 | 11 | Android TV | — | 37 |
| TCL 65C725 | BeyondTV4 | 11 | Android TV | — | 19 |
| TCL 65Q550G | BeyondTV4 | 11 | Google TV | — | 29 |
| TCL 65Q650G | BeyondTV4 | 11 | Google TV | Realtek | 26 |
| TCL G03 / BeyondTV4 firmware V8-R51MT05-LF1V652 | BeyondTV4 | 11 | Google TV | Realtek | 39 |
| TCL 43P725 | BeyondTV4 / BeyondTV6 | 11 | Android TV | — | 20 |
| TCL 50C725K | BeyondTV4 / BeyondTV6 | 11 | Google TV | Realtek | 22 |
| TCL 55C725 | BeyondTV4 / G03_4K_GB | 11 | Google TV | Realtek | 28 |
| TCL Smart TV Pro | BeyondTV4 / G03_4K_GB | 11 | Google TV | Realtek | 40 |
| TCL 55S546 | BeyondTV4 / G03_4K_US | 11 | Google TV | — | 23 |
| TCL 32L5A | C06 | 11 | Android TV | — | 12 |
| TCL 32S5400A | C06 / C06_2K_GB | 11 | Android TV | MediaTek | 14 |
| TCL 32S5K | C06 / C06_2K_GB | 11 | Android TV | MediaTek | 22 |
| TCL 40S5400A | C06 / C06_2K_GB | 11 | Android TV | MediaTek | 22 |
| TCL 43S5400A | C06 / C06_2K_GB | 11 | Android TV | MediaTek | 23 |
| TCL L40S66E | C06 / C06_2K_GB | 11 | Android TV | MediaTek | 15 |
| TCL 65C735 | G05 / G05_4K_GB | 11 | Google TV | — | 29 |
| TCL Smart TV Pro, US | G05 / G05_4K_US | 11 | Google TV | MediaTek | 29 |
| TCL Smart TV | G07 / G07_4K_GB_NF | 11 | Google TV | Realtek | 34 |
| TCL QM6K Pro Google TV, 2025, US | G08 | 14 | Google TV | MediaTek | 25 |
| TCL Smart TV Pro | G08 | 12 | Google TV | MediaTek | 28 |
| TCL Smart TV Pro | G08 | 12 | Android | MediaTek | 24 |
| TCL 55C745 | G08 / G08_4K_GB | 14 | Google TV | MediaTek | 50 |
| TCL 55C7K-UK QD-Mini LED Google TV, 2025, UK | G08 / G08_4K_GB | 14 | Google TV | MediaTek | 32 |
| TCL 65" C7K QD-Mini LED Google TV, Brazil | G08 / G08_4K_GB | 14 | Google TV | MediaTek | 27 |
| TCL 65" C7L Google TV, 2025, Australia | G08 / G08_4K_GB | 14 | Google TV | MediaTek | 27 |
| TCL 75" C755 QD-Mini LED Google TV, 2024, Australia | G08 / G08_4K_GB | 14 | Google TV | MediaTek | 35 |
| TCL 75" C845X2 Google TV, UK/Europe build | G08 / G08_4K_GB | 14 | Google TV | MediaTek | 32 |
| TCL 85RM7L Google TV | G08 / G08_4K_GB | 14 | Google TV | MediaTek | 22 |
| TCL C89B 85" Google TV, 2024 | G08 / G08_4K_GB | 14 | Google TV | MediaTek | 33 |
| TCL Q7C QD-Mini LED, Europe | G08 / G08_4K_GB | 14 | Google TV | MediaTek | 37 |
| TCL 75" T7 Series 4K 144Hz QLED Google TV | G08 / G08_4K_US | 14 | Google TV | MediaTek | 37 |
| TCL Smart TV Pro, UK firmware | G09 / G09_4K_GB | 12 | Google TV | Amlogic | 35 |
| TCL 55P7K, Middle East | G10 / G10_4K_GB | 12 | Google TV | Realtek | 29 |
| TCL 75P8K, Europe / Nordics | G10 / G10_4K_GB | 12 | Google TV | Realtek | 24 |
| TCL 55P8LS QD-Mini LED, Vietnam | G10 / G10_4K_GB_32BIT | 12 | Google TV | Realtek | 32 |
| TCL 55" 4K Google TV, 2023 model year, US | G10 / G10_4K_US_NF | 12 | Google TV | Realtek | 17 |
| TCL 55S470G | G10 / G10_4K_US_NF | 12 | Google TV | Realtek | 29 |
| TCL 43S5K and 32V5C, India | G13 / G13_2K_GB | 14 | Google TV | MediaTek | 12 |
| TCL UnionTV, Latin America | UnionTV | 9 | Android TV | Realtek | 27 |
| TCL / FFalcon China 2026, device tcl9655_cn / product MT9655_4K_CN, MediaTek MT9655 | tcl9655_cn / MT9655_4K_CN | 14 | Android, Китай | MediaTek | 27 |
| TCL 55Q10G Pro | tcl_mt5879_cn | 11 | Android, Китай | MediaTek | 20 |
| TCL 43S450F-CA | — | 11 | Fire TV | MediaTek | 45 |
| TCL 50DP660 | — | 8 | Android TV | MediaTek | 26 |
| TCL 58S571F | — | 11 | Fire TV | MediaTek | 32 |
| TCL ak30a5 | — | 9 | Android TV, Китай | Amlogic | 16 |
| TCL tc8000_ay30a2 | — | 11 | Android, Китай | Amlogic | 20 |
<!-- devices:end -->

База собрана скриптом `tools/build_device_db.py` из списков проекта
[cleanyourtv](https://github.com/Gathin23/cleanyourtv) (MIT License,
Copyright (c) 2026 Gathin). Чтобы обновить её, склонируйте cleanyourtv и
запустите `python tools/build_device_db.py путь/к/cleanyourtv`. Защитный список
TCL сверен с проектом [free-my-tv](https://github.com/simbasjungles/free-my-tv):
где он и cleanyourtv расходятся, программа ставит ⚠ и пишет об этом.

## Установленные приложения

На вкладке **Установленные приложения** видны все приложения на ТВ: тип
(стороннее или системное), включено ли оно и когда последний раз запускалось.
Отметьте нужные и нажмите **Удалить**, **Отключить** или **Включить**.
Сторонние приложения удаляются полностью, их APK сохраняется в бэкап.
Системные показываются по галочке «Показывать системные», для них работают
те же проверки, что и на вкладке «Очистка».

## Экран ТВ на компьютере

Кнопка **🖥 Экран ТВ** открывает окно с изображением телевизора, и им можно
управлять с компьютера: стрелки и Enter работают как пульт, можно печатать
текст, правая кнопка мыши — «Назад», средняя — «Домой». Звук остаётся на ТВ.
Платное видео (Netflix, YouTube и т. п.), HDMI-входы и антенна в окне будут
чёрными: это защита от копирования в самом Android.

Работает на встроенном [scrcpy](https://github.com/Genymobile/scrcpy)
(Apache License 2.0, Genymobile). Из консоли: `python atv_cleaner.py --screen`.

## Тёмная тема

Кнопка в правом верхнем углу переключает светлую и тёмную тему. При первом
запуске берётся тема Windows, выбор запоминается в `settings.json` рядом с exe.

## Установка приложений

**Установить APK на ТВ** ставит один или несколько файлов `.apk`, а также
наборы `.apks` и `.xapk` (базовый APK с частями). Если установка не прошла,
в журнале будет понятная причина: не та версия Android, не тот процессор,
не хватает места, другая подпись. Если новое приложение оказалось лаунчером
(Projectivy, FLauncher и т. п.), программа предложит сделать его домашним.
OBB-файлы игр из `.xapk` не копируются.

## Android 11+: беспроводная отладка

На новых ТВ (например, TCL C7K на Android 14) вместо «Отладки по сети» бывает
только «Беспроводная отладка» с сопряжением по коду. Включите её, откройте
«Подключение с кодом» и нажмите в программе **🔑 Сопряжение по коду**
(в окнах «Найти ТВ» и «Как включить отладку»): IP, порт и шестизначный код
с экрана ТВ. После этого программа включает на ТВ порт 5555, и до перезагрузки
ТВ подключается просто по IP. Поиск ТВ находит такие телевизоры сам.
Из консоли: `python atv_cleaner.py --pair 192.168.1.50:37099 123456`.

## Драйвер

По сети (Wi-Fi или кабель в роутер) драйвер не нужен. Телевизоры и приставки
Xiaomi обычно подключаются именно так: у них USB-порты для флешек, а не для
подключения к компьютеру.

## Безопасность

- **По умолчанию пакеты отключаются** (`pm disable-user --user 0`), а не
  удаляются: приложение остаётся на ТВ, но не запускается. Так советуют
  делать в темах 4PDA и в гайдах по Xiaomi TV, это полностью обратимо
  кнопкой **Восстановить из бэкапа**.
- Режим **Удалять** (`pm uninstall -k --user 0`) тоже есть. После него не
  делайте сброс к заводским настройкам, пока не восстановите пакеты: на
  некоторых Xiaomi TV это, по сообщениям пользователей, приводило к
  циклической перезагрузке.
- Программа не даёт трогать системные компоненты, голосовой поиск, пульт,
  последний лаунчер и последнюю клавиатуру, persistent-пакеты и пакеты с
  правами системы.
- Перед изменениями сохраняется бэкап: список пакетов, а при удалении ещё и
  APK сторонних приложений.
- На Xiaomi кнопка Home на пульте привязана к PatchWall. Чтобы она открывала
  другой лаунчер, PatchWall нужно отключить, программа предупредит об этом.
  Без ADB PatchWall можно отключить и так: Настройки устройства → PatchWall
  (область обслуживания) → «Другой источник», затем перезагрузка и
  отключение PatchWall в списке приложений.

## Без exe

`Запустить ATV Cleaner.bat` запускает консольную версию
(`atv_cleaner.py`), нужен только Python.
Установка из консоли: `python atv_cleaner.py --install файл.apk`. Окно: `python gui.py`.
