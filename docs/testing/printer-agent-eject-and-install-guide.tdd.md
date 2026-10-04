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
| 8 | Chek transaction saqlangan oyni Uzbek nomi bilan ko‘rsatadi; modal tarixdagi oylarni qo‘lda tanlash uchun yuklaydi | `python3 -m unittest tests/test_thermal_receipt_layout.py` | PASS |
| 9 | Yangi to‘lov, refund, tarixdan print va PDF fallback bir xil 56 mm kenglik hamda 7 pt ixcham matn profilidan foydalanadi | `python3 -m unittest tests/test_thermal_receipt_layout.py` | PASS |
| 10 | To‘lov tasdiqlash oynasi guruh, oy va summani bo‘sh ochadi; guruh almashtirish summa qiymatini qo‘ymaydi | `python3 -m unittest tests/test_thermal_receipt_layout.py` | PASS |
| 11 | Legacy ikkinchi printer birinchi printerdagi 18 mm footer chiqarishini saqlaydi, lekin `42 04` kesish kodini yubormaydi | `python3 -m unittest tests/test_thermal_receipt_layout.py`; lokal agent smoke | PASS |
| 12 | Agentning ichki test cheki ham real cheklarning 35-belgi profilidan foydalanadi; ikkinchi CUPS queue qog‘oz profili 48×210 mm | `python3 -m unittest tests/test_thermal_receipt_layout.py`; `lpoptions` | PASS |
| 13 | Legacy ikkinchi printer barcha satrda Font-B ni majburlaydi; birinchi va ikkinchi printerga alohida test cheki yuboriladi | `python3 -m unittest tests/test_thermal_receipt_layout.py`; `--test` | PASS |

RED: `test_developer_printer_guide_is_one_clear_installation_flow` yangi 1–3 qadamli sarlavhalar yo‘qligi sababli xato berdi.

GREEN: qo‘llanma bitta oqimga yig‘ildi, eski takroriy Windows/Linux bloklari olib tashlandi; refund cheklari ixchamlashtirildi, chek chiqarish 18 mm ga uzaytirildi va eski ikkinchi printer uchun kesish kodini olib tashlab, ixcham shrift hamda birinchi printerdagi aynan o‘sha ESC J 18 mm chiqarish buyrug‘ini saqlaydigan rejim qo‘shildi. Yuklab olinadigan agentning standart profili ham birinchi printernikidek 56 mm / 1.5 mm / 35 belgi qilib hujjatlashtirildi. Ikkinchi lokal CUPS queue ham birinchi printer bilan bir xil 48×210 mm qog‘oz profiliga o‘tkazildi; agentning ichki test cheki ham eski 42 emas, 35-belgi profildan foydalanadi. Legacy ikkinchi agentda barcha matnlar Font-B ni ikki standart ESC/POS buyrug‘i bilan majburiy yoqadi. Chekga transaction oyi qo‘shildi. To‘lov tasdiqlash oynasi esa har safar guruh, oy va summani bo‘sh ochadi: administrator tarixdagi oyni tanlashi va summani qo‘lda kiritishi mumkin. Yangi va tarixdan qayta chiqarilgan to‘lov/refund cheklari uchun bitta 56 mm, 7 pt PDF fallback profili qo‘llandi. 24 test muvaffaqiyatli o‘tdi.

Qamrov: ushbu o‘zgarish statik qo‘llanma, ESC/POS buyruqlari va moslik rejimini tekshiradi. Brauzerdan copy tugmasi hamda fizik printerda qirqish jarayoni qo‘lda tekshiriladi.
