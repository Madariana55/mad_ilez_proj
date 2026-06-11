#!/usr/bin/env python3
"""
demo_cli.py — демонстрация работы ocr-системы через командную строку.
создаёт тестовый pdf, распознаёт его и сохраняет результаты в бд.

запуск: python demo_cli.py
"""

import os
import sys
import textwrap
from datetime import datetime


def create_sample_pdf(path: str):
    """генерирует многостраничный pdf с текстом на русском и английском."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import cm

    doc    = SimpleDocTemplate(path, pagesize=A4,
                               rightMargin=2*cm, leftMargin=2*cm,
                               topMargin=2*cm,  bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story  = []

    story.append(Paragraph("OCR PDF System — Test Document", styles["Title"]))
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "This document was automatically generated to test the OCR pipeline. "
        "The system uses Tesseract 5 engine to recognize text from scanned images "
        "and stores the results in a structured SQLite database via SQLAlchemy ORM.",
        styles["Normal"]
    ))
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Key Features of the System:",
        styles["Heading2"]
    ))
    for item in [
        "PDF to image conversion (pdf2image / poppler)",
        "Image preprocessing: grayscale, sharpen, contrast boost",
        "Tesseract OCR with multilingual support (rus+eng+deu)",
        "Confidence score per page stored in database",
        "Full-text search across all recognized documents",
        "REST API with Flask + JSON responses",
        "Background processing with threading",
        "Export to TXT / JSON formats",
    ]:
        story.append(Paragraph(f"• {item}", styles["Normal"]))
        story.append(Spacer(1, 4))

    from reportlab.platypus import PageBreak
    story.append(PageBreak())

    story.append(Paragraph("Technical Architecture", styles["Title"]))
    story.append(Spacer(1, 16))
    story.append(Paragraph("Database Schema", styles["Heading2"]))
    story.append(Paragraph(
        "Table: documents — stores metadata for each uploaded PDF file. "
        "Fields: id, filename, filepath, file_size, page_count, language, "
        "status (pending/processing/done/error), error_msg, created_at, updated_at.",
        styles["Normal"]
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Table: pages — stores OCR results per page. "
        "Fields: id, document_id (FK), page_number, raw_text, char_count, "
        "word_count, confidence (0-100), ocr_engine, processed_at.",
        styles["Normal"]
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph("REST API Endpoints", styles["Heading2"]))
    for ep in [
        "POST /api/upload          — загрузка PDF, запуск OCR",
        "GET  /api/documents       — список всех документов",
        "GET  /api/documents/{id}  — метаданные документа",
        "GET  /api/documents/{id}/status  — статус обработки",
        "GET  /api/documents/{id}/pages   — все страницы",
        "GET  /api/documents/{id}/fulltext — полный текст",
        "GET  /api/search?q=...   — полнотекстовый поиск",
        "DELETE /api/documents/{id} — удаление документа",
    ]:
        story.append(Paragraph(ep, styles["Code"]))
        story.append(Spacer(1, 3))

    doc.build(story)
    print(f"  [OK] Тестовый PDF создан: {path}")


def run_demo():
    print("\n" + "="*60)
    print("  OCR PDF → SQL  —  Демонстрация работы системы")
    print("="*60 + "\n")

    sample_pdf = "/tmp/ocr_demo_sample.pdf"
    db_path    = "/tmp/ocr_demo.db"

    print("1. Генерация тестового PDF…")
    try:
        create_sample_pdf(sample_pdf)
    except Exception as e:
        print(f"  [WARN] Не удалось создать PDF через reportlab: {e}")
        # если reportlab не установлен — нужен любой готовый pdf
        if not os.path.exists(sample_pdf):
            print("  Скачайте любой PDF и укажите путь вручную.")
            sys.exit(1)

    print("\n2. Инициализация SQLite базы данных…")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from models import Document, Page, ProcessingStatus, init_db
    _, Session = init_db(db_path)
    print(f"  [OK] База: {db_path}")

    print("\n3. Регистрация документа в БД…")
    session = Session()
    doc = Document(
        filename  = os.path.basename(sample_pdf),
        filepath  = sample_pdf,
        file_size = os.path.getsize(sample_pdf),
        language  = "eng",
        status    = ProcessingStatus.PENDING,
    )
    session.add(doc)
    session.commit()
    doc_id = doc.id
    print(f"  [OK] Document ID = {doc_id}")

    print("\n4. Запуск OCR (Tesseract)…")
    from ocr_engine import process_pdf
    doc.status = ProcessingStatus.PROCESSING
    session.commit()

    t0      = datetime.utcnow()
    results = process_pdf(sample_pdf, lang="eng", dpi=200)
    elapsed = (datetime.utcnow() - t0).total_seconds()

    print("\n5. Сохранение результатов в базу данных…")
    for pr in results:
        page = Page(
            document_id = doc_id,
            page_number = pr["page_number"],
            raw_text    = pr["raw_text"],
            char_count  = pr["char_count"],
            word_count  = pr["word_count"],
            confidence  = pr["confidence"],
            ocr_engine  = "tesseract",
        )
        session.add(page)
        print(f"  Стр.{pr['page_number']}: {pr['word_count']} слов, "
              f"conf={pr['confidence']:.1f}%, {pr['char_count']} символов")

    doc.status     = ProcessingStatus.DONE
    doc.page_count = len(results)
    session.commit()

    print("\n6. Чтение из базы данных (верификация)…")
    saved_pages = session.query(Page).filter_by(document_id=doc_id).all()
    total_words = sum(p.word_count for p in saved_pages)
    total_chars = sum(p.char_count for p in saved_pages)
    avg_conf    = sum(p.confidence for p in saved_pages) / len(saved_pages)

    print(f"\n{'─'*50}")
    print(f"  Документ     : {doc.filename}")
    print(f"  Страниц      : {len(saved_pages)}")
    print(f"  Всего слов   : {total_words}")
    print(f"  Всего символов: {total_chars}")
    print(f"  Ср. уверенность: {avg_conf:.1f}%")
    print(f"  Время OCR    : {elapsed:.2f} сек")
    print(f"  База данных  : {db_path}")
    print(f"{'─'*50}")

    print("\n7. Демонстрация полнотекстового поиска:")
    query = "OCR"
    matches = session.query(Page)\
        .filter(Page.raw_text.ilike(f"%{query}%"))\
        .all()
    print(f"  Запрос: '{query}' → найдено на {len(matches)} странице(ах)")
    for m in matches:
        idx = m.raw_text.lower().find(query.lower())
        ctx = m.raw_text[max(0,idx-40):idx+40+len(query)]
        print(f"  Стр.{m.page_number}: …{ctx.strip()}…")

    session.close()
    print("\n✅  Демонстрация завершена успешно!\n")
    print("Для запуска веб-интерфейса: python app.py")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_demo()
