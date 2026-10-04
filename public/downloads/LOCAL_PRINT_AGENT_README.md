# Diamond Education avtomatik chek printeri

Bu agent chek tasdiqlangach uni lokal termal printerga dialogsiz yuboradi. U faqat shu kompyuterning `127.0.0.1:18765` manzilida ishlaydi; internetga yoki serverga printer ochilmaydi.

## Windows o‘rnatish

1. Termal printer drayverini o‘rnating va Windows **Default printer** sifatida belgilang.
2. Python 3.11 yoki yangirog‘ini `python.org/downloads/windows` dan o‘rnating. O‘rnatishda **Add Python to PATH** bandini belgilang.
3. Shu papkadagi `diamond-print-agent.py`, `run-diamond-print-agent-windows.bat` va `install-diamond-print-agent-windows.ps1` fayllarini bitta papkaga yuklab oling.
4. PowerShell'ni ochib shu papkada quyidagini ishga tushiring:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install-diamond-print-agent-windows.ps1 -Start
   ```

5. Developer → **Lokal chek printeri** sahifasidan holatni tekshiring. Shu sahifada **Test chek chiqarish** tugmasi va qog‘oz eni, ikki chet bo‘shlig‘i, satr eni sozlamalari bor. Saqlangan sozlamalar aynan shu Windows kompyuterida doimiy qoladi.
   Agent chek kesilishidan avval oxirgi qatorlar printer ichida qolmasligi uchun uni 8 mm tashqariga chiqaradi.

## Linux (XPrinter XP-58IIL)

```bash
python3 diamond-print-agent.py --printer XP58IIL
```

Agentni doim ishlashi uchun ushbu buyruqni login/startup xizmatiga qo‘shing. Test uchun:

```bash
python3 diamond-print-agent.py --printer XP58IIL --test
```

## Xavfsizlik va muammo yechimi

- Agent faqat lokal kompyuterda ishlaydi va faqat `diamond-education.uz` so‘rovlarini qabul qiladi.
- Chek yoki o‘quvchi ma’lumotlari diskka yozilmaydi.
- Holat `offline` bo‘lsa agentni qayta ishga tushiring, printer drayveri/USB kabeli va Default printer sozlamasini tekshiring.
- Agent ishlamasa sayt chekni avvalgi brauzer-print oynasi orqali chiqarishga qaytadi.
- Yangi installer har safar shu 8 mm chiqarish sozlamasi bor eng yangi agentni yuklaydi.
