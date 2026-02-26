#!/usr/bin/env python3
"""
Dori Ma'lumot Boti v4.0 - Rasmiy ma'lumotlar bazasi
O'zbekiston Respublikasi Sog'liqni Saqlash Vazirligi ma'lumotlari asosida
"""

import asyncio
import logging
import os
import re
import json
import aiohttp
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from telegram.constants import ParseMode

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Conversation states
(ASOSIY_MENYU, DORI_QIDIRISH, TEXNIKA_QIDIRISH, DIAGNOSTIKA_QIDIRISH) = range(4)

# ============================================================================
# MA'LUMOTLAR BAZASI KLASSI
# ============================================================================

class MedicineDatabase:
    """Dorilar va tibbiy buyumlar ma'lumotlar bazasi"""
    
    def __init__(self):
        self.drugs = []          # Dorilar ro'yxati
        self.tech = []           # Tibbiy texnika
        self.diagnostics = []    # In vitro diagnostika
        self.annulled_drugs = [] # Annullangan dorilar
        self.annulled_tech = []  # Annullangan texnika
        self.load_data()
    
    def load_data(self):
        """Excel fayllardan ma'lumotlarni yuklash"""
        try:
            # 1. Dori vositalari (substansiyalar)
            if os.path.exists("2. Субстанция .xls"):
                df = pd.read_excel("2. Субстанция .xls", sheet_name="ПРОСМОТР")
                for _, row in df.iterrows():
                    if pd.notna(row.get("Торговое название и <br> синоним")):
                        drug = {
                            "name": str(row.get("Торговое название и <br> синоним", "")),
                            "international": str(row.get("Международное название", "")),
                            "form": str(row.get("Лекарственная форма выпуска", "")),
                            "country": str(row.get("Страна-производитель", "")),
                            "manufacturer": str(row.get("Фирма производитель", "")),
                            "reg_number": str(row.get("№ Регистрационного удостоверения", "")),
                            "reg_date": str(row.get("Дата  регистрации и перерегис-трации", "")),
                            "type": "substance"
                        }
                        self.drugs.append(drug)
            
            # 2. In vivo diagnostika
            if os.path.exists("3. Лек.пр.(in vivo).xls"):
                df = pd.read_excel("3. Лек.пр.(in vivo).xls", sheet_name="ПРОСМОТР")
                for _, row in df.iterrows():
                    if pd.notna(row.get("Торговое название")):
                        drug = {
                            "name": str(row.get("Торговое название", "")),
                            "form": str(row.get("Форма выпуска", "")),
                            "country": str(row.get("Страна-производитель", "")),
                            "manufacturer": str(row.get("Фирма производитель", "")),
                            "application": str(row.get("Область применения", "")),
                            "reg_number": str(row.get("№ Регистрационного удостоверения", "")),
                            "reg_date": str(row.get("Дата регистрации и перерегис-трации", "")),
                            "type": "in_vivo"
                        }
                        self.drugs.append(drug)
            
            # 3. Tibbiy texnika va buyumlar
            if os.path.exists("4. Мед.техника и мед.изд.xls"):
                df = pd.read_excel("4. Мед.техника и мед.изд.xls", sheet_name="ПРОСМОТР")
                for _, row in df.iterrows():
                    if pd.notna(row.get("Tibbiy texnika va tibbiy buyumlarning nomi/Наименование медицинской техники   и изделия медицинского назначения")):
                        tech = {
                            "name": str(row.get("Tibbiy texnika va tibbiy buyumlarning nomi/Наименование медицинской техники   и изделия медицинского назначения", "")),
                            "description": str(row.get("Qo'llanilish sohasi va maxsulot turi/Назначение или краткое описание", "")),
                            "country": str(row.get("Ishlab chiqaruvchi davlati/Страна-производитель", "")),
                            "manufacturer": str(row.get("Ishlab chiqaruvchi/Фирма производитель", "")),
                            "reg_number": str(row.get("Ro'yxatdan o'tkazilganlik raqami/№ Регистрационного удостоверения", "")),
                            "reg_date": str(row.get("Ro‘yxatdan o'tkazilgan sana/Дата регистрации и перерегистрации", "")),
                        }
                        self.tech.append(tech)
            
            # 4. In vitro diagnostika
            if os.path.exists("5. ИМН для in vitro диаг .xls"):
                df = pd.read_excel("5. ИМН для in vitro диаг .xls", sheet_name="ПРОСМОТР")
                for _, row in df.iterrows():
                    if pd.notna(row.get("Наименование ИМН для in vitro диагностики")):
                        diag = {
                            "name": str(row.get("Наименование ИМН для in vitro диагностики", "")),
                            "form": str(row.get("Форма выпуска", "")),
                            "country": str(row.get("Страна-производитель", "")),
                            "manufacturer": str(row.get("Фирма производитель", "")),
                            "application": str(row.get("Область применения", "")),
                            "reg_number": str(row.get("№ Регистрационного удостоверения", "")),
                            "reg_date": str(row.get("Дата регистрации и перерегис-трации", "")),
                        }
                        self.diagnostics.append(diag)
            
            # 5. Annullangan dorilar
            if os.path.exists("6. Аннул.лек.срва .xls"):
                df = pd.read_excel("6. Аннул.лек.срва .xls", sheet_name="ПРОСМОТР")
                for _, row in df.iterrows():
                    if pd.notna(row.get("Торговое название и <br> синоним")):
                        annulled = {
                            "name": str(row.get("Торговое название и <br> синоним", "")),
                            "international": str(row.get("Международное название", "")),
                            "form": str(row.get("Лекарственная форма выпуска", "")),
                            "country": str(row.get("Страна-производитель", "")),
                            "manufacturer": str(row.get("Фирма производитель", "")),
                            "reg_number": str(row.get("№ Регистрационного удостоверения", "")),
                        }
                        self.annulled_drugs.append(annulled)
            
            logger.info(f"✅ Ma'lumotlar bazasi yuklandi:")
            logger.info(f"   - Dorilar: {len(self.drugs)} ta")
            logger.info(f"   - Tibbiy texnika: {len(self.tech)} ta")
            logger.info(f"   - Diagnostika: {len(self.diagnostics)} ta")
            logger.info(f"   - Annullangan: {len(self.annulled_drugs)} ta")
            
        except Exception as e:
            logger.error(f"❌ Ma'lumotlarni yuklashda xato: {e}")
    
    def search_drugs(self, query: str) -> List[Dict]:
        """Dorilarni qidirish"""
        query = query.lower().strip()
        results = []
        
        # Barcha dorilarni qidirish
        for drug in self.drugs:
            if (query in drug["name"].lower() or 
                query in drug.get("international", "").lower() or
                query in drug.get("manufacturer", "").lower()):
                results.append(drug)
        
        # Annullanganlarni ham tekshirish
        for drug in self.annulled_drugs:
            if query in drug["name"].lower():
                drug_copy = drug.copy()
                drug_copy["annulled"] = True
                results.append(drug_copy)
        
        return results[:20]  # 20 tadan ko'p bo'lmasin
    
    def search_tech(self, query: str) -> List[Dict]:
        """Tibbiy texnikani qidirish"""
        query = query.lower().strip()
        results = []
        
        for item in self.tech:
            if (query in item["name"].lower() or 
                query in item.get("description", "").lower() or
                query in item.get("manufacturer", "").lower()):
                results.append(item)
        
        return results[:20]
    
    def search_diagnostics(self, query: str) -> List[Dict]:
        """Diagnostika vositalarini qidirish"""
        query = query.lower().strip()
        results = []
        
        for item in self.diagnostics:
            if (query in item["name"].lower() or 
                query in item.get("application", "").lower() or
                query in item.get("manufacturer", "").lower()):
                results.append(item)
        
        return results[:20]
    
    def get_drug_by_reg(self, reg_number: str) -> Optional[Dict]:
        """Ro'yxatdan o'tkazish raqami bo'yicha dori topish"""
        for drug in self.drugs:
            if reg_number in drug.get("reg_number", ""):
                return drug
        return None

# Ma'lumotlar bazasini yaratish
db = MedicineDatabase()

# ============================================================================
# OPENFDA API INTEGRATSIYASI (Xalqaro dorilar uchun)
# ============================================================================

async def search_openfda(drug_name: str) -> Optional[Dict]:
    """OpenFDA API orqali xalqaro dorilarni qidirish"""
    try:
        url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:{drug_name}&limit=1"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("results"):
                        result = data["results"][0]
                        openfda = result.get("openfda", {})
                        
                        return {
                            "name": drug_name,
                            "manufacturer": openfda.get("manufacturer_name", [""])[0],
                            "substance": openfda.get("substance_name", [""])[0],
                            "product_type": openfda.get("product_type", [""])[0],
                            "route": openfda.get("route", [""])[0],
                            "purpose": result.get("purpose", [""])[0],
                            "indications": result.get("indications_and_usage", [""])[0],
                            "warnings": result.get("warnings", [""])[0],
                            "source": "FDA (AQSh)"
                        }
    except Exception as e:
        logger.warning(f"OpenFDA xatosi: {e}")
    
    return None

# ============================================================================
# FORMATLASH FUNKSIYALARI
# ============================================================================

def format_drug_result(drug: Dict) -> str:
    """Dori ma'lumotini formatlash"""
    lines = []
    
    # Annullanganlik holati
    if drug.get("annulled"):
        lines.append("❌ *BU DORI ANNULLANGAN!*")
        lines.append("⚠️ Ushbu dori O'zbekistonda ro'yxatdan chiqarilgan!")
        lines.append("")
    
    # Nomi
    name = drug["name"].split("<br>")[0].strip()
    lines.append(f"💊 *{name}*")
    lines.append("━" * 32)
    
    # Xalqaro nomi
    if drug.get("international") and drug["international"] != "nan":
        lines.append(f"🌍 *Xalqaro nomi:* {drug['international']}")
    
    # Shakli
    if drug.get("form") and drug["form"] != "nan":
        lines.append(f"📦 *Shakli:* {drug['form']}")
    
    # Ishlab chiqaruvchi
    if drug.get("manufacturer") and drug["manufacturer"] != "nan":
        lines.append(f"🏭 *Ishlab chiqaruvchi:* {drug['manufacturer']}")
    
    # Mamlakat
    if drug.get("country") and drug["country"] != "nan":
        lines.append(f"🌍 *Davlat:* {drug['country']}")
    
    # Qo'llanilishi
    if drug.get("application") and drug["application"] != "nan":
        app = drug["application"][:100]
        lines.append(f"📋 *Qo'llanilishi:* {app}...")
    
    # Ro'yxatdan o'tgan raqam
    if drug.get("reg_number") and drug["reg_number"] != "nan":
        lines.append(f"📝 *Ro'yxat raqami:* {drug['reg_number']}")
    
    # Ro'yxatdan o'tgan sana
    if drug.get("reg_date") and drug["reg_date"] != "nan":
        lines.append(f"📅 *Ro'yxat sanasi:* {drug['reg_date']}")
    
    lines.append("")
    lines.append("━" * 32)
    lines.append("✅ Ushbu dori O'zbekistonda ro'yxatdan o'tgan")
    
    return "\n".join(lines)

def format_tech_result(tech: Dict) -> str:
    """Tibbiy texnika ma'lumotini formatlash"""
    lines = []
    
    # Nomi
    name = tech["name"].split("<br>")[0].strip()
    lines.append(f"⚕️ *{name}*")
    lines.append("━" * 32)
    
    # Tavsif
    if tech.get("description") and tech["description"] != "nan":
        desc = tech["description"][:200]
        lines.append(f"📋 *Tavsif:* {desc}...")
    
    # Ishlab chiqaruvchi
    if tech.get("manufacturer") and tech["manufacturer"] != "nan":
        lines.append(f"🏭 *Ishlab chiqaruvchi:* {tech['manufacturer']}")
    
    # Mamlakat
    if tech.get("country") and tech["country"] != "nan":
        lines.append(f"🌍 *Davlat:* {tech['country']}")
    
    # Ro'yxat raqami
    if tech.get("reg_number") and tech["reg_number"] != "nan":
        lines.append(f"📝 *Ro'yxat raqami:* {tech['reg_number']}")
    
    # Ro'yxat sanasi
    if tech.get("reg_date") and tech["reg_date"] != "nan":
        lines.append(f"📅 *Ro'yxat sanasi:* {tech['reg_date']}")
    
    return "\n".join(lines)

def format_diagnostic_result(diag: Dict) -> str:
    """Diagnostika vositasi ma'lumotini formatlash"""
    lines = []
    
    # Nomi
    lines.append(f"🔬 *{diag['name']}*")
    lines.append("━" * 32)
    
    # Shakli
    if diag.get("form") and diag["form"] != "nan":
        lines.append(f"📦 *Shakli:* {diag['form']}")
    
    # Qo'llanilishi
    if diag.get("application") and diag["application"] != "nan":
        lines.append(f"📋 *Qo'llanilishi:* {diag['application']}")
    
    # Ishlab chiqaruvchi
    if diag.get("manufacturer") and diag["manufacturer"] != "nan":
        lines.append(f"🏭 *Ishlab chiqaruvchi:* {diag['manufacturer']}")
    
    # Mamlakat
    if diag.get("country") and diag["country"] != "nan":
        lines.append(f"🌍 *Davlat:* {diag['country']}")
    
    # Ro'yxat raqami
    if diag.get("reg_number") and diag["reg_number"] != "nan":
        lines.append(f"📝 *Ro'yxat raqami:* {diag['reg_number']}")
    
    # Ro'yxat sanasi
    if diag.get("reg_date") and diag["reg_date"] != "nan":
        lines.append(f"📅 *Ro'yxat sanasi:* {diag['reg_date']}")
    
    return "\n".join(lines)

def format_search_results(results: List[Dict], query: str, result_type: str) -> str:
    """Qidiruv natijalarini formatlash"""
    if not results:
        return f"❌ '{query}' bo'yicha hech narsa topilmadi."
    
    lines = [f"🔍 '{query}' bo'yicha {len(results)} ta natija:", "━" * 32]
    
    for i, item in enumerate(results[:10], 1):
        name = item["name"].split("<br>")[0].strip()[:60]
        
        if result_type == "drug":
            if item.get("annulled"):
                lines.append(f"{i}. ❌ {name} (ANNULLANGAN)")
            else:
                lines.append(f"{i}. 💊 {name}")
        
        elif result_type == "tech":
            lines.append(f"{i}. ⚕️ {name}")
        
        elif result_type == "diagnostic":
            lines.append(f"{i}. 🔬 {name}")
    
    if len(results) > 10:
        lines.append(f"\n... va yana {len(results)-10} ta natija")
    
    lines.append("")
    lines.append("Batafsil ma'lumot uchun raqamni tanlang")
    
    return "\n".join(lines)

# ============================================================================
# KLAVIATURALAR
# ============================================================================

def main_keyboard() -> ReplyKeyboardMarkup:
    """Asosiy menyu"""
    keyboard = [
        [KeyboardButton("💊 Dori qidirish"), KeyboardButton("⚕️ Tibbiy texnika")],
        [KeyboardButton("🔬 Diagnostika"), KeyboardButton("📋 Annullangan dorilar")],
        [KeyboardButton("🌐 Xalqaro dorilar"), KeyboardButton("❓ Yordam")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ============================================================================
# HANDLERLAR
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi"""
    user = update.effective_user
    
    welcome_text = (
        f"👋 Assalomu alaykum, *{user.first_name}*!\n\n"
        "🔰 *Dori Ma'lumot Boti v4.0* - Rasmiy ma'lumotlar bazasi\n\n"
        "📌 *Imkoniyatlar:*\n"
        "✅ O'zbekistonda ro'yxatdan o'tgan dorilar\n"
        "✅ Tibbiy texnika va asbob-uskunalar\n"
        "✅ In vitro diagnostika vositalari\n"
        "✅ Annullangan dorilar ro'yxati\n"
        "✅ Xalqaro dorilar (FDA ma'lumotlari)\n\n"
        "📊 *Ma'lumotlar bazasi:*\n"
        f"• Dorilar: {len(db.drugs)} ta\n"
        f"• Tibbiy texnika: {len(db.tech)} ta\n"
        f"• Diagnostika: {len(db.diagnostics)} ta\n\n"
        "👇 Kerakli bo'limni tanlang"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menyu tugmalarini boshqarish"""
    text = update.message.text
    
    if text == "💊 Dori qidirish":
        await update.message.reply_text(
            "💊 Qidirmoqchi bo'lgan dori nomini kiriting:\n"
            "Masalan: *Paratsetamol*, *Amoksitsillin*, *Ibuprofen*",
            parse_mode=ParseMode.MARKDOWN
        )
        return DORI_QIDIRISH
    
    elif text == "⚕️ Tibbiy texnika":
        await update.message.reply_text(
            "⚕️ Qidirmoqchi bo'lgan tibbiy asbob-uskuna nomini kiriting:\n"
            "Masalan: *Tomograf*, *Ultratovush*, *Stomatologik kreslo*",
            parse_mode=ParseMode.MARKDOWN
        )
        return TEXNIKA_QIDIRISH
    
    elif text == "🔬 Diagnostika":
        await update.message.reply_text(
            "🔬 Qidirmoqchi bo'lgan diagnostika vositasini kiriting:\n"
            "Masalan: *VICH test*, *Glyukometr*, *Reagent*",
            parse_mode=ParseMode.MARKDOWN
        )
        return DIAGNOSTIKA_QIDIRISH
    
    elif text == "📋 Annullangan dorilar":
        if db.annulled_drugs:
            text = "📋 *Annullangan dorilar:*\n\n"
            for i, drug in enumerate(db.annulled_drugs[:10], 1):
                name = drug["name"].split("<br>")[0].strip()[:50]
                text += f"{i}. ❌ {name}\n"
            text += f"\n... va yana {len(db.annulled_drugs)-10} ta dori annullangan"
        else:
            text = "📋 Annullangan dorilar ro'yxati bo'sh"
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return ASOSIY_MENYU
    
    elif text == "🌐 Xalqaro dorilar":
        await update.message.reply_text(
            "🌐 Xalqaro dori nomini kiriting:\n"
            "Masalan: *Paracetamol*, *Ibuprofen*, *Amoxicillin*\n\n"
            "⚠️ Ma'lumotlar FDA (AQSh) bazasidan olinadi",
            parse_mode=ParseMode.MARKDOWN
        )
        return DORI_QIDIRISH  # Xuddi shu state, lekin keyin farqlaymiz
    
    elif text == "❓ Yordam":
        help_text = (
            "❓ *Yordam*\n\n"
            "*📌 Qanday ishlatish:*\n"
            "• Kerakli bo'limni tanlang\n"
            "• Qidiruv so'zini kiriting\n"
            "• Natijalardan birini tanlang\n\n"
            "*🔍 Qidiruv bo'yicha maslahatlar:*\n"
            "• Lotin yoki kirillda yozishingiz mumkin\n"
            "• Qisqa nomlar bilan qidiring\n"
            "• Aniq nomini bilmasangiz, bir qismini yozing\n\n"
            "*📞 Aloqa:* @admin"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    return ASOSIY_MENYU

async def handle_drug_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dori qidiruvini boshqarish"""
    query = update.message.text.strip()
    
    # Xalqaro dori qidirish (agar /international komandasi bilan kelgan bo'lsa)
    if context.user_data.get("search_mode") == "international":
        searching = await update.message.reply_text(
            f"🔍 '{query}' FDA bazasidan qidirilmoqda...\n"
            "🌐 Bu bir necha soniya olishi mumkin"
        )
        
        result = await search_openfda(query)
        await searching.delete()
        
        if result:
            text = format_drug_result(result)
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(
                f"❌ '{query}' FDA bazasida topilmadi.\n\n"
                "Boshqa nom bilan urinib ko'ring."
            )
        
        context.user_data.pop("search_mode", None)
        return ASOSIY_MENYU
    
    # Oddiy dori qidirish
    searching = await update.message.reply_text(f"🔍 '{query}' qidirilmoqda...")
    
    results = db.search_drugs(query)
    await searching.delete()
    
    if results:
        if len(results) == 1:
            # Bitta natija bo'lsa, to'g'ridan-to'g'ri ko'rsatish
            text = format_drug_result(results[0])
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        else:
            # Bir nechta natija bo'lsa, ro'yxat ko'rsatish
            text = format_search_results(results, query, "drug")
            
            # Tugmalar yaratish
            keyboard = []
            for i, result in enumerate(results[:10], 1):
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {result['name'][:50]}",
                    callback_data=f"drug_select:{i-1}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔍 Yangi qidiruv", callback_data="new_search")])
            
            # Natijalarni contextga saqlash
            context.user_data["last_search"] = results
            
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        await update.message.reply_text(
            f"❌ '{query}' topilmadi.\n\n"
            "💡 *Takliflar:*\n"
            "• Nomni to'g'ri yozganingizni tekshiring\n"
            "• Qisqaroq nom bilan qidiring\n"
            "• Lotin alifbosida yozing\n\n"
            "Yoki '🌐 Xalqaro dorilar' bo'limida qidirib ko'ring"
        )
    
    return ASOSIY_MENYU

async def handle_tech_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tibbiy texnika qidiruvi"""
    query = update.message.text.strip()
    
    searching = await update.message.reply_text(f"🔍 '{query}' qidirilmoqda...")
    
    results = db.search_tech(query)
    await searching.delete()
    
    if results:
        if len(results) == 1:
            text = format_tech_result(results[0])
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        else:
            text = format_search_results(results, query, "tech")
            
            keyboard = []
            for i, result in enumerate(results[:10], 1):
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {result['name'][:50]}",
                    callback_data=f"tech_select:{i-1}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔍 Yangi qidiruv", callback_data="new_search")])
            
            context.user_data["last_search"] = results
            
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        await update.message.reply_text(
            f"❌ '{query}' bo'yicha tibbiy texnika topilmadi."
        )
    
    return ASOSIY_MENYU

async def handle_diagnostic_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Diagnostika vositalari qidiruvi"""
    query = update.message.text.strip()
    
    searching = await update.message.reply_text(f"🔍 '{query}' qidirilmoqda...")
    
    results = db.search_diagnostics(query)
    await searching.delete()
    
    if results:
        if len(results) == 1:
            text = format_diagnostic_result(results[0])
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        else:
            text = format_search_results(results, query, "diagnostic")
            
            keyboard = []
            for i, result in enumerate(results[:10], 1):
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {result['name'][:50]}",
                    callback_data=f"diag_select:{i-1}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔍 Yangi qidiruv", callback_data="new_search")])
            
            context.user_data["last_search"] = results
            
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        await update.message.reply_text(
            f"❌ '{query}' bo'yicha diagnostika vositalari topilmadi."
        )
    
    return ASOSIY_MENYU

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback query larni boshqarish"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    results = context.user_data.get("last_search", [])
    
    if data == "new_search":
        await query.message.reply_text(
            "🔍 Yangi qidiruv so'zini kiriting:",
            reply_markup=main_keyboard()
        )
        return
    
    elif data.startswith("drug_select:"):
        idx = int(data.split(":")[1])
        if 0 <= idx < len(results):
            text = format_drug_result(results[idx])
            await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    elif data.startswith("tech_select:"):
        idx = int(data.split(":")[1])
        if 0 <= idx < len(results):
            text = format_tech_result(results[idx])
            await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    elif data.startswith("diag_select:"):
        idx = int(data.split(":")[1])
        if 0 <= idx < len(results):
            text = format_diagnostic_result(results[idx])
            await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Asosiy funksiya"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^(💊 Dori qidirish|⚕️ Tibbiy texnika|🔬 Diagnostika|🌐 Xalqaro dorilar)$"), handle_menu),
        ],
        states={
            DORI_QIDIRISH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_drug_search)],
            TEXNIKA_QIDIRISH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tech_search)],
            DIAGNOSTIKA_QIDIRISH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_diagnostic_search)],
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False,
    )
    
    # Handlerlarni qo'shish
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    
    logger.info("🤖 Dori Bot v4.0 (Rasmiy ma'lumotlar) ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
