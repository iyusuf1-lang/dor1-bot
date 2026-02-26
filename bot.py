#!/usr/bin/env python3
"""
Dori qidiruv boti - O'zbekiston va xalqaro bozor
Telegram bot: python-telegram-bot v20+
"""

import asyncio
import logging
import os
import re
import aiohttp
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ─────────────────────────────────────────────
# MATNLAR (O'zbek va Rus)
# ─────────────────────────────────────────────
TEXTS = {
    "uz": {
        "welcome": (
            "💊 *Dori Qidiruv Boti*\n\n"
            "Salom! Men sizga dori haqida to'liq ma'lumot beraman:\n"
            "• Narxi va ishlab chiqaruvchi\n"
            "• Qaysi aptekalar va onlayn do'konlarda bor\n"
            "• Retsept kerakmi yoki yo'qmi\n"
            "• Markirovka holati\n"
            "• O'zbekistonda yo'q bo'lsa — qayerdan sotib olish mumkin\n\n"
            "Dori nomini yozing (o'zbek yoki rus tilida):"
        ),
        "searching": "🔍 *{name}* qidirilmoqda... iltimos kuting.",
        "not_found": (
            "❌ *{name}* O'zbekiston aptekalarida topilmadi.\n\n"
            "🌍 *Qo'shni davlatlardan sotib olish:*\n"
            "• 🇷🇺 **Rossiya:** eapteka.ru, apteka.ru, zdravcity.ru\n"
            "• 🇰🇿 **Qozog'iston:** apteka.kz, zdorovie.kz\n"
            "• 🇰🇬 **Qirg'iziston:** apteka.kg\n"
            "• 🌐 **Xalqaro:** iherb.com, amazon.com\n\n"
            "⚠️ Import qilishdan oldin O'zbekiston bojxona qoidalarini tekshiring!"
        ),
        "language_select": "Tilni tanlang / Выберите язык:",
        "search_again": "🔄 Yangi qidiruv",
        "buy_abroad": "🌍 Xorijdan sotib olish",
        "analogs": "💊 O'xshash dorilar",
    },
    "ru": {
        "welcome": (
            "💊 *Бот поиска лекарств*\n\n"
            "Привет! Я предоставлю полную информацию о лекарстве:\n"
            "• Цена и производитель\n"
            "• В каких аптеках и онлайн-магазинах есть\n"
            "• Нужен ли рецепт\n"
            "• Статус маркировки\n"
            "• Если нет в Узбекистане — где купить\n\n"
            "Напишите название лекарства:"
        ),
        "searching": "🔍 Ищем *{name}*... пожалуйста подождите.",
        "not_found": (
            "❌ *{name}* не найден в аптеках Узбекистана.\n\n"
            "🌍 *Купить в соседних странах:*\n"
            "• 🇷🇺 **Россия:** eapteka.ru, apteka.ru, zdravcity.ru\n"
            "• 🇰🇿 **Казахстан:** apteka.kz, zdorovie.kz\n"
            "• 🇰🇬 **Кыргызстан:** apteka.kg\n"
            "• 🌐 **Международно:** iherb.com, amazon.com\n\n"
            "⚠️ Перед импортом проверьте таможенные правила Узбекистана!"
        ),
        "language_select": "Tilni tanlang / Выберите язык:",
        "search_again": "🔄 Новый поиск",
        "buy_abroad": "🌍 Купить за рубежом",
        "analogs": "💊 Аналоги",
    },
}


def get_lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", "uz")


# ─────────────────────────────────────────────
# WEB SCRAPING FUNKSIYALARI
# ─────────────────────────────────────────────

async def search_apteka_uz(drug_name: str) -> dict:
    """apteka.uz saytidan ma'lumot olish"""
    results = {
        "found": False,
        "name": drug_name,
        "price_min": None,
        "price_max": None,
        "manufacturer": None,
        "country": None,
        "prescription": None,
        "marking": None,
        "description": None,
        "image_url": None,
        "pharmacies": [],
        "online_shops": [],
        "source": None,
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "uz,ru;q=0.9,en;q=0.8",
    }

    search_urls = [
        f"https://apteka.uz/search/?q={drug_name.replace(' ', '+')}",
        f"https://tabletka.uz/search?q={drug_name.replace(' ', '+')}",
    ]

    async with aiohttp.ClientSession() as session:
        # 1. apteka.uz qidirish
        try:
            url = f"https://apteka.uz/search/?q={drug_name.replace(' ', '+')}"
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")

                    # Mahsulot kartochkalarini qidirish
                    product_cards = soup.select(".product-card, .catalog-item, .drug-item, [class*='product']")

                    if not product_cards:
                        # Umumiy qidiruv
                        product_cards = soup.find_all(
                            lambda tag: tag.name in ["div", "article"] and
                            any(cls in tag.get("class", []) for cls in ["product", "item", "card", "drug"])
                        )

                    if product_cards:
                        card = product_cards[0]
                        results["found"] = True
                        results["source"] = "apteka.uz"

                        # Narx
                        price_elem = card.select_one(
                            "[class*='price'], .price, .cost"
                        )
                        if price_elem:
                            price_text = price_elem.get_text(strip=True)
                            numbers = re.findall(r"[\d\s]+", price_text)
                            if numbers:
                                price_str = "".join(numbers[0].split())
                                try:
                                    results["price_min"] = int(price_str)
                                except:
                                    pass

                        # Rasm
                        img = card.select_one("img")
                        if img:
                            src = img.get("src") or img.get("data-src", "")
                            if src and not src.startswith("http"):
                                src = "https://apteka.uz" + src
                            results["image_url"] = src

                        # Nom
                        name_elem = card.select_one("h2, h3, .name, [class*='title']")
                        if name_elem:
                            results["name"] = name_elem.get_text(strip=True)[:100]

        except Exception as e:
            logger.warning(f"apteka.uz xatolik: {e}")

        # 2. tabletka.uz qidirish (agar topilmasa)
        if not results["found"]:
            try:
                url = f"https://tabletka.uz/search?q={drug_name.replace(' ', '+')}"
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, "html.parser")

                        items = soup.select(".product, .item, [class*='drug'], [class*='medicine']")
                        if items:
                            results["found"] = True
                            results["source"] = "tabletka.uz"
                            item = items[0]

                            price_elem = item.select_one("[class*='price']")
                            if price_elem:
                                numbers = re.findall(r"\d+", price_elem.get_text())
                                if numbers:
                                    results["price_min"] = int("".join(numbers[:6]))

                            img = item.select_one("img")
                            if img:
                                results["image_url"] = img.get("src") or img.get("data-src")

            except Exception as e:
                logger.warning(f"tabletka.uz xatolik: {e}")

        # 3. Agar hech birida topilmasa — OpenFDA orqali xalqaro ma'lumot
        if not results["found"]:
            try:
                fda_url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:{drug_name}&limit=1"
                async with session.get(fda_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("results"):
                            result = data["results"][0]
                            results["found"] = True
                            results["source"] = "FDA (AQSh)"
                            results["country"] = "AQSh"

                            openfda = result.get("openfda", {})
                            if openfda.get("manufacturer_name"):
                                results["manufacturer"] = openfda["manufacturer_name"][0]

                            # Retsept holati
                            if result.get("product_type") == ["PRESCRIPTION DRUG"]:
                                results["prescription"] = True
                            elif result.get("product_type") == ["OTC"]:
                                results["prescription"] = False

                            if result.get("purpose"):
                                results["description"] = result["purpose"][0][:300]

            except Exception as e:
                logger.warning(f"FDA API xatolik: {e}")

    # Default ma'lumotlar (agar topildi lekin to'liq emas)
    if results["found"] and not results["prescription"]:
        # Retsept haqida taxminiy ma'lumot - keng tarqalgan OTC doriler
        otc_keywords = [
            "paracetamol", "ibuprofen", "aspirin", "noshpa",
            "analgin", "pentalgin", "suprastin", "loratadin",
            "vitamin", "validol", "corvalol", "activated carbon"
        ]
        drug_lower = drug_name.lower()
        if any(kw in drug_lower for kw in otc_keywords):
            results["prescription"] = False
        else:
            results["prescription"] = None  # Noma'lum

    return results


def format_drug_info_uz(info: dict) -> str:
    """O'zbek tilida dori ma'lumotlarini formatlash"""
    lines = []
    lines.append(f"💊 *{info['name'].upper()}*")
    lines.append("─" * 30)

    if info.get("source"):
        lines.append(f"📡 *Manba:* {info['source']}")

    if info.get("manufacturer"):
        lines.append(f"🏭 *Ishlab chiqaruvchi:* {info['manufacturer']}")

    if info.get("country"):
        lines.append(f"🌍 *Davlat:* {info['country']}")

    if info.get("price_min"):
        price = f"{info['price_min']:,}".replace(",", " ")
        if info.get("price_max"):
            price_max = f"{info['price_max']:,}".replace(",", " ")
            lines.append(f"💰 *Narx:* {price} – {price_max} so'm")
        else:
            lines.append(f"💰 *Narx:* ~{price} so'm")

    # Retsept
    if info.get("prescription") is True:
        lines.append("📋 *Retsept:* ✅ Retsept kerak")
    elif info.get("prescription") is False:
        lines.append("📋 *Retsept:* ❌ Retseptsiz sotiladi")
    else:
        lines.append("📋 *Retsept:* ❓ Aniqlanmagan")

    # Markirovka
    if info.get("marking") is True:
        lines.append("🏷 *Markirovka:* ✅ Mavjud")
    elif info.get("marking") is False:
        lines.append("🏷 *Markirovka:* ❌ Yo'q")
    else:
        lines.append("🏷 *Markirovka:* ❓ Ma'lumot yo'q")

    if info.get("description"):
        desc = info["description"][:200]
        lines.append(f"\n📝 *Tavsif:* {desc}...")

    if info.get("pharmacies"):
        lines.append(f"\n🏪 *Aptekalar:*")
        for ph in info["pharmacies"][:3]:
            lines.append(f"  • {ph}")

    if info.get("online_shops"):
        lines.append(f"\n🛒 *Onlayn do'konlar:*")
        for sh in info["online_shops"][:3]:
            lines.append(f"  • {sh}")

    lines.append("\n─" * 30)
    lines.append("⚠️ _Dori ishlatishdan oldin shifokor bilan maslahatlashing!_")

    return "\n".join(lines)


def format_drug_info_ru(info: dict) -> str:
    """Rus tilida dori ma'lumotlarini formatlash"""
    lines = []
    lines.append(f"💊 *{info['name'].upper()}*")
    lines.append("─" * 30)

    if info.get("source"):
        lines.append(f"📡 *Источник:* {info['source']}")

    if info.get("manufacturer"):
        lines.append(f"🏭 *Производитель:* {info['manufacturer']}")

    if info.get("country"):
        lines.append(f"🌍 *Страна:* {info['country']}")

    if info.get("price_min"):
        price = f"{info['price_min']:,}".replace(",", " ")
        lines.append(f"💰 *Цена:* ~{price} сум")

    if info.get("prescription") is True:
        lines.append("📋 *Рецепт:* ✅ Требуется рецепт")
    elif info.get("prescription") is False:
        lines.append("📋 *Рецепт:* ❌ Без рецепта")
    else:
        lines.append("📋 *Рецепт:* ❓ Неизвестно")

    if info.get("marking") is True:
        lines.append("🏷 *Маркировка:* ✅ Есть")
    elif info.get("marking") is False:
        lines.append("🏷 *Маркировка:* ❌ Нет")
    else:
        lines.append("🏷 *Маркировка:* ❓ Нет данных")

    if info.get("description"):
        desc = info["description"][:200]
        lines.append(f"\n📝 *Описание:* {desc}...")

    lines.append("\n─" * 30)
    lines.append("⚠️ _Перед применением проконсультируйтесь с врачом!_")

    return "\n".join(lines)


def build_result_keyboard(lang: str, drug_name: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    keyboard = [
        [
            InlineKeyboardButton(t["buy_abroad"], callback_data=f"abroad:{drug_name[:30]}"),
            InlineKeyboardButton(t["analogs"], callback_data=f"analogs:{drug_name[:30]}"),
        ],
        [InlineKeyboardButton(t["search_again"], callback_data="new_search")],
    ]
    return InlineKeyboardMarkup(keyboard)


def abroad_info(drug_name: str, lang: str) -> str:
    if lang == "uz":
        return (
            f"🌍 *{drug_name}* — Xorijdan sotib olish yo'llari:\n\n"
            "🇷🇺 *Rossiya:*\n"
            "  • eapteka.ru — yetkazib berish bor\n"
            "  • apteka.ru — katta assortiment\n"
            "  • zdravcity.ru — arzon narxlar\n\n"
            "🇰🇿 *Qozog'iston:*\n"
            "  • apteka.kz\n"
            "  • medfarm.kz\n\n"
            "🇩🇪 *Germaniya (Yevropa):*\n"
            "  • shop-apotheke.com\n"
            "  • medpex.de\n\n"
            "🌐 *Xalqaro:*\n"
            "  • iherb.com (vitamin, BAD)\n"
            "  • amazon.com\n\n"
            "📦 *Yetkazib berish:*\n"
            "  • CDEK, Boxberry — Rossiyadan\n"
            "  • DHL, FedEx — Yevropadan\n\n"
            "⚠️ *Muhim:* O'zbekistonga dori import qilish uchun\n"
            "ruxsat talab qilinishi mumkin. Qimmatbaho va nazorat\n"
            "ostidagi dorilar uchun maxsus ruxsatnoma kerak!"
        )
    else:
        return (
            f"🌍 *{drug_name}* — Покупка за рубежом:\n\n"
            "🇷🇺 *Россия:*\n"
            "  • eapteka.ru — есть доставка\n"
            "  • apteka.ru — большой ассортимент\n"
            "  • zdravcity.ru — низкие цены\n\n"
            "🇰🇿 *Казахстан:*\n"
            "  • apteka.kz\n"
            "  • medfarm.kz\n\n"
            "🇩🇪 *Германия (Европа):*\n"
            "  • shop-apotheke.com\n"
            "  • medpex.de\n\n"
            "🌐 *Международно:*\n"
            "  • iherb.com (витамины, БАД)\n"
            "  • amazon.com\n\n"
            "📦 *Доставка:*\n"
            "  • CDEK, Boxberry — из России\n"
            "  • DHL, FedEx — из Европы\n\n"
            "⚠️ *Важно:* Для ввоза лекарств в Узбекистан\n"
            "может потребоваться разрешение. Для дорогостоящих\n"
            "и контролируемых препаратов нужен специальный пропуск!"
        )


def analogs_info(drug_name: str, lang: str) -> str:
    # Ma'lum dorilor uchun analog ma'lumotlar
    analogs_db = {
        "paracetamol": ["Panadol", "Tylenol", "Efferalgan", "Mexalen"],
        "ibuprofen": ["Nurofen", "Advil", "Ibuprom", "Brufen"],
        "amoxicillin": ["Amoxil", "Flemoxin", "Ospamox", "Amosin"],
        "omeprazol": ["Omez", "Gastrozol", "Losec", "Prilosec"],
        "ciprofloxacin": ["Cifran", "Tsiprobay", "Quintor"],
        "metformin": ["Glucophage", "Siofor", "Gliformin"],
        "atorvastatin": ["Lipitor", "Torvakard", "Atoris"],
        "lisinopril": ["Diroton", "Lisinoton", "Prinivil"],
        "noshpa": ["Drotaverin", "Spasmol", "Spasmomen"],
        "analgin": ["Metamizol", "Baralgin", "Spazgan"],
    }

    drug_lower = drug_name.lower().replace(" ", "")
    found_analogs = []
    for key, values in analogs_db.items():
        if key in drug_lower or drug_lower in key:
            found_analogs = values
            break

    if lang == "uz":
        if found_analogs:
            analog_list = "\n".join(f"  • {a}" for a in found_analogs)
            return f"💊 *{drug_name}* uchun o'xshash dorilar:\n\n{analog_list}\n\n_Analogni ishlatishdan oldin shifokor bilan maslahatlashing!_"
        else:
            return f"💊 *{drug_name}* uchun ma'lumotlar bazasida analog topilmadi.\n\nShifokor yoki farmatsevtdan so'rang."
    else:
        if found_analogs:
            analog_list = "\n".join(f"  • {a}" for a in found_analogs)
            return f"💊 Аналоги *{drug_name}*:\n\n{analog_list}\n\n_Перед применением аналога проконсультируйтесь с врачом!_"
        else:
            return f"💊 Аналоги *{drug_name}* не найдены в базе.\n\nСпросите у врача или фармацевта."


# ─────────────────────────────────────────────
# HANDLER FUNKSIYALARI
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bot boshlash"""
    keyboard = [
        [
            InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang:uz"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        TEXTS["uz"]["language_select"],
        reply_markup=reply_markup
    )


async def handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Til tanlash"""
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":")[1]
    context.user_data["lang"] = lang
    await query.edit_message_text(
        TEXTS[lang]["welcome"],
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dori nomini qabul qilish va qidirish"""
    drug_name = update.message.text.strip()
    lang = get_lang(context)

    # Qidirish boshlandi xabari
    search_msg = await update.message.reply_text(
        TEXTS[lang]["searching"].format(name=drug_name),
        parse_mode="Markdown"
    )

    # Ma'lumot qidirish
    info = await search_apteka_uz(drug_name)

    await search_msg.delete()

    if info["found"]:
        # Ma'lumot topildi
        if lang == "uz":
            text = format_drug_info_uz(info)
        else:
            text = format_drug_info_ru(info)

        keyboard = build_result_keyboard(lang, drug_name)

        if info.get("image_url"):
            try:
                await update.message.reply_photo(
                    photo=info["image_url"],
                    caption=text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception:
                await update.message.reply_text(
                    text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        else:
            await update.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
    else:
        # Topilmadi
        text = TEXTS[lang]["not_found"].format(name=drug_name)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(TEXTS[lang]["buy_abroad"], callback_data=f"abroad:{drug_name[:30]}")],
            [InlineKeyboardButton(TEXTS[lang]["search_again"], callback_data="new_search")],
        ])
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline tugmalar"""
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    data = query.data

    if data == "new_search":
        await query.message.reply_text(
            "🔍 Yangi dori nomini yozing:" if lang == "uz" else "🔍 Напишите название нового лекарства:"
        )

    elif data.startswith("abroad:"):
        drug_name = data.split(":", 1)[1]
        text = abroad_info(drug_name, lang)
        await query.message.reply_text(text, parse_mode="Markdown")

    elif data.startswith("analogs:"):
        drug_name = data.split(":", 1)[1]
        text = analogs_info(drug_name, lang)
        await query.message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_lang(context)
    if lang == "uz":
        text = (
            "ℹ️ *Yordam*\n\n"
            "Bot foydalanish:\n"
            "1. /start — botni qayta ishga tushirish\n"
            "2. Dori nomini yozing (masalan: *Paracetamol*)\n"
            "3. Bot ma'lumot topib beradi\n\n"
            "💡 *Maslahat:* Dori nomini to'g'ri yozing\n"
            "va turli variantlarni sinab ko'ring."
        )
    else:
        text = (
            "ℹ️ *Помощь*\n\n"
            "Использование бота:\n"
            "1. /start — перезапустить бот\n"
            "2. Напишите название лекарства (например: *Парацетамол*)\n"
            "3. Бот найдёт информацию\n\n"
            "💡 *Совет:* Пишите правильное название\n"
            "и попробуйте разные варианты написания."
        )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_language, pattern="^lang:"))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
