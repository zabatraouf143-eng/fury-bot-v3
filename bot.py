import os
import re
import io
import glob
import shutil
import zipfile
import threading
import subprocess
from PIL import Image
from flask import Flask
import telebot
from google import genai
from pydantic import BaseModel

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8765104365:AAFPTCvIRu7YsC2ljqvmRAsXyQeBAa7yP7s")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PORT = int(os.environ.get("PORT", 10000))

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
SESSIONS = {}

class EditIntent(BaseModel):
    is_edit: bool
    reply: str
    new_name: str | None = None
    change_icon: bool = False

@app.route("/")
def health():
    return "OK", 200

def fallback_intent(text: str) -> EditIntent:
    t = text.strip().lower()
    change_icon = any(k in t for k in ["صورة", "تصويرة", "ايقونة", "أيقونة", "ايكون", "photo", "image", "icon", "logo"])

    new_name = None
    m = re.search(r"(?:اسم\s*(?:التطبيق)?|الاسم|nom|name)\s*(?:هو|هوا|الى|إلى|:|=)?\s*(.+)", text.strip(), re.IGNORECASE)
    if m:
        candidate = m.group(1).strip().strip('"').strip("'")
        if candidate and candidate.lower() not in ["التطبيق", "app", "القديم"]:
            new_name = candidate

    if change_icon or new_name:
        msg = "فهمتك! "
        if new_name:
            msg += f"راح نبدل الاسم إلى: {new_name} "
        if change_icon:
            msg += "وراح نبدل الصورة."
        return EditIntent(is_edit=True, reply=msg.strip(), new_name=new_name, change_icon=change_icon)

    return EditIntent(
        is_edit=False,
        reply="أنا هنا! قولي واش تحب تبدل: الصورة ولا اسم التطبيق (مثلا: بدل الاسم إلى Fury Mod)."
    )

def understand_text(text: str) -> EditIntent:
    if not client:
        return fallback_intent(text)
    prompt = (
        "أنت مساعد ذكي في بوت تعديل APK. تفهم الدارجة الجزائرية، العربية، الفرنسية، الإنجليزية، والهندية. "
        "رد بنفس لغة المستخدم بأسلوب طبيعي وبشري. "
        "إذا طلب تغيير اسم التطبيق ضعه في new_name واجعل is_edit=true. "
        "إذا طلب تغيير الصورة/الأيقونة اجعل change_icon=true و is_edit=true. "
        "إذا كانت دردشة عادية اجعل is_edit=false."
    )
    try:
        res = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=text,
            config={
                "system_instruction": prompt,
                "response_mime_type": "application/json",
                "response_schema": EditIntent,
                "temperature": 0.3,
            },
        )
        return EditIntent.model_validate_json(res.text)
    except Exception:
        return fallback_intent(text)

def sign_apk(unsigned_apk: str, out_dir: str) -> str:
    for old in glob.glob(f"{out_dir}/*Signed.apk"):
        os.remove(old)
    res = subprocess.run(
        ["java", "-Xmx256m", "-jar", "/usr/local/bin/signer.jar", "-a", unsigned_apk, "-o", out_dir, "--allowResign"],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        raise RuntimeError(f"فشل التوقيع: {res.stderr[-300:]}")
    signed = glob.glob(f"{out_dir}/*Signed.apk")
    return signed[0] if signed else unsigned_apk

def _resize_bytes(img_rgba: Image.Image, raw_bytes: bytes, ext: str) -> bytes | None:
    try:
        with Image.open(io.BytesIO(raw_bytes)) as old:
            w, h = old.size
        buf = io.BytesIO()
        fmt = "WEBP" if ext.lower() == ".webp" else "PNG"
        img_rgba.resize((w, h), Image.Resampling.LANCZOS).save(buf, fmt)
        return buf.getvalue()
    except Exception:
        return None

def replace_icon_zip_fallback(apk_in: str, icon_in: str, unsigned_apk: str) -> int:
    img = Image.open(icon_in).convert("RGBA")
    replaced_count = 0
    with zipfile.ZipFile(apk_in, "r") as zin, zipfile.ZipFile(unsigned_apk, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            fn = item.filename
            if fn.startswith("META-INF/") and (fn.endswith(".SF") or fn.endswith(".RSA") or fn.endswith(".DSA")):
                continue
            data = zin.read(fn)
            low = fn.lower()
            ext = os.path.splitext(low)[1]
            if low.startswith("res/") and ext in (".png", ".webp") and ("launcher" in low or "icon" in low or "logo" in low):
                new_bytes = _resize_bytes(img, data, ext)
                if new_bytes is not None:
                    data = new_bytes
                    replaced_count += 1
            zout.writestr(item, data)
    return replaced_count

def process_apk(user_id: int, new_name: str | None, change_icon: bool) -> tuple[str, int]:
    base = f"/tmp/work_{user_id}"
    apk_in = f"{base}/in.apk"
    dec_dir = f"{base}/dec"
    unsigned_apk = f"{base}/unsigned.apk"
    icon_in = f"{base}/icon.png"
    icon_replaced = 0

    if os.path.exists(dec_dir):
        shutil.rmtree(dec_dir)

    d_res = subprocess.run(["apktool", "d", "-f", "-s", apk_in, "-o", dec_dir], capture_output=True, text=True)
    if d_res.returncode != 0:
        raise RuntimeError(f"فشل الفك: {d_res.stderr[-300:]}")

    if new_name:
        for strings_file in glob.glob(f"{dec_dir}/res/values*/strings.xml"):
            with open(strings_file, "r", encoding="utf-8", errors="ignore") as f:
                data = f.read()
            data = re.sub(r'(<string name="app_name">)(.*?)(</string>)', rf"\g<1>{new_name}\g<3>", data)
            with open(strings_file, "w", encoding="utf-8") as f:
                f.write(data)

        manifest = f"{dec_dir}/AndroidManifest.xml"
        if os.path.exists(manifest):
            with open(manifest, "r", encoding="utf-8", errors="ignore") as f:
                m_data = f.read()
            m_data = re.sub(r'android:label="[^"@]+"', f'android:label="{new_name}"', m_data)
            with open(manifest, "w", encoding="utf-8") as f:
                f.write(m_data)

    if change_icon and os.path.exists(icon_in):
        img = Image.open(icon_in).convert("RGBA")
        candidates = (
            glob.glob(f"{dec_dir}/res/**/*launcher*.png", recursive=True)
            + glob.glob(f"{dec_dir}/res/**/*launcher*.webp", recursive=True)
            + glob.glob(f"{dec_dir}/res/**/*icon*.png", recursive=True)
            + glob.glob(f"{dec_dir}/res/**/*icon*.webp", recursive=True)
        )
        for path in set(candidates):
            ext = os.path.splitext(path)[1]
            with open(path, "rb") as f:
                raw = f.read()
            new_bytes = _resize_bytes(img, raw, ext)
            if new_bytes is not None:
                with open(path, "wb") as f:
                    f.write(new_bytes)
                icon_replaced += 1

    b_res = subprocess.run(["apktool", "b", "-f", "--use-aapt2", dec_dir, "-o", unsigned_apk], capture_output=True, text=True)
    if b_res.returncode != 0:
        if change_icon and not new_name and os.path.exists(icon_in):
            icon_replaced = replace_icon_zip_fallback(apk_in, icon_in, unsigned_apk)
        else:
            err_tail = (b_res.stderr or b_res.stdout or "")[-350:]
            raise RuntimeError(f"التطبيق محمي ضد إعادة البناء:\n{err_tail}")

    return sign_apk(unsigned_apk, base), icon_replaced

@bot.message_handler(commands=["start"])
def cmd_start(m):
    SESSIONS[m.from_user.id] = {}
    bot.reply_to(m, "أهلا! ابعثلي التطبيق (APK) ومن بعد قولي الاسم أو الصورة اللي تحب تبدلها.")

@bot.message_handler(content_types=["document"])
def on_doc(m):
    if not m.document.file_name.lower().endswith(".apk"):
        return bot.reply_to(m, "ابعث ملف بصيغة .apk برك.")
    base = f"/tmp/work_{m.from_user.id}"
    os.makedirs(base, exist_ok=True)
    data = bot.download_file(bot.get_file(m.document.file_id).file_path)
    with open(f"{base}/in.apk", "wb") as f:
        f.write(data)
    SESSIONS.setdefault(m.from_user.id, {})["has_apk"] = True
    bot.reply_to(m, "وصلني التطبيق! وش تحب تعدل فيه؟")

@bot.message_handler(content_types=["photo"])
def on_photo(m):
    base = f"/tmp/work_{m.from_user.id}"
    os.makedirs(base, exist_ok=True)
    data = bot.download_file(bot.get_file(m.photo[-1].file_id).file_path)
    with open(f"{base}/icon.png", "wb") as f:
        f.write(data)
    SESSIONS.setdefault(m.from_user.id, {})["has_icon"] = True
    bot.reply_to(m, "وصلتني الصورة! قولي طبق التعديل ولا زيد الاسم الجديد.")

@bot.message_handler(content_types=["text"])
def on_text(m):
    uid = m.from_user.id
    sess = SESSIONS.setdefault(uid, {})
    intent = understand_text(m.text)

    if not intent.is_edit:
        return bot.reply_to(m, intent.reply)

    if not sess.get("has_apk"):
        return bot.reply_to(m, "ابعثلي ملف الـ APK هو الأول باش نقدر نعدل عليه.")

    use_icon = intent.change_icon or sess.get("has_icon", False)
    if not intent.new_name and not use_icon:
        return bot.reply_to(m, intent.reply)

    wait_msg = bot.reply_to(m, f"{intent.reply}\n⏳ جاري التعديل وإعادة التوقيع...")
    try:
        out_apk, replaced_count = process_apk(uid, intent.new_name, use_icon)
        caption = f"تم التعديل (ملفات الأيقونة المبدلة: {replaced_count})" if use_icon else "تم التعديل بنجاح"
        with open(out_apk, "rb") as f:
            bot.send_document(uid, f, visible_file_name=f"{intent.new_name or 'modified'}.apk", caption=caption)
        sess["has_icon"] = False
    except Exception as e:
        bot.edit_message_text(f"فشل التعديل على هذا التطبيق:\n{e}", uid, wait_msg.message_id)

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT), daemon=True).start()
    bot.infinity_polling(skip_pending=True)
  
