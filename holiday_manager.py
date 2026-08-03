from datetime import date, timedelta
from typing import Dict, List

import holidays


def _fmt_ddmmyyyy(d: date) -> str:
    return d.strftime("%d-%m-%Y")


uz_holidays = holidays.country_holidays("UZ", years=range(2025, 2028))


def is_holiday_or_weekend(check_date: date) -> tuple[bool, str]:
    if check_date.weekday() >= 5:
        return True, "Dam olish kuni (shanba yoki yakshanba)"
    if check_date in uz_holidays:
        return True, f"Bayram: {uz_holidays.get(check_date)}"
    return False, "Oddiy ish kuni"


def get_days_status(start_offset: int = 0, days_count: int = 4, lang: str = "uz") -> List[Dict]:
    from i18n import otmen_reason_for_date, weekday_calendar_name

    today = date.today()
    result: List[Dict] = []
    for i in range(max(0, int(days_count))):
        d = today + timedelta(days=int(start_offset) + i)
        is_special, reason_db = is_holiday_or_weekend(d)
        is_weekend = d.weekday() >= 5
        is_holiday = d in uz_holidays
        wk = weekday_calendar_name(lang, d.weekday())
        reason = otmen_reason_for_date(lang, d)
        date_ui = _fmt_ddmmyyyy(d)
        result.append(
            {
                "date": d,
                "date_str": d.strftime("%Y-%m-%d"),
                "date_ui": date_ui,
                "weekday": wk,
                "is_special": is_special,
                "is_weekend": is_weekend,
                "is_holiday": is_holiday,
                "reason": reason,
                "reason_db": reason_db,
                "full_info": f"{date_ui} ({wk}) — {reason}",
            }
        )
    return result


def get_next_11_days_status(lang: str = "uz") -> List[Dict]:
    # bugun + 10 kun
    return get_days_status(start_offset=0, days_count=11, lang=lang)
