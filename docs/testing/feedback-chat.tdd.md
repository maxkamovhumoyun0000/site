# Taklif va shikoyat chat — TDD qaydi

## Qamrab olingan oqim

- Admin javob yuborsa murojaat `Javob kutilmoqda` holatiga o‘tadi.
- Foydalanuvchi yakunlangan murojaatga yana yozsa, u `Yangi` holatiga qaytadi.
- API eski va yangi status nomlarini bir xil, ko‘rsatiladigan holatga normalizatsiya qiladi.

## Testlar

`tests/test_feedback_chat.py` izolyatsiyalangan unit-testlarni saqlaydi. Ular status o‘tish qoidalarini ma’lumotlar bazasi yoki tashqi tarmoqqa ulanmasdan tekshiradi.

```bash
pytest -q tests/test_feedback_chat.py
```

## Qo‘lda tekshiruv

1. Admin sifatida headerdan `To‘lovlar`ni oching: u desktop drawer/sidebar ichida ko‘rinmasligi kerak. Headerda faqat bitta chat belgisi qoladi.
2. Chat belgisidan `Taklif & Shikoyat`ni bosing: u umumiy chat panelining ichida emas, alohida sahifada ochilishi kerak.
3. Foydalanuvchi murojaat yuborsin; admin uni `Ko‘rilmoqda`ga qo‘ysin va javob bersin. Holat `Javob kutilmoqda` bo‘ladi.
4. Foydalanuvchi javob yozsin; holat yana `Yangi`ga qaytadi. Admin yakunlash uchun `Hal qilindi`ni tanlaydi.
