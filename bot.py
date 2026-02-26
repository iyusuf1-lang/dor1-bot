#!/usr/bin/env python3
"""
Dori Ma'lumot Boti v4.0 - Rasmiy ma'lumotlar bazasi
O'zbekiston Respublikasi Sog'liqni Saqlash Vazirligi ma'lumotlari asosida
"""

# Xatolarni oldini olish uchun - kutubxonalarni tekshirish
import sys
import subprocess
import pkg_resources
import os

def check_and_install(package, install_name=None):
    """Kutubxona borligini tekshirish va yo'q bo'lsa o'rnatish"""
    if install_name is None:
        install_name = package
    
    try:
        dist = pkg_resources.get_distribution(package)
        print(f"✅ {package} {dist.version} o'rnatilgan")
    except pkg_resources.DistributionNotFound:
        print(f"⚠️ {package} o'rnatilmagan, o'rnatilmoqda...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", install_name])
        print(f"✅ {package} o'rnatildi")
    except Exception as e:
        print(f"⚠️ {package} tekshirishda xato: {e}")

# Kerakli kutubxonalarni tekshirish va o'rnatish
print("📦 Kutubxonalarni tekshirish...")
required_packages = [
    ("pandas", "pandas"),
    ("openpyxl", "openpyxl"),
    ("aiohttp", "aiohttp"),
    ("telegram", "python-telegram-bot"),
    ("bs4", "beautifulsoup4"),
    ("lxml", "lxml"),
    ("xlrd", "xlrd")
]

for pkg, install_name in required_packages:
    check_and_install(pkg, install_name)

# Endi import qilish
import pandas as pd
import logging
import re
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import aiohttp
from bs4 import BeautifulSoup
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

# Bot token - environment variable dan olish
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN topilmadi!")
    logger.error("Railway.app -> Variables bo'limida BOT_TOKEN ni o'rnating")
    sys.exit(1)

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
    
    def safe_str(self, value):
        """Xavfsiz string olish"""
        if pd.isna(value):
            return ""
        return str(value).strip()
    
    def load_data(self):
        """Excel fayllardan ma'lumotlarni yuklash"""
        try:
            # Mavjud fayllarni tekshirish
            excel_files = [
                "2. Субстанция .xls",
                "3. Лек.пр.(in vivo).xls", 
                "4. Мед.техника и мед.изд.xls",
                "5. ИМН для in vitro диаг .xls",
                "6. Аннул.лек.срва .xls",
                "7. Аннул.изделия мед.назначения и медтехники.xls"
            ]
            
            for file in excel_files:
                if not os.path.exists(file):
                    logger.warning(f"⚠️ {file} topilmadi")
            
            # 1. Dori vositalari (substansiyalar)
            if os.path.exists("2. Субстанция .xls"):
                try:
                    df = pd.read_excel("2. Субстанция .xls", sheet_name=0)
                    for _, row in df.iterrows():
                        name = self.safe_str(row.get("Торговое название и <br> синоним", ""))
                        if name and name != "nan" and len(name) > 3:
                            drug = {
                                "name": name,
                                "international": self.safe_str(row.get("Международное название", "")),
                                "form": self.safe_str(row.get("Лекарственная форма выпуска", "")),
                                "country": self.safe_str(row.get("Страна-производитель", "")),
                                "manufacturer": self.safe_str(row.get("Фирма производитель", "")),
                                "reg_number": self.safe_str(row.get("№ Регистрационного удостоверения", "")),
                                "reg_date": self.safe_str(row.get("Дата  регистрации и перерегис-трации", "")),
                                "type": "substance"
                            }
                            self.drugs.append(drug)
                    logger.info(f"✅ Dorilar: {len(self.drugs)} ta yuklandi")
                except Exception as e:
                    logger.error(f"❌ Dorilarni yuklashda xato: {e}")
            
            # 2. In vivo diagnostika
            if os.path.exists("3. Лек.пр.(in vivo).xls"):
                try:
                    df = pd.read_excel("3. Лек.пр.(in vivo).xls", sheet_name=0)
                    for _, row in df.iterrows():
                        name = self.safe_str(row.get("Торговое название", ""))
                        if name and name != "nan" and len(name) > 3:
                            drug = {
                                "name": name,
                                "form": self.safe_str(row.get("Форма выпуска", "")),
                                "country": self.safe_str(row.get("Страна-производитель", "")),
                                "manufacturer": self.safe_str(row.get("Фирма производитель", "")),
                                "application": self.safe_str(row.get("Область применения", "")),
                                "reg_number": self.safe_str(row.get("№ Регистрационного удостоверения", "")),
                                "reg_date": self.safe_str(row.get("Дата регистрации и перерегис-трации", "")),
                                "type": "in_vivo"
                            }
                            self.drugs.append(drug)
                except Exception as e:
                    logger.error(f"❌ In vivo ma'lumotlarni yuklashda xato: {e}")
            
            # 3. Tibbiy texnika
            if os.path.exists("4. Мед.техника и мед.изд.xls"):
                try:
                    df = pd.read_excel("4. Мед.техника и мед.изд.xls", sheet_name=0)
                    for _, row in df.iterrows():
                        name_col = "Tibbiy texnika va tibbiy buyumlarning nomi/Наименование медицинской техники   и изделия медицинского назначения"
                        name = self.safe_str(row.get(name_col, ""))
                        if name and name != "nan" and len(name) > 3:
                            tech = {
                                "name": name,
                                "description": self.safe_str(row.get("Qo'llanilish sohasi va maxsulot turi/Назначение или краткое описание", "")),
                                "country": self.safe_str(row.get("Ishlab chiqaruvchi davlati/Страна-производитель", "")),
                                "manufacturer": self.safe_str(row.get("Ishlab chiqaruvchi/Фирма производитель", "")),
                                "reg_number": self.safe_str(row.get("Ro'yxatdan o'tkazilganlik raqami/№ Регистрационного удостоверения", "")),
                                "reg_date": self.safe_str(row.get("Ro‘yxatdan o'tkazilgan sana/Дата регистрации и перерегистрации", "")),
                            }
                            self.tech.append(tech)
                    logger.info(f"✅ Tibbiy texnika: {len(self.tech)} ta yuklandi")
                except Exception as e:
                    logger.error(f"❌ Tibbiy texnikani yuklashda xato: {e}")
            
            # 4. In vitro diagnostika
            if os.path.exists("5. ИМН для in vitro диаг .xls"):
                try:
                    df = pd.read_excel("5. ИМН для in vitro диаг .xls", sheet_name=0)
                    for _, row in df.iterrows():
                        name = self.safe_str(row.get("Наименование ИМН для in vitro диагностики", ""))
                        if name and name != "nan" and len(name) > 3:
                            diag = {
                                "name": name,
                                "form": self.safe_str(row.get("Форма выпуска", "")),
                                "country": self.safe_str(row.get("Страна-производитель", "")),
                                "manufacturer": self.safe_str(row.get("Фирма производитель", "")),
                                "application": self.safe_str(row.get("Область применения", "")),
                                "reg_number": self.safe_str(row.get("№ Регистрационного удостоверения", "")),
                                "reg_date": self.safe_str(row.get("Дата регистрации и перерегис-трации", "")),
                            }
                            self.diagnostics.append(diag)
                    logger.info(f"✅ Diagnostika: {len(self.diagnostics)} ta yuklandi")
                except Exception as e:
                    logger.error(f"❌ Diagnostikani yuklashda xato: {e}")
            
            # 5. Annullangan dorilar
            if os.path.exists("6. Аннул.лек.срва .xls"):
                try:
                    df = pd.read_excel("6. Аннул.лек.срва .xls", sheet_name=0)
                    for _, row in df.iterrows():
                        name = self.safe_str(row.get("Торговое название и <br> синоним", ""))
                        if name and name != "nan" and len(name) > 3:
                            annulled = {
                                "name": name,
                                "international": self.safe_str(row.get("Международное название", "")),
                                "form": self.safe_str(row.get("Лекарственная форма выпуска", "")),
                                "country": self.safe_str(row.get("Страна-производитель", "")),
                                "manufacturer": self.safe_str(row.get("Фирма производитель", "")),
                                "reg_number": self.safe_str(row.get("№ Регистрационного удостоверения", "")),
                            }
                            self.annulled_drugs.append(annulled)
                    logger.info(f"✅ Annullangan: {len(self.annulled_drugs)} ta yuklandi")
                except Exception as e:
                    logger.error(f"❌ Annullanganlarni yuklashda xato: {e}")
            
            logger.info("=" * 50)
            logger.info("📊 MA'LUMOTLAR BAZASI:")
            logger.info(f"   • Dorilar: {len(self.drugs)} ta")
            logger.info(f"   • Tibbiy texnika: {len(self.tech)} ta")
            logger.info(f"   • Diagnostika: {len(self.diagnostics)} ta")
            logger.info(f"   • Annullangan: {len(self.annulled_drugs)} ta")
            logger.info("=" * 50)
            
        except Exception as e:
            logger.error(f"❌ Ma'lumotlarni yuklashda xato: {e}")
    
    def normalize_text(self, text: str) -> str:
        """Matnni normallashtirish"""
        if not text:
            return ""
        # HTML teglarini olib tashlash
        text = re.sub(r'<[^>]+>', ' ', str(text))
        # Ko'p probellarni bitta probelga almashtirish
        text = re.sub(r'\s+', ' ', text)
        return text.lower().strip()
    
    def search_drugs(self, query: str) -> List[Dict]:
        """Dorilarni qidirish"""
        query = self.normalize_text(query)
        if not query or len(query) < 2:
            return []
        
        results = []
        query_words = query.split()
        
        for drug in self.drugs:
            name = self.normalize_text(drug["name"])
            intl = self.normalize_text(drug.get("international", ""))
            mfr = self.normalize_text(drug.get("manufacturer", ""))
            
            # So'zlarni tekshirish
            match = False
            for word in query_words:
                if len(word) < 2:
                    continue
                if word in name or word in intl or word in mfr:
                    match = True
                    break
            
            if match:
                results.append(drug)
        
        # Annullanganlarni ham tekshirish
        for drug in self.annulled_drugs:
            name = self.normalize_text(drug["name"])
            for word in query_words:
                if len(word) > 1 and word in name:
                    drug_copy = drug.copy()
                    drug_copy["annulled"] = True
                    results.append(drug_copy)
                    break
        
        # Unikal qilish
        unique_results = []
        seen = set()
        for drug in results:
            name = drug.get("name", "")
            if name not in seen:
                seen.add(name)
                unique_results.append(drug)
        
        return unique_results[:20]
    
    def search_tech(self, query: str) -> List[Dict]:
        """Tibbiy texnikani qidirish"""
        query = self.normalize_text(query)
        if not query or len(query) < 2:
            return []
        
        results = []
        query_words = query.split()
        
        for item in self.tech:
            name = self.normalize_text(item["name"])
            desc = self.normalize_text(item.get("description", ""))
            mfr = self.normalize_text(item.get("manufacturer", ""))
            
            for word in query_words:
                if len(word) > 1 and (word in name or word in desc or word in mfr):
                    results.append(item)
                    break
        
        return results[:20]
    
    def search_diagnostics(self, query: str) -> List[Dict]:
        """Diagnostika vositalarini qidirish"""
        query = self.normalize_text(query)
        if not query or len(query) < 2:
            return []
        
        results = []
        query_words = query.split()
        
        for item in self.diagnostics:
            name = self.normalize_text(item["name"])
            app = self.normalize_text(item.get("application", ""))
            mfr = self.normalize_text(item.get("manufacturer", ""))
            
            for word in query_words:
                if len(word) > 1 and (word in name or word in app or word in mfr):
                    results.append(item)
                    break
        
        return results[:20]

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
                        
                        manufacturer = openfda.get("manufacturer_name", [""])[0]
                        if isinstance(manufacturer, list):
                            manufacturer = manufacturer[0] if manufacturer else ""
                        
                        substance = openfda.get("substance_name", [""])[0]
                        if isinstance(substance, list):
                            substance = substance[0] if substance else ""
                        
                        return {
                            "name": drug_name,
                            "manufacturer": manufacturer,
                            "substance": substance,
                            "product_type": openfda.get("product_type", [""])[0],
                            "route": openfda.get("route", [""])[0],
                            "purpose": result.get("purpose", [""])[0] if isinstance(result.get("purpose"), list) else "",
                            "indications": result.get("indications_and_usage", [""])[0] if isinstance(result.get("indications_and_usage"), list) else "",
                            "warnings": result.get("warnings", [""])[0] if isinstance(result.get("warnings"), list) else "",
                            "source": "FDA (AQSh)"
                        }
    except Exception as e:
        logger.warning(f"OpenFDA xatosi: {e}")
    
    return None

# ============================================================================
# FORMATLASH FUNKSIYALARI
# ============================================================================

def clean_text(text: str, max_len: int = 100) -> str:
    """Matnni tozalash va qisqartirish"""
    if not text or text == "nan":
        return ""
    # HTML teglarini olib tashlash
    text = re.sub(r'<[^>]+>', ' ', str(text))
    # Ko'p probellarni bitta probelga almashtirish
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text

def format_drug_result(drug: Dict) -> str:
    """Dori ma'lumotini formatlash"""
    lines = []
    
    # Annullanganlik holati
    if drug.get("annulled"):
        lines.append("❌ *❗ BU DORI ANNULLANGAN❗*")
        lines.append("⚠️ Ushbu dori O'zbekistonda ro'yxatdan chiqarilgan!")
        lines.append("")
    
    # Nomi
    name = clean_text(drug["name"], 100)
    lines.append(f"💊 *{name}*")
    lines.append("━" * 32)
    
    # Xalqaro nomi
    if drug.get("international") and drug["international"] not in ["nan", ""]:
        intl = clean_text(drug["international"], 100)
        lines.append(f"🌍 *Xalqaro nomi:* {intl}")
    
    # Shakli
    if drug.get("form") and drug["form"] not in ["nan", ""]:
        form = clean_text(drug["form"], 100)
        lines.append(f"📦 *Shakli:* {form}")
    
    # Ishlab chiqaruvchi
    if drug.get("manufacturer") and drug["manufacturer"] not in ["nan", ""]:
        mfr = clean_text(drug["manufacturer"], 100)
        lines.append(f"🏭 *Ishlab chiqaruvchi:* {mfr}")
    
    # Mamlakat
    if drug.get("country") and drug["country"] not in ["nan", ""]:
        country = clean_text(drug["country"], 50)
        lines.append(f"🌍 *Davlat:* {country}")
    
    # Qo'llanilishi
    if drug.get("application") and drug["application"] not in ["nan", ""]:
        app = clean_text(drug["application"], 150)
        lines.append(f"📋 *Qo'llanilishi:* {app}")
    
    # Ro'yxatdan o'tgan raqam
    if drug.get("reg_number") and drug["reg_number"] not in ["nan", ""]:
        reg = clean_text(drug["reg_number"], 50)
        lines.append(f"📝 *Ro'yxat raqami:* {reg}")
    
    # Ro'yxatdan o'tgan sana
    if drug.get("reg_date") and drug["reg_date"] not in ["nan", ""]:
        date = clean_text(drug["reg_date"], 50)
        lines.append(f"📅 *Ro'yxat sanasi:* {date}")
    
    lines.append("")
    lines.append("━" * 32)
    if not drug.get("annulled"):
        lines.append("✅ Ushbu dori O'zbekistonda ro'yxatdan o'tgan")
    else:
        lines.append("⚠️ Dori ishlatishdan oldin shifokor bilan maslahatlashing!")
    
    return "\n".join(lines)

def format_tech_result(tech: Dict) -> str:
    """Tibbiy texnika ma'lumotini formatlash"""
    lines = []
    
    # Nomi
    name = clean_text(tech["name"], 100)
    lines.append(f"⚕️ *{name}*")
    lines.append("━" * 32)
    
    # Tavsif
    if tech.get("description") and tech["description"] not in ["nan", ""]:
        desc = clean_text(tech["description"], 200)
        lines.append(f"📋 *Tavsif:* {desc}")
    
    # Ishlab chiqaruvchi
    if tech.get("manufacturer") and tech["manufacturer"] not in ["nan", ""]:
        mfr = clean_text(tech["manufacturer"], 100)
        lines.append(f"🏭 *Ishlab chiqaruvchi:* {mfr}")
    
    # Mamlakat
    if tech.get("country") and tech["country"] not in ["nan", ""]:
        country = clean_text(tech["country"], 50)
        lines.append(f"🌍 *Davlat:* {country}")
    
    # Ro'yxat raqami
    if tech.get("reg_number") and tech["reg_number"] not in ["nan", ""]:
        reg = clean_text(tech["reg_number"], 50)
        lines.append(f"📝 *Ro'yxat raqami:* {reg}")
    
    # Ro'yxat sanasi
    if tech.get("reg_date") and tech["reg_date"] not in ["nan", ""]:
        date = clean_text(tech["reg_date"], 50)
        lines.append(f"📅 *Ro'yxat sanasi:* {date}")
    
    return "\n".join(lines)

def format_diagnostic_result(diag: Dict) -> str:
    """Diagnostika vositasi ma'lumotini formatlash"""
    lines = []
    
    # Nomi
    name = clean_text(diag["name"], 100)
    lines.append(f"🔬 *{name}*")
    lines.append("━" * 32)
    
    # Shakli
    if diag.get("form") and diag["form"] not in ["nan", ""]:
        form = clean_text(diag["form"], 100)
        lines.append(f"📦 *Shakli:* {form}")
    
    # Qo'llanilishi
    if diag.get("application") and diag["application"] not in ["nan", ""]:
        app = clean_text(diag["application"], 150)
        lines.append(f"📋 *Qo'llanilishi:* {app}")
    
    # Ishlab chiqaruvchi
    if diag.get("manufacturer") and diag["manufacturer"] not in ["nan", ""]:
        mfr = clean_text(diag["manufacturer"], 100)
        lines.append(f"🏭 *Ishlab chiqaruvchi:* {mfr}")
    
    # Mamlakat
    if diag.get("country") and diag["country"] not in ["nan", ""]:
        country = clean_text(diag["country"], 50)
        lines.append(f"🌍 *Davlat:* {country}")
    
    # Ro'yxat raqami
    if diag.get("reg_number") and diag["reg_number"] not in ["nan", ""]:
        reg = clean_text(diag["reg_number"], 50)
        lines.append(f"📝 *Ro'yxat raqami:* {reg}")
    
    # Ro'yxat sanasi
    if diag.get("reg_date") and diag["reg_date"] not in ["nan", ""]:
        date = clean_text(diag["reg_date"], 50)
        lines.append(f"📅 *Ro'yxat sanasi:* {date}")
    
    return "\n".join(lines)

def format_search_results(results: List[Dict], query: str, result_type: str) -> str:
    """Qidiruv natijalarini formatlash"""
    if not results:
        return f"❌ '{query}' bo'yicha hech narsa topilmadi."
    
    lines = [f"🔍 '{query}' bo'yicha {len(results)} ta natija:", "━" * 32]
    
    for i, item in enumerate(results[:10], 1):
        name = clean_text(item["name"], 60)
        
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
    )
    
    # Ma'lumotlar bazasi statistikasini qo'shish
    if len(db.drugs) > 0 or len(db.tech) > 0:
        welcome_text += "📊 *Ma'lumotlar bazasi:*\n"
        if len(db.drugs) > 0:
            welcome_text += f"• Dorilar: {len(db.drugs)} ta\n"
        if len(db.tech) > 0:
            welcome_text += f"• Tibbiy texnika: {len(db.tech)} ta\n"
        if len(db.diagnostics) > 0:
            welcome_text += f"• Diagnostika: {len(db.diagnostics)} ta\n"
        if len(db.annulled_drugs) > 0:
            welcome_text += f"• Annullangan: {len(db.annulled_drugs)} ta\n"
    else:
        welcome_text += "⚠️ Ma'lumotlar bazasi yuklanmadi. Excel fayllarni tekshiring.\n"
    
    welcome_text += "\n👇 Kerakli bo'limni tanlang"
    
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
            for i, drug in enumerate(db.annulled_drugs[:15], 1):
                name = clean_text(drug["name"], 50)
                text += f"{i}. ❌ {name}\n"
            if len(db.annulled_drugs) > 15:
                text += f"\n... va yana {len(db.annulled_drugs)-15} ta dori annullangan"
        else:
            text = "📋 Annullangan dorilar ro'yxati bo'sh"
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return ASOSIY_MENYU
    
    elif text == "🌐 Xalqaro dorilar":
        context.user_data["search_mode"] = "international"
        await update.message.reply_text(
            "🌐 Xalqaro dori nomini kiriting:\n"
            "Masalan: *Paracetamol*, *Ibuprofen*, *Amoxicillin*\n\n"
            "⚠️ Ma'lumotlar FDA (AQSh) bazasidan olinadi",
            parse_mode=ParseMode.MARKDOWN
        )
        return DORI_QIDIRISH
    
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
    
    if len(query) < 2:
        await update.message.reply_text("❗ Qidiruv so'zi kamida 2 harfdan iborat bo'lishi kerak")
        return DORI_QIDIRISH
    
    # Xalqaro dori qidirish
    if context.user_data.get("search_mode") == "international":
        searching = await update.message.reply_text(
            f"🔍 '{query}' FDA bazasidan qidirilmoqda...\n"
            "🌐 Bu bir necha soniya olishi mumkin"
        )
        
        result = await search_openfda(query)
        await searching.delete()
        
        if result:
            # FDA natijasini formatlash
            lines = []
            lines.append(f"🌐 *{result['name'].upper()}*")
            lines.append("━" * 32)
            
            if result.get("manufacturer"):
                lines.append(f"🏭 *Ishlab chiqaruvchi:* {result['manufacturer']}")
            if result.get("substance"):
                lines.append(f"🧪 *Modda:* {result['substance']}")
            if result.get("product_type"):
                lines.append(f"📦 *Turi:* {result['product_type']}")
            if result.get("route"):
                lines.append(f"💊 *Qo'llash:* {result['route']}")
            if result.get("purpose"):
                lines.append(f"🎯 *Maqsadi:* {result['purpose']}")
            if result.get("indications"):
                lines.append(f"📋 *Qo'llanilishi:* {result['indications'][:200]}")
            if result.get("source"):
                lines.append(f"📡 *Manba:* {result['source']}")
            
            lines.append("")
            lines.append("⚠️ Dori ishlatishdan oldin shifokor bilan maslahatlashing!")
            
            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
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
                name = clean_text(result["name"], 40)
                if result.get("annulled"):
                    btn_text = f"{i}. ❌ {name}"
                else:
                    btn_text = f"{i}. 💊 {name}"
                keyboard.append([InlineKeyboardButton(
                    btn_text,
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
            "Yoki '🌐 Xalqaro dorilar' bo'limida qidirib ko'ring",
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ASOSIY_MENYU

async def handle_tech_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tibbiy texnika qidiruvi"""
    query = update.message.text.strip()
    
    if len(query) < 2:
        await update.message.reply_text("❗ Qidiruv so'zi kamida 2 harfdan iborat bo'lishi kerak")
        return TEXNIKA_QIDIRISH
    
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
                name = clean_text(result["name"], 40)
                keyboard.append([InlineKeyboardButton(
                    f"{i}. ⚕️ {name}",
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
    
    if len(query) < 2:
        await update.message.reply_text("❗ Qidiruv so'zi kamida 2 harfdan iborat bo'lishi kerak")
        return DIAGNOSTIKA_QIDIRISH
    
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
                name = clean_text(result["name"], 40)
                keyboard.append([InlineKeyboardButton(
                    f"{i}. 🔬 {name}",
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
    try:
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
        app.add_handler(CommandHandler("help", lambda u, c: handle_menu(u, c)))
        app.add_handler(conv_handler)
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
        
        logger.info("=" * 50)
        logger.info("🤖 Dori Bot v4.0 ishga tushdi!")
        logger.info(f"📊 Ma'lumotlar: {len(db.drugs)} dori, {len(db.tech)} texnika")
        logger.info("=" * 50)
        
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"❌ Bot ishga tushishda xato: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
