from collections import defaultdict
from mutagen.mp3 import MP3
from flask import send_file
import soundfile as sf


from datetime import datetime
from flask import Flask, render_template, request, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import os
import sqlite3

app = Flask(__name__)
app.secret_key = 'walter'  # Cámbiala por algo más seguro
app.config['UPLOAD_FOLDER_MP3'] = 'static/mp3'
app.config['UPLOAD_FOLDER_PDF'] = 'static/pdf'
app.config['UPLOAD_FOLDER_IMG'] = 'static/imagenes'

# Usuario y contraseña (puedes cambiar esto)
USUARIO_ADMIN = 'walter'
CONTRASENA_HASH = generate_password_hash('walter')



def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Función para conectar con la base de datos
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# ✅ Función para cambiar el tono del archivo MP3
import subprocess

def cambiar_tono_sox(ruta_mp3, semitonos, salida_mp3):
    cents = int(semitonos * 100)  # 1 semitono = 100 cents
    comando = [
        'sox', ruta_mp3, salida_mp3,
        'pitch', str(cents)
    ]
    try:
        subprocess.run(comando, check=True)
    except subprocess.CalledProcessError as e:
        print("❌ Error al aplicar cambio de tono con sox:", e)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario = request.form['usuario']
        contrasena = request.form['contrasena']
        if usuario == USUARIO_ADMIN and check_password_hash(CONTRASENA_HASH, contrasena):
            session['usuario'] = usuario
            return redirect('/admin')
        else:
            error = 'Credenciales incorrectas'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect('/')

@app.route('/')
def index():
    conn = get_db_connection()
    archivos = conn.execute('SELECT * FROM archivos ORDER BY fecha_subida DESC').fetchall()
    conn.close()

    agrupados = defaultdict(list)
    for archivo in archivos:
        fecha = datetime.strptime(archivo['fecha_subida'], '%Y-%m-%d %H:%M:%S').date()
        agrupados[fecha].append(archivo)

    return render_template('index.html', agrupados=agrupados)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    mensaje = None
    tipo_mensaje = "success"


    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        mp3 = request.files.get('mp3')
        pdf = request.files.get('pdf')
        tono = request.form.get('tono')
        bpm = request.form.get('bpm')
        compas = request.form.get('compas')
        duracion = request.form.get('duracion')
        imagen = request.files.get('imagen')
        tonos_seleccionados = request.form.getlist('tono')
        tono = ', '.join(tonos_seleccionados) if tonos_seleccionados else None

        imagen_path = None
        if imagen and imagen.filename != '':
            imagen_path = os.path.join(app.config['UPLOAD_FOLDER_IMG'], imagen.filename)
            imagen.save(imagen_path)

        # Validaciones
        if not titulo:
            mensaje = "❌ El título es obligatorio."
            tipo_mensaje = "error"
        elif not mp3 or mp3.filename == '':
            mensaje = "❌ Debes seleccionar un archivo MP3."
            tipo_mensaje = "error"
        elif not pdf or pdf.filename == '':
            mensaje = "❌ Debes seleccionar un archivo PDF."
            tipo_mensaje = "error"
        else:

            # Guardar archivos en carpetas locales
            mp3_path = os.path.join(app.config['UPLOAD_FOLDER_MP3'], mp3.filename)
            pdf_path = os.path.join(app.config['UPLOAD_FOLDER_PDF'], pdf.filename)
            mp3_path = mp3_path.replace('\\', '/') # ✅ Corrige la barra para que funcione en la web
            pdf_path = pdf_path.replace('\\', '/') # ✅ Corrige la barra para que funcione en la web

            mp3.save(mp3_path)
            pdf.save(pdf_path)

            # ✅ Calcular duración automáticamente con mutagen
            try:
                audio = MP3(mp3_path)
                duracion_segundos = int(audio.info.length)
                minutos = duracion_segundos // 60
                segundos = duracion_segundos % 60
                duracion = f"{minutos}:{segundos:02d}"
            except Exception as e:
                duracion = None
                print("Error al calcular duración:", e)


            # 🔽 Aquí agregas la parte que guarda en la base de datos
            conn = get_db_connection()
            conn.execute('INSERT INTO archivos (titulo, mp3_path, pdf_path, tono, bpm, compas, duracion, imagen_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (titulo, mp3_path, pdf_path, tono, bpm, compas, duracion, imagen_path))
            conn.commit()
            conn.close()

            
            mensaje = "Archivos subidos exitosamente."
            tipo_mensaje = "success"

            

    conn = get_db_connection()
    archivos = conn.execute('SELECT * FROM archivos ORDER BY fecha_subida DESC').fetchall()
    conn.close()

         


    return render_template('admin.html', mensaje=mensaje, tipo_mensaje=tipo_mensaje, archivos=archivos)


@app.route('/cambiar_tono/<int:archivo_id>/<int:n_steps>')
def cambiar_tono(archivo_id, n_steps):
    from datetime import datetime

    conn = get_db_connection()
    archivo = conn.execute('SELECT * FROM archivos WHERE id = ?', (archivo_id,)).fetchone()
    conn.close()

    if not archivo:
        return "Archivo no encontrado", 404

    ruta_original = os.path.join(app.root_path, archivo['mp3_path'])

    if not os.path.exists(ruta_original):
        return "Archivo MP3 no encontrado", 404

    timestamp = int(datetime.now().timestamp())
    nombre_nuevo = f"{archivo_id}_tono_{n_steps}_{timestamp}.mp3"
    ruta_nueva = os.path.join(app.config['UPLOAD_FOLDER_MP3'], nombre_nuevo)
    ruta_nueva_absoluta = os.path.join(app.root_path, ruta_nueva)

    cambiar_tono_sox(ruta_original, n_steps, ruta_nueva_absoluta)

    if not os.path.exists(ruta_nueva_absoluta):
        return "Error al generar el archivo", 500

    return send_file(ruta_nueva_absoluta, mimetype='audio/mpeg')


@app.route('/eliminar/<int:archivo_id>', methods=['POST'])
def eliminar(archivo_id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    archivo = conn.execute('SELECT * FROM archivos WHERE id = ?', (archivo_id,)).fetchone()

    if archivo:
        # Eliminar archivos del disco
        if archivo['mp3_path'] and os.path.exists(archivo['mp3_path']):
            os.remove(archivo['mp3_path'])
        if archivo['pdf_path'] and os.path.exists(archivo['pdf_path']):
            os.remove(archivo['pdf_path'])

        # Eliminar registro de la base de datos
        conn.execute('DELETE FROM archivos WHERE id = ?', (archivo_id,))
        conn.commit()

    conn.close()
    return redirect(url_for('admin', mensaje='Archivo eliminado correctamente.', tipo_mensaje='success'))
    

if __name__ == '__main__':
    app.run(debug=True)

  