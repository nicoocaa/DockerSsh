from flask import Flask, render_template, request
import subprocess
import docker

app = Flask(__name__)
client = docker.from_env()

@app.route('/', methods=['GET', 'POST'])
def index():
    container_ip = None
    if request.method == 'POST':
        # Démarre le conteneur
        container = client.containers.run(
            "debian-ssh-secure",  # Remplace par ton image buildée
            detach=True,
            ports={'22/tcp': None},  # Docker choisit un port host libre
        )

        # Récupère les infos réseau
        container.reload()
        port = container.attrs['NetworkSettings']['Ports']['22/tcp'][0]['HostPort']
        ip = "localhost"

        container_ip = f"{ip}:{port}"

    return render_template("index.html", container_ip=container_ip)

if __name__ == "__main__":
    app.run(debug=True)
