from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import docker
import os
import threading
import time
import socket
import random
from datetime import timedelta

app = Flask(__name__)
app.secret_key = "votre_clef_secrete"
app.permanent_session_lifetime = timedelta(hours=2)
client = docker.from_env()
running_containers = {}  # { user_id: { image: container } }

DATABASE = 'users.db'
app.jinja_env.globals.update(session=session)

# ---------- Port helper ----------
def get_free_port(start=32770, end=32780):
    ports = list(range(start, end))
    random.shuffle(ports)
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    raise RuntimeError("Aucun port libre disponible dans la plage spécifiée.")

# ---------- DB ----------
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

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template("index.html")

@app.route('/profile_redirect')
def profile_redirect():
    if 'user_id' in session:
        return redirect(url_for('account'))
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
        if user and check_password_hash(user[2], request.form['password']):
            session.permanent = True 
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

    user_id = session['user_id']
    user_containers = running_containers.get(user_id, {})
    rendered_images = []

    for image, container in list(user_containers.items()):
        try:
            container.reload()
            ports = container.attrs['NetworkSettings']['Ports']
            port_bindings = ports.get('22/tcp')

            if isinstance(port_bindings, list) and len(port_bindings) > 0:
                port = port_bindings[0]['HostPort']
                ssh_command = f"ssh dockeruser@217.154.24.12 -p {port}"
            else:
                ssh_command = "⏳ Démarrage en cours..."

            rendered_images.append((image, ssh_command))

        except Exception as e:
            print(f"[ERREUR] reload {image} : {e}")
            rendered_images.append((image, "❌ Erreur conteneur"))

    return render_template("account.html", containers=rendered_images, remaining_time=3600)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/start_container/<image>', methods=['POST'])
def start_container(image):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    if user_id not in running_containers:
        running_containers[user_id] = {}

    if image not in running_containers[user_id]:
        host_port = str(get_free_port(32770, 32780))
        container = client.containers.run(
            image,
            detach=True,
            ports={'22/tcp': host_port},
        )

        # On enregistre le conteneur tout de suite
        running_containers[user_id][image] = container

        # Timer pour arrêt auto
        threading.Thread(target=auto_stop_container, args=(container, user_id, image), daemon=True).start()

    return redirect(url_for('account'))

@app.route('/stop/<image>', methods=['POST'])
def stop_container(image):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    container = running_containers.get(user_id, {}).get(image)
    if container:
        try:
            container.stop()
            container.remove()
        except Exception as e:
            print(f"Erreur arrêt conteneur : {e}")
        running_containers[user_id].pop(image, None)

    return redirect(url_for('account'))

def auto_stop_container(container, user_id, image, delay=3600):
    time.sleep(delay)
    try:
        container.reload()
        if container.status == "running":
            container.stop()
            container.remove()
            print(f"Conteneur {image} de l'utilisateur {user_id} stoppé automatiquement.")
    except Exception as e:
        print(f"Erreur auto-stop : {e}")
    running_containers[user_id].pop(image, None)

# ---------- Main ----------
if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)

