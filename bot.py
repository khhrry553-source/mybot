import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import imageio_ffmpeg

# تعيين التوكن مباشرة هنا لتجنب أي مشاكل في قراءته من المنصة
TOKEN = "8786365418:AAFhRMXC-cYelDMbmGrwPk6GSHE0RQRjrTY"
bot = telebot.TeleBot(TOKEN)

TEMP_DIR = "downloads"
os.makedirs(TEMP_DIR, exist_ok=True)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message,
        "مرحباً بك في بوت تحسين جودة الفيديوهات لتيك توك 🚀\n\n"
        "أرسل لي أي فيديو وسأقوم برفع دقته وتحسين إطاراته فوراً!"
    )

@bot.message_handler(content_types=['video'])
def handle_video(message):
    input_path = None
    output_path = None
    try:
        msg = bot.reply_to(message, "⏳ جاري استلام الفيديو وبدء معالجة الجودة...")

        file_info = bot.get_file(message.video.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        input_path = os.path.join(TEMP_DIR, f"input_{message.chat.id}.mp4")
        output_path = os.path.join(TEMP_DIR, f"output_{message.chat.id}.mp4")

        with open(input_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        bot.edit_message_text("⚙️ جاري رفع دقة الفيديو وضبط الإطارات (60 FPS)...", message.chat.id, msg.message_id)

        # الحصول على مسار FFmpeg المدمج تلقائياً عبر بايثون
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        import subprocess
        command = [
            ffmpeg_exe, '-y', '-i', input_path,
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=60',
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
            '-c:a', 'aac', '-b:a', '192k',
            output_path
        ]

        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        bot.edit_message_text("📤 جاري إرسال الفيديو المحسن بجودة عالية...", message.chat.id, msg.message_id)

        with open(output_path, 'rb') as video_file:
            markup = InlineKeyboardMarkup()
            tiktok_url = "https://www.tiktok.com/creator-center/upload"
            btn_tiktok = InlineKeyboardButton("🚀 فتح تيك توك والنشر بجودة عالية", url=tiktok_url)
            markup.add(btn_tiktok)

            bot.send_video(
                message.chat.id,
                video_file,
                caption="✨ **تم تحسين الفيديو بنجاح!**\n\n- الدقة: 1080x1920 (Full HD)\n- الإطارات: 60 FPS\n\nاضغط أدناه لفتح تيك توك ورفع الفيديو:",
                reply_markup=markup,
                parse_mode="Markdown"
            )

        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ أثناء معالجة الفيديو:\n`{str(e)}`")
    
    finally:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)

if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
