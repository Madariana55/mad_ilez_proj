# OCR PDF → SQL

**Импорт текста из изображений PDF-документов с использованием технологии OCR и хранением данных в базе данных SQL**

---

## Стек технологий

| Слой | Технология |
|------|-----------|
| OCR-движок | **Tesseract 5** (pytesseract) |
| PDF → изображения | **pdf2image** (poppler) |
| Предобработка изображений | **Pillow** (grayscale, sharpen, contrast) |
| База данных | **SQLite** (через SQLAlchemy ORM) |
| Веб-фреймворк | **Flask** |
| Фоновая обработка | **threading** |
| Экспорт | TXT, JSON |

---

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                      Пользователь                        │
│                  (браузер / REST-клиент)                 │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP
┌───────────────────────▼─────────────────────────────────┐
│                   Flask Web App                          │
│   POST /api/upload  GET /api/documents  GET /api/search  │
└───────┬───────────────────────────────────┬─────────────┘
        │ threading                          │ SQLAlchemy
┌───────▼──────────────┐         ┌──────────▼────────────┐
│    OCR Engine        │         │    SQLite Database    │
│  pdf2image → PIL     │         │  ┌────────────────┐   │
│  preprocess_image()  │────────►│  │  documents     │   │
│  pytesseract OCR     │         │  │  pages         │   │
│  confidence score    │         │  └────────────────┘   │
└──────────────────────┘         └───────────────────────┘
```

---

## Структура проекта

```
ocr_project/
├── app.py          # Flask-приложение, REST API (8 эндпоинтов)
├── models.py       # SQLAlchemy ORM: Document, Page
├── ocr_engine.py   # OCR-ядро: pdf2image + pytesseract
├── demo_cli.py     # CLI-демонстрация без веб-сервера
├── requirements.txt
├── templates/
│   ├── index.html      # Главная: загрузка, список, поиск
│   └── document.html   # Просмотр страниц, экспорт
└── uploads/            # Загруженные PDF-файлы
```

---

## Установка и запуск

### 1. Системные зависимости
```bash
# Ubuntu / Debian
sudo apt-get install tesseract-ocr tesseract-ocr-rus poppler-utils

# Проверка
tesseract --version
```

### 2. Python-зависимости
```bash
pip install -r requirements.txt
```

### 3. Запуск

**Веб-интерфейс:**
```bash
python app.py
# Открыть: http://localhost:5000
```

**CLI-демонстрация:**
```bash
python demo_cli.py
```

---

## База данных: схема таблиц

### Таблица `documents`

| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | Автоинкремент |
| filename | VARCHAR(255) | Имя файла |
| filepath | VARCHAR(512) | Путь к файлу |
| file_size | INTEGER | Размер в байтах |
| page_count | INTEGER | Число страниц |
| language | VARCHAR(50) | Язык OCR (rus+eng) |
| status | ENUM | pending/processing/done/error |
| error_msg | TEXT | Текст ошибки (если есть) |
| created_at | DATETIME | Дата загрузки |
| updated_at | DATETIME | Дата обновления |

### Таблица `pages`

| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | Автоинкремент |
| document_id | INTEGER FK | Ссылка на documents.id |
| page_number | INTEGER | Номер страницы |
| raw_text | TEXT | Распознанный текст |
| char_count | INTEGER | Кол-во символов |
| word_count | INTEGER | Кол-во слов |
| confidence | FLOAT | Уверенность OCR (0-100) |
| ocr_engine | VARCHAR(50) | Движок (tesseract) |
| processed_at | DATETIME | Дата обработки |

---

## REST API

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| POST | /api/upload | Загрузить PDF, запустить OCR |
| GET | /api/documents | Список всех документов |
| GET | /api/documents/{id} | Метаданные документа |
| GET | /api/documents/{id}/status | Статус обработки |
| GET | /api/documents/{id}/pages | Все страницы с текстом |
| GET | /api/documents/{id}/fulltext | Полный текст документа |
| GET | /api/search?q=запрос | Поиск по всем текстам |
| DELETE | /api/documents/{id} | Удалить документ |

---

## Пример использования API

```bash
# Загрузить PDF
curl -X POST http://localhost:5000/api/upload \
  -F "file=@document.pdf" \
  -F "language=rus+eng"

# Ответ:
# {"doc_id": 1, "message": "Файл принят, OCR запущен"}

# Проверить статус
curl http://localhost:5000/api/documents/1/status

# Получить текст первой страницы
curl http://localhost:5000/api/documents/1/pages/1

# Поиск
curl "http://localhost:5000/api/search?q=договор"
```

---

## Процесс OCR (pipeline)

```
PDF файл
   │
   ▼ pdf2image (poppler, DPI=300)
Список PIL Image (одна на страницу)
   │
   ▼ preprocess_image()
   ├── convert("L")          # Оттенки серого
   ├── SHARPEN filter        # Повышение резкости
   └── Contrast × 2.0       # Повышение контраста
   │
   ▼ pytesseract.image_to_data()
Confidence score (0–100) на каждое слово → усредняется
   │
   ▼ pytesseract.image_to_string()
Текст страницы
   │
   ▼ SQLAlchemy Session
Запись в таблицу pages
```

---

## Автор

Курсовой проект по теме:  
*«Импорт текста из изображений PDF-документов с использованием технологии OCR и хранением данных в базе данных SQL»*
Выполнила студентка кафедры ИСиТ Арчакова Мадина Руслановна.
