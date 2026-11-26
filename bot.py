import os
import re
import glob
import shutil
import threading
import subprocess
from PIL import Image
from flask import Flask
import telebot
from google import genai
from pydantic import BaseModel

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8765104365:AAFPTCvIRu7YsC2ljqvmRAsXyQeBAa7yP7s")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
PORT = int(os.environ.get("PORT", 10000))

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)
SESSIONS = {}

class EditIntent(BaseModel):
    is_edit: bool
    reply: str
    new_name: str | None = None
    change_icon: bool = False

@app.route("/")
def health():
    return "OK", 200

def understand_text(text: str) -> EditIntent:
    prompt = (
        "أنت مساعد ذكي في بوت تعديل APK. تفهم الدارجة الجزائرية، العربية، الفرنسية، الإنجليزية، والهندية. "
        "رد بنفس لغة المستخدم بأسلوب طبيعي وبشري. "
        "إذا طلب تغيير اسم التطبيق ضعه في new_name واجعل is_edit=true. "
        "إذا طلب تغيير الصورة/الأيقونة اجعل change_icon=true و is_edit=true. "
        "إذا كانت دردشة عادية اجعل is_edit=false."
    )
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
  def process_apk(user_id: int, new_name: str | None, change_icon: bool) -> str:
    base = f"/tmp/work_{user_id}"
    apk_in = f"{base}/in.apk"
    dec_dir = f"{base}/dec"
    unsigned_apk = f"{base}/unsigned.apk"
    signed_apk = f"{base}/final.apk"
    icon_in = f"{base}/icon.png"

    if os.path.exists(dec_dir):
        shutil.rmtree(dec_dir)

    subprocess.run(["apktool", "d", "-f", "-s", apk_in, "-o", dec_dir], check=True)

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
        for path in glob.glob(f"{dec_dir}/res/**/*ic_launcher*.png", recursive=True):
            with Image.open(path) as old:
                w, h = old.size
            img.resize((w, h)).save(path, "PNG")
        for path in glob.glob(f"{dec_dir}/res/**/*ic_launcher*.webp", recursive=True):
            with Image.open(path) as old:
                w, h = old.size
            img.resize((w, h)).save(path, "WEBP")

    subprocess.run(["apktool", "b", dec_dir, "-o", unsigned_apk], check=True)

    ks = "/tmp/debug.keystore"
    if not os.path.exists(ks):
        subprocess.run([
            "keytool", "-genkey", "-v", "-keystore", ks, "-storepass", "android",
            "-alias", "androiddebugkey", "-keypass", "android", "-keyalg", "RSA",
            "-keysize", "2048", "-validity", "10000", "-dname", "CN=Android Debug,O=Android,C=US"
        ], check=True)

    subprocess.run([
        "apksigner", "sign", "--ks", ks, "--ks-pass", "pass:android",
        "--key-pass", "pass:android", "--out", signed_apk, unsigned_apk
    ], check=True)
    return signed_apk

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
    try:
        intent = understand_text(m.text)
    except Exception:
        return bot.reply_to(m, "صرالي مشكل صغير في الاتصال، عاود ابعث رسالتك.")

    if not intent.is_edit:
        return bot.reply_to(m, intent.reply)

    if not sess.get("has_apk"):
        return bot.reply_to(m, "ابعثلي ملف الـ APK هو الأول باش نقدر نعدل عليه.")

    use_icon = intent.change_icon or sess.get("has_icon", False)
    if not intent.new_name and not use_icon:
        return bot.reply_to(m, intent.reply)

    wait_msg = bot.reply_to(m, f"{intent.reply}\n⏳ جاري التعديل وإعادة التوقيع...")
    try:
        out_apk = process_apk(uid, intent.new_name, use_icon)
        with open(out_apk, "rb") as f:
            bot.send_document(uid, f, visible_file_name=f"{intent.new_name or 'modified'}.apk")
        sess["has_icon"] = False
    except Exception as e:
        bot.edit_message_text(f"فشل التعديل على هذا التطبيق: {e}", uid, wait_msg.message_id)

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT), daemon=True).start()
    bot.infinity_polling(skip_pending=True)
      
