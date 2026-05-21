# WallRotate (MVP)

Menu-bar додаток для macOS, що автоматично міняє шпалери робочого столу,
підтягуючи зображення з **Unsplash** або **Hall of FRAMED** за заданим інтервалом.

Це MVP-білд: працює як фоновий додаток в рядку меню, міняє шпалеру
за таймером і має базові налаштування прямо в меню.

![Іконка WallRotate в рядку меню — світла й темна теми](assets/menubar-preview.png)

Іконка — монохромна **template-іконка**: macOS автоматично робить її чорною
у світлій темі та білою в темній (і підсвічує при кліку).

## Можливості
- Автоматична зміна шпалери за інтервалом (15 хв / 30 хв / 1 год / 3 год / 6 год).
- «Next wallpaper» — змінити негайно.
- «Pause / Resume» — призупинити ротацію.
- **Два джерела зображень** (перемикач у меню «Source»):
  - **Unsplash** — фотографії за ключовими словами через офіційне API.
  - **Hall of FRAMED** — куровані ігрові скріншоти з framedsc.com (без API-ключа).
- «Set theme…» — ключові слова для пошуку Unsplash (напр. `nature, mountains, ocean`).
- «Set Unsplash API key…» — вставити ключ без редагування коду.
- **Hall of FRAMED filters** — підменю з фільтрами для куратора:
  - Min score (≥ 5 / 10 / 25 / 50) — мінімальний рейтинг скріншоту.
  - Color group — фільтр за домінантною кольоровою групою.
  - Include / Exclude games — список ігор через кому (часткове співпадіння).
  - Лічильник «N shots match» показує скільки скріншотів проходять фільтр.
- «Launch at login» — автозапуск при вході в систему (галочка стану).
- Адаптивна template-іконка в menu bar (чорна у світлій темі, біла в темній).
- Підтримка кількох моніторів, включно з fullscreen-застосунками.
- Локальний кеш фото з обмеженням розміру.
- Дотримання правил Unsplash API (download-тригер + атрибуція автора з UTM).

## Крок 1. Отримати Unsplash Access Key (опційно, лише для Unsplash)
1. Відкрий https://unsplash.com/developers і увійди / зареєструйся.
2. **Your apps → New Application**, прийми умови.
3. Скопіюй значення **Access Key** (НЕ Secret Key).

> Demo-режим дає 50 запитів/год — для зміни раз на годину цього з головою.

> Для Hall of FRAMED ключ не потрібен — дані тягнуться з публічного
> JSON-репозиторію на GitHub. Цей крок можна пропустити, якщо плануєш
> користуватись лише цим джерелом.

## Крок 2. Встановити залежності
```bash
cd wallrotate
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Крок 3. Запустити
```bash
python3 app.py
```
У рядку меню зʼявиться іконка WallRotate. Дві опції першого запуску:

**А. Через Hall of FRAMED (без ключа).**
У меню **Source → Hall of FRAMED**. Перша ротація стартує одразу;
налаштуй фільтри в **Hall of FRAMED filters** за смаком.

**Б. Через Unsplash (з API-ключем).**
- або заздалегідь експортуй ключ:
  ```bash
  export UNSPLASH_ACCESS_KEY="твій_access_key"
  python3 app.py
  ```
- або запусти без ключа і встанови його через меню → **Set Unsplash API key…**

Після збереження ключа додаток одразу завантажить і поставить першу шпалеру,
а далі мінятиме її за обраним інтервалом.

## Де зберігаються дані
- Налаштування: `~/Library/Application Support/WallRotate/config.json`
- Кеш фото: `~/Library/Application Support/WallRotate/cache/`

## Структура проекту
```
wallrotate/
├── app.py              # точка входу: меню-бар, таймер, дії
├── config.py           # налаштування (JSON) і шляхи
├── models.py           # модель Photo
├── wallpaper.py        # встановлення шпалери (NSWorkspace / osascript)
├── cache.py            # завантаження і кеш фото
├── launch_agent.py     # автозапуск при вході (LaunchAgent)
├── providers/
│   ├── base.py         # інтерфейс ImageProvider
│   ├── unsplash.py     # реалізація для Unsplash
│   └── framedsc.py     # реалізація для Hall of FRAMED
├── assets/             # template-іконка menu bar (svg/pdf/png) + прев'ю
├── requirements.txt
├── requirements-dev.txt # інструменти збірки (setuptools, wheel, py2app)
├── build_app.sh        # збірка .app однією командою
└── setup.py            # пакування у .app через py2app
```

## Додати нове джерело
Реалізуй `ImageProvider` (`providers/base.py`) у новому файлі в `providers/`
і поверни `Photo` з `get_random()`. Unsplash — приклад у `providers/unsplash.py`.

## Автозапуск при вході
У меню є пункт **«Launch at login»**. Увімкнення створює LaunchAgent у
`~/Library/LaunchAgents/dev.wallrotate.app.plist`. Він набуває чинності
при **наступному** вході в систему (щоб не запускати другий екземпляр поверх
уже відкритого). Працює і для запуску зі скрипта, і для зібраного `.app`.

> Якщо запускаєш зі скрипта в venv — автозапуск посилатиметься на той самий
> інтерпретатор і `app.py`. Для стабільного автозапуску краще зібрати `.app`
> (нижче) і ввімкнути «Launch at login» уже в ньому.

## Збірка у standalone .app

Найпростіше — скриптом (сам створить venv і поставить усе потрібне):
```bash
./build_app.sh
# результат: dist/WallRotate.app
```

Або вручну (важливо: у тому самому venv, де стоять залежності):
```bash
source .venv/bin/activate
pip install -r requirements-dev.txt   # setuptools, wheel, py2app
python setup.py py2app
# результат: dist/WallRotate.app
```

> Помилка `No module named 'setuptools'` означає, що команду запущено в Python
> без інструментів збірки (зазвичай — поза venv або в системному python3).
> Активуй venv і встанови `requirements-dev.txt`, або просто запусти `./build_app.sh`.

Для швидкої перевірки під час розробки є alias-режим (не standalone, але
збирається миттєво й бачить твої файли напряму):
```bash
python setup.py py2app -A
```

- `LSUIElement=True` робить додаток фоновим (без іконки в Dock).
- Іконки з `assets/` автоматично пакуються в `Contents/Resources/assets/`.
- Перенеси `WallRotate.app` у `/Applications` і запусти.

Перший запуск некваліфікованого `.app` Gatekeeper може блокувати —
відкрий через **праву кнопку → Open** (або System Settings → Privacy &
Security → Open Anyway). Для роздачі іншим знадобиться підпис Developer ID
+ нотаризація Apple.

## Ліцензія на фото

**Unsplash.** Зображення надаються Unsplash згідно з їхньою ліцензією та
[API Guidelines](https://help.unsplash.com/en/articles/2511245-unsplash-api-guidelines).
Додаток виконує обовʼязковий download-тригер і показує автора з посиланням.

**Hall of FRAMED.** Скріншоти з [framedsc.com](https://framedsc.com) — куроване
ком'юніті фотографів усередині відеоігор. Авторські права належать
ігровим студіям і авторам скріншотів; пункт меню «Open author» відкриває
профіль автора. Скріншоти проєкту Hall of FRAMED призначені для особистого
некомерційного використання як шпалери.
