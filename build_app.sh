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

# 5. Ad-hoc переподписання
# py2app залишає у Contents/Resources/ багато .so-розширень із tainted-сторінками
# (page hashes не збігаються з вмістом файла). На macOS 14+ AMFI/CODE SIGNING
# вбиває процес SIGKILL без жодного повідомлення в stdout/stderr — лише через
# `log show` видно "rejecting invalid page ... in file zlib.cpython-313-darwin.so".
#
# `codesign --deep` не обходить .so-файли всередині Resources/ (вони не є
# вкладеними бандлами), тому підписуємо їх поіменно, потім Python framework,
# головні бінарники, і фінально --deep запечатує бандл.
APP="dist/WallRotate.app"
echo "==> Ad-hoc підписую .so / .dylib у бандлі"
find "$APP" -type f \( -name "*.so" -o -name "*.dylib" \) -print0 \
  | xargs -0 -n1 codesign --force --sign - 2>/dev/null || true

PY_FW="$APP/Contents/Frameworks/Python.framework/Versions/3.13/Python"
[ -f "$PY_FW" ] && codesign --force --sign - "$PY_FW"

for bin in "$APP/Contents/MacOS/python" "$APP/Contents/MacOS/WallRotate"; do
  [ -f "$bin" ] && codesign --force --sign - "$bin"
done

echo "==> Запечатую бандл (--deep)"
codesign --force --deep --sign - "$APP"

echo
echo "Готово: dist/WallRotate.app"
echo "Перенеси його в /Applications і відкрий (перший раз: права кнопка -> Open)."
