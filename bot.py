import json
import os
import telebot
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN", "8765104365:AAFPTCvIRu7YsC2ljqvmRAsXyQeBAa7yP7s")
bot = telebot.TeleBot(BOT_TOKEN)

CHANNELS = [
    {"name": "قناة F_ONDRAY_FF", "username": "@F_ONDRAY_FF", "url": "https://t.me/F_ONDRAY_FF"},
    {"name": "قناة setupvedeo", "username": "@setupvedeo", "url": "https://t.me/setupvedeo"},
    {"name": "قناة shadowxtn", "username": "@shadowxtn", "url": "https://t.me/shadowxtn"},
]

DATA_FILE = "bot_data.json"
MAIN_DEV = "raouf100K"

# حالات انتظار إدخال من المطور: {user_id: "waiting_code" | "waiting_dev"}
dev_states = {}


def load_data():
    default_data = {
        "reward_code": "CODE-2026-FREE",
        "devs": [MAIN_DEV.lower()]
    }
    if not os.path.exists(DATA_FILE):
        save_data(default_data)
        return default_data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "reward_code" not in data:
                data["reward_code"] = default_data["reward_code"]
            if "devs" not in data or not isinstance(data["devs"], list):
                data["devs"] = [MAIN_DEV.lower()]
            if MAIN_DEV.lower() not in [d.lower() for d in data["devs"]]:
                data["devs"].append(MAIN_DEV.lower())
            return data
    except Exception:
        return default_data


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_developer(user):
    if not user or not user.username:
        return False
    data = load_data()
    return user.username.lstrip("@").lower() in [d.lower() for d in data.get("devs", [])]


def check_subscriptions(user_id):
    subscribed = []
    not_subscribed = []
    valid_statuses = {"member", "administrator", "creator"}

    for ch in CHANNELS:
        try:
            member = bot.get_chat_member(ch["username"], user_id)
            if member.status in valid_statuses:
                subscribed.append(ch)
            else:
                not_subscribed.append(ch)
        except Exception:
            not_subscribed.append(ch)

    return subscribed, not_subscribed


def build_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in CHANNELS:
        markup.add(types.InlineKeyboardButton(text=f"📢 اشترك في {ch['name']}", url=ch["url"]))
    markup.add(types.InlineKeyboardButton(text="🎁 الحصول على الكود", callback_data="get_code"))
    markup.add(types.InlineKeyboardButton(text="🛠️ لوحة المطورين", callback_data="dev_panel"))
    return markup


def build_dev_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(text="✏️ تعديل الكود", callback_data="edit_code"))
    markup.add(types.InlineKeyboardButton(text="➕ اضافة مطور جديد", callback_data="add_dev"))
    markup.add(types.InlineKeyboardButton(text="🔙 رجوع للقائمة الرئيسية", callback_data="back_main"))
    return markup


@bot.message_handler(commands=["start"])
def handle_start(message):
    user_id = message.from_user.id
    if user_id in dev_states:
        del dev_states[user_id]

    text = (
        "أهلاً بك 👋\n\n"
        "للحصول على الكود، يجب عليك الاشتراك أولاً في القنوات التالية ثم الضغط على زر **الحصول على الكود**:\n"
        "1️⃣ https://t.me/F_ONDRAY_FF\n"
        "2️⃣ https://t.me/setupvedeo\n"
        "3️⃣ https://t.me/shadowxtn"
    )
    bot.send_message(message.chat.id, text, reply_markup=build_main_keyboard(), disable_web_page_preview=True)


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user = call.from_user
    user_id = user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if call.data == "back_main":
        if user_id in dev_states:
            del dev_states[user_id]
        text = (
            "أهلاً بك 👋\n\n"
            "اشترك في القنوات الثلاث ثم اضغط على **الحصول على الكود**:\n"
            "• https://t.me/F_ONDRAY_FF\n"
            "• https://t.me/setupvedeo\n"
            "• https://t.me/shadowxtn"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=build_main_keyboard(), disable_web_page_preview=True)
        bot.answer_callback_query(call.id)
        return

    if call.data == "get_code":
        subscribed, not_subscribed = check_subscriptions(user_id)
        total = len(CHANNELS)
        sub_count = len(subscribed)

        if sub_count == 0:
            bot.answer_callback_query(call.id, "❌ لم تشترك في أي قناة بعد!", show_alert=True)
            msg = (
                "❌ **اشترك في القنوات أولاً!**\n\n"
                "لم تقم بالاشتراك في أي قناة من القنوات المطلوبة. اشترك في جميع القنوات ثم أعد المحاولة."
            )
            bot.send_message(chat_id, msg, reply_markup=build_main_keyboard(), disable_web_page_preview=True)
            return

        if 0 < sub_count < total:
            missing_links = "\n".join([f"• {ch['url']}" for ch in not_subscribed])
            bot.answer_callback_query(call.id, "⚠️ لم تكمل الاشتراك في باقي القنوات!", show_alert=True)
            msg = (
                f"⚠️ **لم تشترك في باقي القنوات!**\n\n"
                f"لقد اشتركت في ({sub_count} من {total}) قنوات فقط.\n"
                f"القنوات المتبقية التي يجب الاشتراك فيها:\n{missing_links}\n\n"
                "بعد الاشتراك في الكل اضغط على **الحصول على الكود** مرة أخرى."
            )
            bot.send_message(chat_id, msg, reply_markup=build_main_keyboard(), disable_web_page_preview=True)
            return

        # اشترك في جميع القنوات
        data = load_data()
        current_code = data.get("reward_code", "")
        bot.answer_callback_query(call.id, "✅ تم التحقق من اشتراكك بنجاح!")
        msg = (
            "🎉 **مبروك! لقد اشتركت في جميع القنوات.**\n\n"
            f"🔑 **الكود الخاص بك هو:**\n`{current_code}`"
        )
        bot.send_message(chat_id, msg, parse_mode="Markdown")
        return

    if call.data == "dev_panel":
        if not is_developer(user):
            bot.answer_callback_query(call.id, "⛔ عذراً، هذا الزر مخصص للمطورين فقط!", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        data = load_data()
        devs_text = ", ".join([f"@{d}" for d in data.get("devs", [])])
        panel_text = (
            "🛠️ **مرحباً بك في لوحة المطورين**\n\n"
            f"🔑 الكود الحالي: `{data.get('reward_code', '')}`\n"
            f"👥 المطورون الحاليون: {devs_text}\n\n"
            "اختر الإجراء المطلوب:"
        )
        bot.edit_message_text(panel_text, chat_id, message_id, parse_mode="Markdown", reply_markup=build_dev_keyboard())
        return

    if call.data == "edit_code":
        if not is_developer(user):
            bot.answer_callback_query(call.id, "⛔ غير مسموح لك بالدخول هنا!", show_alert=True)
            return

        dev_states[user_id] = "waiting_code"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "✏️ **أدخل الكود الجديد الذي تريد أن يظهر للمستخدمين عند الاشتراك:**", parse_mode="Markdown")
        return

    if call.data == "add_dev":
        if not is_developer(user):
            bot.answer_callback_query(call.id, "⛔ غير مسموح لك بالدخول هنا!", show_alert=True)
            return

        dev_states[user_id] = "waiting_dev"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "➕ **أدخل يوزرنيم المطور الجديد (مثال: @username أو username):**", parse_mode="Markdown")
        return


@bot.message_handler(func=lambda message: message.from_user.id in dev_states)
def handle_dev_inputs(message):
    user = message.from_user
    user_id = user.id

    if not is_developer(user):
        dev_states.pop(user_id, None)
        bot.send_message(message.chat.id, "⛔ ليس لديك صلاحية المطور.")
        return

    state = dev_states.get(user_id)
    text_input = (message.text or "").strip()

    if not text_input:
        bot.send_message(message.chat.id, "⚠️ يرجى إرسال نص صحيح.")
        return

    data = load_data()

    if state == "waiting_code":
        data["reward_code"] = text_input
        save_data(data)
        del dev_states[user_id]
        bot.send_message(
            message.chat.id,
            f"✅ **تم حفظ الكود بنجاح!**\n\n🔑 الكود الجديد: `{text_input}`",
            parse_mode="Markdown",
            reply_markup=build_dev_keyboard()
        )

    elif state == "waiting_dev":
        clean_username = text_input.lstrip("@").strip().lower()
        if not clean_username:
            bot.send_message(message.chat.id, "⚠️ يوزرنيم غير صالح، أعد المحاولة.")
            return

        devs_lower = [d.lower() for d in data.get("devs", [])]
        if clean_username not in devs_lower:
            data["devs"].append(clean_username)
            save_data(data)

        del dev_states[user_id]
        bot.send_message(
            message.chat.id,
            f"✅ **تمت إضافة المطور بنجاح!**\n\n👤 المطور: `@{clean_username}`\nأصبح الآن قادراً على الدخول إلى لوحة المطورين.",
            parse_mode="Markdown",
            reply_markup=build_dev_keyboard()
        )


if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling(skip_pending=True)
  
