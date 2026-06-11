"""
ocr_engine.py — ядро OCR: конвертация pdf → изображения → текст через tesseract
"""

import os
import logging
from typing import List, Tuple

import pytesseract
from pdf2image import convert_from_path
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)


def preprocess_image(img: Image.Image) -> Image.Image:
    # перевод в оттенки серого, резкость, контраст
    img = img.convert("L")
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(2.0)
    return img


def extract_text_from_page(img: Image.Image, lang: str = "rus+eng") -> Tuple[str, float]:
    # возвращает (текст, уверенность)
    img = preprocess_image(img)

    try:
        data = pytesseract.image_to_data(
            img, lang=lang,
            output_type=pytesseract.Output.DICT
        )
        confidences = [
            int(c) for c in data["conf"]
            if str(c).lstrip("-").isdigit() and int(c) >= 0
        ]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    except Exception:
        avg_conf = 0.0

    text = pytesseract.image_to_string(img, lang=lang)
    return text.strip(), avg_conf


def process_pdf(filepath: str, lang: str = "rus+eng",
                dpi: int = 300) -> List[dict]:
    # возвращает список словарей по страницам: номер, текст, длина, число слов, уверенность
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"файл не найден: {filepath}")

    logger.info(f"конвертация pdf → изображения: {filepath} (dpi={dpi})")
    try:
        images = convert_from_path(filepath, dpi=dpi)
    except Exception as e:
        raise RuntimeError(f"ошибка конвертации pdf: {e}")

    results = []
    total = len(images)

    for idx, img in enumerate(images, start=1):
        logger.info(f"  ocr страница {idx}/{total}…")
        try:
            text, conf = extract_text_from_page(img, lang=lang)
        except Exception as e:
            logger.warning(f"  ошибка ocr на стр. {idx}: {e}")
            text, conf = "", 0.0

        words = [w for w in text.split() if w]
        results.append({
            "page_number": idx,
            "raw_text":    text,
            "char_count":  len(text),
            "word_count":  len(words),
            "confidence":  conf,
        })

    return results


def get_available_languages() -> List[str]:
    # список языков, доступных в tesseract
    try:
        langs = pytesseract.get_languages()
        return langs
    except Exception:
        return ["eng"]
