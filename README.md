# CampusFind - Campus Lost & Found

CampusFind is a campus lost-and-found app built with Streamlit and SQLite. Students can browse and filter reports, register and log in, post lost or found items with optional photos, and submit claim requests. An admin can review claims. The `assets/` folder contains original local illustrations used for the hero and listing placeholders.

## Run locally

Requires Python 3.11 or later.

### Windows (PowerShell)

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m streamlit run streamlit_app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Streamlit opens the app at http://localhost:8501. SQLite creates `campus.db` automatically. To configure an admin locally, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and replace its example credentials. Do not commit `secrets.toml`.

## Deploy with Streamlit Community Cloud

1. Push this project to a GitHub repository, including `streamlit_app.py`, `requirements.txt`, and `.streamlit/config.toml`. Do not upload `.env`, `.streamlit/secrets.toml`, `campus.db`, or uploaded photos.
2. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) with the GitHub account that can access the repository.
3. Choose **Create app**, select the repository and branch, and set the main file to `streamlit_app.py`.
4. In the app's **Settings → Secrets**, add the values below (use your own strong, unique admin password):

   ```toml
   ADMIN_EMAIL = "your-admin-email@example.com"
   ADMIN_PASSWORD = "replace-with-a-unique-strong-password"
   ```

5. Deploy. The app creates the admin account on first startup; public registration only creates student accounts.

The GitHub repository can be public or private, but a private repository must be accessible to the GitHub account connected to Streamlit Community Cloud. Streamlit Cloud installs the pinned dependency ranges from `requirements.txt`.

## Data and deployment limits

This starter uses a local SQLite database and stores uploaded photos in `static/uploads/`. Those files are ignored by Git and are not durable storage on Streamlit Community Cloud: app rebuilds or restarts can lose user accounts, listings, claims, and photos. Use a hosted database and object storage before relying on this app for real campus records. Do not put personal or sensitive information in a public demo.

## Project structure

```text
campus_lost_found/
├── streamlit_app.py
├── .gitignore
├── requirements.txt
├── assets/
│   ├── campus_hero.png
│   └── item_*.png
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
```
