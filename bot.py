import json
import os
import telebot
from telebot import types

TOKEN = "8765104365:AAFPTCvIRu7YsC2ljqvmRAsXyQeBAa7yP7s"
bot = telebot.TeleBot(TOKEN)

CHANNELS = [
    {"title": "قناة 1", "username": "F_ONDRAY_FF", "url": "https://t.me/F_ONDRAY_FF"},
    {"title": "قناة 2", "username": "setupvedeo", "url": "https://t.me/setupvedeo"},
    {"title": "قناة 3", "username": "shadowxtn", "url": "https://t.me/shadowxtn"},
]

MAIN_DEV = "raouf100K"
DATA_FILE = "bot_data.json"
user_states = {}


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("code", "FREEFIRE-CODE-2026")
            data.setdefault("devs", [])
            return data
    return {"code": "FREEFIRE-CODE-2026", "devs": []}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


bot_data = load_data()


def is_dev(user):
    if not user or not user.username:
        return False
    uname = user.username.lstrip("@").lower()
    allowed = {MAIN_DEV.lower()} | {d.lstrip("@").lower() for d in bot_data["devs"]}
    return uname in allowed


def check_channels_status(user_id):
    joined = []
    missing = []
    valid_statuses = {"creator", "administrator", "member", "restricted"}

    for ch in CHANNELS:
        try:
            member = bot.get_chat_member(f"@{ch['username']}", user_id)
            if member.status in valid_statuses:
                joined.append(ch)
            else:
                missing.append(ch)
        except Exception:
            missing.append(ch)

    return joined, missing


def build_start_keyboard(user):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for idx, ch in enumerate(CHANNELS, start=1):
        kb.add(types.InlineKeyboardButton(text=f"📢 اشترك في {ch['title']} (@{ch['username']})", url=ch["url"]))
    kb.add(types.InlineKeyboardButton(text="🎁 الحصول على الكود", callback_data="get_code"))
    kb.add(types.InlineKeyboardButton(text="🛠️ لوحة المطورين", callback_data="dev_panel"))
    return kb
        @bot.message_handler(commands=["start"])
def handle_start(message):
    user_states.pop(message.from_user.id, None)
    text = (
        "أهلاً بك 👋\n\n"
        "للحصول على الكود، يجب الاشتراك في القنوات التالية أولاً ثم الضغط على زر **الحصول على الكود**:"
    )
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=build_start_keyboard(message.from_user),
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user = call.from_user
    chat_id = call.message.chat.id

    if call.data == "get_code":
        joined, missing = check_channels_status(user.id)
        total = len(CHANNELS)

        if len(missing) == total:
            bot.answer_callback_query(call.id, "لم تشترك في القنوات بعد!", show_alert=False)
            bot.send_message(
                chat_id,
                "❌ لم تشترك في القنوات بعد. يرجى الاشتراك في جميع القنوات ثم المحاولة مرة أخرى.",
                reply_markup=build_start_keyboard(user),
            )
        elif len(missing) > 0:
            missing_names = "\n".join([f"• @{c['username']}" for c in missing])
            bot.answer_callback_query(call.id, "لم تشترك في باقي القنوات!", show_alert=False)
            bot.send_message(
                chat_id,
                f"⚠️ لم تشترك في باقي القنوات ({len(joined)}/{total} مكتمل).\n\nالقنوات المتبقية:\n{missing_names}",
                reply_markup=build_start_keyboard(user),
            )
        else:
            bot.answer_callback_query(call.id, "تم التحقق من اشتراكك بنجاح ✅")
            bot.send_message(
                chat_id,
                f"✅ تم التحقق من اشتراكك في جميع القنوات!\n\n🔑 الكود الخاص بك هو:\n`{bot_data['code']}`",
                parse_mode="Markdown",
            )

    elif call.data == "dev_panel":
        if not is_dev(user):
            bot.answer_callback_query(call.id, "غير مصرح لك بالدخول إلى لوحة المطورين.", show_alert=True)
            return

        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton(text="✏️ تعديل الكود", callback_data="dev_edit_code"))
        kb.add(types.InlineKeyboardButton(text="➕ إضافة مطور جديد", callback_data="dev_add_dev"))
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            f"🛠️ **لوحة المطورين**\nالكود الحالي: `{bot_data['code']}`",
            reply_markup=kb,
            parse_mode="Markdown",
        )

    elif call.data == "dev_edit_code":
        if not is_dev(user):
            bot.answer_callback_query(call.id, "غير مصرح لك.", show_alert=True)
            return
        user_states[user.id] = "waiting_new_code"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "✍️ أرسل الكود الجديد الآن:")

    elif call.data == "dev_add_dev":
        if not is_dev(user):
            bot.answer_callback_query(call.id, "غير مصرح لك.", show_alert=True)
            return
        user_states[user.id] = "waiting_new_dev"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "👤 أرسل يوزرنام المطور الجديد (مثال: `@username` أو `username`):")


@bot.message_handler(func=lambda msg: msg.from_user.id in user_states)
def handle_dev_inputs(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    text = (message.text or "").strip()

    if not is_dev(message.from_user):
        user_states.pop(user_id, None)
        bot.send_message(message.chat.id, "غير مصرح لك.")
        return

    if state == "waiting_new_code":
        if not text:
            bot.send_message(message.chat.id, "❌ الكود لا يمكن أن يكون فارغاً، أعد إرساله:")
            return
        bot_data["code"] = text
        save_data(bot_data)
        user_states.pop(user_id, None)
        bot.send_message(message.chat.id, "✅ تم حفظه بنجاح")

    elif state == "waiting_new_dev":
        clean_username = text.lstrip("@").strip()
        if not clean_username:
            bot.send_message(message.chat.id, "❌ يرجى إدخال يوزرنام صحيح:")
            return
        existing = {d.lstrip("@").lower() for d in bot_data["devs"]} | {MAIN_DEV.lower()}
        if clean_username.lower() not in existing:
            bot_data["devs"].append(clean_username)
            save_data(bot_data)
        user_states.pop(user_id, None)
        bot.send_message(message.chat.id, f"✅ تمت إضافة @{clean_username} كمطور بنجاح.")


if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling(skip_pending=True)
      
