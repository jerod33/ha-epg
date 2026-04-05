from datetime import timedelta

DOMAIN = "epg"

CONF_DAYS = "days"
CONF_TV_IDS = "tv_ids"
CONF_SELECTION_MODE = "selection_mode"
CONF_LANGUAGES = "languages"
CONF_PROVIDERS = "providers"

SELECTION_MODE_LANGUAGE = "language"
SELECTION_MODE_PROVIDER = "provider"
SELECTION_MODE_MANUAL = "manual"

AVAILABLE_LANGUAGES = ["CZ", "SK", "PL", "DE", "EN", "FR", "HU", "IT", "RU", "ES"]
AVAILABLE_PROVIDERS = ["O2", "Skylink", "Skylink SK"]

CHANNELS_PER_PAGE = 20

SCAN_INTERVAL = timedelta(hours=4)
USER_AGENT = "SMSTVP/1.7.3 (242;cs_CZ) ID/ef284441-c1cd-4f9e-8e30-f5d8b1ac170c HW/Redmi Note 7 Android/10 (QKQ1.190910.002)"
BASE_URL = "http://programandroid.365dni.cz/android/v6-program.php"