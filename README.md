# WallRotate (MVP)

Menu-bar додаток для macOS, що автоматично міняє шпалери робочого столу,
підтягуючи фото з **Unsplash** за заданим інтервалом.

Це MVP-білд: працює як фоновий додаток в рядку меню (🖼), міняє шпалеру
за таймером і має базові налаштування прямо в меню.

## Можливості
- Автоматична зміна шпалери за інтервалом (15 хв / 30 хв / 1 год / 3 год / 6 год).
- «Next wallpaper» — змінити негайно.
- «Pause / Resume» — призупинити ротацію.
- «Set theme…» — ключові слова для пошуку (напр. `nature, mountains, ocean`).
- «Set Unsplash API key…» — вставити ключ без редагування коду.
- Підтримка кількох моніторів.
- Локальний кеш фото з обмеженням розміру.
- Дотримання правил Unsplash API (download-тригер + атрибуція автора з UTM).

## Крок 1. Отримати Unsplash Access Key (безкоштовно)
1. Відкрий https://unsplash.com/developers і увійди / зареєструйся.
2. **Your apps → New Application**, прийми умови.
3. Скопіюй значення **Access Key** (НЕ Secret Key).

> Demo-режим дає 50 запитів/год — для зміни раз на годину цього з головою.

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
У меню зʼявиться іконка 🖼. Перший запуск:
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
├── providers/
│   ├── base.py         # інтерфейс ImageProvider
│   └── unsplash.py     # реалізація для Unsplash
├── requirements.txt
└── setup.py            # пакування у .app через py2app (опційно)
```

## Додати нове джерело
Реалізуй `ImageProvider` (`providers/base.py`) у новому файлі в `providers/`
і поверни `Photo` з `get_random()`. Unsplash — приклад у `providers/unsplash.py`.

## Пакування у .app (пізніше)
```bash
pip install py2app
python3 setup.py py2app
# результат: dist/WallRotate.app
```
Для запуску на чужих Mac знадобиться підпис Developer ID + нотаризація Apple,
інакше Gatekeeper блокуватиме застосунок.

## Відомі обмеження MVP
- Шпалера ставиться для **активного** Space кожного екрана (обмеження macOS
  щодо просторів — покрити всі Spaces одним викликом нативно не можна).
- Немає автозапуску при вході (додається на етапі пакування через LaunchAgent
  або Login Items).

## Ліцензія на фото
Зображення надаються Unsplash згідно з їхньою ліцензією та
[API Guidelines](https://help.unsplash.com/en/articles/2511245-unsplash-api-guidelines).
Додаток виконує обовʼязковий download-тригер і показує автора з посиланням.
