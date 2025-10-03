import unicodedata


def normalize_text(text: str) -> str:
    translate_map = {
        0x00AD: "",  # soft hyphen
        0x00A0: " ",  # non-breaking space
        0x0085: "\n",  # old next line character
        0x000D: "\n",  # carriage return
        0x0022: "“",  # quotation mark ”
        0x201A: ",",  # low-9 quotation mark ‚ to comma
        0x0567: "",  # armenian small letter eh ֧
        0x200B: "",  # zero width space
        0x2060: "",  # word joiner
        0x05C5: "",  # hebrew point holam
        0xFEFF: "",  # byte order mark
    }
    replace_map = {
        "˟": "*",
    }
    for k, v in replace_map.items():
        text = text.replace(k, v)
    text = unicodedata.normalize("NFC", text)
    return text.translate(translate_map)