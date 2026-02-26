#!/usr/bin/env python3
"""
Dori Ma'lumot Boti - Soddalashtirilgan versiya
"""

import sys
import subprocess
import logging
import os
import re
from datetime import datetime

# Kerakli kutubxonalarni o'rnatish
print("📦 Kutubxonalarni tekshirish...")

try:
    import pandas as pd
    print("✅ pandas o'rnatilgan")
except ImportError:
    print("⚠️ pandas o'rnatilmoqda...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas"])
    import pandas as pd

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler
    from telegram.constants import ParseMode
    print("✅ python-telegram-bot o'rnatilgan")
except ImportError:
    print("⚠️ telegram bot o'rnatilmoqda...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-telegram-bot==20.7"])
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler
    from telegram.constants import ParseMode

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    logger.error("❌ BOT_TOKEN o'rnatilmagan!")
    logger.error("Railway.app -> Variables bo'limida BOT_TOKEN ni o'rnating")
    sys.exit(1)

# Conversation states
(ASOSIY_MENYU, DORI_QIDIRISH) = range(2)

# ======================================================
# SODDA MA'LUMOTLAR BAZASI (TEST UCHUN)
# ======================================================

class SimpleDatabase:
    def __init__(self):
        self.drugs = []
        self.load_test_data()
    
    def load_test_data(self):
        """Test ma'lumotlari - ishlashi uchun"""
        self.drugs = [
            {"name": "Paratsetamol", "manufacturer": "Nika Pharm", "country": "O'zbekiston", "form": "Tabletka 500 mg"},
            {"name": "Ibuprofen", "manufacturer": "Berlin-Chemie", "country": "Germaniya", "form": "Tabletka 400 mg"},
            {"name": "Amoksitsillin", "manufacturer": "Sandoz", "country": "Avstriya", "form": "Kapsula 500 mg"},
            {"name": "Setirizin", "manufacturer": "Zentiva", "country": "Chexiya", "form": "Tabletka 10 mg"},
            {"name": "Omeprazol", "manufacturer": "KRKA", "country": "Sloveniya", "form": "Kapsula 20 mg"},
        ]
        logger.info(f"✅ Test ma'lumotlari: {len(self.drugs)} ta dori")
        
        # Excel fayllarni yuklashga urinish
        try:
            excel_files = [
                ("substansiya.xls", "substansiya"),
                ("invivo.xls", "invivo"),
                ("medtexnika.xls", "texnika"),
                ("diagnostika.xls", "diagnostika"),
                ("annullangan.xls", "annullangan"),
            ]
            
            for filename, ftype in excel_files:
                if os.path.exists(filename):
                    try:
                        df = pd.read_excel(filename)
                        logger.info(f"✅ {filename} yuklandi: {len(df)} qator")
                        
                        # Birinchi ustundan nomlarni olish
                        first_col = df.columns[0]
                        for _, row in df.iterrows():
                            if pd.notna(row[first_col]) and len(str(row[first_col])) > 3:
                                self.drugs.append({
                                    "name": str(row[first_col])[:100],
                                    "manufacturer": "Ma'lumot bazasidan",
                                    "country": "O'zbekiston",
                                    "form": ftype,
                                    "source": filename
                                })
                    except Exception as e:
                        logger.warning(f"❌ {filename} yuklashda xato: {e}")
        except Exception as e:
            logger.warning(f"Excel fayllarni yuklashda xato: {e}")
    
    def search(self, query):
        """Oddiy qidiruv"""
        query = query.lower().strip()
        results = []
        
        for drug in self.drugs:
            if query in drug["name"].lower():
                results.append(drug)
        
        return results[:10]

# Ma'lumotlar bazasi
db = SimpleDatabase()

# ======================================================
# KLAVIATURALAR
# ======================================================

def main_keyboard():
    """Asosiy menyu"""
    keyboard = [
        [KeyboardButton("💊 Dori qidirish"), KeyboardButton("📍 Yaqin aptekalar")],
        [KeyboardButton("❓ Yordam")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def location_keyboard():
    """Lokatsiya yuborish tugmasi"""
    keyboard = [
        [KeyboardButton("📍 Lokatsiyani yuborish", request_location=True)],
        [KeyboardButton("🏠 Asosiy menyu")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ======================================================
# HANDLERLAR
# ======================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi"""
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Assalomu alaykum, *{user.first_name}*!\n\n"
        "💊 Dori nomini yozing yoki pastdagi tugmalardan foydalaning",
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menyu tugmalarini boshqarish"""
    text = update.message.text
    
    if text == "💊 Dori qidirish":
        await update.message.reply_text(
            "🔍 Qidirmoqchi bo'lgan dori nomini yozing:",
            reply_markup=main_keyboard()
        )
        return DORI_QIDIRISH
    
    elif text == "📍 Yaqin aptekalar":
        await update.message.reply_text(
            "📍 Iltimos, lokatsiyangizni yuboring.\n"
            "Men sizga eng yaqin aptekalarni ko'rsataman.",
            reply_markup=location_keyboard()
        )
    
    elif text == "❓ Yordam":
        await update.message.reply_text(
            "❓ *Yordam*\n\n"
            "• Dori nomini yozing - men ma'lumot beraman\n"
            "• Lokatsiya yuboring - yaqin aptekalarni ko'rsataman\n"
            "• /start - qayta ishga tushirish",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif text == "🏠 Asosiy menyu":
        await update.message.reply_text(
            "🏠 Asosiy menyu",
            reply_markup=main_keyboard()
        )
    
    return ASOSIY_MENYU

async def handle_drug_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dori qidirish"""
    query = update.message.text.strip()
    
    if query == "🏠 Asosiy menyu":
        await update.message.reply_text(
            "🏠 Asosiy menyu",
            reply_markup=main_keyboard()
        )
        return ASOSIY_MENYU
    
    # Qidirish
    await update.message.reply_text(f"🔍 '{query}' qidirilmoqda...")
    
    results = db.search(query)
    
    if results:
        for drug in results[:3]:  # Eng ko'pi 3 ta
            text = (
                f"💊 *{drug['name']}*\n"
                f"🏭 *Ishlab chiqaruvchi:* {drug['manufacturer']}\n"
                f"🌍 *Davlat:* {drug['country']}\n"
                f"📦 *Shakli:* {drug['form']}\n"
            )
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
        if len(results) > 3:
            await update.message.reply_text(f"… va yana {len(results)-3} ta natija")
    else:
        # Topilmadi
        text = (
            f"❌ *{query}* O'zbekiston aptekalarida topilmadi.\n\n"
            "💡 *Takliflar:*\n"
            "• Nomni to'g'ri yozganingizni tekshiring\n"
            "• Qisqaroq nom bilan qidiring\n"
            "• Lotin alifbosida yozing\n\n"
            "🌍 *Xorijdan sotib olish:*\n"
            "  • [eapteka.ru](https://eapteka.ru)\n"
            "  • [apteka.ru](https://apteka.ru)\n"
            "  • [iherb.com](https://iherb.com)\n\n"
            "📦 Yetkazib berish: CDEK, DHL"
        )
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Yangi qidiruv", callback_data="new_search")
        ]])
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    
    return ASOSIY_MENYU

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lokatsiyani qabul qilish"""
    location = update.message.location
    
    # Demo aptekalar
    pharmacies = [
        {"name": "Arzon Apteka", "address": "Chilonzor, 21", "distance": "0.8 km", "phone": "+99871 123-45-67"},
        {"name": "Oxana Apteka", "address": "Beruniy, 41", "distance": "1.2 km", "phone": "+99871 234-56-78"},
        {"name": "Dorixona 24", "address": "Amir Temur, 15", "distance": "2.5 km", "phone": "+99871 345-67-89"},
    ]
    
    text = "📍 *Sizga yaqin aptekalar:*\n\n"
    for i, ph in enumerate(pharmacies, 1):
        text += f"{i}. *{ph['name']}*\n"
        text += f"   📍 {ph['address']}\n"
        text += f"   📞 {ph['phone']}\n"
        text += f"   📏 {ph['distance']}\n\n"
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )
    
    return ASOSIY_MENYU

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback query larni boshqarish"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "new_search":
        await query.message.reply_text(
            "🔍 Qidirmoqchi bo'lgan dori nomini yozing:",
            reply_markup=main_keyboard()
        )

# ======================================================
# MAIN
# ======================================================

def main():
    """Asosiy funksiya"""
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Conversation handler
        conv_handler = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex("^(💊 Dori qidirish)$"), handle_menu),
            ],
            states={
                DORI_QIDIRISH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_drug_search)],
            },
            fallbacks=[CommandHandler("start", start)],
            per_message=False,
        )
        
        # Handlerlar
        app.add_handler(CommandHandler("start", start))
        app.add_handler(conv_handler)
        app.add_handler(MessageHandler(filters.LOCATION, handle_location))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
        app.add_handler(CallbackQueryHandler(handle_callback))
        
        logger.info("=" * 50)
        logger.info("🤖 Dori Bot ishga tushdi!")
        logger.info("=" * 50)
        
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"❌ Xato: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
