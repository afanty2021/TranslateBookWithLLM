"""语言名称与 ISO 代码映射工具"""


LANG_MAP = {
    "english": "en",
    "chinese": "zh",
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "japanese": "ja",
    "korean": "ko",
    "russian": "ru",
    "italian": "it",
    "portuguese": "pt",
    "arabic": "ar",
    "hindi": "hi",
    "dutch": "nl",
    "polish": "pl",
    "turkish": "tr",
    "vietnamese": "vi",
    "thai": "th",
    "swedish": "sv",
    "czech": "cs",
    "romanian": "ro",
    "hungarian": "hu",
    "ukrainian": "uk",
    "indonesian": "id",
    "malay": "ms",
    "filipino": "fil",
    "bengali": "bn",
    "greek": "el",
    "danish": "da",
    "finnish": "fi",
    "norwegian": "no",
}


def language_to_code(lang: str) -> str:
    """将语言名称转换为 ISO 639-1 代码。已是代码则原样返回。"""
    if not lang:
        return lang
    lang_lower = lang.lower().strip()
    return LANG_MAP.get(lang_lower, lang_lower)
