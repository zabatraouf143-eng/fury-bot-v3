import os
import re
import shutil
import subprocess
from PIL import Image, ImageOps
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN", "8765104365:AAHYYl2QIDBgkgRR6bXTXJIuH-Vr4dT5I_k")
bot = telebot.TeleBot(BOT_TOKEN)

KEYSTORE_PATH = "release.keystore"
KEY_ALIAS = "botkey"
KEY_PASS = "123456"

sessions = {}


def run_cmd(cmd):
  res = subprocess.run(
      cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
  )
  if res.returncode != 0:
    raise RuntimeError(res.stderr.strip() or "فشل تنفيذ الأمر")


# 1. تغيير اسم التطبيق في Manifest و strings.xml
def change_app_name(decoded_dir, new_name):
  manifest = os.path.join(decoded_dir, "AndroidManifest.xml")
  with open(manifest, "r", encoding="utf-8") as f:
    data = f.read()
  data = re.sub(
      r'(<application\b[^>]*?android:label=")([^"]*)(")',
      rf"\g<1>{new_name}\g<3>",
      data,
      count=1,
  )
  with open(manifest, "w", encoding="utf-8") as f:
    f.write(data)

  strings_xml = os.path.join(decoded_dir, "res", "values", "strings.xml")
  if os.path.exists(strings_xml):
    with open(strings_xml, "r", encoding="utf-8") as f:
      s_data = f.read()
    s_data = re.sub(
        r'(<string name="app_name">)([^<]*)(</string>)',
        rf"\g<1>{new_name}\g<3>",
        s_data,
    )
    with open(strings_xml, "w", encoding="utf-8") as f:
      f.write(s_data)


# 2. تغيير اللوغو الخارجي مع الحفاظ على مقاس كل ملف أصلي
def change_main_logo(decoded_dir, new_logo_path):
  src_img = Image.open(new_logo_path).convert("RGBA")
  count = 0
  for root, _, files in os.walk(os.path.join(decoded_dir, "res")):
    for file in files:
      if file.startswith("ic_launcher") and file.endswith((".png", ".webp")):
        target = os.path.join(root, file)
        with Image.open(target) as orig:
          size = orig.size
        resized = src_img.resize(size, Image.Resampling.LANCZOS)
        resized.save(target)
        count += 1
  return count


# 3. تغيير أيقونة البانل وتلوينها لحالتي التشغيل (ON) والإطفاء (OFF)
def change_panel_icon_and_color(
    decoded_dir, panel_icon_path, target_keyword, hex_color_on, hex_color_off
):
  base_img = Image.open(panel_icon_path).convert("RGBA")
  # فصل قناة الشفافية (Alpha) لتلوين الأيقونة دون تخريب الخلفية الشفافة
  r, g, b, alpha = base_img.split()
  gray = ImageOps.grayscale(base_img)

  img_on = ImageOps.colorize(gray, black="black", white=hex_color_on).convert(
      "RGBA"
  )
  img_on.putalpha(alpha)

  img_off = ImageOps.colorize(gray, black="black", white=hex_color_off).convert(
      "RGBA"
  )
  img_off.putalpha(alpha)

  replaced = 0
  for folder in ["res", "assets"]:
    search_path = os.path.join(decoded_dir, folder)
    if not os.path.exists(search_path):
      continue
    for root, _, files in os.walk(search_path):
      for file in files:
        lower_name = file.lower()
        if target_keyword.lower() in lower_name and lower_name.endswith(
            (".png", ".webp")
        ):
          target = os.path.join(root, file)
          with Image.open(target) as orig:
            size = orig.size
          # اختيار اللون حسب اسم الملف (on / active أو off)
          if "off" in lower_name or "disable" in lower_name:
            img_off.resize(size, Image.Resampling.LANCZOS).save(target)
          else:
            img_on.resize(size, Image.Resampling.LANCZOS).save(target)
          replaced += 1
  return replaced


# 4. تغيير ألوان البانل داخل ملف colors.xml إذا كانت مبنية برمجياً
def update_xml_colors(decoded_dir, old_hex, new_hex):
  colors_xml = os.path.join(decoded_dir, "res", "values", "colors.xml")
  if os.path.exists(colors_xml):
    with open(colors_xml, "r", encoding="utf-8") as f:
      content = f.read()
    content = re.sub(re.escape(old_hex), new_hex, content, flags=re.IGNORECASE)
    with open(colors_xml, "w", encoding="utf-8") as f:
      f.write(content)
          
