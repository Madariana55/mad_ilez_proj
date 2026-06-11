"""
app.py — Flask-приложение: REST API + веб-интерфейс
"""

import os
import threading
import logging
from datetime import datetime

from flask import (
    Flask, request, jsonify, render_template,
    send_from_directory, abort
)
from werkzeug.utils import secure_filename

from models import Document, Page, ProcessingStatus, init_db
from ocr_engine import process_pdf, get_available_languages

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXT   = {"pdf"}
MAX_MB        = 50

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"]    = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024

engine, Session = init_db(os.path.join(os.path.dirname(__file__), "ocr_storage.db"))


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def run_ocr_background(doc_id: int, filepath: str, lang: str):
    # запускаем ocr в фоне и сохраняем результаты в бд
    session = Session()
    try:
        doc = session.get(Document, doc_id)
        doc.status = ProcessingStatus.PROCESSING
        session.commit()

        page_results = process_pdf(filepath, lang=lang)

        doc.page_count = len(page_results)
        for pr in page_results:
            page = Page(
                document_id = doc_id,
                page_number = pr["page_number"],
                raw_text    = pr["raw_text"],
                char_count  = pr["char_count"],
                word_count  = pr["word_count"],
                confidence  = pr["confidence"],
                ocr_engine  = "tesseract",
                processed_at= datetime.utcnow(),
            )
            session.add(page)

        doc.status     = ProcessingStatus.DONE
        doc.updated_at = datetime.utcnow()
        session.commit()
        logger.info(f"Документ #{doc_id} обработан: {len(page_results)} стр.")

    except Exception as e:
        session.rollback()
        doc = session.get(Document, doc_id)
        if doc:
            doc.status    = ProcessingStatus.ERROR
            doc.error_msg = str(e)
            session.commit()
        logger.error(f"OCR ошибка для doc #{doc_id}: {e}")
    finally:
        session.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/document/<int:doc_id>")
def document_view(doc_id):
    return render_template("document.html", doc_id=doc_id)


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "Файл не передан"}), 400

    f    = request.files["file"]
    lang = request.form.get("language", "rus+eng")

    if f.filename == "":
        return jsonify({"error": "Имя файла пустое"}), 400
    if not allowed_file(f.filename):
        return jsonify({"error": "Разрешены только PDF-файлы"}), 400

    filename = secure_filename(f.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    # если файл с таким именем уже есть — добавляем временную метку
    if os.path.exists(filepath):
        base, ext = os.path.splitext(filename)
        filename  = f"{base}_{int(datetime.utcnow().timestamp())}{ext}"
        filepath  = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    f.save(filepath)
    file_size = os.path.getsize(filepath)

    session = Session()
    try:
        doc = Document(
            filename  = filename,
            filepath  = filepath,
            file_size = file_size,
            language  = lang,
            status    = ProcessingStatus.PENDING,
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id
    finally:
        session.close()

    t = threading.Thread(target=run_ocr_background,
                         args=(doc_id, filepath, lang), daemon=True)
    t.start()

    return jsonify({"message": "Файл принят, OCR запущен", "doc_id": doc_id}), 202


@app.route("/api/documents", methods=["GET"])
def list_documents():
    session = Session()
    try:
        docs = session.query(Document).order_by(Document.created_at.desc()).all()
        return jsonify([d.to_dict() for d in docs])
    finally:
        session.close()


@app.route("/api/documents/<int:doc_id>", methods=["GET"])
def get_document(doc_id):
    session = Session()
    try:
        doc = session.get(Document, doc_id)
        if not doc:
            abort(404)
        return jsonify(doc.to_dict())
    finally:
        session.close()


@app.route("/api/documents/<int:doc_id>/status", methods=["GET"])
def doc_status(doc_id):
    session = Session()
    try:
        doc = session.get(Document, doc_id)
        if not doc:
            abort(404)
        return jsonify({
            "status":    doc.status.value,
            "page_count": doc.page_count,
            "error_msg": doc.error_msg,
        })
    finally:
        session.close()


@app.route("/api/documents/<int:doc_id>/pages", methods=["GET"])
def get_pages(doc_id):
    session = Session()
    try:
        doc = session.get(Document, doc_id)
        if not doc:
            abort(404)
        pages = session.query(Page)\
            .filter_by(document_id=doc_id)\
            .order_by(Page.page_number)\
            .all()
        return jsonify([p.to_dict() for p in pages])
    finally:
        session.close()


@app.route("/api/documents/<int:doc_id>/pages/<int:page_num>", methods=["GET"])
def get_page(doc_id, page_num):
    session = Session()
    try:
        page = session.query(Page)\
            .filter_by(document_id=doc_id, page_number=page_num)\
            .first()
        if not page:
            abort(404)
        return jsonify(page.to_dict())
    finally:
        session.close()


@app.route("/api/documents/<int:doc_id>/fulltext", methods=["GET"])
def full_text(doc_id):
    session = Session()
    try:
        doc = session.get(Document, doc_id)
        if not doc:
            abort(404)
        pages = session.query(Page)\
            .filter_by(document_id=doc_id)\
            .order_by(Page.page_number)\
            .all()
        combined = "\n\n".join(
            f"=== Страница {p.page_number} ===\n{p.raw_text}" for p in pages
        )
        total_words = sum(p.word_count for p in pages)
        avg_conf    = (sum(p.confidence for p in pages) / len(pages)) if pages else 0
        return jsonify({
            "doc_id":      doc_id,
            "filename":    doc.filename,
            "full_text":   combined,
            "total_chars": sum(p.char_count for p in pages),
            "total_words": total_words,
            "avg_confidence": round(avg_conf, 2),
        })
    finally:
        session.close()


@app.route("/api/search", methods=["GET"])
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Параметр q обязателен"}), 400

    session = Session()
    try:
        matches = session.query(Page)\
            .filter(Page.raw_text.ilike(f"%{q}%"))\
            .order_by(Page.document_id, Page.page_number)\
            .all()
        results = []
        for p in matches:
            # контекст вокруг совпадения
            idx  = p.raw_text.lower().find(q.lower())
            ctx  = p.raw_text[max(0, idx-80): idx+80+len(q)]
            results.append({
                "document_id": p.document_id,
                "page_number": p.page_number,
                "context":     "…" + ctx + "…",
            })
        return jsonify({"query": q, "total": len(results), "results": results})
    finally:
        session.close()


@app.route("/api/documents/<int:doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    session = Session()
    try:
        doc = session.get(Document, doc_id)
        if not doc:
            abort(404)
        if os.path.exists(doc.filepath):
            os.remove(doc.filepath)
        session.delete(doc)
        session.commit()
        return jsonify({"message": f"Документ #{doc_id} удалён"})
    finally:
        session.close()


@app.route("/api/languages", methods=["GET"])
def languages():
    return jsonify({"languages": get_available_languages()})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
