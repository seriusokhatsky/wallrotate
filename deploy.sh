#!/bin/bash
# Деплой без rebuild: оновлює wallpaper.py і app.py в WallRotate.app
#
# Правила оновлення файлів в py2app-бандлі:
#   app.py       → копіюється як є в Contents/Resources/ (__boot__.py читає .py напряму)
#   wallpaper.py → компілюється в .pyc і кладеться в python313.zip (модулі вантажяться з zip)
set -e
cd "$(dirname "$0")"

APP="/Applications/WallRotate.app"
ZIP="$APP/Contents/Resources/lib/python313.zip"

echo "=== Компіляція wallpaper.py ==="
python3.13 -c "import py_compile; py_compile.compile('wallpaper.py', '/tmp/wallpaper.pyc')"
echo "OK"

echo "=== Оновлення zip (wallpaper.pyc) ==="
python3.13 - << 'EOF'
import zipfile
zip_path = '/Applications/WallRotate.app/Contents/Resources/lib/python313.zip'
with zipfile.ZipFile(zip_path, 'r') as z:
    contents = {n: z.read(n) for n in z.namelist()}
with open('/tmp/wallpaper.pyc', 'rb') as f:
    contents['wallpaper.pyc'] = f.read()
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
    for name, data in contents.items():
        z.writestr(name, data)
print("OK")
EOF

echo "=== Копіювання app.py ==="
cp app.py "$APP/Contents/Resources/app.py"
echo "OK"

echo "=== Перезапуск WallRotate ==="
pkill -f WallRotate 2>/dev/null || true
sleep 1
open "$APP"
echo "Запущено"
