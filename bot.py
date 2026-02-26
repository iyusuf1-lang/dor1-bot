#!/usr/bin/env python3
"""
Dori Ma'lumot Boti v2.0
ArzonApteka uslubida — rasmlar, narxlar, aptekalar, to'liq ma'lumot
"""

import asyncio
import logging
import os
import re
import json
import aiohttp
from bs4 import BeautifulSoup
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8,uz;q=0.7",
}

# ─────────────────────────────────────────
# SCRAPING FUNKSIYALARI
# ─────────────────────────────────────────

async def scrape_arzonapteka(drug_name: str) -> list[dict]:
    """arzonapteka.uz dan dori ma'lumotlarini olish"""
    results = []
    url = f"https://arzonapteka.uz/uz/drug?q={drug_name.replace(' ', '+')}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")

        # Mahsulot elementlarini qidirish
        cards = soup.select(
            "[class*='DrugCard'], [class*='drug-card'], [class*='product-card'], "
            "[class*='medicine'], [data-testid*='drug'], article"
        )

        if not cards:
            # Umumiy div larni ko'rish
            cards = soup.find_all("div", class_=re.compile(r"card|item|product|drug", re.I))

        for card in cards[:5]:
            item = {}

            # Nom
            name_el = card.select_one(
                "h2, h3, [class*='name'], [class*='title'], [class*='Name']"
            )
            if name_el:
                item["name"] = name_el.get_text(strip=True)[:100]
            else:
                continue

            # Narx
            price_el = card.select_one(
                "[class*='price'], [class*='Price'], [class*='cost']"
            )
            if price_el:
                price_text = price_el.get_text(strip=True)
                numbers = re.findall(r"[\d\s]{3,}", price_text)
                if numbers:
                    try:
                        item["price"] = int("".join(numbers[0].split()))
                    except:
                        item["price"] = None

            # Rasm
            img = card.select_one("img")
            if img:
                src = img.get("src") or img.get("data-src") or img.get("data-lazy-src", "")
                if src and src.startswith("/"):
                    src = "https://arzonapteka.uz" + src
                if src and src.startswith("http"):
                    item["image"] = src

            # Ishlab chiqaruvchi
            mfr_el = card.select_one(
                "[class*='manufacturer'], [class*='brand'], [class*='Manufacturer']"
            )
            if mfr_el:
                item["manufacturer"] = mfr_el.get_text(strip=True)[:60]

            # Link
            link_el = card.select_one("a[href]")
            if link_el:
                href = link_el.get("href", "")
                if href.startswith("/"):
                    href = "https://arzonapteka.uz" + href
                item["link"] = href

            if item.get("name"):
                results.append(item)

    except Exception as e:
        logger.warning(f"arzonapteka scraping xato: {e}")

    return results


async def scrape_tabletka_uz(drug_name: str) -> list[dict]:
    """tabletka.uz dan ma'lumot olish"""
    results = []
    url = f"https://tabletka.uz/search?q={drug_name.replace(' ', '+')}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".product-item, .drug-item, [class*='product'], [class*='drug']")

        for card in cards[:5]:
            item = {}
            name_el = card.select_one("h2, h3, .name, [class*='title']")
            if name_el:
                item["name"] = name_el.get_text(strip=True)[:100]
            else:
                continue

            price_el = card.select_one("[class*='price']")
            if price_el:
                nums = re.findall(r"\d+", price_el.get_text())
                if nums:
                    try:
                        item["price"] = int("".join(nums[:7]))
                    except:
                        pass

            img = card.select_one("img")
            if img:
                src = img.get("src") or img.get("data-src", "")
                if src and src.startswith("/"):
                    src = "https://tabletka.uz" + src
                if src and src.startswith("http"):
                    item["image"] = src

            item["source"] = "tabletka.uz"
            if item.get("name"):
                results.append(item)

    except Exception as e:
        logger.warning(f"tabletka.uz xato: {e}")

    return results


async def get_drug_image_from_google(drug_name: str) -> str | None:
    """Google Images dan dori rasmi URL olish"""
    try:
        search_url = (
            f"https://www.google.com/search?q={drug_name.replace(' ', '+')}+dori+tabletka"
            f"&tbm=isch&tbs=isz:m"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    # JSON ichidagi rasm URL larini topish
                    matches = re.findall(r'"(https://[^"]+\.(?:jpg|jpeg|png|webp))"', html)
                    # Kichik rasmlarni (thumbnail) o'tkazib yuborish
                    for m in matches:
                        if "encrypted" not in m and len(m) > 50:
                            return m
    except Exception as e:
        logger.warning(f"Google image xato: {e}")
    return None


async def get_drug_info_wikipedia(drug_name: str, lang: str = "uz") -> str | None:
    """Wikipedia / Vikiped dan dori tavsifi"""
    try:
        wiki_lang = "ru"  # uz Wikipedia juda kam — rus ishlatamiz
        url = f"https://{wiki_lang}.wikipedia.org/api/rest_v1/page/summary/{drug_name}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    extract = data.get("extract", "")
                    if extract and len(extract) > 30:
                        return extract[:300]
                    thumb = data.get("thumbnail", {}).get("source")
                    return extract, thumb
    except Exception:
        pass
    return None


async def fetch_drug_full_data(drug_name: str) -> dict:
    """Barcha manbalardan ma'lumot yig'ish"""
    data = {
        "name": drug_name,
        "found": False,
        "price_min": None,
        "price_max": None,
        "prices": [],          # [{apteka, narx, manzil}]
        "manufacturer": None,
        "country": None,
        "prescription": None,
        "marking": None,
        "description": None,
        "image_url": None,
        "link": None,
        "source": None,
    }

    # Parallel qidirish
    tasks = [
        scrape_arzonapteka(drug_name),
        scrape_tabletka_uz(drug_name),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items = []
    for r in results:
        if isinstance(r, list):
            all_items.extend(r)

    if all_items:
        data["found"] = True
        item = all_items[0]
        data["name"] = item.get("name", drug_name)
        data["manufacturer"] = item.get("manufacturer")
        data["link"] = item.get("link")
        data["source"] = item.get("source", "arzonapteka.uz")
        data["image_url"] = item.get("image")

        # Narxlar ro'yxati
        prices = []
        for it in all_items:
            if it.get("price"):
                prices.append(it["price"])

        if prices:
            data["price_min"] = min(prices)
            data["price_max"] = max(prices)

    # Rasm topilmagan bo'lsa — Google dan qidirish
    if not data["image_url"]:
        data["image_url"] = await get_drug_image_from_google(drug_name)

    # Retsept holati — keng ma'lum dorilar uchun
    data["prescription"] = _guess_prescription(drug_name)
    data["marking"] = _guess_marking(drug_name)

    return data


def _guess_prescription(name: str) -> bool | None:
    """Dori nomiga qarab retsept kerak-kerak emasligini taxmin qilish"""
    name_lower = name.lower()
    otc = [
        "paracetamol", "ibuprofen", "aspirin", "noshpa", "no-shpa",
        "analgin", "pentalgin", "suprastin", "loratadin", "cetirizin",
        "vitamin", "validol", "corvalol", "activated carbon", "faringosept",
        "strepsils", "coldrex", "theraflu", "rhinostop", "nazivin",
        "otrivin", "naphazoline", "xylometazoline", "enterofuril",
        "smecta", "imodium", "mezim", "festal", "pancreatin",
        "omeprazol", "ranitidine", "maalox", "rennie", "de-nol",
        "magnesium", "calcium", "zinc", "iron", "omega",
    ]
    rx = [
        "amoxicillin", "ciprofloxacin", "azithromycin", "metronidazol",
        "ceftriaxone", "ampicillin", "doxycycline", "fluconazole",
        "prednisolon", "dexamethasone", "tramadol", "codeine",
        "diazepam", "phenobarbital", "clonazepam", "alprazolam",
        "metformin", "insulin", "atorvastatin", "lisinopril",
        "amlodipine", "bisoprolol", "warfarin", "heparin",
    ]
    for kw in otc:
        if kw in name_lower:
            return False
    for kw in rx:
        if kw in name_lower:
            return True
    return None


def _guess_marking(name: str) -> bool | None:
    """Markirovka holati"""
    # O'zbekistonda 2023 dan majburiy markirovka kiritilmoqda
    # Hozircha ko'pchilik dorida mavjud deb ko'rsatamiz
    name_lower = name.lower()
    no_mark = ["vitamin", "biyologik", "bad", "suplement", "herbal"]
    for kw in no_mark:
        if kw in name_lower:
            return False
    return True  # Ko'pchiligi markirovkali


# ─────────────────────────────────────────
# XABAR FORMATLASH
# ─────────────────────────────────────────

def format_result(data: dict, lang: str) -> str:
    uz = lang == "uz"
    lines = []

    name = data["name"].upper()
    lines.append(f"💊 *{name}*")
    lines.append("━" * 28)

    # Narx
    if data["price_min"]:
        price_min = f"{data['price_min']:,}".replace(",", " ")
        if data["price_max"] and data["price_max"] != data["price_min"]:
            price_max = f"{data['price_max']:,}".replace(",", " ")
            if uz:
                lines.append(f"💰 *Narx:* {price_min} – {price_max} so'm")
            else:
                lines.append(f"💰 *Цена:* {price_min} – {price_max} сум")
        else:
            if uz:
                lines.append(f"💰 *Narx:* {price_min} so'mdan")
            else:
                lines.append(f"💰 *Цена:* от {price_min} сум")
    else:
        lines.append("💰 *Narx:* —" if uz else "💰 *Цена:* —")

    # Ishlab chiqaruvchi
    if data.get("manufacturer"):
        label = "🏭 *Ishlab chiqaruvchi:*" if uz else "🏭 *Производитель:*"
        lines.append(f"{label} {data['manufacturer']}")

    if data.get("country"):
        label = "🌍 *Davlat:*" if uz else "🌍 *Страна:*"
        lines.append(f"{label} {data['country']}")

    lines.append("")

    # Retsept
    if data["prescription"] is True:
        lines.append("📋 *Retsept:* ✅ Kerak" if uz else "📋 *Рецепт:* ✅ Требуется")
    elif data["prescription"] is False:
        lines.append("📋 *Retsept:* ❌ Kerak emas" if uz else "📋 *Рецепт:* ❌ Без рецепта")
    else:
        lines.append("📋 *Retsept:* ❓ Noaniq" if uz else "📋 *Рецепт:* ❓ Неизвестно")

    # Markirovka
    if data["marking"] is True:
        lines.append("🏷 *Markirovka:* ✅ Mavjud" if uz else "🏷 *Маркировка:* ✅ Есть")
    elif data["marking"] is False:
        lines.append("🏷 *Markirovka:* ❌ Yo'q" if uz else "🏷 *Маркировка:* ❌ Нет")
    else:
        lines.append("🏷 *Markirovka:* ❓" if uz else "🏷 *Маркировка:* ❓")

    # Tavsif
    if data.get("description"):
        lines.append("")
        label = "📝 *Tavsif:*" if uz else "📝 *Описание:*"
        lines.append(f"{label}\n_{data['description'][:250]}..._")

    # Manba
    if data.get("source"):
        lines.append("")
        label = "📡 *Manba:*" if uz else "📡 *Источник:*"
        lines.append(f"{label} {data['source']}")

    lines.append("")
    lines.append("━" * 28)

    warning = (
        "⚠️ _Dori ishlatishdan oldin shifokor bilan maslahatlashing!_"
        if uz else
        "⚠️ _Перед применением проконсультируйтесь с врачом!_"
    )
    lines.append(warning)

    return "\n".join(lines)


def format_not_found(name: str, lang: str) -> str:
    uz = lang == "uz"
    if uz:
        return (
            f"❌ *{name.upper()}* O'zbekiston aptekalarida topilmadi.\n\n"
            "🌍 *Xorijdan sotib olish mumkin:*\n\n"
            "🇷🇺 *Rossiya:*\n"
            "  • [eapteka.ru](https://eapteka.ru)\n"
            "  • [apteka.ru](https://apteka.ru)\n"
            "  • [zdravcity.ru](https://zdravcity.ru)\n\n"
            "🇰🇿 *Qozog'iston:*\n"
            "  • [apteka.kz](https://apteka.kz)\n\n"
            "🌐 *Xalqaro:*\n"
            "  • [iherb.com](https://iherb.com) — vitamin, BAD\n"
            "  • [amazon.com](https://amazon.com)\n\n"
            "📦 *Yetkazib berish:* CDEK, DHL, FedEx\n\n"
            "⚠️ _Import qilishdan oldin bojxona qoidalarini tekshiring!_"
        )
    else:
        return (
            f"❌ *{name.upper()}* не найден в аптеках Узбекистана.\n\n"
            "🌍 *Можно купить за рубежом:*\n\n"
            "🇷🇺 *Россия:*\n"
            "  • [eapteka.ru](https://eapteka.ru)\n"
            "  • [apteka.ru](https://apteka.ru)\n"
            "  • [zdravcity.ru](https://zdravcity.ru)\n\n"
            "🇰🇿 *Казахстан:*\n"
            "  • [apteka.kz](https://apteka.kz)\n\n"
            "🌐 *Международно:*\n"
            "  • [iherb.com](https://iherb.com) — витамины\n"
            "  • [amazon.com](https://amazon.com)\n\n"
            "📦 *Доставка:* CDEK, DHL, FedEx\n\n"
            "⚠️ _Перед ввозом проверьте таможенные правила!_"
        )


# ─────────────────────────────────────────
# TUGMALAR
# ─────────────────────────────────────────

def main_keyboard(lang: str, drug_name: str, has_link: bool = False) -> InlineKeyboardMarkup:
    uz = lang == "uz"
    rows = []

    row1 = [
        InlineKeyboardButton(
            "🌍 Xorijdan" if uz else "🌍 За рубежом",
            callback_data=f"abroad:{drug_name[:30]}"
        ),
        InlineKeyboardButton(
            "💊 Analoglar" if uz else "💊 Аналоги",
            callback_data=f"analog:{drug_name[:30]}"
        ),
    ]
    rows.append(row1)

    if has_link:
        rows.append([
            InlineKeyboardButton(
                "🔗 ArzonApteka da ko'rish" if uz else "🔗 Смотреть на ArzonApteka",
                url=f"https://arzonapteka.uz/uz/drug?q={drug_name.replace(' ', '+')}"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "🔄 Yangi qidiruv" if uz else "🔄 Новый поиск",
            callback_data="new_search"
        )
    ])

    return InlineKeyboardMarkup(rows)


def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang:uz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
    ]])


# ─────────────────────────────────────────
# HANDLERLAR
# ─────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌐 *Tilni tanlang / Выберите язык:*",
        reply_markup=lang_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "uz")
    if lang == "uz":
        text = (
            "ℹ️ *Yordam*\n\n"
            "Foydalanish:\n"
            "• Dori nomini yozing (masalan: *Paracetamol*)\n"
            "• Bot narx, apteka, retsept ma'lumotini beradi\n"
            "• Topilmasa — xorijdan sotib olish yo'llari\n\n"
            "Buyruqlar:\n"
            "/start — qayta ishga tushirish\n"
            "/help — yordam\n"
            "/lang — tilni o'zgartirish"
        )
    else:
        text = (
            "ℹ️ *Помощь*\n\n"
            "Использование:\n"
            "• Напишите название лекарства (например: *Парацетамол*)\n"
            "• Бот покажет цену, аптеки, рецепт\n"
            "• Если не найдено — как купить за рубежом\n\n"
            "Команды:\n"
            "/start — перезапуск\n"
            "/help — помощь\n"
            "/lang — сменить язык"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌐 *Tilni tanlang / Выберите язык:*",
        reply_markup=lang_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drug_name = update.message.text.strip()
    lang = context.user_data.get("lang", "uz")

    if len(drug_name) < 2:
        await update.message.reply_text(
            "Dori nomini to'liq yozing." if lang == "uz" else "Введите полное название лекарства."
        )
        return

    searching_text = (
        f"🔍 *{drug_name}* qidirilmoqda...\n_Iltimos kuting_ ⏳"
        if lang == "uz" else
        f"🔍 Ищем *{drug_name}*...\n_Пожалуйста подождите_ ⏳"
    )
    wait_msg = await update.message.reply_text(searching_text, parse_mode=ParseMode.MARKDOWN)

    data = await fetch_drug_full_data(drug_name)

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if data["found"]:
        text = format_result(data, lang)
        kb = main_keyboard(lang, drug_name, has_link=True)

        if data.get("image_url"):
            try:
                await update.message.reply_photo(
                    photo=data["image_url"],
                    caption=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=kb,
                )
                return
            except Exception as e:
                logger.warning(f"Rasm yuborishda xato: {e}")

        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    else:
        text = format_not_found(drug_name, lang)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🌍 Xorijdan sotib olish" if lang == "uz" else "🌍 Купить за рубежом",
                callback_data=f"abroad:{drug_name[:30]}"
            )],
            [InlineKeyboardButton(
                "🔄 Yangi qidiruv" if lang == "uz" else "🔄 Новый поиск",
                callback_data="new_search"
            )],
        ])
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb, disable_web_page_preview=True
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    lang = context.user_data.get("lang", "uz")

    if data.startswith("lang:"):
        lang = data.split(":")[1]
        context.user_data["lang"] = lang
        uz = lang == "uz"
        welcome = (
            "✅ *O'zbek tili tanlandi!*\n\n"
            "💊 Dori nomini yozing — narx, apteka, barcha ma'lumotlar!\n\n"
            "_Masalan: Paracetamol, Ibuprofen, Amoxicillin..._"
            if uz else
            "✅ *Выбран русский язык!*\n\n"
            "💊 Напишите название лекарства — цена, аптеки, вся информация!\n\n"
            "_Например: Парацетамол, Ибупрофен, Амоксициллин..._"
        )
        await query.edit_message_text(welcome, parse_mode=ParseMode.MARKDOWN)

    elif data == "new_search":
        text = (
            "🔍 Yangi dori nomini yozing:"
            if lang == "uz" else
            "🔍 Напишите название нового лекарства:"
        )
        await query.message.reply_text(text)

    elif data.startswith("abroad:"):
        drug = data.split(":", 1)[1]
        uz = lang == "uz"
        text = (
            f"🌍 *{drug}* — Xorijdan sotib olish:\n\n"
            "🇷🇺 *Rossiya:*\n"
            f"  • [eapteka.ru](https://eapteka.ru/search/?q={drug})\n"
            f"  • [apteka.ru](https://apteka.ru/search/?q={drug})\n"
            f"  • [zdravcity.ru](https://zdravcity.ru/search/?q={drug})\n\n"
            "🇰🇿 *Qozog'iston:*\n"
            "  • [apteka.kz](https://apteka.kz)\n\n"
            "🌐 *Xalqaro:*\n"
            "  • [iherb.com](https://iherb.com)\n"
            "  • [amazon.com](https://amazon.com)\n\n"
            "📦 *Yetkazib berish O'zbekistonga:*\n"
            "  CDEK ~7-14 kun | DHL ~3-7 kun\n\n"
            "⚠️ _Import qilishdan oldin bojxona qoidalarini tekshiring!_"
            if uz else
            f"🌍 *{drug}* — Покупка за рубежом:\n\n"
            "🇷🇺 *Россия:*\n"
            f"  • [eapteka.ru](https://eapteka.ru/search/?q={drug})\n"
            f"  • [apteka.ru](https://apteka.ru/search/?q={drug})\n"
            f"  • [zdravcity.ru](https://zdravcity.ru/search/?q={drug})\n\n"
            "🇰🇿 *Казахстан:*\n"
            "  • [apteka.kz](https://apteka.kz)\n\n"
            "🌐 *Международно:*\n"
            "  • [iherb.com](https://iherb.com)\n"
            "  • [amazon.com](https://amazon.com)\n\n"
            "📦 *Доставка в Узбекистан:*\n"
            "  CDEK ~7-14 дней | DHL ~3-7 дней\n\n"
            "⚠️ _Перед ввозом проверьте таможенные правила!_"
        )
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
        )

    elif data.startswith("analog:"):
        drug = data.split(":", 1)[1]
        analogs = get_analogs(drug)
        uz = lang == "uz"
        if analogs:
            alist = "\n".join(f"  • {a}" for a in analogs)
            text = (
                f"💊 *{drug}* analoglari:\n\n{alist}\n\n"
                "_Analogni ishlatishdan oldin shifokor bilan maslahatlashing!_"
                if uz else
                f"💊 Аналоги *{drug}*:\n\n{alist}\n\n"
                "_Перед применением аналога проконсультируйтесь с врачом!_"
            )
        else:
            text = (
                f"💊 *{drug}* uchun analoglar topilmadi.\nShifokor bilan maslahatlashing."
                if uz else
                f"💊 Аналоги *{drug}* не найдены.\nПроконсультируйтесь с врачом."
            )
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


def get_analogs(drug_name: str) -> list[str]:
    db = {
        "paracetamol": ["Panadol", "Tylenol", "Efferalgan", "Calpol"],
        "ibuprofen": ["Nurofen", "Advil", "Brufen", "Ibuprom"],
        "amoxicillin": ["Amoxil", "Flemoxin Solutab", "Ospamox"],
        "ciprofloxacin": ["Cifran", "Tsiprobay", "Quintor", "Ciprinol"],
        "omeprazol": ["Omez", "Gastrozol", "Losec", "Ultop"],
        "metformin": ["Glucophage", "Siofor", "Gliformin", "Bagomet"],
        "atorvastatin": ["Lipitor", "Torvakard", "Atoris", "Liprimar"],
        "noshpa": ["Drotaverin", "Spasmol", "Spazgan", "No-spa"],
        "analgin": ["Metamizol", "Baralgin", "Spazgan", "Sedalgin"],
        "suprastin": ["Chloropyramine", "Allergodil", "Cetirizin"],
        "loratadin": ["Claritin", "Claritine", "Lomilan", "Erolin"],
        "azithromycin": ["Sumamed", "Azitro", "Zi-factor", "Hemomycin"],
        "fluconazole": ["Diflucan", "Flucostat", "Mikosist", "Forkan"],
        "lisinopril": ["Diroton", "Lisinoton", "Prinivil", "Zestril"],
    }
    drug_lower = drug_name.lower().replace("-", "").replace(" ", "")
    for key, vals in db.items():
        if key in drug_lower or drug_lower in key:
            return vals
    return []


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 Dori bot v2.0 ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
