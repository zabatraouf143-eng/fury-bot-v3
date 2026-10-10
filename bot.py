import sqlite3
import threading
import time
import uuid
import datetime
import random
import string
import os
from flask import Flask, render_template_string, request
import telebot
from telebot import types

TOKEN = "8925665338:AAG-di-iZ3KzyriU_RlOkSSw1KplFzJr3c8"
bot = telebot.TeleBot(TOKEN)
DEV_USERNAME = "raouf100K"

app = Flask(__name__)

conn = sqlite3.connect("fury_game.db", check_same_thread=False)
cursor = conn.cursor()

# جداول قاعدة البيانات
cursor.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0,
            invited_by INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            last_active REAL DEFAULT 0
        )""")

cursor.execute("""CREATE TABLE IF NOT EXISTS user_button_cooldowns (
            user_id INTEGER,
            button_id INTEGER,
            last_used REAL,
            PRIMARY KEY (user_id, button_id)
        )""")

cursor.execute("""CREATE TABLE IF NOT EXISTS custom_links (
            button_id INTEGER PRIMARY KEY,
            url TEXT
        )""")

cursor.execute("""CREATE TABLE IF NOT EXISTS user_bans (
            user_id INTEGER PRIMARY KEY,
            fail_count INTEGER DEFAULT 0,
            ban_until REAL DEFAULT 0,
            ban_level INTEGER DEFAULT 0
        )""")

cursor.execute("""CREATE TABLE IF NOT EXISTS secure_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER,
            button_id INTEGER,
            generated_code TEXT,
            is_used INTEGER DEFAULT 0,
            expires_at REAL
        )""")

cursor.execute("CREATE TABLE IF NOT EXISTS wheel_cooldowns (user_id INTEGER PRIMARY KEY, last_spin REAL, spin_step INTEGER)")
conn.commit()

def is_developer(user):
    return user.username == DEV_USERNAME

def main_menu_markup(user):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_profile = types.KeyboardButton("👤 الملف الشخصي")
    btn_earn = types.KeyboardButton("🎁 تجميع النقاط")
    btn_shop = types.KeyboardButton("🛍️ عروض المتجر")
    btn_support = types.KeyboardButton("📞 الإبلاغ بالمشاكل")
    btn_chat = types.KeyboardButton("💬 تواصل مع المطور")

    markup.add(btn_profile, btn_earn)
    markup.add(btn_shop, btn_support)
    markup.add(btn_chat)

    if is_developer(user):
        btn_admin = types.KeyboardButton("⚙️ لوحة المطورين")
        markup.add(btn_admin)
        
    return markup
@bot.message_handler(commands=["start"])
def send_start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    current_time = time.time()
    
    args = message.text.split()
    invited_by = 0
    if len(args) > 1:
        try:
            ref_id = int(args[1])
            if ref_id != user_id: invited_by = ref_id
        except ValueError: pass

    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, invited_by, last_active) VALUES (?, ?, ?, ?)", (user_id, username, invited_by, current_time))
        if invited_by != 0:
            cursor.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?", (invited_by,))
    else:
        cursor.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (current_time, user_id))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    active_threshold = current_time - 86400
    cursor.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (active_threshold,))
    active_users = cursor.fetchone()[0]

    welcome_text = f"💎 **أهلاً بك عزيزي في بوت شحن جواهر فري فاير مجاناً!** 🎮\n\n👥 **عدد المستخدمين الكلي:** `{total_users}`\n⚡ **المستخدمين النشطين (24 ساعة):** `{active_users}`\n\nاختر ما يناسبك من الأزرار بالأسفل لتجميع النقاط وشحن جواهرك! 🔥"
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu_markup(message.from_user), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text in ["👤 الملف الشخصي", "🎁 تجميع النقاط", "🛍️ عروض المتجر", "📞 الإبلاغ بالمشاكل", "💬 تواصل مع المطور", "⚙️ لوحة المطورين", "🔙 رجوع للقائمة الرئيسية"])
def handle_main_buttons(message):
    user_id = message.from_user.id
    text = message.text
    current_time = time.time()
    cursor.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (current_time, user_id))
    conn.commit()

    if text == "👤 الملف الشخصي":
        cursor.execute("SELECT points, referral_count FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        pts, refs = (res[0] if res else 0), (res[1] if res else 0)
        profile_text = f"👤 **الملف الشخصي الخاص بك:**\n\n🆔 **آيدي حسابك:** `{user_id}`\n⭐ **رصيد النقاط:** `{pts}` نقطة\n👥 **المنضمين عبر رابطك:** `{refs}` شخص\n🔗 **رابط الاحالة:**\n`https://t.me/{bot.get_me().username}?start={user_id}`"
        bot.send_message(message.chat.id, profile_text, parse_mode="Markdown")

    elif text == "🎁 تجميع النقاط":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📌 الطريقة الأولى (رابط الاحالة)", callback_data="earn_method_1"))
        markup.add(types.InlineKeyboardButton("🔗 الطريقة الثانية (اختصار الروابط) - V3", callback_data="earn_method_2"))
        markup.add(types.InlineKeyboardButton("🎡 الطريقة الثالثة (عجلة الحظ)", callback_data="earn_wheel"))
        bot.send_message(message.chat.id, "🎁 **اختر طريقة تجميع النقاط المناسبة لك:**", reply_markup=markup, parse_mode="Markdown")

    elif text == "🛍️ عروض المتجر":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💎 110 جوهرة = 220 نقطة", callback_data="shop_1"))
        markup.add(types.InlineKeyboardButton("💎 220 جوهرة = 420 نقطة", callback_data="shop_2"))
        markup.add(types.InlineKeyboardButton("💎 330 جوهرة = 640 نقطة", callback_data="shop_3"))
        shop_msg = "🛍️ **قائمة عروض شحن جواهر فري فاير (V3):**\n\n1️⃣ **110 جوهرة** = `220 نقطة`\n2️⃣ **220 جوهرة** = `420 نقطة`\n3️⃣ **330 جوهرة** = `640 نقطة`\n\nاضغط على العرض لاختياره! 🟢"
        bot.send_message(message.chat.id, shop_msg, reply_markup=markup, parse_mode="Markdown")

    elif text in ["📞 الإبلاغ بالمشاكل", "💬 تواصل مع المطور"]:
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💬 مراسلة المطور مباشرة", url=f"https://t.me/{DEV_USERNAME}"))
        bot.send_message(message.chat.id, "📞 **هل تواجه مشكلة أو استفسار؟**\nتواصل مع المطور مباشرة عبر الزر أدناه:", reply_markup=markup, parse_mode="Markdown")

    elif text == "⚙️ لوحة المطورين":
        if not is_developer(message.from_user):
            bot.reply_to(message, "❌ عذراً، هذه اللوحة خاصة بالمطور فقط!")
            return
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(types.KeyboardButton("➕ إضافة نقاط"), types.KeyboardButton("➖ خصم نقاط"),
                   types.KeyboardButton("🔗 إضافة روابط"), types.KeyboardButton("📢 إضافة منشور"), types.KeyboardButton("🔙 رجوع للقائمة الرئيسية"))
        bot.send_message(message.chat.id, "⚙ **أهلاً بك في لوحة المطورين:**", reply_markup=markup)

    elif text == "🔙 رجوع للقائمة الرئيسية":
        bot.send_message(message.chat.id, "🏠 القائمة الرئيسية:", reply_markup=main_menu_markup(message.from_user))

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id

    if call.data == "earn_method_1":
        ref_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        text = f"📌 **الطريقة الأولى:**\nشارك رابطك:\n`{ref_link}`\n\n💡 كل شخص ينضم ويجمع 30 نقطة تربح أنت 25 نقطة!"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_earn"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "earn_method_2":
        text = "🔗 **الطريقة الثانية (اختصار الروابط) - V3:**\nاختر أحد الأزرار أدناه (1 إلى 15):"
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(f"زر {i}", callback_data=f"link_btn_{i}") for i in range(1, 16)]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_earn"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "earn_wheel":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🎯 تدوير العجلة الآن", callback_data="do_spin"),
                   types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_earn"))
        bot.edit_message_text("🎡 **الطريقة الثالثة: عجلة الحظ اليومية!**\n\n⏳ يمكنك تدويرها كل 24 ساعة لربح نقاط مجانية.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "back_to_earn":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📌 الطريقة الأولى (رابط الاحالة)", callback_data="earn_method_1"))
        markup.add(types.InlineKeyboardButton("🔗 الطريقة الثانية (اختصار الروابط) - V3", callback_data="earn_method_2"))
        markup.add(types.InlineKeyboardButton("🎡 الطريقة الثالثة (عجلة الحظ)", callback_data="earn_wheel"))
        bot.edit_message_text("🎁 **اختر طريقة تجميع النقاط المناسبة لك:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "do_spin":
        current_time = time.time()
        cursor.execute("SELECT last_spin, spin_step FROM wheel_cooldowns WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and (current_time - row[0] < 86400):
            rem_h = int((86400 - (current_time - row[0])) / 3600)
            bot.answer_callback_query(call.id, f"⏳ انتظر {rem_h} ساعة لتدوير العجلة مجدداً!", show_alert=True)
            return
        
        spin_step = (row[1] + 1) if row else 1
        earned_pts = 3 if spin_step == 1 else (0 if spin_step == 2 else (3 if spin_step == 3 else 1))
            
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (earned_pts, user_id))
        cursor.execute("INSERT OR REPLACE INTO wheel_cooldowns (user_id, last_spin, spin_step) VALUES (?, ?, ?)", (user_id, current_time, spin_step))
        conn.commit()
        
        bot.answer_callback_query(call.id, f"🎉 مبروك! ربحت {earned_pts} نقطة!", show_alert=True)
        bot.edit_message_text(f"🎯 **نتيجة عجلة الحظ:**\n✨ حصلت على: `{earned_pts} نقطة`!", call.message.chat.id, call.message.message_id, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 رجوع", callback_data="earn_wheel")), parse_mode="Markdown")

    elif call.data.startswith("set_link_"):
        if not is_developer(call.from_user):
            bot.answer_callback_query(call.id, "❌ خاصة بالمطور فقط!", show_alert=True)
            return
        btn_id = int(call.data.split("_")[2])
        msg = bot.send_message(call.message.chat.id, f"🔗 أرسل الرابط المختصر الجديد للزر رقم `{btn_id}`:")
        bot.register_next_step_handler(msg, lambda m: save_custom_link(m, btn_id))
        bot.answer_callback_query(call.id)

    elif call.data.startswith("link_btn_"):
        btn_id = int(call.data.split("_")[2])
        current_time = time.time()
        cursor.execute("SELECT last_used FROM user_button_cooldowns WHERE user_id = ? AND button_id = ?", (user_id, btn_id))
        row = cursor.fetchone()
        if row and (current_time - row[0] < 86400):
            bot.answer_callback_query(call.id, "⏳ الزر قيد الانتظار (24 ساعة).", show_alert=True)
            return

        token = str(uuid.uuid4())
        expires_at = current_time + 600
        cursor.execute("INSERT INTO secure_tokens (token, user_id, button_id, expires_at) VALUES (?, ?, ?, ?)", (token, user_id, btn_id, expires_at))
        conn.commit()

        cursor.execute("SELECT url FROM custom_links WHERE button_id = ?", (btn_id,))
        link_row = cursor.fetchone()
        
        base_site_url = link_row[0] if (link_row and link_row[0]) else "https://fury-bot-v3.onrender.com"
        target_url = f"{base_site_url}&token={token}" if "?" in base_site_url else f"{base_site_url}?token={token}"

        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🌐 الانتقال لرابط الاختصار", url=target_url)).add(types.InlineKeyboardButton("🔙 رجوع", callback_data="earn_method_2"))
        bot.edit_message_text(f"🔗 **الزر رقم {btn_id}:**\nاضغط للذهاب لرابط الاختصار وإتمام العملية للحصول على الكود!", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("shop_"):
        shop_type = call.data.split("_")[1]
        items = {"1": "110 جوهرة (220 نقطة)", "2": "220 جوهرة (420 نقطة)", "3": "330 جوهرة (640 نقطة)"}
        item_name = items.get(shop_type, "عرض غير معروف")
        
        msg = f"🛍️ لقد اخترت عرض: {item_name}\n\nللتأكيد، راسل المطور:\n1️⃣ آيدي فري فاير\n2️⃣ آيدي البوت (`{user_id}`)\n3️⃣ اسم العرض 🟢"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💬 مراسلة المطور للتأكيد", url=f"https://t.me/{DEV_USERNAME}"))
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")
def save_custom_link(message, btn_id):
    if not is_developer(message.from_user):
        bot.reply_to(message, "❌ ليس لديك صلاحية!")
        return
    url = message.text.strip()
    cursor.execute("INSERT OR REPLACE INTO custom_links (button_id, url) VALUES (?, ?)", (btn_id, url))
    conn.commit()
    bot.reply_to(message, f"✅ تم حفظ الرابط للزر رقم {btn_id} بنجاح!")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()
    current_time = time.time()
    cursor.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (current_time, user_id))
    conn.commit()

    if text == "🔗 إضافة روابط" and is_developer(message.from_user):
        markup = types.InlineKeyboardMarkup(row_width=5)
        buttons = [types.InlineKeyboardButton(f"رابط {i}", callback_data=f"set_link_{i}") for i in range(1, 16)]
        markup.add(*buttons)
        bot.send_message(message.chat.id, "🔗 **اختر الزر (1 إلى 15) لتعديل رابطه:**", reply_markup=markup)
        return

    elif text == "➕ إضافة نقاط" and is_developer(message.from_user):
        msg = bot.send_message(message.chat.id, "➕ أرسل الآيدي والنقاط هكذا:\n`ID Points`")
        bot.register_next_step_handler(msg, process_add_points)
        return

    elif text == "➖ خصم نقاط" and is_developer(message.from_user):
        msg = bot.send_message(message.chat.id, "➖ أرسل الآيدي والنقاط هكذا:\n`ID Points`")
        bot.register_next_step_handler(msg, process_sub_points)
        return

    elif text == "📢 إضافة منشور" and is_developer(message.from_user):
        msg = bot.send_message(message.chat.id, "📢 أرسل المنشور لإرساله للجميع:")
        bot.register_next_step_handler(msg, process_broadcast)
        return

    cursor.execute("SELECT fail_count, ban_until, ban_level FROM user_bans WHERE user_id = ?", (user_id,))
    ban_data = cursor.fetchone()
    if ban_data and current_time < ban_data[1]:
        bot.reply_to(message, f"❌ حسابك محظور مؤقتاً لمدة `{int((ban_data[1] - current_time) / 60)}` دقيقة.", parse_mode="Markdown")
        return

    if 8 <= len(text) <= 16:
        cursor.execute("SELECT token, button_id, is_used FROM secure_tokens WHERE generated_code = ? AND user_id = ?", (text, user_id))
        token_row = cursor.fetchone()
        if token_row:
            if token_row[2] == 1:
                bot.reply_to(message, "⚠ هذا الكود مستخدم من قبل!", parse_mode="Markdown")
                return
            cursor.execute("UPDATE secure_tokens SET is_used = 1 WHERE token = ?", (token_row[0],))
            cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (user_id,))
            cursor.execute("INSERT OR REPLACE INTO user_button_cooldowns (user_id, button_id, last_used) VALUES (?, ?, ?)", (user_id, token_row[1], current_time))
            cursor.execute("DELETE FROM user_bans WHERE user_id = ?", (user_id,))
            conn.commit()
            bot.reply_to(message, "🎉 **تهانينا! الكود صحيح وتم إضافة `1 نقطة` بنجاح!** 🔥", parse_mode="Markdown")
            return
        else:
            handle_failed_code(message, user_id)
            return

def handle_failed_code(message, user_id):
    current_time = time.time()
    cursor.execute("SELECT fail_count, ban_level FROM user_bans WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    fail_count = (row[0] + 1) if row else 1
    ban_level = row[1] if row else 0

    if fail_count >= 3:
        ban_level += 1
        ban_duration = 600 if ban_level == 1 else (3600 if ban_level == 2 else 86400)
        cursor.execute("INSERT OR REPLACE INTO user_bans (user_id, fail_count, ban_until, ban_level) VALUES (?, 0, ?, ?)", (user_id, current_time + ban_duration, ban_level))
        conn.commit()
        bot.reply_to(message, f"❌ خطأ 3 مرات! تم حظرك مؤقتاً لمدة `{int(ban_duration / 60)}` دقيقة.", parse_mode="Markdown")
    else:
        cursor.execute("INSERT OR REPLACE INTO user_bans (user_id, fail_count, ban_until, ban_level) VALUES (?, ?, 0, ?)", (user_id, fail_count, ban_level))
        conn.commit()
        bot.reply_to(message, f"❌ كود خاطئ! تتبقى لك `{3 - fail_count}` محاولات.", parse_mode="Markdown")

def process_add_points(message):
    if not is_developer(message.from_user): return
    try:
        p = message.text.split()
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (int(p[1]), int(p[0])))
        conn.commit()
        bot.reply_to(message, "✅ تمت الإضافة بنجاح.")
    except Exception: bot.reply_to(message, "❌ خطأ في الصيغة.")

def process_sub_points(message):
    if not is_developer(message.from_user): return
    try:
        p = message.text.split()
        cursor.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (int(p[1]), int(p[0])))
        conn.commit()
        bot.reply_to(message, "✅ تم الخصم بنجاح.
    except Exception: bot.reply_to(message, "❌ خطأ في الصيغة.")

def process_broadcast(message):
    if not is_developer(message.from_user): return
    success = sum(1 for u in cursor.execute("SELECT user_id FROM users").fetchall() if bot.send_message(u[0], message.text))
    bot.reply_to(message, f"📢 تم الإرسال إلى {success} مستخدماً.")

HTML_TEMPLATE = """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>FURY SYSTEM V3</title>
<style>body{background:#0f172a;color:#f8fafc;font-family:Tahoma;text-align:center;padding:20px}.container{max-width:400px;margin:40px auto;background:#1e293b;padding:25px;border-radius:15px}input{width:90%;padding:12px;margin:15px 0;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;text-align:center}button{background:#22c55e;color:#fff;border:none;padding:12px;border-radius:8px;width:100%;font-weight:bold;cursor:pointer}.error{color:#ef4444;font-weight:bold}.success{color:#22c55e;font-size:20px;font-weight:bold;background:#0f172a;padding:15px;border-radius:8px;border:1px dashed #22c55e}</style></head>
<body><div class="container"><h2>نظام التحقق (V3)</h2>
{% if error %}<p class="error">{{ error }}</p>{% elif code %}<p>الكود الخاص بك:</p><div class="success">{{ code }}</div>{% else %}
<form method=HTML_TEMPLATE = """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>FURY SYSTEM V3</title>
<style>body{background:#0f172a;color:#f8fafc;font-family:Tahoma;text-align:center;padding:20px}.container{max-width:400px;margin:40px auto;background:#1e293b;padding:25px;border-radius:15px}input{width:90%;padding:12px;margin:15px 0;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;text-align:center}button{background:#22c55e;color:#fff;border:none;padding:12px;border-radius:8px;width:100%;font-weight:bold;cursor:pointer}.error{color:#ef4444;font-weight:bold}.success{color:#22c55e;font-size:20px;font-weight:bold;background:#0f172a;padding:15px;border-radius:8px;border:1px dashed #22c55e}</style></head><body><div class="container"><h2>🔥 نظام التحقق (V3)</h2>
{% if error %}<p class="error">{{ error }}</p>{% elif code %}<p>الكود الخاص بك:</p><div class="success">{{ code }}</div>{% else %}
<form method="POST"><input type="number" name="telegram_id" placeholder="أدخل ايدي حسابك داخل البوت للتحقق منك" required><button type="submit">إرسال</button></form>{% endif %}</div></body></html>"""

@app.route("/", methods=["GET", "POST"])
def verify_page():
    token = request.args.get("token")
    if not token: return render_template_string(HTML_TEMPLATE, error="❌ خطأ: رابط غير صالح!")
    row = cursor.execute("SELECT user_id, button_id, is_used, expires_at FROM secure_tokens WHERE token = ?", (token,)).fetchone()
    if not row or row[2] == 1 or time.time() > row[3]: return render_template_string(HTML_TEMPLATE, error="❌ الرابط منتهي أو مستهلك!")
    
    if request.method == "POST":
        if str(row[0]) != str(request.form.get("telegram_id")): return render_template_string(HTML_TEMPLATE, error="❌ الآيدي غير مطابق!")
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
        cursor.execute("UPDATE secure_tokens SET generated_code = ? WHERE token = ?", (code, token))
        conn.commit()
        return render_template_string(HTML_TEMPLATE, code=code)
    return render_template_string(HTML_TEMPLATE)

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# تشغيل البوت في الخلفية عند بداية الخدمة
threading.Thread(target=lambda: bot.infinity_polling(timeout=60, long_polling_timeout=60), daemon=True).start()

if __name__ == "__main__":
    run_flask()

