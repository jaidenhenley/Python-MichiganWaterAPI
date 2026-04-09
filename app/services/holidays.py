import holidays
from datetime import date

def is_holiday(check_date: date) -> bool:
    mi_holidays = holidays.US(state="MI")
    return check_date in mi_holidays