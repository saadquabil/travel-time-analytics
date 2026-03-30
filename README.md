# NYC Boulevard Traffic Dashboard

Dashboard d'analyse du trafic et du **travel time** sur les boulevards de New York (NYC DOT).

## Architecture

```
Browser :3000
    |
    v
frontend (Nginx)        -- sert le HTML, proxy /api/* vers le backend
    |
    v
backend  (Python) :8765 -- API REST, lit les donnees depuis MongoDB
    |
    v
mongo    (MongoDB) :27017 -- stocke les segments et metadonnees

seed     (Python)        -- importe le CSV dans MongoDB (one-shot)
```

| Service    | Role                                        | Port  |
|------------|---------------------------------------------|-------|
| `frontend` | Sert l'interface web (Nginx)                | 3000  |
| `backend`  | API REST (Python)                           | 8765  |
| `mongo`    | Base de donnees MongoDB                     | 27017 |
| `seed`     | Import CSV vers MongoDB (s'arrete apres)    | —     |

## Prerequis

- [Docker](https://docs.docker.com/get-docker/) (v20+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2+)

## Lancement rapide

```bash
# Cloner le projet et se placer dans le repertoire
cd nyc_v4

# Lancer tout le projet

```

C'est tout. Les 4 services demarrent dans l'ordre :
1. **mongo** demarre
2. **seed** lit `data/traffic.csv`, calcule les segments, les insere dans MongoDB, puis s'arrete
3. **backend** demarre et se connecte a MongoDB
4. **frontend** demarre et proxy les requetes API vers le backend

## Acces

| Interface          | URL                          |
|--------------------|------------------------------|
| Dashboard          | http://localhost:3000        |
| API - segments     | http://localhost:8765/api/segments |
| API - meta         | http://localhost:8765/api/meta    |
| API - health       | http://localhost:8765/api/health  |
| MongoDB            | mongodb://localhost:27017/nyc_traffic |

## Commandes utiles

```bash
# Lancer le projet
docker compose up --build

# Lancer en arriere-plan
docker compose up --build -d

# Voir les logs
docker compose logs -f

# Voir les logs d'un service specifique
docker compose logs -f backend

# Relancer l'import des donnees
docker compose run seed

# Arreter les conteneurs
docker compose down

# Arreter et supprimer les donnees MongoDB
docker compose down -v

# Reconstruire les images sans cache
docker compose build --no-cache
```

## Structure du projet

```
nyc_v4/
|-- frontend/
|   |-- index.html          Interface web (Leaflet + Chart.js)
|   |-- nginx.conf          Configuration Nginx (proxy API)
|   |-- Dockerfile          Image Nginx
|
|-- backend/
|   |-- server.py           Serveur API Python (lit MongoDB)
|   |-- requirements.txt    Dependances Python (pymongo)
|   |-- Dockerfile          Image Python
|
|-- seed/
|   |-- seed.py             Script d'import CSV -> MongoDB
|   |-- requirements.txt    Dependances Python (pymongo)
|   |-- Dockerfile          Image Python
|
|-- data/
|   |-- traffic.csv         Donnees source (5460 lignes)
|   |-- build_segments.py   Script original (reference)
|
|-- docker-compose.yml      Orchestration des services
|-- .env.example            Variables d'environnement
|-- .dockerignore           Fichiers exclus du build Docker
|-- run.py                  Lancement hors Docker (optionnel)
|-- README.md               Ce fichier
```

## Endpoints API

### GET /api/segments

Retourne tous les segments avec leurs statistiques.

Parametre optionnel : `?status=critical` (filtre par statut).

Statuts possibles : `free`, `normal`, `slow`, `heavy`, `critical`.

### GET /api/meta

Retourne les metadonnees globales (stats, seuils, resume des segments).

### GET /api/health

Retourne `{"ok": true, "segments": 16}` si le backend fonctionne.

## Variables d'environnement

| Variable    | Default                                | Description               |
|-------------|----------------------------------------|---------------------------|
| `MONGO_URI` | `mongodb://mongo:27017/nyc_traffic`    | URI de connexion MongoDB  |
| `PORT`      | `8765`                                 | Port du backend           |
| `CSV_PATH`  | `/data/traffic.csv`                    | Chemin du fichier CSV     |

## Collections MongoDB

### `segments`

16 documents, un par segment routier. Champs : `id`, `name`, `pts` (coordonnees GPS), `avg_speed`, `avg_tt`, `min_tt`, `max_tt`, `p10_tt`, `p90_tt`, `n_samples`, `status`, `color`, `weight`.

### `meta`

1 document (`_id: "main"`) contenant les statistiques globales et les seuils de classification.

## Technologies

- **Frontend** : HTML/CSS/JS, Leaflet (carte), Chart.js (graphiques)
- **Backend** : Python 3.11, pymongo
- **Base de donnees** : MongoDB 7
- **Conteneurisation** : Docker, Docker Compose
- **Reverse proxy** : Nginx
