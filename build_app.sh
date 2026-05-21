#!/usr/bin/env bash
# Збірка WallRotate.app через py2app у власному venv.
# Запуск:  ./build_app.sh   (або:  bash build_app.sh)
set -euo pipefail

cd "$(dirname "$0")"

# 1. venv (створюємо, якщо немає)
if [ ! -d ".venv" ]; then
  echo "==> Створюю virtualenv (.venv)"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 2. Інструменти збірки + залежності у ТЕ САМЕ оточення
echo "==> Встановлюю setuptools/wheel, залежності та py2app"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install py2app

# 3. Чистимо попередню збірку
rm -rf build dist

# 4. Збірка
echo "==> Збираю WallRotate.app"
python setup.py py2app

echo
echo "Готово: dist/WallRotate.app"
echo "Перенеси його в /Applications і відкрий (перший раз: права кнопка -> Open)."
