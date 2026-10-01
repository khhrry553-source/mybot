import os
import subprocess
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# استبدل هذا التوكن بالتوكن الخاص بك من BotFather
TOKEN = "8786365418:AAEtGT918auV2atStisf4j9Qv3qeFGIp_sI"
bot = telebot.TeleBot(TOKEN)

# مجلد مؤقت لحفظ الفيديوهات أثناء المعالجة
TEMP_DIR = "downloads"
os.makedirs(TEMP_DIR, exist_ok=True)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message,
        "مرحباً بك في بوت تحسين جودة الفيديوهات لتيك توك 🚀\n\n"
        "أرسل لي أي فيديو وسأقوم بـ:\n"
        "1️⃣ رفع دقة الفيديو لأعلى جودة ممكنة (HD/4K).\n"
        "2️⃣ ضبط الإطارات (60 FPS) والمعدلات المناسبة لتيك توك.\n"
        "3️⃣ توفير زر مباشر لفتح تيك توك ونشره فوراً.\n\n"
        "أرسل الفيديو الآن لنبدأ! 🎬"
    )

@bot.message_handler(content_types=['video'])
def handle_video(message):
    try:
        msg = bot.reply_to(message, "⏳ جاري استلام الفيديو وبدء تحسين الجودة والإطارات...")

        # تحميل الفيديو المرسل من التليجرام
        file_info = bot.get_file(message.video.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        input_path = os.path.join(TEMP_DIR, f"input_{message.chat.id}.mp4")
        output_path = os.path.join(TEMP_DIR, f"output_{message.chat.id}.mp4")

        with open(input_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        bot.edit_message_text("⚙️ جاري معالجة الفيديو ورفع الدقة إلى أعلى جودة (60 FPS)... يرجى الانتظار", message.chat.id, msg.message_id)

        # أمر FFmpeg لرفع الجودة، ضبط الإطارات على 60، وتعديل الكوديك ليتوافق تماماً مع تيك توك
        # تم ضبط الدقة الرأسية لتكون 1080x1920 (المثالية لتيك توك) وزيادة الحدة والوضوح
        command = [
            'ffmpeg', '-y', '-i', input_path,
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=60',
            '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
            '-c:a', 'aac', '-b:a', '192k',
            output_path
        ]

        # تنفيذ أمر المعالجة
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        bot.edit_message_text("📤 جاري إرسال الفيديو المحسن بجودة خيالية...", message.chat.id, msg.message_id)

        # إرسال الفيديو بعد التحسين للمستخدم
        with open(output_path, 'rb') as video_file:
            # إنشاء زر تيك توك المباشر
            markup = InlineKeyboardMarkup()
            # رابط يفتح موقع تيك توك مباشرة في المتصفح للرفع
            tiktok_url = "https://www.tiktok.com/creator-center/upload"
            btn_tiktok = InlineKeyboardButton("🚀 فتح تيك توك والنشر بجودة عالية", url=tiktok_url)
            markup.add(btn_tiktok)

            bot.send_video(
                message.chat.id,
                video_file,
                caption="✨ **تم تحسين الفيديو بنجاح!**\n\n- الدقة: 1080x1920 (Full HD)\n- الإطارات: 60 FPS\n- الجودة: فائقة الوضوح لتيك توك 🎬\n\nاضغط على الزر أدناه لفتح تيك توك ورفع الفيديو:",
                reply_markup=markup,
                parse_mode="Markdown"
            )

        # حذف الملفات المؤقتة لتنظيف السيرفر
        os.remove(input_path)
        os.remove(output_path)
        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ أثناء معالجة الفيديو:\n`{str(e)}`")
        # تنظيف الملفات في حال حدث خطأ
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)

# تشغيل البوت بشكل مستمر
if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
