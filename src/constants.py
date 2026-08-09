LOGIN_ENDPOINT = "https://login.aimharder.com/api/login"

# Login is served from login.aimharder.com, but the class and booking APIs live on
# <box>.aimharder.com. The auth cookie has to be readable from both.
AUTH_COOKIE_NAME = "amhrdrauth"
AUTH_COOKIE_DOMAIN = "aimharder.com"

days_of_week_index = {
    "MONDAY": 0,
    "TUESDAY": 1,
    "WEDNESDAY": 2,
    "THURSDAY": 3,
    "FRIDAY": 4,
    "SATURDAY": 5,
    "SUNDAY": 6,
}


def book_endpoint(box_name):
    return f"https://{box_name}.aimharder.com/api/book"


def classes_endpoint(box_name):
    return f"https://{box_name}.aimharder.com/api/bookings"
