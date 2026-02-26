# 💊 Dori Qidiruv Telegram Boti

## Bot nima qiladi?
- Dori nomini qabul qiladi (o'zbek yoki rus tilida)
- apteka.uz, tabletka.uz saytlaridan qidiradi
- Narxi, ishlab chiqaruvchi, retsept holati, markirovka ko'rsatadi
- O'zbekistonda yo'q bo'lsa — xorijdan qanday sotib olish mumkinligini aytadi
- O'xshash dorilar (analoglar) tavsiya qiladi
- O'zbek va Rus tillarida ishlaydi

---

## O'rnatish

### 1. Bot token olish
1. Telegram da [@BotFather](https://t.me/BotFather) ga boring
2. `/newbot` yozing
3. Bot nomi va username bering
4. Token oling (ko'rinishi: `123456789:AAF...`)

### 2. Token qo'yish
`bot.py` faylida:
```python
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
```
`YOUR_BOT_TOKEN_HERE` o'rniga tokeningizni qo'ying
**yoki** environment variable sifatida o'rnating.

### 3. Local ishga tushirish
```bash
pip install -r requirements.txt
python bot.py
```

---

## Railway.app ga Deploy qilish (BEPUL)

### 1. GitHub ga upload qiling
```bash
git init
git add .
git commit -m "Dori bot"
git remote add origin https://github.com/USERNAME/dori-bot.git
git push -u origin main
```

### 2. Railway.app da:
1. [railway.app](https://railway.app) ga kiring
2. "New Project" → "Deploy from GitHub repo"
3. Reponi tanlang
4. **Environment Variables** qo'shing:
   - `BOT_TOKEN` = sizning bot tokeningiz

### 3. Tayyor!
Railway avtomatik ishga tushiradi. Bepul 500 soat/oy beradi.

---

## Fayl tuzilmasi
```
dori_bot/
├── bot.py          # Asosiy bot kodi
├── requirements.txt # Kutubxonalar
├── railway.toml    # Railway konfiguratsiyasi
└── README.md       # Ushbu fayl
```

---

## Kelajakda qo'shish mumkin bo'lgan imkoniyatlar
- [ ] Dori eslatmasi (kuniga 2 marta eslatib turish)
- [ ] Foydalanuvchi tarixi (oxirgi qidirilgan dorilar)
- [ ] Admin panel (statistika ko'rish)
- [ ] Ko'proq saytlar qo'shish (health.uz, medsafe.uz)
- [ ] Dori ta'sir o'zaro munosabatlari (2 dori birgalikda xavflimi)

---

## Muhim eslatma
Bu bot ma'lumot berish uchun. Dori ishlatishdan oldin shifokor bilan maslahatlashing!
