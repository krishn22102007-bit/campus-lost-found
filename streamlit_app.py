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
ASSET_DIR = BASE_DIR / "assets"
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
CATEGORY_IMAGES = {
    "Electronics": "item_electronics.png",
    "Accessories": "item_accessories.png",
    "Books & notes": "item_books.png",
    "Clothing": "item_clothing.png",
    "Keys & cards": "item_keys.png",
    "Other": "item_other.png",
}

st.set_page_config(page_title="CampusFind | Lost & Found", page_icon="⌖", layout="wide")


def apply_theme():
    st.markdown(
        """
        <style>
        :root { --ink:#1d2b22; --muted:#758278; --green:#245b40; --mint:#e8f1e8; --line:#e6ebe4; --cream:#f7f8f4; }
        [data-testid="stAppViewContainer"] { background:var(--cream); }
        [data-testid="stHeader"] { background:transparent; }
        .stMainBlockContainer { max-width:1280px; padding:1.6rem 2.4rem 4rem; }
        [data-testid="stSidebar"] { background:#17372a; border-right:0; }
        [data-testid="stSidebar"] * { color:#f3f6f1; }
        [data-testid="stSidebar"] [data-testid="stRadio"] label { border-radius:12px; padding:.45rem .6rem; }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background:#ffffff14; }
        [data-testid="stSidebar"] hr { border-color:#ffffff30; }
        h1,h2,h3,h4 { color:var(--ink); font-family:'Manrope','Segoe UI',sans-serif; letter-spacing:-.03em; }
        p, label, input, button, textarea, select { font-family:'DM Sans','Segoe UI',sans-serif; }
        .stMarkdown p { color:#66766b; line-height:1.65; }
        [data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--line)!important; border-radius:18px!important; background:#fff; }
        [data-testid="stImage"] img { border-radius:15px; }
        div[data-testid="stButton"] > button { min-height:2.7rem; border-radius:11px; border:1px solid #dfe7df; font-weight:700; transition:all .18s ease; }
        div[data-testid="stButton"] > button:hover { border-color:#80a88c; color:#245b40; transform:translateY(-1px); }
        div[data-testid="stButton"] > button[kind="primary"] { background:#245b40; color:#fff; border-color:#245b40; }
        div[data-testid="stButton"] > button[kind="primary"]:hover { background:#194a32; color:#fff; }
        [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-testid="stSelectbox"] [role="combobox"] { border-radius:11px; }
        .sidebar-brand { display:flex; align-items:center; gap:11px; margin:.6rem 0 1.4rem; font:800 1.15rem 'Manrope','Segoe UI',sans-serif; }
        .sidebar-mark { width:38px; height:38px; display:grid; place-items:center; border-radius:12px; background:#d8e9d8; color:#245b40!important; font-size:1.45rem; }
        .sidebar-subtitle { color:#bad0bd!important; font-size:.78rem; line-height:1.5; margin-bottom:1.4rem; }
        .hero-copy { padding:.9rem 0 .4rem; }
        .eyebrow { color:#467452; font-size:.72rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase; }
        .hero-title { color:#1e3024; font:800 clamp(2.5rem,5vw,4.35rem)/1.07 'Manrope','Segoe UI',sans-serif; letter-spacing:-.065em; margin:.9rem 0 1rem; }
        .hero-title span { color:#3e7950; }
        .hero-subtitle { color:#6f7f73; font-size:1rem; line-height:1.75; max-width:34rem; }
        .hero-trust { display:flex; align-items:center; gap:.55rem; margin-top:1.15rem; color:#718075; font-size:.8rem; }
        .trust-dot { width:8px; height:8px; border-radius:50%; display:inline-block; background:#79a980; box-shadow:0 0 0 5px #79a98020; }
        .hero-anchor { display:inline-flex; align-items:center; gap:.55rem; margin-top:.4rem; padding:.78rem 1rem; border:1px solid #dfe7df; border-radius:11px; color:#285f41!important; font-size:.83rem; font-weight:700; text-decoration:none!important; background:#fff; }
        .hero-anchor:hover { border-color:#80a88c; background:#f6faf5; }
        .section-kicker { color:#4c7957; font-size:.68rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase; margin-bottom:.35rem; }
        .section-title { color:#203126; font:800 clamp(1.7rem,3vw,2.4rem)/1.15 'Manrope','Segoe UI',sans-serif; letter-spacing:-.05em; margin:.15rem 0 .3rem; }
        .section-copy { color:#78857b; font-size:.9rem; margin:0 0 1rem; }
        .stat-card { min-height:92px; border:1px solid #e6ebe4; border-radius:16px; background:#fff; padding:1rem 1.15rem; }
        .stat-value { display:block; color:#245b40; font:800 1.45rem 'Manrope','Segoe UI',sans-serif; }
        .stat-label { color:#7d8a80; font-size:.75rem; }
        .item-label { display:inline-block; border-radius:999px; padding:.28rem .58rem; background:#edf5ed; color:#376f49; font-size:.65rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
        .item-label.lost { background:#fbefe1; color:#a56332; }
        .empty-title { color:#25362a; font:800 1.3rem 'Manrope','Segoe UI',sans-serif; margin-bottom:.25rem; }
        .stTabs [data-baseweb="tab-list"] { gap:.4rem; }
        .stTabs [data-baseweb="tab"] { border-radius:10px 10px 0 0; }
        @media (max-width:760px) {
            .stMainBlockContainer { padding:1.15rem 1rem 3rem; }
            .hero-title { font-size:2.75rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def count_open_items():
    with connect_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM items WHERE status = 'open'").fetchone()[0]


def image_for_item(item):
    if item["image"]:
        uploaded = UPLOAD_DIR / item["image"]
        if uploaded.is_file():
            return uploaded
    return ASSET_DIR / CATEGORY_IMAGES.get(item["category"], CATEGORY_IMAGES["Other"])


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


def go_to_page(page):
    st.session_state["campusfind_page"] = page
    st.rerun()


def render_hero(user, listing_count):
    copy, artwork = st.columns([1.08, 0.92], gap="large", vertical_alignment="center")
    with copy:
        st.markdown(
            """
            <div class="hero-copy">
              <div class="eyebrow">A kinder campus starts here</div>
              <div class="hero-title">Lost something?<br><span>Found something?</span></div>
              <div class="hero-subtitle">A little campus kindness goes a long way. Find what went missing, return what you discovered, and keep your community moving.</div>
              <div class="hero-trust"><span class="trust-dot"></span> A simple, human way to bring things home</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        actions = st.columns([1, 1.15], gap="small")
        with actions[0]:
            st.markdown(
                '<a class="hero-anchor" href="#community-board">Explore listings <span>↓</span></a>',
                unsafe_allow_html=True,
            )
        with actions[1]:
            target_page = "Report an item" if user else "Log in / Sign up"
            if st.button("＋  Post an item", type="primary", width="stretch", key="hero_post"):
                go_to_page(target_page)
    with artwork:
        st.image(str(ASSET_DIR / "campus_hero.png"), width="stretch")

    metrics = st.columns(3, gap="medium")
    for column, value, label in [
        (metrics[0], str(listing_count), "Open community listings"),
        (metrics[1], "24/7", "Campus access"),
        (metrics[2], "One campus", "A stronger community"),
    ]:
        with column:
            st.markdown(
                f'<div class="stat-card"><span class="stat-value">{value}</span><span class="stat-label">{label}</span></div>',
                unsafe_allow_html=True,
            )
    st.write("")


def render_item_detail(item, user):
    st.markdown('<div class="section-kicker">Listing details</div>', unsafe_allow_html=True)
    top = st.columns([5, 1])
    with top[0]:
        st.markdown(f"## {item['title']}")
    with top[1]:
        if st.button("Close", key="close_item_detail", width="stretch"):
            st.session_state.pop("selected_item_id", None)
            st.rerun()

    image_column, detail_column = st.columns([0.95, 1.25], gap="large")
    with image_column:
        st.image(str(image_for_item(item)), width="stretch")
    with detail_column:
        label = "lost" if item["item_type"] == "lost" else "found"
        st.markdown(
            f'<span class="item-label {label}">{item["item_type"]} item</span>',
            unsafe_allow_html=True,
        )
        st.write("")
        st.write(item["description"])
        st.caption(f"📍 {item['location']}  ·  {item['event_date']}")
        st.caption(f"Reported by {item['reporter']}  ·  {item['category']}")
        if user and user["id"] != item["user_id"]:
            with st.form(f"claim_{item['id']}"):
                message = st.text_area(
                    "Share a detail only the owner would know",
                    placeholder="At least 10 characters of useful identifying detail",
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


def render_browse(user):
    st.markdown(
        """
        <div id="community-board" class="section-kicker">The community board</div>
        <div class="section-title">Find what you're looking for.</div>
        <p class="section-copy">Browse recent reports from around campus.</p>
        """,
        unsafe_allow_html=True,
    )
    filters = st.columns([2.15, 1.2, 1.2], gap="medium")
    search = filters[0].text_input(
        "Search listings",
        placeholder="Search items, places, details...",
        key="campusfind_search",
    )
    kind = filters[1].segmented_control(
        "Report type",
        ["All", "Lost", "Found"],
        default="All",
        label_visibility="collapsed",
        key="campusfind_type_filter",
    )
    category = filters[2].selectbox(
        "Category",
        ["All", *CATEGORIES],
        label_visibility="collapsed",
        key="campusfind_category_filter",
    )
    items = query_items(search.strip(), kind, category)
    count_text = f"{len(items)} open {'listing' if len(items) == 1 else 'listings'}"
    st.caption(count_text)
    if not items:
        empty_image, empty_copy = st.columns([0.8, 1.5], gap="large", vertical_alignment="center")
        with empty_image:
            st.image(str(ASSET_DIR / "item_other.png"), width="stretch")
        with empty_copy:
            st.markdown('<div class="empty-title">No matches just yet</div>', unsafe_allow_html=True)
            st.write("Try a different search, or add a report to help someone in your campus community.")
            if st.button("＋  Add a listing", type="primary", width="stretch", key="empty_add_listing"):
                go_to_page("Report an item" if user else "Log in / Sign up")
        st.session_state.pop("selected_item_id", None)
        return

    selected_id = st.session_state.get("selected_item_id")
    if not any(row["id"] == selected_id for row in items):
        st.session_state.pop("selected_item_id", None)

    for start in range(0, len(items), 3):
        cards = st.columns(3, gap="medium")
        for column, item in zip(cards, items[start : start + 3]):
            with column:
                with st.container(border=True):
                    st.image(str(image_for_item(item)), width="stretch")
                    label = "lost" if item["item_type"] == "lost" else "found"
                    st.markdown(
                        f'<span class="item-label {label}">{item["item_type"]} item</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"### {item['title']}")
                    description = item["description"]
                    st.caption(description if len(description) <= 105 else f"{description[:102].rstrip()}…")
                    st.caption(f"📍 {item['location']}  ·  {item['category']}")
                    if st.button("View details  →", key=f"view_item_{item['id']}", width="stretch"):
                        st.session_state["selected_item_id"] = item["id"]
                        st.rerun()

    selected_id = st.session_state.get("selected_item_id")
    if selected_id is not None:
        selected = next((row for row in items if row["id"] == selected_id), None)
        if selected:
            st.divider()
            with st.container(border=True):
                render_item_detail(selected, user)


def render_report(user):
    intro, image = st.columns([1.35, 0.65], gap="large", vertical_alignment="center")
    with intro:
        st.markdown('<div class="section-kicker">Add to the community board</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Help it find its way home.</div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="section-copy">Share clear details and a photo if you have one. Avoid posting sensitive personal information.</p>',
            unsafe_allow_html=True,
        )
    with image:
        st.image(str(ASSET_DIR / "item_books.png"), width="stretch")

    with st.container(border=True):
        with st.form("listing_form", clear_on_submit=True):
            first, second = st.columns(2)
            kind = first.selectbox("Report type", ["Lost", "Found"])
            category = second.selectbox("Category", CATEGORIES)
            title = st.text_input("Item name", max_chars=100, placeholder="e.g. Blue water bottle")
            description = st.text_area("Description", placeholder="Colour, brand, or identifying details")
            first, second = st.columns(2)
            location = first.text_input("Location", placeholder="Library, Block B...")
            event_date = second.date_input("Date", value=date.today(), max_value=date.today())
            upload = st.file_uploader(
                "Photo (optional, PNG/JPG/WEBP, max 5 MB)",
                type=["png", "jpg", "jpeg", "webp"],
            )
            submitted = st.form_submit_button("Publish report", type="primary", width="stretch")
    if submitted:
        try:
            save_listing(user, kind, category, title, description, location, event_date, upload)
            st.success("Your report is now live.")
        except ValueError as exc:
            st.error(str(exc))


def render_auth():
    intro, image = st.columns([1.3, 0.7], gap="large", vertical_alignment="center")
    with intro:
        st.markdown('<div class="section-kicker">Your campus, connected</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Good things find their way.</div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="section-copy">Sign in to post reports, follow up on claims, and help your campus community.</p>',
            unsafe_allow_html=True,
        )
    with image:
        st.image(str(ASSET_DIR / "item_accessories.png"), width="stretch")
    login_tab, register_tab = st.tabs(["Log in", "Create account"])
    with login_tab:
        with st.form("login_form"):
            email = st.text_input("College email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", type="primary", width="stretch")
        if submitted:
            with connect_db() as conn:
                user = conn.execute(
                    "SELECT id, password FROM users WHERE email = ?",
                    (email.strip().lower(),),
                ).fetchone()
            if user and check_password_hash(user["password"], password):
                st.session_state.user_id = user["id"]
                st.session_state["campusfind_page"] = "Browse items"
                st.rerun()
            st.error("Incorrect email or password.")
    with register_tab:
        with st.form("register_form"):
            name = st.text_input("Full name", max_chars=80)
            email = st.text_input("College email", key="register_email")
            password = st.text_input("Password (at least 8 characters)", type="password", key="register_password")
            submitted = st.form_submit_button("Create account", type="primary", width="stretch")
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
                    st.session_state["campusfind_page"] = "Browse items"
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("An account with that email already exists.")


def render_my_claims(user):
    st.markdown('<div class="section-kicker">Your activity</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">My claim requests</div>', unsafe_allow_html=True)
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
            st.markdown(f"### {claim['title']}")
            st.caption(f"Request status: {claim['status'].title()}")
            st.write(claim["message"])


def render_admin():
    st.markdown('<div class="section-kicker">Community care</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Review claim requests</div>', unsafe_allow_html=True)
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
            st.markdown(f"### {claim['title']}")
            st.caption(f"Claimant: {claim['claimant']}  ·  {claim['status'].title()}")
            st.write(claim["message"])
            if claim["status"] == "pending":
                accept, reject = st.columns(2)
                if accept.button("Approve claim", key=f"approve_{claim['id']}", type="primary"):
                    with connect_db() as conn:
                        conn.execute("UPDATE claims SET status = 'approved' WHERE id = ?", (claim["id"],))
                        conn.execute("UPDATE items SET status = 'resolved' WHERE id = ?", (claim["item_id"],))
                    st.rerun()
                if reject.button("Decline", key=f"reject_{claim['id']}"):
                    with connect_db() as conn:
                        conn.execute("UPDATE claims SET status = 'rejected' WHERE id = ?", (claim["id"],))
                    st.rerun()


def main():
    apply_theme()
    try:
        initialize_db()
    except (OSError, sqlite3.Error, ValueError) as exc:
        st.error(f"Could not initialize CampusFind: {exc}")
        st.stop()

    user = current_user()
    pages = ["Browse items", "Report an item", "My claims"]
    if user and user["role"] == "admin":
        pages.append("Admin review")
    if not user:
        pages = ["Browse items", "Log in / Sign up"]
    if st.session_state.get("campusfind_page") not in pages:
        st.session_state["campusfind_page"] = "Browse items"

    with st.sidebar:
        st.markdown(
            '<div class="sidebar-brand"><span class="sidebar-mark">⌖</span><span>CampusFind</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="sidebar-subtitle">Lost something? Found something?<br>Let’s bring it back.</div>',
            unsafe_allow_html=True,
        )
        page = st.radio(
            "Navigate",
            pages,
            index=pages.index(st.session_state["campusfind_page"]),
            label_visibility="collapsed",
        )
        st.session_state["campusfind_page"] = page
        st.divider()
        if user:
            st.caption(f"Signed in as {user['name'].split()[0]}")
            if st.button("Log out", width="stretch"):
                st.session_state.pop("user_id", None)
                st.session_state["campusfind_page"] = "Browse items"
                st.rerun()
        else:
            st.caption("Good people. Better campus.")
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("Every item has a way home.")

    if page == "Browse items":
        render_hero(user, count_open_items())
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
