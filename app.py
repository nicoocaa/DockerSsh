from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import docker
import os
import threading
import time

app = Flask(__name__)
app.secret_key = "votre_clef_secrete"  # Remplace en production
client = docker.from_env()
running_container = None

DATABASE = 'users.db'

# Rendre session disponible dans tous les templates
app.jinja_env.globals.update(session=session)

# ----------------- DB UTILS -----------------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL)''')
        db.commit()

# ----------------- ROUTES -----------------
@app.route('/')
def index():
    return render_template("index.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
        if user and check_password_hash(user[2], request.form['password']):
            session['user_id'] = user[0]
            return redirect(url_for('account'))
        else:
            error = "Identifiants invalides."
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        db = get_db()
        try:
            hashed_pw = generate_password_hash(request.form['password'])
            db.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                       (request.form['username'], hashed_pw))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            error = "Ce nom d'utilisateur est déjà pris."
    return render_template('register.html', error=error)

@app.route('/account')
def account():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('account.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ----------------- CONTAINER LOGIC -----------------
def auto_stop_container(container, delay=3600):
    time.sleep(delay)
    try:
        container.reload()
        if container.status == "running":
            container.stop()
            container.remove()
            print(f"Conteneur {container.name} arrêté automatiquement après {delay} secondes.")
    except Exception as e:
        print(f"Erreur lors de l'arrêt automatique du conteneur : {e}")

@app.route('/start_container', methods=['POST'])
def start_container():
    global running_container
    container_ip = None

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if not running_container:
        running_container = client.containers.run(
            "debian-ssh-secure",  # Remplace par le nom de ton image
            detach=True,
            ports={'22/tcp': None},
        )
        running_container.reload()
        threading.Thread(target=auto_stop_container, args=(running_container,), daemon=True).start()

    port = running_container.attrs['NetworkSettings']['Ports']['22/tcp'][0]['HostPort']
    container_ip = f"localhost:{port}"
    return render_template("account.html", container_ip=container_ip)

@app.route('/stop', methods=['POST'])
def stop_container():
    global running_container
    if running_container:
        running_container.stop()
        running_container.remove()
        running_container = None
    return redirect(url_for('account'))

# ----------------- MAIN -----------------
if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)

