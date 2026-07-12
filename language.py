"""
World language options and lightweight UI translation helpers.

Translations use Google's public web translation endpoint when a non-English
language is selected. If the network service is unavailable, English text is
returned so the app remains usable.
"""
from functools import lru_cache

import requests


_FAILED_LANGUAGES = set()


WORLD_LANGUAGES = {
    "en": {"name": "English", "native": "English"},
    "af": {"name": "Afrikaans", "native": "Afrikaans"},
    "sq": {"name": "Albanian", "native": "Shqip"},
    "am": {"name": "Amharic", "native": "አማርኛ"},
    "ar": {"name": "Arabic", "native": "العربية"},
    "hy": {"name": "Armenian", "native": "Հայերեն"},
    "as": {"name": "Assamese", "native": "অসমীয়া"},
    "ay": {"name": "Aymara", "native": "Aymara"},
    "az": {"name": "Azerbaijani", "native": "Azərbaycanca"},
    "bm": {"name": "Bambara", "native": "Bamanankan"},
    "eu": {"name": "Basque", "native": "Euskara"},
    "be": {"name": "Belarusian", "native": "Беларуская"},
    "bn": {"name": "Bengali", "native": "বাংলা"},
    "bho": {"name": "Bhojpuri", "native": "भोजपुरी"},
    "bs": {"name": "Bosnian", "native": "Bosanski"},
    "bg": {"name": "Bulgarian", "native": "Български"},
    "ca": {"name": "Catalan", "native": "Català"},
    "ceb": {"name": "Cebuano", "native": "Cebuano"},
    "ny": {"name": "Chichewa", "native": "Chichewa"},
    "zh-CN": {"name": "Chinese Simplified", "native": "简体中文"},
    "zh-TW": {"name": "Chinese Traditional", "native": "繁體中文"},
    "co": {"name": "Corsican", "native": "Corsu"},
    "hr": {"name": "Croatian", "native": "Hrvatski"},
    "cs": {"name": "Czech", "native": "Čeština"},
    "da": {"name": "Danish", "native": "Dansk"},
    "dv": {"name": "Dhivehi", "native": "ދިވެހި"},
    "doi": {"name": "Dogri", "native": "डोगरी"},
    "nl": {"name": "Dutch", "native": "Nederlands"},
    "eo": {"name": "Esperanto", "native": "Esperanto"},
    "et": {"name": "Estonian", "native": "Eesti"},
    "ee": {"name": "Ewe", "native": "Eʋegbe"},
    "fil": {"name": "Filipino", "native": "Filipino"},
    "fi": {"name": "Finnish", "native": "Suomi"},
    "fr": {"name": "French", "native": "Français"},
    "fy": {"name": "Frisian", "native": "Frysk"},
    "gl": {"name": "Galician", "native": "Galego"},
    "ka": {"name": "Georgian", "native": "ქართული"},
    "de": {"name": "German", "native": "Deutsch"},
    "el": {"name": "Greek", "native": "Ελληνικά"},
    "gn": {"name": "Guarani", "native": "Avañe'ẽ"},
    "gu": {"name": "Gujarati", "native": "ગુજરાતી"},
    "ht": {"name": "Haitian Creole", "native": "Kreyòl Ayisyen"},
    "ha": {"name": "Hausa", "native": "Hausa"},
    "haw": {"name": "Hawaiian", "native": "ʻŌlelo Hawaiʻi"},
    "iw": {"name": "Hebrew", "native": "עברית"},
    "hi": {"name": "Hindi", "native": "हिन्दी"},
    "hmn": {"name": "Hmong", "native": "Hmong"},
    "hu": {"name": "Hungarian", "native": "Magyar"},
    "is": {"name": "Icelandic", "native": "Íslenska"},
    "ig": {"name": "Igbo", "native": "Igbo"},
    "ilo": {"name": "Ilocano", "native": "Ilokano"},
    "id": {"name": "Indonesian", "native": "Bahasa Indonesia"},
    "ga": {"name": "Irish", "native": "Gaeilge"},
    "it": {"name": "Italian", "native": "Italiano"},
    "ja": {"name": "Japanese", "native": "日本語"},
    "jv": {"name": "Javanese", "native": "Basa Jawa"},
    "kn": {"name": "Kannada", "native": "ಕನ್ನಡ"},
    "kk": {"name": "Kazakh", "native": "Қазақша"},
    "km": {"name": "Khmer", "native": "ខ្មែរ"},
    "rw": {"name": "Kinyarwanda", "native": "Kinyarwanda"},
    "gom": {"name": "Konkani", "native": "कोंकणी"},
    "ko": {"name": "Korean", "native": "한국어"},
    "kri": {"name": "Krio", "native": "Krio"},
    "ku": {"name": "Kurdish", "native": "Kurdî"},
    "ckb": {"name": "Kurdish Sorani", "native": "کوردیی ناوەندی"},
    "ky": {"name": "Kyrgyz", "native": "Кыргызча"},
    "lo": {"name": "Lao", "native": "ລາວ"},
    "la": {"name": "Latin", "native": "Latina"},
    "lv": {"name": "Latvian", "native": "Latviešu"},
    "ln": {"name": "Lingala", "native": "Lingála"},
    "lt": {"name": "Lithuanian", "native": "Lietuvių"},
    "lg": {"name": "Luganda", "native": "Luganda"},
    "lb": {"name": "Luxembourgish", "native": "Lëtzebuergesch"},
    "mk": {"name": "Macedonian", "native": "Македонски"},
    "mai": {"name": "Maithili", "native": "मैथिली"},
    "mg": {"name": "Malagasy", "native": "Malagasy"},
    "ms": {"name": "Malay", "native": "Bahasa Melayu"},
    "ml": {"name": "Malayalam", "native": "മലയാളം"},
    "mt": {"name": "Maltese", "native": "Malti"},
    "mi": {"name": "Maori", "native": "Māori"},
    "mr": {"name": "Marathi", "native": "मराठी"},
    "mni-Mtei": {"name": "Meiteilon", "native": "ꯃꯤꯇꯩꯂꯣꯟ"},
    "lus": {"name": "Mizo", "native": "Mizo ṭawng"},
    "mn": {"name": "Mongolian", "native": "Монгол"},
    "my": {"name": "Myanmar", "native": "မြန်မာ"},
    "ne": {"name": "Nepali", "native": "नेपाली"},
    "no": {"name": "Norwegian", "native": "Norsk"},
    "or": {"name": "Odia", "native": "ଓଡ଼ିଆ"},
    "om": {"name": "Oromo", "native": "Afaan Oromoo"},
    "ps": {"name": "Pashto", "native": "پښتو"},
    "fa": {"name": "Persian", "native": "فارسی"},
    "pl": {"name": "Polish", "native": "Polski"},
    "pt": {"name": "Portuguese", "native": "Português"},
    "pa": {"name": "Punjabi", "native": "ਪੰਜਾਬੀ"},
    "qu": {"name": "Quechua", "native": "Runasimi"},
    "ro": {"name": "Romanian", "native": "Română"},
    "ru": {"name": "Russian", "native": "Русский"},
    "sm": {"name": "Samoan", "native": "Gagana Samoa"},
    "sa": {"name": "Sanskrit", "native": "संस्कृतम्"},
    "gd": {"name": "Scots Gaelic", "native": "Gàidhlig"},
    "nso": {"name": "Sepedi", "native": "Sepedi"},
    "sr": {"name": "Serbian", "native": "Српски"},
    "st": {"name": "Sesotho", "native": "Sesotho"},
    "sn": {"name": "Shona", "native": "Shona"},
    "sd": {"name": "Sindhi", "native": "سنڌي"},
    "si": {"name": "Sinhala", "native": "සිංහල"},
    "sk": {"name": "Slovak", "native": "Slovenčina"},
    "sl": {"name": "Slovenian", "native": "Slovenščina"},
    "so": {"name": "Somali", "native": "Soomaali"},
    "es": {"name": "Spanish", "native": "Español"},
    "su": {"name": "Sundanese", "native": "Basa Sunda"},
    "sw": {"name": "Swahili", "native": "Kiswahili"},
    "sv": {"name": "Swedish", "native": "Svenska"},
    "tg": {"name": "Tajik", "native": "Тоҷикӣ"},
    "ta": {"name": "Tamil", "native": "தமிழ்"},
    "tt": {"name": "Tatar", "native": "Татарча"},
    "te": {"name": "Telugu", "native": "తెలుగు"},
    "th": {"name": "Thai", "native": "ไทย"},
    "ti": {"name": "Tigrinya", "native": "ትግርኛ"},
    "ts": {"name": "Tsonga", "native": "Tsonga"},
    "tr": {"name": "Turkish", "native": "Türkçe"},
    "tk": {"name": "Turkmen", "native": "Türkmençe"},
    "ak": {"name": "Twi", "native": "Twi"},
    "uk": {"name": "Ukrainian", "native": "Українська"},
    "ur": {"name": "Urdu", "native": "اردو"},
    "ug": {"name": "Uyghur", "native": "ئۇيغۇرچە"},
    "uz": {"name": "Uzbek", "native": "Oʻzbekcha"},
    "vi": {"name": "Vietnamese", "native": "Tiếng Việt"},
    "cy": {"name": "Welsh", "native": "Cymraeg"},
    "xh": {"name": "Xhosa", "native": "isiXhosa"},
    "yi": {"name": "Yiddish", "native": "יידיש"},
    "yo": {"name": "Yoruba", "native": "Yorùbá"},
    "zu": {"name": "Zulu", "native": "isiZulu"},
}


def get_language(code):
    return WORLD_LANGUAGES.get(code, WORLD_LANGUAGES["en"])


def language_options():
    """Return list of 'CODE - Native (English)' strings for a dropdown."""
    return [
        f"{code} - {meta['native']} ({meta['name']})"
        for code, meta in WORLD_LANGUAGES.items()
    ]


def code_from_language_option(option):
    return str(option).split(" - ", 1)[0].strip()


@lru_cache(maxsize=4096)
def translate_text(text, target_lang="en"):
    """Translate short UI text into target_lang, falling back to English."""
    text = "" if text is None else str(text)
    target_lang = target_lang or "en"
    if not text or target_lang == "en" or target_lang not in WORLD_LANGUAGES or target_lang in _FAILED_LANGUAGES:
        return text

    try:
        response = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={
                "client": "gtx",
                "sl": "en",
                "tl": target_lang,
                "dt": "t",
                "q": text,
            },
            timeout=2,
        )
        response.raise_for_status()
        data = response.json()
        translated = "".join(part[0] for part in data[0] if part and part[0])
        return translated or text
    except Exception:
        _FAILED_LANGUAGES.add(target_lang)
        return text
