from dateutil import parser  # pip install python-dateutil
from zoneinfo import ZoneInfo
from datetime import datetime, timezone, timedelta, time


def convertBattleTime(battleTimeString):
    dt_utc = datetime.strptime(battleTimeString, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(ZoneInfo("America/Phoenix"))

def is_in_war_window(timestamp_str):
    dt = datetime.strptime(timestamp_str, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)
    dt = dt.astimezone(ZoneInfo("America/Phoenix"))

    weekday = dt.weekday()
    days_since_thursday = (weekday - 3) % 7
    thursday_305am = datetime.combine(dt.date(), time(3, 5), tzinfo=ZoneInfo("America/Phoenix")) - timedelta(days=days_since_thursday)
    monday_305am = thursday_305am + timedelta(days=4)

    return thursday_305am <= dt < monday_305am



def check_current_day(ts):
    if isinstance(ts, str):
        ts = datetime.strptime(ts, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)

    # Convert to Arizona time
    ts = ts.astimezone(ZoneInfo("America/Phoenix"))

    # Shift back 3 hours so 2:59am counts as previous day
    shifted_ts = ts - timedelta(hours=3, minutes=5)

    days_map = {
        3: 1,  # Thursday
        4: 2,  # Friday
        5: 3,  # Saturday
        6: 4,  # Sunday
    }
    return days_map.get(shifted_ts.weekday())


from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def get_current_war_day():
    # Current time in Arizona
    now = datetime.now(ZoneInfo("America/Phoenix"))

    # Shift back 2h 45m to align with your war day cutoff
    shifted = now - timedelta(hours=3, minutes=5)

    # Map: 3 = Thursday → day 1, ..., 0 = Monday early morning → day 4
    days_map = {
        0: 4,
        1: 4,
        2: 4,
        3: 1,  # Thursday
        4: 2,  # Friday
        5: 3,  # Saturday
        6: 4,  # Sunday
    } # Only has to run on monday for a bit

    return days_map.get(shifted.weekday(), None)  # returns None if somehow outside map


def main():
    checkTime = '20250522T100058.000Z'
    converted = convertBattleTime(checkTime)
    print(check_current_day(converted))


main()

