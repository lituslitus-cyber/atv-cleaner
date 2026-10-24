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

## Рекомендации по моделям Xiaomi

Программа определяет модель ТВ и сверяется с базой `xiaomi_db.py`: что
сообщество отключало на 31 модели Xiaomi и Redmi (Mi Box 3, Mi Box S 1–3,
TV Stick 4K, Mi TV 4A/P1, серии MSSP, MOOQ, AXSO, Google TV и китайские прошивки).
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
| Устройство | Модель | Кодовое имя | Android | Прошивка | Чип | Пакетов |
|---|---|---|---|---|---|---|
| Xiaomi Mi Box 3 | MIBOX3 | once | 9 | Android TV | Amlogic | 24 |
| Xiaomi Mi Box S | MIBOX4 | oneday | 9 | Android TV | Amlogic | 22 |
| Xiaomi Mi Box S 2nd gen | MiTV-AFKR0 | jaws | 11 | Google TV | Amlogic | 16 |
| Xiaomi TV Box S 3rd gen | MiTV-AFMU0 | twilight | 14 | Google TV | Amlogic | 25 |
| Xiaomi TV Stick 4K | MiTV-AYFR0 | soul | 14 | Android TV | Amlogic | 22 |
| Xiaomi TV Stick 4K 2nd gen | MiTV-AFMU1 | twilight | 14 | Google TV | Amlogic | 24 |
| Redmi TV | MiTV-ANTL0 | starwars | 5 | Android | Amlogic | 11 |
| Redmi TV | MiTV-MFTP0 | alita | 9 | Android, Китай | MediaTek | 16 |
| Xiaomi Mi TV | MiTV-MOOQ0 | croods | 10 | Android TV | MediaTek | 29 |
| Xiaomi Mi TV 4A | MiTV-MOOQ1 | tarzan | 10 | Android TV | — | 21 |
| Xiaomi Mi TV P1 43" | MiTV-MOOQ2 | croods | 11 | Android TV | MediaTek | 27 |
| Xiaomi MiTV-AESP0 | MiTV-AESP0 | aquaman | 9 | Android TV | — | 42 |
| Xiaomi MiTV-ANSP0 | MiTV-ANSP0 | jobs | 9 | Android, Китай | Amlogic | 31 |
| Xiaomi MiTV-ASTP0 | MiTV-ASTP0 | mulan | 9 | Android, Китай | Amlogic | 38 |
| Xiaomi MiTV-ASTP1 | MiTV-ASTP1 | maverick | 9 | Android, Китай | Amlogic | 18 |
| Xiaomi MiTV-AXFR1 | MiTV-AXFR1 | rango | 11 | Android TV | Amlogic | 25 |
| Xiaomi MiTV-AXSO0 | MiTV-AXSO0 | dangal | 9 | Android TV | Amlogic | 33 |
| Xiaomi MiTV-AXSO2 | MiTV-AXSO2 | dangalUHD | 9 | Android TV | Amlogic | 32 |
| Xiaomi MiTV-MFTR0 | MiTV-MFTR0 | freeguy | 11 | HyperOS, Китай | MediaTek | 22 |
| Xiaomi MiTV-MOOR2 | MiTV-MOOR2 | venom | 11 | Google TV | MediaTek | 22 |
| Xiaomi MiTV-MOSR4 | MiTV-MOSR4 | irobot | 11 | Google TV | MediaTek | 27 |
| Xiaomi MiTV-MSSP0 / Xiaomi Mi TV 4A 32 | MiTV-MSSP0 | amelie | 9 | Android TV | — | 11 |
| Xiaomi MiTV-MSSP1 | MiTV-MSSP1 | nino | 9 | Android TV | — | 8 |
| Xiaomi MiTV-MSSP2 | MiTV-MSSP2 | volver | 9 | Android TV | MediaTek | 16 |
| Xiaomi MiTV-MSSP3 | MiTV-MSSP3 | machuca | 11 | Android TV | MediaTek | 23 |
| Xiaomi MiTV-MSSP3 | MiTV-MSSP3 | machuca | 9 | Android TV | MediaTek | 18 |
| Xiaomi Redmi Smart TV A Pro 55" 2025 Energy-saving | MiTV-ASTR0 | blueplanet | 14 | HyperOS, Китай | Amlogic | 26 |
| Xiaomi TV A Pro 75" 2026 | MiTV-MZTU0 | river | 14 | Google TV | MediaTek | 19 |
| Xiaomi TV EA Pro 55" | MiTV-MTEQ0 | baymax | 10 | Android, Китай | MediaTek | 52 |
| Xiaomi TV S Mini LED 75 2025 | MiTV-MOEU0 | ladybird | 14 | Google TV | MediaTek | 19 |
| Xiaomi TV S Pro 100 Mini LED 2025 | MiTV-MFFU0 | finch | 14 | HyperOS, Китай | MediaTek | 14 |
<!-- devices:end -->

База собрана скриптом `tools/build_xiaomi_db.py` из списков проекта
[cleanyourtv](https://github.com/Gathin23/cleanyourtv) (MIT License,
Copyright (c) 2026 Gathin). Чтобы обновить её, склонируйте cleanyourtv и
запустите `python tools/build_xiaomi_db.py путь/к/cleanyourtv`.

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
