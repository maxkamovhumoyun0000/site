# Printer agent: chek chiqarish va o‘rnatish qo‘llanmasi — TDD evidence

Source: foydalanuvchining XP-58IIL chek qirqilishidan oldin oxirgi satrlar printerdan tashqariga chiqishi va Developer sahifasidagi o‘rnatish qo‘llanmasini soddalashtirish talabi.

| # | Kafolat | Test / buyruq | Natija |
|---|---|---|---|
| 1 | Server chekni qirqishdan oldin taxminan 13 mm chiqaradi | `python3 -m unittest tests/test_thermal_receipt_layout.py` | PASS |
| 2 | Yuklab olinadigan agent test cheki uchun ham taxminan 13 mm chiqaradi, installerlar va Developer qo‘llanmasi buni tushuntiradi | `python3 -m unittest tests/test_thermal_receipt_layout.py` | PASS |
| 3 | Developer sahifasida Windows/Linux uchun bitta qo‘llanma va 1–3 qadamli oqim bor; eski takroriy bloklar yo‘q | `python3 -m unittest tests/test_thermal_receipt_layout.py` | PASS |
| 4 | Yuklab olinadigan agent Python sintaksisi to‘g‘ri va frontend lintdan o‘tadi | `python3 -m py_compile public/downloads/diamond-print-agent.py` ; `npm run lint` | PASS |

RED: `test_developer_printer_guide_is_one_clear_installation_flow` yangi 1–3 qadamli sarlavhalar yo‘qligi sababli xato berdi.

GREEN: qo‘llanma bitta oqimga yig‘ildi, eski takroriy Windows/Linux bloklari olib tashlandi; 13 test muvaffaqiyatli o‘tdi.

Qamrov: ushbu o‘zgarish statik qo‘llanma va ESC/POS buyruqlarini tekshiradi. Brauzerdan copy tugmasi va fizik printerda qirqish jarayoni qo‘lda tekshiriladi.
