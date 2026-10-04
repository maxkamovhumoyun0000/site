# Printer agent: chek chiqarish va o‘rnatish qo‘llanmasi — TDD evidence

Source: foydalanuvchining XP-58IIL chek qirqilishidan oldin oxirgi satrlar printerdan tashqariga chiqishi va Developer sahifasidagi o‘rnatish qo‘llanmasini soddalashtirish talabi.

| # | Kafolat | Test / buyruq | Natija |
|---|---|---|---|
| 1 | Server chekni qirqishdan oldin taxminan 18 mm chiqaradi | `python3 -m unittest tests/test_thermal_receipt_layout.py` | PASS |
| 2 | Yuklab olinadigan agent test cheki uchun ham taxminan 18 mm chiqaradi, installerlar va Developer qo‘llanmasi buni tushuntiradi | `python3 -m unittest tests/test_thermal_receipt_layout.py` | PASS |
| 3 | Developer test cheki haqiqiy chek bilan bir xil server formatida, `DIAMOND EDUCATION` sarlavhasi va saqlangan satr enida yaratiladi | `python3 -m unittest tests/test_thermal_receipt_layout.py` | PASS |
| 4 | Windows installer administrator tasdiqlashi bilan xavfsiz Generic/Text raw queue’ni, Linux installer CUPS raw queue’ni faqat aniq XP-58IIL aniqlanganda tayyorlaydi | `python3 -m unittest tests/test_thermal_receipt_layout.py`; `bash -n public/downloads/install-diamond-print-agent-linux.sh` | PASS |
| 5 | Yuklab olinadigan agent Python sintaksisi to‘g‘ri va frontend lintdan o‘tadi | `python3 -m py_compile public/downloads/diamond-print-agent.py` ; `npm run lint` | PASS |
| 6 | ESC/POS’ni matn sifatida bosadigan ikkinchi printer uchun moslik rejimi `42 04` kabi cut/feed kodlarini olib tashlaydi | `python3 -m unittest tests/test_thermal_receipt_layout.py` | PASS |
| 7 | Yuklab olinadigan agent ham birinchi XP-58IIL printerining 56 mm / 1.5 mm / 35 belgi standart profili bilan boshlanadi | `python3 -m unittest tests/test_thermal_receipt_layout.py` | PASS |
| 8 | Chek transaction saqlangan oyni Uzbek nomi bilan ko‘rsatadi; modal avvalgi to‘lanmagan oy bo‘lsa uni birinchi tanlaydi | `python3 -m unittest tests/test_thermal_receipt_layout.py` | PASS |
| 9 | Yangi to‘lov, refund, tarixdan print va PDF fallback bir xil 56 mm kenglik hamda 7 pt ixcham matn profilidan foydalanadi | `python3 -m unittest tests/test_thermal_receipt_layout.py` | PASS |

RED: `test_developer_printer_guide_is_one_clear_installation_flow` yangi 1–3 qadamli sarlavhalar yo‘qligi sababli xato berdi.

GREEN: qo‘llanma bitta oqimga yig‘ildi, eski takroriy Windows/Linux bloklari olib tashlandi; refund cheklari ixchamlashtirildi, chek chiqarish 18 mm ga uzaytirildi va eski ikkinchi printer uchun kesish/chiqarish buyruqlarini olib tashlab, ixcham shriftni saqlaydigan rejim qo‘shildi. Yuklab olinadigan agentning standart profili ham birinchi printernikidek 56 mm / 1.5 mm / 35 belgi qilib hujjatlashtirildi. Chekga transaction oyi qo‘shildi va keyingi oyda ochilgan to‘lov oynasi eng eski to‘lanmagan oyga yo‘naltirildi. Yangi va tarixdan qayta chiqarilgan to‘lov/refund cheklari uchun bitta 56 mm, 7 pt PDF fallback profili qo‘llandi. 22 test muvaffaqiyatli o‘tdi.

Qamrov: ushbu o‘zgarish statik qo‘llanma, ESC/POS buyruqlari va moslik rejimini tekshiradi. Brauzerdan copy tugmasi hamda fizik printerda qirqish jarayoni qo‘lda tekshiriladi.
