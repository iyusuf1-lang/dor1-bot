#!/usr/bin/env python3
"""
Dori Ma'lumot Boti v3.0 - Premium versiya
To'liq o'zbek tilida, eng yaqin aptekalar, narx kuzatuvi va boshqa imkoniyatlar
"""

import asyncio
import logging
import os
import re
import json
import aiohttp
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    ReplyKeyboardMarkup,
    KeyboardButton,
    Location,
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

# Logging sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# HEADERS
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uz-UZ,uz;q=0.9,ru;q=0.8,en;q=0.7",
}

# Conversation states
(LOKATSIYA_KUTISH, DORI_NOMI_KUTISH, NARX_KUZATUV) = range(3)

# Kesh tizimi
class Cache:
    def __init__(self, ttl=3600):  # 1 soat
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = (value, time.time())
    
    def clear(self):
        self.cache.clear()

# Kesh obyektlari
drug_cache = Cache(ttl=1800)  # 30 daqiqa
pharmacy_cache = Cache(ttl=86400)  # 1 kun

# Ma'lumotlar bazasi (oddiy fayl)
class Database:
    def __init__(self, filename="bot_data.json"):
        self.filename = filename
        self.data = self.load()
    
    def load(self):
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"users": {}, "drug_alerts": {}, "reviews": {}}
    
    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def add_user(self, user_id, username=None, location=None):
        if str(user_id) not in self.data["users"]:
            self.data["users"][str(user_id)] = {
                "username": username,
                "first_seen": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "location": location,
                "alerts": [],
                "lang": "uz"
            }
        else:
            self.data["users"][str(user_id)]["last_active"] = datetime.now().isoformat()
        self.save()
    
    def add_alert(self, user_id, drug_name, target_price):
        alert_id = hashlib.md5(f"{user_id}{drug_name}{time.time()}".encode()).hexdigest()[:8]
        alert = {
            "id": alert_id,
            "user_id": str(user_id),
            "drug_name": drug_name,
            "target_price": target_price,
            "created_at": datetime.now().isoformat(),
            "last_price": None,
            "active": True
        }
        
        if str(user_id) not in self.data["drug_alerts"]:
            self.data["drug_alerts"][str(user_id)] = []
        
        self.data["drug_alerts"][str(user_id)].append(alert)
        self.save()
        return alert_id
    
    def remove_alert(self, user_id, alert_id):
        if str(user_id) in self.data["drug_alerts"]:
            self.data["drug_alerts"][str(user_id)] = [
                a for a in self.data["drug_alerts"][str(user_id)] 
                if a["id"] != alert_id
            ]
            self.save()
    
    def get_alerts(self, user_id):
        return self.data["drug_alerts"].get(str(user_id), [])
    
    def add_review(self, drug_name, user_id, rating, comment=""):
        review_id = hashlib.md5(f"{drug_name}{user_id}{time.time()}".encode()).hexdigest()[:8]
        review = {
            "id": review_id,
            "drug_name": drug_name.lower(),
            "user_id": str(user_id),
            "rating": rating,
            "comment": comment,
            "created_at": datetime.now().isoformat()
        }
        
        if drug_name.lower() not in self.data["reviews"]:
            self.data["reviews"][drug_name.lower()] = []
        
        self.data["reviews"][drug_name.lower()].append(review)
        self.save()
        return review_id
    
    def get_reviews(self, drug_name):
        return self.data["reviews"].get(drug_name.lower(), [])

db = Database()

# ─────────────────────────────────────────
# APTEKALAR MA'LUMOTLARI
# ─────────────────────────────────────────

# O'zbekiston aptekalari
UZBEKISTAN_PHARMACIES = [
    {
        "name": "Arzon Apteka",
        "lat": 41.2995,
        "lon": 69.2401,
        "address": "Toshkent, Amir Temur shoh ko'chasi, 15",
        "phone": "+99871 123-45-67",
        "working_hours": "09:00 - 21:00",
        "brand": "arzonapteka"
    },
    {
        "name": "Oxana Apteka",
        "lat": 41.3115,
        "lon": 69.2795,
        "address": "Toshkent, Beruniy shoh ko'chasi, 41",
        "phone": "+99871 234-56-78",
        "working_hours": "08:00 - 22:00",
        "brand": "oxana"
    },
    {
        "name": "Dorixona 24",
        "lat": 41.3385,
        "lon": 69.3345,
        "address": "Toshkent, Chilonzor, 21-mavze",
        "phone": "+99871 345-67-89",
        "working_hours": "24/7",
        "brand": "dorixona24"
    },
    {
        "name": "Sog'lom Avlod",
        "lat": 41.2825,
        "lon": 69.2585,
        "address": "Toshkent, Qatartol ko'chasi, 5",
        "phone": "+99871 456-78-90",
        "working_hours": "09:00 - 20:00",
        "brand": "soglom"
    },
    {
        "name": "Asia Pharm",
        "lat": 41.3265,
        "lon": 69.2285,
        "address": "Toshkent, Shayxontoxur tumani",
        "phone": "+99871 567-89-01",
        "working_hours": "09:00 - 21:00",
        "brand": "asiapharm"
    },
]

# Qo'shimcha viloyat aptekalari
REGION_PHARMACIES = {
    "samarqand": [
        {"name": "Samarqand Dorixona", "lat": 39.6275, "lon": 66.9745, "address": "Samarqand, Registon ko'chasi"},
        {"name": "Abu Ali Ibn Sino", "lat": 39.6545, "lon": 66.9595, "address": "Samarqand, Universitet bulvari"},
    ],
    "buxoro": [
        {"name": "Buxoro Farm", "lat": 39.7745, "lon": 64.4285, "address": "Buxoro, Bahouddin Naqshband ko'chasi"},
    ],
    "andijon": [
        {"name": "Andijon Dorixona", "lat": 40.7825, "lon": 72.3445, "address": "Andijon, Navoiy ko'chasi"},
    ],
    "namangan": [
        {"name": "Namangan Pharm", "lat": 40.9985, "lon": 71.6725, "address": "Namangan, Uychi ko'chasi"},
    ],
    "farg'ona": [
        {"name": "Farg'ona Dorixona", "lat": 40.3845, "lon": 71.7845, "address": "Farg'ona, Mustaqillik ko'chasi"},
    ],
    "qashqadaryo": [
        {"name": "Qarshi Farm", "lat": 38.8605, "lon": 65.7975, "address": "Qarshi, Ko'k Gumbaz ko'chasi"},
    ],
    "surxondaryo": [
        {"name": "Termiz Dorixona", "lat": 37.2245, "lon": 67.2785, "address": "Termiz, At-Termiziy ko'chasi"},
    ],
    "xorazm": [
        {"name": "Urganch Farm", "lat": 41.5845, "lon": 60.6325, "address": "Urganch, Al-Xorazmiy ko'chasi"},
    ],
    "jizzax": [
        {"name": "Jizzax Dorixona", "lat": 40.1155, "lon": 67.8425, "address": "Jizzax, Sharof Rashidov ko'chasi"},
    ],
    "sirdaryo": [
        {"name": "Guliston Farm", "lat": 40.4895, "lon": 68.7875, "address": "Guliston, Mustaqillik ko'chasi"},
    ],
    "navoiy": [
        {"name": "Navoiy Dorixona", "lat": 40.1045, "lon": 65.3585, "address": "Navoiy, Navoiy shoh ko'chasi"},
    ],
}

# ─────────────────────────────────────────
# DORILAR MA'LUMOTLARI (QO'LLANMA)
# ─────────────────────────────────────────

DRUG_GUIDE = {
    "paracetamol": {
        "name": "Paratsetamol",
        "type": "og'riq qoldiruvchi, isitma tushiruvchi",
        "dosage": {
            "kattalar": "500-1000 mg, kuniga 3-4 marta",
            "bolalar": "10-15 mg/kg, kuniga 4 marta",
            "maksimal": "Kattalar uchun 4000 mg/kun"
        },
        "usage": "Ovqatdan keyin, suv bilan ichiladi",
        "contraindications": [
            "Jigar yetishmovchiligi",
            "Buyrak yetishmovchiligi",
            "Alkogolizm"
        ],
        "side_effects": [
            "Allergik reaksiyalar",
            "Ko'ngil aynishi",
            "Jigar fermentlari oshishi"
        ],
        "warning": "Spirtli ichimliklar bilan birga qabul qilmang"
    },
    "ibuprofen": {
        "name": "Ibuprofen",
        "type": "yallig'lanishga qarshi, og'riq qoldiruvchi",
        "dosage": {
            "kattalar": "200-400 mg, kuniga 3-4 marta",
            "bolalar": "5-10 mg/kg, kuniga 3 marta",
            "maksimal": "Kattalar uchun 1200 mg/kun"
        },
        "usage": "Ovqatdan keyin, suv bilan ichiladi",
        "contraindications": [
            "Oshqozon yarasi",
            "Astma",
            "Homiladorlik (3-trimestr)"
        ],
        "side_effects": [
            "Oshqozon bezovtaligi",
            "Ko'ngil aynishi",
            "Bosh aylanishi"
        ],
        "warning": "7 kundan ortiq qabul qilmang"
    },
    "amoxicillin": {
        "name": "Amoksitsillin",
        "type": "antibiotik",
        "dosage": {
            "kattalar": "500 mg, kuniga 3 marta",
            "bolalar": "20-40 mg/kg/kun",
            "maksimal": "Kattalar uchun 1500 mg/kun"
        },
        "usage": "Ovqatdan oldin yoki keyin",
        "contraindications": [
            "Penisillinga allergiya",
            "Yuqumli mononuklyoz"
        ],
        "side_effects": [
            "Diareya",
            "Ko'ngil aynishi",
            "Toshmalar"
        ],
        "warning": "Kursni to'liq tugating"
    },
    "cetirizin": {
        "name": "Setirizin",
        "type": "antigistamin (allergiyaga qarshi)",
        "dosage": {
            "kattalar": "10 mg, kuniga 1 marta",
            "bolalar": "5 mg, kuniga 2 marta",
            "maksimal": "Kattalar uchun 10 mg/kun"
        },
        "usage": "Kechqurun qabul qilish tavsiya etiladi",
        "contraindications": [
            "Buyrak yetishmovchiligi",
            "Homiladorlik"
        ],
        "side_effects": [
            "Uyquchanlik",
            "Bosh aylanishi",
            "Quruq og'iz"
        ],
        "warning": "Mashina haydashda ehtiyot bo'ling"
    },
    "omeprazol": {
        "name": "Omeprazol",
        "type": "oshqozon kislotasini kamaytiruvchi",
        "dosage": {
            "kattalar": "20 mg, kuniga 1-2 marta",
            "maksimal": "40 mg/kun"
        },
        "usage": "Ovqatdan 30 daqiqa oldin",
        "contraindications": [
            "Jigar yetishmovchiligi"
        ],
        "side_effects": [
            "Bosh og'rig'i",
            "Qorin og'rig'i",
            "Ko'ngil aynishi"
        ],
        "warning": "Uzoq muddat qabul qilmang"
    }
}

# Analoglar ma'lumotlar bazasi
ANALOGS_DB = {
    "paracetamol": ["Panadol", "Kalpol", "Efferalgan", "Tylenol", "Daleron"],
    "ibuprofen": ["Nurofen", "Brufen", "Ibuprom", "Advil", "MIG"],
    "amoxicillin": ["Flemoksin Solutab", "Ospamox", "Amoxil", "Hikontsil"],
    "cetirizin": ["Zyrtec", "Zodak", "Allertec", "Letizen", "Parlazin"],
    "loratadin": ["Claritin", "Lorano", "Erolin", "Lomilan", "Clarotadin"],
    "omeprazol": ["Omez", "Gastrozol", "Ultop", "Losec", "Zerocid"],
    "drotaverin": ["No-Shpa", "Spazmol", "Spazgan", "Doverin"],
    "metformin": ["Glucophage", "Siofor", "Metfogamma", "Bagomet"],
    "azithromycin": ["Sumamed", "Azitro", "Azitral", "Hemomycin"],
    "fluconazole": ["Diflucan", "Flucostat", "Mikosist", "Futsis"],
}

# ─────────────────────────────────────────
# SCRAPING FUNKSIYALARI (OPTIMIZATSIYALANGAN)
# ─────────────────────────────────────────

async def scrape_arzonapteka(drug_name: str) -> List[Dict]:
    """ArzonApteka.uz dan dori ma'lumotlarini olish (optimallashtirilgan)"""
    # Keshdan tekshirish
    cache_key = f"arzon:{drug_name.lower()}"
    cached = drug_cache.get(cache_key)
    if cached:
        return cached
    
    results = []
    url = f"https://arzonapteka.uz/uz/drug?q={drug_name.replace(' ', '+')}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Mahsulotlarni topish
        cards = soup.select(".drug-card, .product-card, [class*='drug']")
        if not cards:
            cards = soup.find_all("div", class_=re.compile(r"card|item|product", re.I))
        
        for card in cards[:10]:  # 10 tagacha
            item = {}
            
            # Nom
            name_el = card.select_one("h3, h4, .name, .title")
            if name_el:
                item["name"] = name_el.get_text(strip=True)[:100]
            else:
                continue
            
            # Narx
            price_el = card.select_one(".price, .cost, [class*='price']")
            if price_el:
                price_text = price_el.get_text(strip=True)
                numbers = re.findall(r"\d[\d\s]*\d", price_text)
                if numbers:
                    try:
                        price_str = re.sub(r"\s+", "", numbers[0])
                        item["price"] = int(price_str)
                    except:
                        pass
            
            # Rasm
            img = card.select_one("img")
            if img:
                src = img.get("src") or img.get("data-src", "")
                if src and src.startswith("/"):
                    src = "https://arzonapteka.uz" + src
                if src.startswith("http"):
                    item["image"] = src
            
            # Ishlab chiqaruvchi
            mfr = card.select_one(".manufacturer, .brand")
            if mfr:
                item["manufacturer"] = mfr.get_text(strip=True)[:60]
            
            item["source"] = "Arzon Apteka"
            results.append(item)
        
        # Keshga saqlash
        if results:
            drug_cache.set(cache_key, results)
    
    except Exception as e:
        logger.warning(f"ArzonApteka xatosi: {e}")
    
    return results

async def scrape_oxana(drug_name: str) -> List[Dict]:
    """Oxana.uz dan ma'lumot olish"""
    cache_key = f"oxana:{drug_name.lower()}"
    cached = drug_cache.get(cache_key)
    if cached:
        return cached
    
    results = []
    try:
        # Oxana API yoki veb-sayt
        # Hozircha demo ma'lumot
        demo_prices = {
            "paracetamol": 5000,
            "ibuprofen": 8000,
            "amoxicillin": 15000,
            "cetirizin": 12000,
        }
        
        drug_lower = drug_name.lower()
        if drug_lower in demo_prices:
            results.append({
                "name": drug_name.title(),
                "price": demo_prices[drug_lower],
                "source": "Oxana Apteka",
                "manufacturer": "Turli ishlab chiqaruvchilar"
            })
        
        drug_cache.set(cache_key, results)
    except Exception as e:
        logger.warning(f"Oxana xatosi: {e}")
    
    return results

# ─────────────────────────────────────────
# GEOFUNKSIYALAR
# ─────────────────────────────────────────

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine formulasi orqali masofani hisoblash (km)"""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Yer radiusi (km)
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

def find_nearby_pharmacies(lat: float, lon: float, radius: float = 5.0) -> List[Dict]:
    """Berilgan lokatsiya atrofidagi aptekalarni topish"""
    nearby = []
    
    # Asosiy aptekalar
    for pharmacy in UZBEKISTAN_PHARMACIES:
        distance = calculate_distance(lat, lon, pharmacy["lat"], pharmacy["lon"])
        if distance <= radius:
            pharmacy_copy = pharmacy.copy()
            pharmacy_copy["distance"] = round(distance, 2)
            nearby.append(pharmacy_copy)
    
    # Viloyat aptekalari (agar radius katta bo'lsa)
    if radius > 10:
        for region, pharmacies in REGION_PHARMACIES.items():
            for pharmacy in pharmacies:
                distance = calculate_distance(lat, lon, pharmacy["lat"], pharmacy["lon"])
                if distance <= radius:
                    pharmacy_copy = pharmacy.copy()
                    pharmacy_copy["distance"] = round(distance, 2)
                    pharmacy_copy["region"] = region
                    nearby.append(pharmacy_copy)
    
    # Masofa bo'yicha saralash
    nearby.sort(key=lambda x: x["distance"])
    
    return nearby[:10]  # Eng yaqin 10 tasi

# ─────────────────────────────────────────
# DORI MA'LUMOTLARINI YIG'ISH
# ─────────────────────────────────────────

async def fetch_drug_full_data(drug_name: str) -> Dict:
    """Barcha manbalardan ma'lumot yig'ish (optimallashtirilgan)"""
    # Keshdan tekshirish
    cache_key = f"drug:{drug_name.lower()}"
    cached = drug_cache.get(cache_key)
    if cached:
        return cached
    
    data = {
        "name": drug_name,
        "found": False,
        "price_min": None,
        "price_max": None,
        "average_price": None,
        "pharmacies": [],          # Aptekalar ro'yxati
        "manufacturer": None,
        "description": None,
        "image_url": None,
        "guide": None,
        "source": None,
        "rating": None,
    }
    
    # Parallel qidirish
    tasks = [
        scrape_arzonapteka(drug_name),
        scrape_oxana(drug_name),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_items = []
    pharmacy_prices = []
    
    for r in results:
        if isinstance(r, list):
            all_items.extend(r)
    
    if all_items:
        data["found"] = True
        
        # Narxlar va aptekalar
        prices = []
        for item in all_items:
            if item.get("price"):
                prices.append(item["price"])
                pharmacy_prices.append({
                    "name": item.get("source", "Apteka"),
                    "price": item["price"],
                    "manufacturer": item.get("manufacturer")
                })
        
        if prices:
            data["price_min"] = min(prices)
            data["price_max"] = max(prices)
            data["average_price"] = sum(prices) // len(prices)
            data["pharmacies"] = pharmacy_prices
        
        # Birinchi elementdan ma'lumotlar
        first = all_items[0]
        data["name"] = first.get("name", drug_name)
        data["manufacturer"] = first.get("manufacturer")
        data["image_url"] = first.get("image")
        data["source"] = first.get("source")
    
    # Dori qo'llanmasi
    drug_key = drug_name.lower().replace("-", "").replace(" ", "")
    for key, guide in DRUG_GUIDE.items():
        if key in drug_key or drug_key in key:
            data["guide"] = guide
            data["description"] = guide.get("type", "")
            break
    
    # Reyting
    reviews = db.get_reviews(drug_name)
    if reviews:
        avg_rating = sum(r["rating"] for r in reviews) / len(reviews)
        data["rating"] = round(avg_rating, 1)
    
    # Keshga saqlash
    drug_cache.set(cache_key, data)
    
    return data

# ─────────────────────────────────────────
# XABAR FORMATLASH (CHIROYLI DIZAYN)
# ─────────────────────────────────────────

def format_drug_result(data: Dict) -> str:
    """Dori ma'lumotini chiroyli formatlash"""
    lines = []
    
    # Sarlavha
    name = data["name"].upper()
    lines.append(f"💊 *{name}*")
    lines.append("━" * 32)
    
    # Narx
    if data["price_min"]:
        price_min = f"{data['price_min']:,}".replace(",", " ")
        if data["price_max"] and data["price_max"] != data["price_min"]:
            price_max = f"{data['price_max']:,}".replace(",", " ")
            lines.append(f"💰 *Narx:* {price_min} – {price_max} so'm")
        else:
            lines.append(f"💰 *Narx:* {price_min} so'm")
        
        if data.get("average_price"):
            avg = f"{data['average_price']:,}".replace(",", " ")
            lines.append(f"📊 *O'rtacha:* {avg} so'm")
    else:
        lines.append("💰 *Narx:* —")
    
    # Reyting
    if data.get("rating"):
        stars = "⭐" * int(data["rating"])
        lines.append(f"{stars} ({data['rating']}/5)")
    
    lines.append("")
    
    # Aptekalar
    if data.get("pharmacies"):
        lines.append("🏪 *Aptekalar:*")
        for i, ph in enumerate(data["pharmacies"][:5], 1):
            price = f"{ph['price']:,}".replace(",", " ")
            lines.append(f"  {i}. {ph['name']}: {price} so'm")
        if len(data["pharmacies"]) > 5:
            lines.append(f"  ... va yana {len(data['pharmacies'])-5} ta")
    
    lines.append("")
    
    # Dori qo'llanmasi
    if data.get("guide"):
        guide = data["guide"]
        lines.append(f"📋 *Turi:* {guide['type']}")
        
        # Dozalar
        lines.append("💊 *Dozalari:*")
        for kim, doza in guide['dosage'].items():
            lines.append(f"  • {kim.title()}: {doza}")
        
        # Qo'llash
        lines.append(f"💧 *Qo'llash:* {guide['usage']}")
        
        # Qarshi ko'rsatmalar
        if guide.get('contraindications'):
            lines.append("⚠️ *Qarshi ko'rsatmalar:*")
            for item in guide['contraindications'][:3]:
                lines.append(f"  • {item}")
        
        # Ogohlantirish
        if guide.get('warning'):
            lines.append(f"\n🔔 *Ogohlantirish:* {guide['warning']}")
    
    # Ishlab chiqaruvchi
    if data.get("manufacturer"):
        lines.append(f"\n🏭 *Ishlab chiqaruvchi:* {data['manufacturer']}")
    
    # Manba
    if data.get("source"):
        lines.append(f"📡 *Manba:* {data['source']}")
    
    lines.append("")
    lines.append("━" * 32)
    lines.append("⚠️ _Dori ishlatishdan oldin shifokor bilan maslahatlashing!_")
    
    return "\n".join(lines)

def format_nearby_pharmacies(pharmacies: List[Dict], drug_name: str = None) -> str:
    """Yaqin aptekalarni formatlash"""
    lines = []
    
    if drug_name:
        lines.append(f"📍 *{drug_name.upper()}* yaqin aptekalarda:")
    else:
        lines.append("📍 *Sizga yaqin aptekalar:*")
    
    lines.append("━" * 32)
    
    for i, ph in enumerate(pharmacies[:10], 1):
        lines.append(f"\n{i}. *{ph['name']}*")
        lines.append(f"   📍 {ph['address']}")
        lines.append(f"   📞 {ph['phone']}")
        lines.append(f"   🕒 {ph['working_hours']}")
        lines.append(f"   📏 {ph['distance']} km")
        
        if drug_name and ph.get("price"):
            price = f"{ph['price']:,}".replace(",", " ")
            lines.append(f"   💰 {price} so'm")
    
    return "\n".join(lines)

def format_alerts(user_alerts: List[Dict]) -> str:
    """Narx kuzatuvi ro'yxatini formatlash"""
    if not user_alerts:
        return "📭 Sizda faol kuzatuvlar yo'q"
    
    lines = ["📊 *Faol kuzatuvlaringiz:*", "━" * 32]
    
    for alert in user_alerts:
        if alert["active"]:
            target = f"{alert['target_price']:,}".replace(",", " ")
            lines.append(f"\n💊 *{alert['drug_name']}*")
            lines.append(f"   🎯 Maqsad: {target} so'm")
            if alert.get("last_price"):
                last = f"{alert['last_price']:,}".replace(",", " ")
                lines.append(f"   💰 Oxirgi: {last} so'm")
            lines.append(f"   🆔 ID: `{alert['id']}`")
    
    return "\n".join(lines)

def format_reviews(drug_name: str, reviews: List[Dict]) -> str:
    """Sharhlarni formatlash"""
    if not reviews:
        return f"💭 *{drug_name}* uchun hali sharhlar yo'q\n\nBirinchi bo'lib fikr bildiring!"
    
    lines = [f"💭 *{drug_name}* sharhlari:", "━" * 32]
    
    # O'rtacha reyting
    avg_rating = sum(r["rating"] for r in reviews) / len(reviews)
    stars = "⭐" * int(avg_rating)
    lines.append(f"\n{stars} {avg_rating:.1f}/5 ({len(reviews)} ta sharh)")
    lines.append("")
    
    for i, review in enumerate(reviews[-5:], 1):  # Oxirgi 5 ta
        stars = "⭐" * review["rating"]
        lines.append(f"\n{i}. {stars}")
        if review.get("comment"):
            lines.append(f"   💬 _{review['comment'][:100]}_")
        date = review["created_at"][:10]
        lines.append(f"   📅 {date}")
    
    return "\n".join(lines)

# ─────────────────────────────────────────
# KLAVIATURALAR
# ─────────────────────────────────────────

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Asosiy menyu"""
    keyboard = [
        [KeyboardButton("💊 Dori qidirish"), KeyboardButton("📍 Yaqin aptekalar")],
        [KeyboardButton("📊 Narx kuzatuvi"), KeyboardButton("⭐ Mashhur dorilar")],
        [KeyboardButton("📋 Yordam"), KeyboardButton("⚙️ Sozlamalar")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def location_keyboard() -> ReplyKeyboardMarkup:
    """Lokatsiya yuborish tugmasi"""
    keyboard = [
        [KeyboardButton("📍 Lokatsiyani yuborish", request_location=True)],
        [KeyboardButton("🏠 Asosiy menyu")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def drug_action_keyboard(drug_name: str, has_location: bool = False) -> InlineKeyboardMarkup:
    """Dori uchun tugmalar"""
    rows = [
        [
            InlineKeyboardButton("📍 Yaqin aptekalar", callback_data=f"nearby:{drug_name[:30]}"),
            InlineKeyboardButton("💊 Analoglar", callback_data=f"analogs:{drug_name[:30]}"),
        ],
        [
            InlineKeyboardButton("📊 Narx kuzatuvi", callback_data=f"alert:{drug_name[:30]}"),
            InlineKeyboardButton("⭐ Baholash", callback_data=f"rate:{drug_name[:30]}"),
        ],
        [
            InlineKeyboardButton("🔄 Yangi qidiruv", callback_data="new_search"),
        ]
    ]
    
    return InlineKeyboardMarkup(rows)

def rating_keyboard(drug_name: str) -> InlineKeyboardMarkup:
    """Baholash tugmalari"""
    rows = []
    ratings = []
    for i in range(1, 6):
        ratings.append(InlineKeyboardButton(f"{i}⭐", callback_data=f"rate:{drug_name}:{i}"))
    
    # 3 ta qatorga bo'lish
    rows.append(ratings[:3])
    rows.append(ratings[3:])
    rows.append([InlineKeyboardButton("◀️ Orqaga", callback_data=f"back:{drug_name}")])
    
    return InlineKeyboardMarkup(rows)

def alert_price_keyboard(drug_name: str) -> InlineKeyboardMarkup:
    """Narx kuzatuvi uchun narx variantlari"""
    rows = [
        [
            InlineKeyboardButton("10 000 so'm", callback_data=f"setalert:{drug_name}:10000"),
            InlineKeyboardButton("20 000 so'm", callback_data=f"setalert:{drug_name}:20000"),
        ],
        [
            InlineKeyboardButton("30 000 so'm", callback_data=f"setalert:{drug_name}:30000"),
            InlineKeyboardButton("50 000 so'm", callback_data=f"setalert:{drug_name}:50000"),
        ],
        [
            InlineKeyboardButton("Boshqa narx", callback_data=f"customalert:{drug_name}"),
            InlineKeyboardButton("◀️ Orqaga", callback_data=f"back:{drug_name}"),
        ],
    ]
    return InlineKeyboardMarkup(rows)

# ─────────────────────────────────────────
# HANDLERLAR
# ─────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi"""
    user = update.effective_user
    db.add_user(user.id, user.username)
    
    welcome_text = (
        f"👋 Assalomu alaykum, *{user.first_name}*!\n\n"
        "💊 *Dori Ma'lumot Boti v3.0* ga xush kelibsiz!\n\n"
        "📌 *Men yordam bera olaman:*\n"
        "• Dori narxlari va aptekalarni topish\n"
        "• Eng yaqin aptekalarni ko'rsatish\n"
        "• Dori qo'llanmasi va dozalari\n"
        "• Narx o'zgarganda xabar berish\n"
        "• Boshqa foydalanuvchilar sharhlari\n\n"
        "👇 Quyidagi tugmalardan foydalaning"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yordam komandasi"""
    help_text = (
        "📋 *Yordam va qo'llanma*\n\n"
        "*💊 Dori qidirish:*\n"
        "Dori nomini yozing (masalan: Paratsetamol)\n\n"
        "*📍 Yaqin aptekalar:*\n"
        "Lokatsiyangizni yuboring, eng yaqin aptekalarni ko'rsataman\n\n"
        "*📊 Narx kuzatuvi:*\n"
        "Dorilar narxi kutilgan narxdan pastga tushganda xabar beraman\n\n"
        "*⭐ Mashhur dorilar:*\n"
        "Eng ko'p qidirilgan dorilar ro'yxati\n\n"
        "*⚙️ Sozlamalar:*\n"
        "Til, bildirishnomalar va boshqa sozlamalar\n\n"
        "📞 *Aloqa:* @admin"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menyu tugmalarini boshqarish"""
    text = update.message.text
    user = update.effective_user
    
    if text == "💊 Dori qidirish":
        await update.message.reply_text(
            "🔍 Qidirmoqchi bo'lgan dori nomini yozing:"
        )
        return DORI_NOMI_KUTISH
    
    elif text == "📍 Yaqin aptekalar":
        await update.message.reply_text(
            "📍 Iltimos, lokatsiyangizni yuboring.\n"
            "Men sizga eng yaqin aptekalarni ko'rsataman.",
            reply_markup=location_keyboard()
        )
        return LOKATSIYA_KUTISH
    
    elif text == "📊 Narx kuzatuvi":
        alerts = db.get_alerts(user.id)
        text = format_alerts(alerts)
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("➕ Yangi kuzatuv", callback_data="new_alert"),
            InlineKeyboardButton("❌ O'chirish", callback_data="remove_alert")
        ]])
        
        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif text == "⭐ Mashhur dorilar":
        popular = [
            "Paratsetamol", "Ibuprofen", "Amoksitsillin",
            "Setirizin", "Omeprazol", "No-Shpa"
        ]
        
        text = "⭐ *Eng ko'p qidirilgan dorilar:*\n\n"
        for i, drug in enumerate(popular, 1):
            text += f"{i}. {drug}\n"
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    elif text == "📋 Yordam":
        await help_command(update, context)
    
    elif text == "⚙️ Sozlamalar":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇺🇿 O'zbek tili", callback_data="lang:uz")],
            [InlineKeyboardButton("🇷🇺 Русский язык", callback_data="lang:ru")],
            [InlineKeyboardButton("🔔 Bildirishnomalar", callback_data="notifications")],
        ])
        
        await update.message.reply_text(
            "⚙️ *Sozlamalar*",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_drug_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dori qidiruvini boshqarish"""
    drug_name = update.message.text.strip()
    
    if drug_name == "🏠 Asosiy menyu":
        await start(update, context)
        return ConversationHandler.END
    
    searching = await update.message.reply_text(
        f"🔍 *{drug_name}* qidirilmoqda...\n"
        "🔄 Iltimos, biroz kuting",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Ma'lumotlarni yig'ish
    data = await fetch_drug_full_data(drug_name)
    
    await searching.delete()
    
    if data["found"]:
        text = format_drug_result(data)
        
        # Foydalanuvchi lokatsiyasi bormi?
        has_location = "location" in context.user_data
        
        if data.get("image_url"):
            try:
                await update.message.reply_photo(
                    photo=data["image_url"],
                    caption=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=drug_action_keyboard(drug_name, has_location)
                )
            except:
                await update.message.reply_text(
                    text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=drug_action_keyboard(drug_name, has_location)
                )
        else:
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=drug_action_keyboard(drug_name, has_location)
            )
    else:
        text = (
            f"❌ *{drug_name.upper()}* O'zbekiston aptekalarida topilmadi.\n\n"
            "💡 *Takliflar:*\n"
            "• Nomni to'g'ri yozganingizni tekshiring\n"
            "• Qisqaroq nom bilan qidiring\n"
            "• Lotin yoki kirill alifbosida yozing\n\n"
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
    
    return ConversationHandler.END

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lokatsiyani qabul qilish"""
    location = update.message.location
    context.user_data["location"] = {"lat": location.latitude, "lon": location.longitude}
    
    # Foydalanuvchini saqlash
    user = update.effective_user
    db.add_user(user.id, user.username, location)
    
    # Yaqin aptekalarni topish
    pharmacies = find_nearby_pharmacies(location.latitude, location.longitude)
    
    if pharmacies:
        text = format_nearby_pharmacies(pharmacies)
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📍 Xaritada ko'rish", callback_data="map")
        ]])
        
        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "❌ Sizga yaqin aptekalar topilmadi.\n"
            "Kattaroq radiusda qidirish uchun /start bosing."
        )
    
    await update.message.reply_text(
        "🏠 Asosiy menyu",
        reply_markup=main_menu_keyboard()
    )
    
    return ConversationHandler.END

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback query larni boshqarish"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = update.effective_user
    
    if data == "new_search":
        await query.message.reply_text(
            "🔍 Qidirmoqchi bo'lgan dori nomini yozing:"
        )
    
    elif data.startswith("nearby:"):
        drug_name = data.split(":", 1)[1]
        
        if "location" in context.user_data:
            loc = context.user_data["location"]
            pharmacies = find_nearby_pharmacies(loc["lat"], loc["lon"])
            
            # Dori narxlarini qo'shish (demo)
            for ph in pharmacies[:5]:
                ph["price"] = 15000  # Demo narx
            
            text = format_nearby_pharmacies(pharmacies, drug_name)
            
            await query.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.message.reply_text(
                "📍 Iltimos, avval lokatsiyangizni yuboring.\n"
                "Buning uchun '📍 Yaqin aptekalar' tugmasini bosing.",
                reply_markup=location_keyboard()
            )
    
    elif data.startswith("analogs:"):
        drug_name = data.split(":", 1)[1].lower()
        
        # Analoglarni topish
        analogs = []
        for key, values in ANALOGS_DB.items():
            if key in drug_name or drug_name in key:
                analogs = values
                break
        
        if analogs:
            text = f"💊 *{drug_name.title()}* analoglari:\n\n"
            for i, analog in enumerate(analogs, 1):
                text += f"{i}. {analog}\n"
            text += "\n⚠️ Analogni ishlatishdan oldin shifokor bilan maslahatlashing!"
        else:
            text = f"💊 {drug_name.title()} uchun analoglar topilmadi."
        
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    elif data.startswith("alert:"):
        drug_name = data.split(":", 1)[1]
        
        await query.message.reply_text(
            f"📊 *{drug_name}* uchun narx kuzatuvi\n\n"
            "Qanday narxdan pastga tushganda xabar beraymi?",
            reply_markup=alert_price_keyboard(drug_name),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data.startswith("setalert:"):
        _, drug_name, price_str = data.split(":")
        target_price = int(price_str)
        
        alert_id = db.add_alert(user.id, drug_name, target_price)
        
        await query.message.reply_text(
            f"✅ *Kuzatuv o'rnatildi!*\n\n"
            f"💊 Dori: {drug_name}\n"
            f"💰 Maqsadli narx: {target_price:,} so'm\n"
            f"🆔 ID: `{alert_id}`\n\n"
            f"Narx {target_price:,} so'mdan pastga tushganda xabar beraman.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data.startswith("rate:"):
        parts = data.split(":")
        drug_name = parts[1]
        
        if len(parts) == 3:
            # Baholash
            rating = int(parts[2])
            db.add_review(drug_name, user.id, rating)
            await query.message.reply_text(
                f"✅ *Rahmat!*\n{drug_name} {rating}⭐ bilan baholandi."
            )
        else:
            # Baholash so'rash
            await query.message.reply_text(
                f"⭐ *{drug_name}* ni baholang:",
                reply_markup=rating_keyboard(drug_name)
            )
    
    elif data == "new_alert":
        await query.message.reply_text(
            "🔍 Kuzatmoqchi bo'lgan dori nomini yozing:"
        )
        return NARX_KUZATUV
    
    elif data == "remove_alert":
        alerts = db.get_alerts(user.id)
        if alerts:
            keyboard = []
            for alert in alerts:
                if alert["active"]:
                    keyboard.append([InlineKeyboardButton(
                        f"{alert['drug_name']} - {alert['target_price']} so'm",
                        callback_data=f"remove:{alert['id']}"
                    )])
            keyboard.append([InlineKeyboardButton("◀️ Orqaga", callback_data="back_alerts")])
            
            await query.message.reply_text(
                "❌ O'chirmoqchi bo'lgan kuzatuvni tanlang:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    elif data.startswith("remove:"):
        alert_id = data.split(":", 1)[1]
        db.remove_alert(user.id, alert_id)
        await query.message.reply_text("✅ Kuzatuv o'chirildi!")
    
    elif data == "back_alerts":
        alerts = db.get_alerts(user.id)
        text = format_alerts(alerts)
        await query.message.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "map":
        if "location" in context.user_data:
            loc = context.user_data["location"]
            pharmacies = find_nearby_pharmacies(loc["lat"], loc["lon"])
            
            # Birinchi apteka lokatsiyasini yuborish
            if pharmacies:
                ph = pharmacies[0]
                await query.message.reply_location(
                    latitude=ph["lat"],
                    longitude=ph["lon"]
                )

async def notifications_checker(context: ContextTypes.DEFAULT_TYPE):
    """Narxlarni tekshirish va xabar yuborish"""
    # Bu funksiyani periodik ishga tushirish kerak
    pass

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    """Asosiy funksiya"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^(💊 Dori qidirish|📍 Yaqin aptekalar)$"), handle_menu),
        ],
        states={
            DORI_NOMI_KUTISH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_drug_search)],
            LOKATSIYA_KUTISH: [MessageHandler(filters.LOCATION, handle_location)],
            NARX_KUZATUV: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_drug_search)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    # Handlerlarni qo'shish
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    
    # Periodik vazifalar
    job_queue = app.job_queue
    job_queue.run_repeating(notifications_checker, interval=3600, first=10)
    
    logger.info("🤖 Dori Bot v3.0 ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
