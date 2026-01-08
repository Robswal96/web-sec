# crear_db.py
import sqlite3

conn = sqlite3.connect('database.db')
conn.execute('''
CREATE TABLE IF NOT EXISTS archivos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    mp3_path TEXT NOT NULL,
    pdf_path TEXT NOT NULL,
    fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')
conn.close()