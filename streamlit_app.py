import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

import streamlit as st
from PIL import Image, UnidentifiedImageError
from streamlit.errors import StreamlitSecretNotFoundError
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
CATEGORIES = [
    "Electronics",
    "Accessories",
    "Books & notes",
    "Clothing",
    "Keys & cards",
    "Other",
]
MAX_IMAGE_BYTES = 5 * 1024 * 1024

st.set_page_config(page_title="CampusFind | Lost & Found", page_icon="⌖", layout="wide")


def setting(name, default=""):
    try:
        return st.secrets[name]
    except (KeyError, StreamlitSecretNotFoundError):
        return os.environ.get(name, default)


DB_PATH = Path(setting("DATABASE_PATH", str(BASE_DIR / "campus.db")))


@contextmanager
def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize_db():
    with connect_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                item_type TEXT NOT NULL CHECK(item_type IN ('lost', 'found')),
                location TEXT NOT NULL,
                event_date TEXT NOT NULL,
                image TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                user_id INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL REFERENCES items(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
            """
        )
        admin_email = setting("ADMIN_EMAIL").strip().lower()
        admin_password = setting("ADMIN_PASSWORD")
        if bool(admin_email) != bool(admin_password):
            raise ValueError("Set both ADMIN_EMAIL and ADMIN_PASSWORD to configure the admin account.")
        if admin_email:
            user = conn.execute("SELECT id FROM users WHERE email = ?", (admin_email,)).fetchone()
            if user:
                conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user["id"],))
            else:
                conn.execute(
                    """INSERT INTO users(name, email, password, role, created_at)
                       VALUES (?, ?, ?, 'admin', ?)""",
                    (
                        "Campus Admin",
                        admin_email,
                        generate_password_hash(admin_password),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )


def get_user(user_id):
    if not user_id:
        return None
    with connect_db() as conn:
        return conn.execute(
            "SELECT id, name, email, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def current_user():
    return get_user(st.session_state.get("user_id"))


def query_items(search, item_type, category):
    sql = """SELECT items.*, users.name AS reporter
             FROM items JOIN users ON users.id = items.user_id
             WHERE items.status = 'open'"""
    params = []
    if search:
        sql += " AND (items.title LIKE ? OR items.description LIKE ? OR items.location LIKE ?)"
        params.extend([f"%{search}%"] * 3)
    if item_type != "All":
        sql += " AND items.item_type = ?"
        params.append(item_type.lower())
    if category != "All":
        sql += " AND items.category = ?"
        params.append(category)
    sql += " ORDER BY items.created_at DESC"
    with connect_db() as conn:
        return conn.execute(sql, params).fetchall()


def store_image(upload):
    if upload is None:
        return None
    data = upload.getvalue()
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Images must be 5 MB or smaller.")
    try:
        with Image.open(upload) as source:
            source.verify()
        upload.seek(0)
        with Image.open(upload) as source:
            if source.width * source.height > 25_000_000:
                raise ValueError("Images must be 25 megapixels or smaller.")
            image = source.convert("RGB")
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            filename = f"{uuid.uuid4().hex}.jpg"
            image.save(UPLOAD_DIR / filename, format="JPEG", quality=88, optimize=True)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Choose a valid PNG, JPG, JPEG, or WEBP image.") from exc
    return filename


def render_auth():
    login_tab, register_tab = st.tabs(["Log in", "Create account"])
    with login_tab:
        with st.form("login_form"):
            email = st.text_input("College email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)
        if submitted:
            with connect_db() as conn:
                user = conn.execute(
                    "SELECT id, password FROM users WHERE email = ?",
                    (email.strip().lower(),),
                ).fetchone()
            if user and check_password_hash(user["password"], password):
                st.session_state.user_id = user["id"]
                st.rerun()
            st.error("Incorrect email or password.")
    with register_tab:
        with st.form("register_form"):
            name = st.text_input("Full name", max_chars=80)
            email = st.text_input("College email", key="register_email")
            password = st.text_input("Password (at least 8 characters)", type="password", key="register_password")
            submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
        if submitted:
            name, email = name.strip(), email.strip().lower()
            if not name or "@" not in email or len(password) < 8:
                st.error("Enter your name, a valid email, and a password of at least 8 characters.")
            else:
                try:
                    with connect_db() as conn:
                        cursor = conn.execute(
                            """INSERT INTO users(name, email, password, created_at)
                               VALUES (?, ?, ?, ?)""",
                            (
                                name,
                                email,
                                generate_password_hash(password),
                                datetime.now(timezone.utc).isoformat(),
                            ),
                        )
                    st.session_state.user_id = cursor.lastrowid
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("An account with that email already exists.")


def save_listing(user, kind, category, title, description, location, event_date, upload):
    if not all((title.strip(), description.strip(), location.strip())):
        raise ValueError("Complete the item name, description, and location.")
    image = store_image(upload)
    with connect_db() as conn:
        conn.execute(
            """INSERT INTO items
               (title, description, category, item_type, location, event_date, image, user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                title.strip(),
                description.strip(),
                category,
                kind.lower(),
                location.strip(),
                event_date.isoformat(),
                image,
                user["id"],
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def render_browse(user):
    st.subheader("Find what you're looking for")
    st.caption("Browse recent reports from around campus.")
    filters = st.columns([2, 1, 1])
    search = filters[0].text_input("Search listings", placeholder="Item, place, or detail")
    kind = filters[1].selectbox("Report type", ["All", "Lost", "Found"])
    category = filters[2].selectbox("Category", ["All", *CATEGORIES])
    items = query_items(search.strip(), kind, category)
    st.caption(f"{len(items)} open {'listing' if len(items) == 1 else 'listings'}")
    if not items:
        st.info("No listings match those filters yet.")
        return
    labels = {
        row["id"]: f'{row["item_type"].title()}: {row["title"]} · {row["location"]}'
        for row in items
    }
    selected_id = st.selectbox("Choose a listing to view details", labels, format_func=labels.get)
    item = next(row for row in items if row["id"] == selected_id)
    with st.container(border=True):
        st.markdown(f"### {item['title']}")
        st.caption(f"{item['item_type'].upper()} · {item['category']}")
        columns = st.columns([1, 2])
        image_path = UPLOAD_DIR / item["image"] if item["image"] else None
        if image_path and image_path.is_file():
            columns[0].image(str(image_path), use_container_width=True)
        columns[1].write(item["description"])
        columns[1].write(f"**Location:** {item['location']}")
        columns[1].write(f"**Date:** {item['event_date']}")
        columns[1].write(f"**Reported by:** {item['reporter']}")
        if user and user["id"] != item["user_id"]:
            with st.form(f"claim_{item['id']}"):
                message = st.text_area(
                    "Share identifying details only the owner would know (at least 10 characters)."
                )
                submitted = st.form_submit_button("Send claim request", type="primary")
            if submitted:
                if len(message.strip()) < 10:
                    st.error("Please provide at least 10 characters of useful detail.")
                else:
                    with connect_db() as conn:
                        conn.execute(
                            "INSERT INTO claims(item_id, user_id, message, created_at) VALUES (?, ?, ?, ?)",
                            (
                                item["id"],
                                user["id"],
                                message.strip(),
                                datetime.now(timezone.utc).isoformat(),
                            ),
                        )
                    st.success("Claim sent. The reporter can review it.")
        elif not user:
            st.info("Log in to send a claim request.")
        else:
            st.caption("This is your listing.")


def render_report(user):
    st.subheader("Report an item")
    st.caption("Share clear details. Avoid posting sensitive personal information.")
    with st.form("listing_form", clear_on_submit=True):
        first, second = st.columns(2)
        kind = first.selectbox("Report type", ["Lost", "Found"])
        category = second.selectbox("Category", CATEGORIES)
        title = st.text_input("Item name", max_chars=100)
        description = st.text_area("Description")
        first, second = st.columns(2)
        location = first.text_input("Location")
        event_date = second.date_input("Date", value=date.today(), max_value=date.today())
        upload = st.file_uploader("Photo (optional, PNG/JPG/WEBP, max 5 MB)", type=["png", "jpg", "jpeg", "webp"])
        submitted = st.form_submit_button("Publish report", type="primary")
    if submitted:
        try:
            save_listing(user, kind, category, title, description, location, event_date, upload)
            st.success("Your report is now live.")
        except ValueError as exc:
            st.error(str(exc))


def render_my_claims(user):
    st.subheader("My claim requests")
    with connect_db() as conn:
        claims = conn.execute(
            """SELECT claims.*, items.title
               FROM claims JOIN items ON items.id = claims.item_id
               WHERE claims.user_id = ?
               ORDER BY claims.created_at DESC""",
            (user["id"],),
        ).fetchall()
    if not claims:
        st.info("You haven't sent any claim requests yet.")
        return
    for claim in claims:
        with st.container(border=True):
            st.markdown(f"**{claim['title']}** · {claim['status'].title()}")
            st.write(claim["message"])


def render_admin():
    st.subheader("Claim review")
    with connect_db() as conn:
        claims = conn.execute(
            """SELECT claims.*, items.title, users.name AS claimant
               FROM claims JOIN items ON items.id = claims.item_id
               JOIN users ON users.id = claims.user_id
               ORDER BY claims.created_at DESC"""
        ).fetchall()
    if not claims:
        st.info("There are no claim requests.")
        return
    for claim in claims:
        with st.container(border=True):
            st.markdown(f"**{claim['title']}** · {claim['status'].title()}")
            st.caption(f"Claimant: {claim['claimant']}")
            st.write(claim["message"])
            if claim["status"] == "pending":
                accept, reject = st.columns(2)
                if accept.button("Approve", key=f"approve_{claim['id']}"):
                    with connect_db() as conn:
                        conn.execute("UPDATE claims SET status = 'approved' WHERE id = ?", (claim["id"],))
                        conn.execute("UPDATE items SET status = 'resolved' WHERE id = ?", (claim["item_id"],))
                    st.rerun()
                if reject.button("Reject", key=f"reject_{claim['id']}"):
                    with connect_db() as conn:
                        conn.execute("UPDATE claims SET status = 'rejected' WHERE id = ?", (claim["id"],))
                    st.rerun()


def main():
    try:
        initialize_db()
    except (OSError, sqlite3.Error, ValueError) as exc:
        st.error(f"Could not initialize CampusFind: {exc}")
        st.stop()

    st.title("⌖ CampusFind")
    st.caption("Lost something? Found something? Bring it back.")
    user = current_user()
    with st.sidebar:
        st.markdown("## CampusFind")
        if user:
            st.write(f"Hi, {user['name'].split()[0]}")
            if st.button("Log out", use_container_width=True):
                st.session_state.pop("user_id", None)
                st.rerun()
            pages = ["Browse items", "Report an item", "My claims"]
            if user["role"] == "admin":
                pages.append("Admin review")
            page = st.radio("Navigate", pages, label_visibility="collapsed")
        else:
            st.write("Good people. Better campus.")
            page = st.radio("Navigate", ["Browse items", "Log in / Sign up"], label_visibility="collapsed")
        st.divider()
        st.caption("Every item has a way home.")

    if page == "Browse items":
        render_browse(user)
    elif page == "Log in / Sign up":
        render_auth()
    elif page == "Report an item":
        render_report(user)
    elif page == "My claims":
        render_my_claims(user)
    elif page == "Admin review":
        render_admin()


if __name__ == "__main__":
    main()
