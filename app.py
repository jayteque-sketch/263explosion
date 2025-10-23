from flask import Flask, render_template, render_template_string, request, url_for, session, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import time
import requests

# Initialize Flask app
app = Flask(__name__)

# ---------------------- Secret Key (for sessions) ----------------------
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-dev-key')

# ---------------------- Database Configuration ----------------------
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------------- Email Configuration ----------------------
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

mail = Mail(app)

from flask_mail import Mail
mail = Mail(app)


# Create directories
os.makedirs('static/uploads', exist_ok=True)
os.makedirs('static/img/sponsors', exist_ok=True)

ALLOWED_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}

PROVINCES = [
    "Bulawayo", "Harare", "Manicaland", "Mashonaland Central",
    "Mashonaland East", "Mashonaland West", "Masvingo",
    "Matabeleland North", "Matabeleland South", "Midlands",
    "Mbare", "Diaspora"
]

CATEGORIES = [
    "Vehicles", "Property", "Jobs", "Services", "Electronics",
    "Fashion", "Home & Garden", "Education", "Farming", "Community"
]

SECTORS = [
    "Agriculture", "Mining", "Energy", "Tourism", "Manufacturing",
    "ICT", "Healthcare", "Education", "Transport & Logistics", "Financial Services",
    "Real Estate", "Renewables"
]

# Country codes for phone numbers
COUNTRY_CODES = [
    {"code": "+263", "country": "Zimbabwe"},
    {"code": "+260", "country": "Zambia"},
    {"code": "+971", "country": "UAE"},
    {"code": "+27", "country": "South Africa"},
    {"code": "+1", "country": "USA/Canada"},
    {"code": "+44", "country": "UK"},
    {"code": "+61", "country": "Australia"},
    {"code": "+91", "country": "India"},
    {"code": "+86", "country": "China"},
    {"code": "+254", "country": "Kenya"},
    {"code": "+234", "country": "Nigeria"},
    {"code": "+255", "country": "Tanzania"}
]

MARKET_CURRENCIES = [
    {"pair": "USD/ZWL", "rate": "-"},
    {"pair": "ZAR/USD", "rate": "-"},
    {"pair": "GBP/USD", "rate": "-"},
    {"pair": "EUR/USD", "rate": "-"},
    {"pair": "BWP/USD", "rate": "-"},
    {"pair": "CNY/USD", "rate": "-"}
]

MARKET_METALS = [
    {"metal": "Gold (oz)", "price": "-"},
    {"metal": "Platinum (oz)", "price": "-"},
    {"metal": "Palladium (oz)", "price": "-"},
    {"metal": "Silver (oz)", "price": "-"},
    {"metal": "Copper (lb)", "price": "-"},
    {"metal": "Chrome (t)", "price": "-"},
    {"metal": "Iron Ore (t)", "price": "-"},
    {"metal": "Lithium (t)", "price": "-"},
    {"metal": "Graphite (t)", "price": "-"},
    {"metal": "Nickel (t)", "price": "-"}
]

CACHE = {"currencies": {"ts": 0, "data": MARKET_CURRENCIES}, "metals": {"ts": 0, "data": MARKET_METALS}}


# Database Models - UPDATED for multiple photos and view_count
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    listings = db.relationship('Listing', backref='seller_user', lazy=True)


class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    province = db.Column(db.String(100), nullable=False)
    price = db.Column(db.String(50))
    description = db.Column(db.Text)
    phone = db.Column(db.String(20))
    whatsapp = db.Column(db.String(20))
    email = db.Column(db.String(120))
    # Changed from single photo to multiple photos (comma-separated filenames)
    photos = db.Column(db.String(1000))  # Store comma-separated filenames
    country_code_phone = db.Column(db.String(5), default='+263')
    country_code_whatsapp = db.Column(db.String(5), default='+263')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Add view_count for popularity tracking
    view_count = db.Column(db.Integer, default=0)


class Sponsor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    image = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)


# Database Migration Function
def migrate_database():
    """Migrate database schema without losing data"""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns('listing')]

    migrations_applied = []

    # Migration 1: Add photos column if it doesn't exist
    if 'photos' not in columns:
        try:
            # Check if old photo column exists
            if 'photo' in columns:
                # Add new photos column and migrate data
                db.session.execute(text('ALTER TABLE listing ADD COLUMN photos VARCHAR(1000)'))
                db.session.execute(text('UPDATE listing SET photos = photo WHERE photo IS NOT NULL'))
                migrations_applied.append("Added photos column and migrated data from photo")
            else:
                # Just add the new column
                db.session.execute(text('ALTER TABLE listing ADD COLUMN photos VARCHAR(1000)'))
                migrations_applied.append("Added photos column")
        except Exception as e:
            print(f"Migration error (photos): {e}")
            db.session.rollback()

    # Migration 2: Add country code columns
    if 'country_code_phone' not in columns:
        try:
            db.session.execute(text('ALTER TABLE listing ADD COLUMN country_code_phone VARCHAR(5) DEFAULT "+263"'))
            migrations_applied.append("Added country_code_phone column")
        except Exception as e:
            print(f"Migration error (country_code_phone): {e}")
            db.session.rollback()

    if 'country_code_whatsapp' not in columns:
        try:
            db.session.execute(text('ALTER TABLE listing ADD COLUMN country_code_whatsapp VARCHAR(5) DEFAULT "+263"'))
            migrations_applied.append("Added country_code_whatsapp column")
        except Exception as e:
            print(f"Migration error (country_code_whatsapp): {e}")
            db.session.rollback()

    # Migration 3: Add view_count column
    if 'view_count' not in columns:
        try:
            db.session.execute(text('ALTER TABLE listing ADD COLUMN view_count INTEGER DEFAULT 0'))
            migrations_applied.append("Added view_count column")
        except Exception as e:
            print(f"Migration error (view_count): {e}")
            db.session.rollback()

    if migrations_applied:
        db.session.commit()
        print(f"Database migrations applied: {', '.join(migrations_applied)}")
    else:
        print("No database migrations needed")


# Create tables and migrate
with app.app_context():
    db.create_all()
    migrate_database()
    # Initialize default data only if no users exist
    if User.query.count() == 0:
        # Default sponsors - ONLY Hitbay Sanitation
        if Sponsor.query.count() == 0:
            default_sponsors = [
                {"name": "Hitbay Sanitation", "image": "hitbay.jpg", "url": "https://www.hitbaysanitation.co.zw"},
                {"name": "Horizon Vehicles", "image": "horizonvehicles.jpeg", "url": "https://horizonvehicles.com/country/zimbabwe"}             ]
            for sponsor_data in default_sponsors:
                sponsor = Sponsor(**sponsor_data)
                db.session.add(sponsor)

        # Default admin user
        if User.query.filter_by(email="admin@263explosion.com").first() is None:
            admin_user = User(
                email="admin@263explosion.com",
                name="Admin",
                password_hash=generate_password_hash("test123")
            )
            db.session.add(admin_user)

        # Default regular user
        if User.query.filter_by(email="user@263explosion.com").first() is None:
            regular_user = User(
                email="user@263explosion.com",
                name="Zimbo User",
                password_hash=generate_password_hash("263explosion")
            )
            db.session.add(regular_user)

        db.session.commit()
        print("Default data initialized")


# Helper functions
def current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


def login_required(view_func):
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please login to continue.", "warning")
            return redirect(url_for('login', next=request.path))
        return view_func(*args, **kwargs)

    wrapper.__name__ = view_func.__name__
    return wrapper


def get_sponsors_from_db():
    return Sponsor.query.filter_by(is_active=True).all()


def default_nav(user):
    # Create the navigation HTML without using template variables
    sectors_html = ''.join(
        [f'<li><a class="dropdown-item" href="{url_for("invest_sector", sector=s)}">{s}</a></li>' for s in SECTORS])

    return f'''
      <li class="nav-item dropdown">
        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">How to Invest in Zimbabwe</a>
        <ul class="dropdown-menu dropdown-menu-end">
          {sectors_html}
          <li><hr class="dropdown-divider"></li>
          <li><a class="dropdown-item" href="{url_for('invest')}">Overview</a></li>
        </ul>
      </li>
      <li class="nav-item dropdown">
        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Markets</a>
        <ul class="dropdown-menu dropdown-menu-end">
          <li><a class="dropdown-item" href="{url_for('markets_currencies')}">Exchange Rates</a></li>
          <li><a class="dropdown-item" href="{url_for('markets_metals')}">Metals Prices</a></li>
          <li><hr class="dropdown-divider"></li>
          <li><a class="dropdown-item" href="{url_for('markets')}">Overview</a></li>
        </ul>
      </li>
      {f'<li class="nav-item me-2"><a href="{url_for("post_listing")}" class="btn btn-outline-warning btn-sm">Post</a></li><li class="nav-item"><span class="text-white-50 small me-2">Welcome, {user.name}</span></li><li class="nav-item"><a href="{url_for("logout")}" class="btn btn-outline-light btn-sm">Logout</a></li>' if user else f'<li class="nav-item"><a href="{url_for("login")}" class="btn btn-danger btn-sm">Login</a></li>'}
    '''


# Market data functions
def get_live_currencies(ttl=600):
    now = time.time()
    if now - CACHE["currencies"]["ts"] < ttl and CACHE["currencies"]["data"][0]["rate"] != "-":
        return CACHE["currencies"]["data"]

    try:
        apis_to_try = [
            "https://api.exchangerate.host/latest?base=USD",
            "https://api.frankfurter.app/latest?from=USD",
            "https://open.er-api.com/v6/latest/USD"
        ]

        rates = {}
        for api_url in apis_to_try:
            try:
                resp = requests.get(api_url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('rates'):
                        rates = data['rates']
                        break
            except:
                continue

        if not rates:
            print("All currency APIs failed, using cached data")
            return CACHE["currencies"]["data"]

        zwl_rate = rates.get('ZWL') or 322.0

        out = [
            {"pair": "USD/ZWL", "rate": f"{zwl_rate:,.2f}"},
            {"pair": "ZAR/USD", "rate": f"{1 / rates.get('ZAR', 18.5):,.4f}" if rates.get('ZAR') else "N/A"},
            {"pair": "GBP/USD", "rate": f"{1 / rates.get('GBP', 0.79):,.4f}" if rates.get('GBP') else "N/A"},
            {"pair": "EUR/USD", "rate": f"{1 / rates.get('EUR', 0.93):,.4f}" if rates.get('EUR') else "N/A"},
            {"pair": "BWP/USD", "rate": f"{1 / rates.get('BWP', 13.5):,.4f}" if rates.get('BWP') else "N/A"},
            {"pair": "CNY/USD", "rate": f"{1 / rates.get('CNY', 7.25):,.4f}" if rates.get('CNY') else "N/A"},
        ]

        CACHE["currencies"] = {"ts": now, "data": out}
        return out

    except Exception as e:
        print(f"Error fetching currencies: {e}")
        return CACHE["currencies"]["data"]


def get_live_metals(ttl=600):
    now = time.time()
    if now - CACHE["metals"]["ts"] < ttl and CACHE["metals"]["data"][0]["price"] != "-":
        return CACHE["metals"]["data"]

    try:
        metals_data = []

        try:
            resp = requests.get(
                "https://api.metalpriceapi.com/v1/latest",
                params={"api_key": "demo", "base": "USD", "currencies": "XAU,XAG,XPT,XPD"},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                rates = data.get('rates', {})

                gold_price = rates.get('XAU')
                silver_price = rates.get('XAG')
                platinum_price = rates.get('XPT')
                palladium_price = rates.get('XPD')

                if gold_price:
                    metals_data.append({"metal": "Gold (oz)", "price": f"${1 / gold_price * 31.1035:,.2f}"})
                else:
                    metals_data.append({"metal": "Gold (oz)", "price": "$1,950.00"})

                if silver_price:
                    metals_data.append({"metal": "Silver (oz)", "price": f"${1 / silver_price * 31.1035:,.2f}"})
                else:
                    metals_data.append({"metal": "Silver (oz)", "price": "$23.50"})

                if platinum_price:
                    metals_data.append({"metal": "Platinum (oz)", "price": f"${1 / platinum_price * 31.1035:,.2f}"})
                else:
                    metals_data.append({"metal": "Platinum (oz)", "price": "$950.00"})

                if palladium_price:
                    metals_data.append({"metal": "Palladium (oz)", "price": f"${1 / palladium_price * 31.1035:,.2f}"})
                else:
                    metals_data.append({"metal": "Palladium (oz)", "price": "$1,200.00"})

        except:
            metals_data = [
                {"metal": "Gold (oz)", "price": "$1,950.00"},
                {"metal": "Silver (oz)", "price": "$23.50"},
                {"metal": "Platinum (oz)", "price": "$950.00"},
                {"metal": "Palladium (oz)", "price": "$1,200.00"}
            ]

        metals_data.extend([
            {"metal": "Copper (lb)", "price": "$3.85"},
            {"metal": "Chrome (t)", "price": "$280.00"},
            {"metal": "Iron Ore (t)", "price": "$120.00"},
            {"metal": "Lithium (t)", "price": "$15,400.00"},
            {"metal": "Graphite (t)", "price": "$850.00"},
            {"metal": "Nickel (t)", "price": "$18,500.00"}
        ])

        CACHE["metals"] = {"ts": now, "data": metals_data}
        return metals_data

    except Exception as e:
        print(f"Error fetching metals: {e}")
        return [
            {"metal": "Gold (oz)", "price": "$1,950.00"},
            {"metal": "Platinum (oz)", "price": "$950.00"},
            {"metal": "Palladium (oz)", "price": "$1,200.00"},
            {"metal": "Silver (oz)", "price": "$23.50"},
            {"metal": "Copper (lb)", "price": "$3.85"},
            {"metal": "Chrome (t)", "price": "$280.00"},
            {"metal": "Iron Ore (t)", "price": "$120.00"},
            {"metal": "Lithium (t)", "price": "$15,400.00"},
            {"metal": "Graphite (t)", "price": "$850.00"},
            {"metal": "Nickel (t)", "price": "$18,500.00"}
        ]


# Routes
@app.route('/')
def home():
    q = request.args.get('q', '').strip().lower()
    province_filter = request.args.get('province', '')
    sort_by = request.args.get('sort', 'newest')  # Default to newest

    results = []

    if q:
        results = Listing.query.filter(
            db.or_(
                Listing.title.ilike(f'%{q}%'),
                Listing.category.ilike(f'%{q}%'),
                Listing.description.ilike(f'%{q}%')
            )
        )
        if province_filter:
            results = results.filter(Listing.province == province_filter)

        # Apply sorting for search results
        if sort_by == 'popular':
            results = results.order_by(Listing.view_count.desc())
        else:  # newest
            results = results.order_by(Listing.created_at.desc())

        results = results.all()
    else:
        # Show only 6 recent/popular listings when no search
        if sort_by == 'popular':
            results = Listing.query.order_by(Listing.view_count.desc()).limit(6).all()
        else:  # newest
            results = Listing.query.order_by(Listing.created_at.desc()).limit(6).all()

    user = current_user()
    bg_url = url_for('static', filename='img/site-bg.jpg')
    sponsors = get_sponsors_from_db()

    # Updated home template with sorting options
    home_template = '''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body { background-image: url("{{ bg_url }}"); background-repeat: no-repeat; background-position: center center; background-attachment: fixed; background-size: cover; color: white; }
        .overlay { background:rgba(0,0,0,.6); min-height:100vh; padding-top:70px; }
        .province-card { 
            background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%); /* Golden yellow gradient */
            color: #000;
            border-radius:12px;
            padding:1rem;
            font-weight:700;
            text-transform:uppercase;
            text-decoration:none;
            display:block;
            transition:.25s;
            border: 2px solid #FFD700;
            box-shadow: 0 4px 8px rgba(255, 215, 0, 0.3);
        }
        .province-card:hover { 
            background: linear-gradient(135deg, #FFA500 0%, #FF8C00 100%); /* Darker gold on hover */
            color: #000;
            transform:scale(1.05);
            box-shadow: 0 6px 12px rgba(255, 215, 0, 0.5);
            border: 2px solid #FFA500;
        }
        .search-bar { background:#fff; border-radius:12px; padding:10px; max-width:900px; margin:20px auto; }
        .sponsors-section { background: rgba(255,255,255,0.95); border-radius: 15px; padding: 2rem; margin: 2rem auto; max-width: 1200px; }
        .sponsor-img { max-height: 120px; object-fit: contain; padding: 10px; }
        .carousel-control-prev, .carousel-control-next { width: 5%; }
        .carousel-indicators button { background-color: #dc3545; }
        .listing-price { color: #dc3545; font-weight: bold; }
        .listing-card { cursor: pointer; transition: transform 0.2s; }
        .listing-card:hover { transform: translateY(-5px); }
        .sort-options { max-width: 200px; }
        .view-count { font-size: 0.8rem; color: #6c757d; }
        .single-sponsor { display: flex; justify-content: center; align-items: center; }
      </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark fixed-top">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#topnav">
            <span class="navbar-toggler-icon"></span>
          </button>
          <div class="collapse navbar-collapse" id="topnav">
            <ul class="navbar-nav ms-auto align-items-center">
              {{ nav_html|safe }}
            </ul>
          </div>
        </div>
      </nav>
      <div class="overlay text-center">
        <h1 class="fw-bold text-danger mb-1">263 Explosion</h1>
        <p class="lead">Zimbabwe\'s #1 Online Classifieds Platform</p>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% for cat, msg in messages %}
            <div class="alert alert-{{ cat }} w-75 mx-auto">{{ msg }}</div>
          {% endfor %}
        {% endwith %}
        <form method="get" class="search-bar d-flex flex-wrap shadow-sm" enctype="multipart/form-data">
          <input class="form-control me-2 mb-2" name="q" placeholder="Search cars, houses, jobs…" value="{{ request.args.get('q','') }}">
          <select name="province" class="form-select me-2 mb-2" style="max-width:220px;">
            <option value="">All Provinces</option>
            {% for p in provinces %}
              <option value="{{ p }}" {% if p==request.args.get('province') %}selected{% endif %}>{{ p }}</option>
            {% endfor %}
          </select>
          <select name="sort" class="form-select me-2 mb-2 sort-options">
            <option value="newest" {% if request.args.get('sort','newest')=='newest' %}selected{% endif %}>Newest First</option>
            <option value="popular" {% if request.args.get('sort','newest')=='popular' %}selected{% endif %}>Most Popular</option>
          </select>
          <button class="btn btn-danger mb-2">Search</button>
        </form>
        {% if request.args.get('q') or not request.args.get('q') %}
          <div class="container bg-white text-dark rounded py-3 mt-3" style="max-width:1200px;">
            <div class="d-flex justify-content-between align-items-center mb-3">
              <h5 class="mb-0">
                {% if request.args.get('q') %}
                  Search results for "{{ request.args.get('q') }}"
                {% else %}
                  Featured Listings
                  {% if not request.args.get('q') %}
                    <small class="text-muted d-block mt-1">Showing recent 6 listings • <a href="{{ url_for('home') }}?sort={% if sort_by == 'newest' %}popular{% else %}newest{% endif %}" class="text-decoration-none">Show {% if sort_by == 'newest' %}Popular{% else %}Newest{% endif %}</a></small>
                  {% endif %}
                {% endif %}
              </h5>
              {% if not request.args.get('q') and results|length == 6 %}
                <a href="{{ url_for('all_listings') }}?sort={{ sort_by }}" class="btn btn-outline-primary btn-sm">View All Listings</a>
              {% endif %}
            </div>
            {% if results %}
              <div class="row g-3">
              {% for r in results %}
                <div class="col-12 col-md-6 col-lg-4">
                  <div class="card shadow-sm h-100 listing-card" onclick="window.location=\'{{ url_for("listing_detail", listing_id=r.id) }}\'">
                    {% if r.photos %}
                      {% set photo_list = r.photos.split(',') %}
                      {% set first_photo = photo_list[0] %}
                      <img src="{{ url_for('static', filename='uploads/' + first_photo) }}" class="card-img-top" alt="photo" style="height: 200px; object-fit: cover;">
                    {% elif r.photo %}
                      <img src="{{ url_for('static', filename='uploads/' + r.photo) }}" class="card-img-top" alt="photo" style="height: 200px; object-fit: cover;">
                    {% endif %}
                    <div class="card-body">
                      <h5 class="mb-1">{{ r.title }}</h5>
                      {% if r.price %}<div class="listing-price mb-1">${{ r.price }}</div>{% endif %}
                      <small class="text-muted">{{ r.category }} — {{ r.province }}</small>
                      <div class="view-count">
                        <i class="fas fa-eye"></i> {{ r.view_count }} views
                        {% if sort_by == 'newest' %}
                          • {{ r.created_at.strftime('%b %d') }}
                        {% endif %}
                      </div>
                      {% if r.description %}<p class="small mt-2">{{ r.description[:100] }}{{ '...' if r.description|length > 100 else '' }}</p>{% endif %}
                      <div class="d-flex flex-wrap gap-2 mt-2">
                        <a class="btn btn-sm btn-success" target="_blank" href="https://wa.me/{{ r.country_code_whatsapp or '+263' }}{{ r.whatsapp|replace('+','')|replace(' ','') }}">WhatsApp</a>
                        <a class="btn btn-sm btn-outline-primary" href="tel:{{ r.country_code_phone or '+263' }}{{ r.phone }}">Call</a>
                        <a class="btn btn-sm btn-outline-secondary" href="mailto:{{ r.email }}">Email</a>
                      </div>
                      {% if user and user.id == r.user_id %}
                      <form method="post" action="{{ url_for('delete_listing', listing_id=r.id) }}" onsubmit="return confirm('Are you sure you want to delete this listing?');" class="mt-2">
                        <button type="submit" class="btn btn-danger btn-sm w-100">Delete</button>
                      </form>
                      {% endif %}
                    </div>
                  </div>
                </div>
              {% endfor %}
              </div>
            {% else %}
              <div class="text-muted">No results found.</div>
            {% endif %}
          </div>
        {% endif %}
        <hr class="w-75 my-4">
        <p class="h5">Choose a province or district</p>
        <div class="container mt-3">
          <div class="row justify-content-center g-3">
            {% for p in provinces %}
              <div class="col-6 col-md-3"><a class="province-card shadow-sm" href="{{ url_for('province_page', province=p) }}">{{ p }}</a></div>
            {% endfor %}
          </div>
        </div>

        <!-- Sponsors Section -->
        {% if sponsors %}
        <div class="sponsors-section">
          <h3 class="text-danger mb-4">Our Valued Partners & Sponsors</h3>
          {% if sponsors|length == 1 %}
            <!-- Single sponsor display -->
            <div class="single-sponsor">
              {% for sponsor in sponsors %}
                <div class="text-center">
                  <a href="{{ sponsor.url }}" target="_blank">
                    <img src="{{ url_for('static', filename='img/sponsors/' + sponsor.image) }}" 
                         class="sponsor-img img-fluid" 
                         alt="{{ sponsor.name }}"
                         title="{{ sponsor.name }}"
                         style="max-height: 150px;">
                  </a>
                  <h5 class="mt-3">{{ sponsor.name }}</h5>
                </div>
              {% endfor %}
            </div>
          {% else %}
            <!-- Multiple sponsors carousel -->
            <div id="sponsorsCarousel" class="carousel slide" data-bs-ride="carousel">
              <div class="carousel-indicators">
                {% for i in range((sponsors|length + 2) // 3) %}
                  <button type="button" data-bs-target="#sponsorsCarousel" data-bs-slide-to="{{ i }}" class="{% if i==0 %}active{% endif %}"></button>
                {% endfor %}
              </div>
              <div class="carousel-inner">
                {% for i in range(0, sponsors|length, 3) %}
                  <div class="carousel-item {% if i==0 %}active{% endif %}">
                    <div class="row justify-content-center">
                      {% for sponsor in sponsors[i:i+3] %}
                        <div class="col-md-4 text-center">
                          <a href="{{ sponsor.url }}" target="_blank">
                            <img src="{{ url_for('static', filename='img/sponsors/' + sponsor.image) }}" 
                                 class="sponsor-img img-fluid" 
                                 alt="{{ sponsor.name }}"
                                 title="{{ sponsor.name }}">
                          </a>
                        </div>
                      {% endfor %}
                    </div>
                  </div>
                {% endfor %}
              </div>
              <button class="carousel-control-prev" type="button" data-bs-target="#sponsorsCarousel" data-bs-slide="prev">
                <span class="carousel-control-prev-icon" aria-hidden="true"></span>
                <span class="visually-hidden">Previous</span>
              </button>
              <button class="carousel-control-next" type="button" data-bs-target="#sponsorsCarousel" data-bs-slide="next">
                <span class="carousel-control-next-icon" aria-hidden="true"></span>
                <span class="visually-hidden">Next</span>
              </button>
            </div>
          {% endif %}
          <div class="text-center mt-4">
            <p class="text-muted">Interested in becoming a sponsor? <a href="mailto:sponsors@263explosion.com" class="text-danger">Contact us</a></p>
          </div>
        </div>
        {% endif %}
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
      <script src="https://kit.fontawesome.com/your-fontawesome-kit.js"></script>
    </body>
    </html>
    '''

    return render_template_string(
        home_template,
        provinces=PROVINCES,
        results=results,
        user=user,
        bg_url=bg_url,
        sponsors=sponsors,
        nav_html=default_nav(user),
        sort_by=sort_by
    )


# Individual listing page with view counting
@app.route('/listing/<int:listing_id>')
def listing_detail(listing_id):
    listing = Listing.query.get_or_404(listing_id)

    # Increment view count
    listing.view_count = Listing.view_count + 1
    db.session.commit()

    user = current_user()
    bg_url = url_for('static', filename='img/site-bg.jpg')

    # Handle both old single photo and new multiple photos
    photos = []
    if listing.photos:
        photos = listing.photos.split(',')
    # Fallback for old listings that might still use the single photo field
    elif hasattr(listing, 'photo') and listing.photo:
        photos = [listing.photo]

    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>{{ listing.title }} - 263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body { background-image: url("{{ bg_url }}"); background-repeat: no-repeat; background-position: center center; background-attachment: fixed; background-size: cover; }
        .carousel-image { height: 400px; object-fit: cover; }
        .listing-card { max-width: 800px; margin: 0 auto; }
        .view-count { color: #6c757d; font-size: 0.9rem; }
      </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#topnav">
            <span class="navbar-toggler-icon"></span>
          </button>
          <div class="collapse navbar-collapse" id="topnav">
            <ul class="navbar-nav ms-auto align-items-center">
              {{ nav_html|safe }}
            </ul>
          </div>
        </div>
      </nav>
      <div class="container py-4">
        <div class="card shadow-sm listing-card">
          {% if photos %}
          <div id="listingCarousel" class="carousel slide" data-bs-ride="carousel">
            <div class="carousel-indicators">
              {% for i in range(photos|length) %}
              <button type="button" data-bs-target="#listingCarousel" data-bs-slide-to="{{ i }}" class="{% if i == 0 %}active{% endif %}"></button>
              {% endfor %}
            </div>
            <div class="carousel-inner">
              {% for photo in photos %}
              <div class="carousel-item {% if loop.first %}active{% endif %}">
                <img src="{{ url_for('static', filename='uploads/' + photo) }}" class="d-block w-100 carousel-image" alt="Listing photo {{ loop.index }}">
              </div>
              {% endfor %}
            </div>
            <button class="carousel-control-prev" type="button" data-bs-target="#listingCarousel" data-bs-slide="prev">
              <span class="carousel-control-prev-icon" aria-hidden="true"></span>
              <span class="visually-hidden">Previous</span>
            </button>
            <button class="carousel-control-next" type="button" data-bs-target="#listingCarousel" data-bs-slide="next">
              <span class="carousel-control-next-icon" aria-hidden="true"></span>
              <span class="visually-hidden">Next</span>
            </button>
          </div>
          {% endif %}
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start">
              <div>
                <h2 class="card-title">{{ listing.title }}</h2>
                <div class="view-count">
                  <i class="fas fa-eye"></i> {{ listing.view_count }} views • Posted {{ listing.created_at.strftime('%B %d, %Y') }}
                </div>
              </div>
              {% if user and user.id == listing.user_id %}
              <form method="post" action="{{ url_for('delete_listing', listing_id=listing.id) }}" onsubmit="return confirm('Are you sure you want to delete this listing?');">
                <button type="submit" class="btn btn-danger btn-sm">Delete</button>
              </form>
              {% endif %}
            </div>
            {% if listing.price %}<h4 class="text-danger mb-3">${{ listing.price }}</h4>{% endif %}
            <p class="text-muted">{{ listing.category }} • {{ listing.province }} • Seller: {{ listing.seller_user.name }}</p>
            <p class="card-text">{{ listing.description }}</p>
            <div class="mt-4">
              <h5>Contact Seller</h5>
              <div class="d-flex flex-wrap gap-2">
                <a class="btn btn-success" target="_blank" href="https://wa.me/{{ listing.country_code_whatsapp }}{{ listing.whatsapp|replace('+','')|replace(' ','') }}">WhatsApp</a>
                <a class="btn btn-outline-primary" href="tel:{{ listing.country_code_phone }}{{ listing.phone }}">Call</a>
                <a class="btn btn-outline-secondary" href="mailto:{{ listing.email }}">Email</a>
              </div>
              <p class="small text-muted mt-2">
                Phone: {{ listing.country_code_phone }} {{ listing.phone }}<br>
                WhatsApp: {{ listing.country_code_whatsapp }} {{ listing.whatsapp }}<br>
                Email: {{ listing.email }}
              </p>
            </div>
            <div class="mt-3">
              <a href="{{ url_for('category_page', province=listing.province, category=listing.category) }}" class="btn btn-secondary">View More in {{ listing.category }}</a>
              <a href="/" class="btn btn-outline-secondary">Back to Home</a>
            </div>
          </div>
        </div>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
      <script src="https://kit.fontawesome.com/your-fontawesome-kit.js"></script>
    </body>
    </html>
    ''', listing=listing, user=user, bg_url=bg_url, photos=photos, nav_html=default_nav(user))


# Delete listing
@app.route('/listing/<int:listing_id>/delete', methods=['POST'])
@login_required
def delete_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    user = current_user()

    # Check if user owns the listing or is admin
    if listing.user_id != user.id and user.email != "admin@263explosion.com":
        flash("You don't have permission to delete this listing.", "danger")
        return redirect(url_for('listing_detail', listing_id=listing_id))

    # Delete associated photos from filesystem
    if listing.photos:
        for photo in listing.photos.split(','):
            photo_path = os.path.join('static/uploads', photo)
            if os.path.exists(photo_path):
                os.remove(photo_path)

    db.session.delete(listing)
    db.session.commit()

    flash('Listing deleted successfully.', 'success')
    return redirect(url_for('home'))


# All listings page (not limited to 6)
@app.route('/all-listings')
def all_listings():
    q = request.args.get('q', '').strip().lower()
    province_filter = request.args.get('province', '')
    sort_by = request.args.get('sort', 'newest')

    if q:
        results = Listing.query.filter(
            db.or_(
                Listing.title.ilike(f'%{q}%'),
                Listing.category.ilike(f'%{q}%'),
                Listing.description.ilike(f'%{q}%')
            )
        )
        if province_filter:
            results = results.filter(Listing.province == province_filter)
    else:
        results = Listing.query

    # Apply sorting
    if sort_by == 'popular':
        results = results.order_by(Listing.view_count.desc())
    else:  # newest
        results = results.order_by(Listing.created_at.desc())

    results = results.all()

    user = current_user()
    bg_url = url_for('static', filename='img/site-bg.jpg')

    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>All Listings - 263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body { background-image: url("{{ bg_url }}"); background-repeat: no-repeat; background-position: center center; background-attachment: fixed; background-size: cover; color: white; }
        .listing-price { color: #dc3545; font-weight: bold; }
        .listing-card { cursor: pointer; transition: transform 0.2s; }
        .listing-card:hover { transform: translateY(-5px); }
        .view-count { font-size: 0.8rem; color: #6c757d; }
      </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark fixed-top">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#topnav">
            <span class="navbar-toggler-icon"></span>
          </button>
          <div class="collapse navbar-collapse" id="topnav">
            <ul class="navbar-nav ms-auto align-items-center">
              {{ nav_html|safe }}
            </ul>
          </div>
        </div>
      </nav>
      <div class="container py-5 mt-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
          <h2 class="text-danger">All Listings</h2>
          <a href="/" class="btn btn-outline-light">← Back to Home</a>
        </div>

        <!-- Search and Sort Form -->
        <form method="get" class="row g-3 mb-4 p-3 bg-dark rounded">
          <div class="col-md-4">
            <input class="form-control" name="q" placeholder="Search listings..." value="{{ request.args.get('q','') }}">
          </div>
          <div class="col-md-3">
            <select name="province" class="form-select">
              <option value="">All Provinces</option>
              {% for p in provinces %}
                <option value="{{ p }}" {% if p==request.args.get('province') %}selected{% endif %}>{{ p }}</option>
              {% endfor %}
            </select>
          </div>
          <div class="col-md-3">
            <select name="sort" class="form-select">
              <option value="newest" {% if request.args.get('sort','newest')=='newest' %}selected{% endif %}>Newest First</option>
              <option value="popular" {% if request.args.get('sort','newest')=='popular' %}selected{% endif %}>Most Popular</option>
            </select>
          </div>
          <div class="col-md-2">
            <button class="btn btn-danger w-100">Filter</button>
          </div>
        </form>

        <div class="d-flex justify-content-between align-items-center mb-3">
          <h5 class="text-light">
            {% if q %}
              Search results for "{{ q }}" ({{ results|length }} listings)
            {% else %}
              All Listings ({{ results|length }} total)
            {% endif %}
          </h5>
          <div class="text-light">
            Sorted by: <strong>{% if sort_by == 'newest' %}Newest{% else %}Most Popular{% endif %}</strong>
          </div>
        </div>

        {% if results %}
          <div class="row g-3">
          {% for r in results %}
            <div class="col-12 col-md-6 col-lg-4">
              <div class="card shadow-sm h-100 listing-card" onclick="window.location=\'{{ url_for("listing_detail", listing_id=r.id) }}\'">
                {% if r.photos %}
                  {% set photo_list = r.photos.split(',') %}
                  {% set first_photo = photo_list[0] %}
                  <img src="{{ url_for('static', filename='uploads/' + first_photo) }}" class="card-img-top" alt="photo" style="height: 200px; object-fit: cover;">
                {% elif r.photo %}
                  <img src="{{ url_for('static', filename='uploads/' + r.photo) }}" class="card-img-top" alt="photo" style="height: 200px; object-fit: cover;">
                {% endif %}
                <div class="card-body">
                  <h5 class="mb-1">{{ r.title }}</h5>
                  {% if r.price %}<div class="listing-price mb-1">${{ r.price }}</div>{% endif %}
                  <small class="text-muted">{{ r.category }} — {{ r.province }}</small>
                  <div class="view-count">
                    <i class="fas fa-eye"></i> {{ r.view_count }} views
                    {% if sort_by == 'newest' %}
                      • {{ r.created_at.strftime('%b %d') }}
                    {% endif %}
                  </div>
                  {% if r.description %}<p class="small mt-2">{{ r.description[:100] }}{{ '...' if r.description|length > 100 else '' }}</p>{% endif %}
                  <div class="d-flex flex-wrap gap-2 mt-2">
                    <a class="btn btn-sm btn-success" target="_blank" href="https://wa.me/{{ r.country_code_whatsapp or '+263' }}{{ r.whatsapp|replace('+','')|replace(' ','') }}">WhatsApp</a>
                    <a class="btn btn-sm btn-outline-primary" href="tel:{{ r.country_code_phone or '+263' }}{{ r.phone }}">Call</a>
                    <a class="btn btn-sm btn-outline-secondary" href="mailto:{{ r.email }}">Email</a>
                  </div>
                  {% if user and user.id == r.user_id %}
                  <form method="post" action="{{ url_for('delete_listing', listing_id=r.id) }}" onsubmit="return confirm('Are you sure you want to delete this listing?');" class="mt-2">
                    <button type="submit" class="btn btn-danger btn-sm w-100">Delete</button>
                  </form>
                  {% endif %}
                </div>
              </div>
            </div>
          {% endfor %}
          </div>
        {% else %}
          <div class="text-center text-muted py-5">
            <h4>No listings found</h4>
            <p>Try adjusting your search criteria or <a href="/post" class="text-warning">post a new listing</a></p>
          </div>
        {% endif %}
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
      <script src="https://kit.fontawesome.com/your-fontawesome-kit.js"></script>
    </body>
    </html>
    ''', provinces=PROVINCES, results=results, user=user, bg_url=bg_url, nav_html=default_nav(user), q=q,
                                  sort_by=sort_by)


# Province page
@app.route('/province/<province>')
def province_page(province):
    user = current_user()
    bg_url = url_for('static', filename='img/site-bg.jpg')
    province_listings = Listing.query.filter_by(province=province).order_by(Listing.created_at.desc()).all()
    prov_cats = db.session.query(Listing.category).filter_by(province=province).distinct().all()
    prov_cats = [cat[0] for cat in prov_cats] if prov_cats else CATEGORIES

    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>{{ province }} - 263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; background-attachment:fixed; background-size:cover; }
        .listing-card { cursor: pointer; transition: transform 0.2s; }
        .listing-card:hover { transform: translateY(-5px); }
        .view-count { font-size: 0.8rem; color: #6c757d; }
      </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#topnav2">
            <span class="navbar-toggler-icon"></span>
          </button>
          <div class="collapse navbar-collapse" id="topnav2">
            <ul class="navbar-nav ms-auto align-items-center">
              {{ nav_html|safe }}
            </ul>
          </div>
        </div>
      </nav>
      <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h2 class="text-danger fw-bold">263 Explosion — {{ province }}</h2>
          {% if user %}<a href="{{ url_for('post_listing', province=province) }}" class="btn btn-danger">Post in {{ province }}</a>{% endif %}
        </div>
        <p class="lead">Pick a category</p>
        <div class="row g-3 justify-content-start mb-4">
          {% for cat in prov_cats %}
            <div class="col-6 col-md-3">
              <div class="card shadow-sm h-100">
                <div class="card-body d-flex flex-column">
                  <h5 class="fw-bold text-danger">{{ cat }}</h5>
                  <p class="small text-muted">Browse {{ cat }} in {{ province }}</p>
                  <a class="btn btn-outline-danger btn-sm mt-auto" href="{{ url_for('category_page', province=province, category=cat) }}">View</a>
                </div>
              </div>
            </div>
          {% endfor %}
        </div>
        <hr>
        <h4 class="mb-3">Featured in {{ province }}</h4>
        {% if province_listings %}
          <div class="row g-3">
            {% for item in province_listings[:12] %}
              <div class="col-12 col-md-6 col-lg-4">
                <div class="card shadow-sm h-100 listing-card" onclick="window.location='{{ url_for('listing_detail', listing_id=item.id) }}'">
                  {% if item.photos %}
                    {% set first_photo = item.photos.split(',')[0] %}
                    <img src="{{ url_for('static', filename='uploads/' + first_photo) }}" class="card-img-top" alt="photo" style="height: 200px; object-fit: cover;">
                  {% endif %}
                  <div class="card-body">
                    <span class="badge text-bg-danger float-end">{{ item.category }}</span>
                    <h5 class="mb-1">{{ item.title }}</h5>
                    {% if item.price %}<div class="text-success fw-bold mb-1">${{ item.price }}</div>{% endif %}
                    <small class="text-muted">{{ item.province }} · Seller: {{ item.seller_user.name }}</small>
                    <div class="view-count">
                      <i class="fas fa-eye"></i> {{ item.view_count }} views • {{ item.created_at.strftime('%b %d') }}
                    </div>
                    {% if item.description %}<p class="small mt-2">{{ item.description[:100] }}{{ '...' if item.description|length > 100 else '' }}</p>{% endif %}
                    <div class="d-flex flex-wrap gap-2 mt-2">
                      <a class="btn btn-sm btn-success" target="_blank" href="https://wa.me/{{ item.country_code_whatsapp }}{{ item.whatsapp|replace('+','')|replace(' ','') }}">WhatsApp</a>
                      <a class="btn btn-sm btn-outline-primary" href="tel:{{ item.country_code_phone }}{{ item.phone }}">Call</a>
                      <a class="btn btn-sm btn-outline-secondary" href="mailto:{{ item.email }}">Email</a>
                    </div>
                    {% if user and user.id == item.user_id %}
                    <form method="post" action="{{ url_for('delete_listing', listing_id=item.id) }}" onsubmit="return confirm('Are you sure you want to delete this listing?');" class="mt-2">
                      <button type="submit" class="btn btn-danger btn-sm w-100">Delete</button>
                    </form>
                    {% endif %}
                  </div>
                </div>
              </div>
            {% endfor %}
          </div>
        {% else %}
          <p class="text-muted">No listings yet in {{ province }}.</p>
        {% endif %}
        <div class="text-center mt-4"><a href="/" class="btn btn-secondary">⬅ Back to Provinces</a></div>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
      <script src="https://kit.fontawesome.com/your-fontawesome-kit.js"></script>
    </body>
    </html>
    ''', province=province, prov_cats=prov_cats, province_listings=province_listings, user=user, bg_url=bg_url,
                                  nav_html=default_nav(user))


# Category page
@app.route('/province/<province>/<path:category>', endpoint='category_page')
def category_page(province, category):
    matches = Listing.query.filter_by(province=province, category=category).order_by(Listing.created_at.desc()).all()
    user = current_user()
    bg_url = url_for('static', filename='img/site-bg.jpg')
    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>{{ category }} in {{ province }} - 263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body { background-image: url("{{ bg_url }}"); background-repeat: no-repeat; background-position: center center; background-attachment: fixed; background-size: cover; }
        .listing-card { cursor: pointer; transition: transform 0.2s; }
        .listing-card:hover { transform: translateY(-5px); }
        .view-count { font-size: 0.8rem; color: #6c757d; }
      </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#topnav3">
            <span class="navbar-toggler-icon"></span>
          </button>
          <div class="collapse navbar-collapse" id="topnav3">
            <ul class="navbar-nav ms-auto align-items-center">
              {{ nav_html|safe }}
            </ul>
          </div>
        </div>
      </nav>
      <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h3 class="text-danger fw-bold">{{ category }} — {{ province }}</h3>
          {% if user %}<a href="{{ url_for('post_listing', province=province, category=category) }}" class="btn btn-danger">Post {{ category }}</a>{% endif %}
        </div>
        {% if matches %}
          <div class="row g-3">
            {% for item in matches %}
              <div class="col-12 col-md-6 col-lg-4">
                <div class="card shadow-sm h-100 listing-card" onclick="window.location='{{ url_for('listing_detail', listing_id=item.id) }}'">
                  {% if item.photos %}
                    {% set first_photo = item.photos.split(',')[0] %}
                    <img src="{{ url_for('static', filename='uploads/' + first_photo) }}" class="card-img-top" alt="photo" style="height: 200px; object-fit: cover;">
                  {% endif %}
                  <div class="card-body">
                    <h5 class="mb-1">{{ item.title }}</h5>
                    {% if item.price %}<div class="text-success fw-bold mb-1">${{ item.price }}</div>{% endif %}
                    <small class="text-muted">{{ item.category }} · {{ item.province }} · Seller: {{ item.seller_user.name }}</small>
                    <div class="view-count">
                      <i class="fas fa-eye"></i> {{ item.view_count }} views • {{ item.created_at.strftime('%b %d') }}
                    </div>
                    {% if item.description %}<p class="small mt-2">{{ item.description[:100] }}{{ '...' if item.description|length > 100 else '' }}</p>{% endif %}
                    <div class="d-flex flex-wrap gap-2 mt-2">
                      <a class="btn btn-sm btn-success" target="_blank" href="https://wa.me/{{ item.country_code_whatsapp }}{{ item.whatsapp|replace('+','')|replace(' ','') }}">WhatsApp</a>
                      <a class="btn btn-sm btn-outline-primary" href="tel:{{ item.country_code_phone }}{{ item.phone }}">Call</a>
                      <a class="btn btn-sm btn-outline-secondary" href="mailto:{{ item.email }}">Email</a>
                    </div>
                    {% if user and user.id == item.user_id %}
                    <form method="post" action="{{ url_for('delete_listing', listing_id=item.id) }}" onsubmit="return confirm('Are you sure you want to delete this listing?');" class="mt-2">
                      <button type="submit" class="btn btn-danger btn-sm w-100">Delete</button>
                    </form>
                    {% endif %}
                  </div>
                </div>
              </div>
            {% endfor %}
          </div>
        {% else %}
          <p class="text-muted text-center">No listings yet in this category for {{ province }}.</p>
        {% endif %}
        <div class="d-flex gap-2 justify-content-center mt-4">
          <a class="btn btn-outline-secondary" href="{{ url_for('province_page', province=province) }}">⬅ Back to {{ province }}</a>
          <a class="btn btn-secondary" href="/">🏠 Home</a>
        </div>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
      <script src="https://kit.fontawesome.com/your-fontawesome-kit.js"></script>
    </body>
    </html>
    ''', province=province, category=category, matches=matches, user=user, bg_url=bg_url, nav_html=default_nav(user))


# Post listing route with multiple photos and country codes
@app.route('/post', methods=['GET', 'POST'])
@app.route('/post/<province>', methods=['GET', 'POST'])
@app.route('/post/<province>/<path:category>', methods=['GET', 'POST'])
@login_required
def post_listing(province=None, category=None):
    user = current_user()
    bg_url = url_for('static', filename='img/site-bg.jpg')

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        sel_province = request.form.get('province') or province or ''
        sel_category = request.form.get('category') or category or ''
        price = request.form.get('price', '')
        description = request.form.get('description', '')
        seller = request.form.get('seller', '').strip() or user.name
        phone = request.form.get('phone', '').strip()
        whatsapp = request.form.get('whatsapp', '').strip() or phone
        email = request.form.get('email', '').strip() or user.email
        country_code_phone = request.form.get('country_code_phone', '+263')
        country_code_whatsapp = request.form.get('country_code_whatsapp', '+263')

        photo_files = request.files.getlist('photos')
        filenames = []

        # Handle multiple photo uploads (up to 10)
        for i, photo_file in enumerate(photo_files[:10]):
            if photo_file and photo_file.filename:
                ext = os.path.splitext(photo_file.filename)[1].lower()
                if ext in ALLOWED_EXT:
                    safe = secure_filename(photo_file.filename)
                    filename = f"{int(time.time())}_{i}_{safe}"
                    photo_file.save(os.path.join('static/uploads', filename))
                    filenames.append(filename)
                else:
                    flash(f'Unsupported image type for file {i + 1}.', 'danger')
                    return redirect(request.url)

        if not title or not sel_province or not sel_category:
            flash('Title, province and category are required.', 'danger')
            return redirect(request.url)

        # Create new listing in database
        new_listing = Listing(
            title=title,
            category=sel_category,
            province=sel_province,
            price=price,
            description=description,
            phone=phone,
            whatsapp=whatsapp,
            email=email,
            photos=','.join(filenames) if filenames else None,
            country_code_phone=country_code_phone,
            country_code_whatsapp=country_code_whatsapp,
            user_id=user.id
        )

        db.session.add(new_listing)
        db.session.commit()

        flash('Listing posted successfully!', 'success')
        return redirect(url_for('listing_detail', listing_id=new_listing.id))

    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Post Listing - 263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; background-attachment:fixed; background-size:cover; }
      </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#topnav">
            <span class="navbar-toggler-icon"></span>
          </button>
          <div class="collapse navbar-collapse" id="topnav">
            <ul class="navbar-nav ms-auto align-items-center">
              {{ nav_html|safe }}
            </ul>
          </div>
        </div>
      </nav>
      <div class="container py-4">
        <h3 class="text-danger fw-bold mb-3">Post a Listing</h3>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% for cat, msg in messages %}
            <div class="alert alert-{{cat}}">{{ msg }}</div>
          {% endfor %}
        {% endwith %}
        <form method="post" enctype="multipart/form-data" class="row g-3">
          <div class="col-12 col-md-8">
            <label class="form-label">Title *</label>
            <input name="title" class="form-control" required>
          </div>
          <div class="col-12 col-md-4">
            <label class="form-label">Price ($)</label>
            <input name="price" class="form-control" placeholder="e.g., 15000">
          </div>
          <div class="col-12 col-md-6">
            <label class="form-label">Category *</label>
            <select name="category" class="form-select" required>
              <option value="">Select</option>
              {% for c in categories %}
                <option value="{{c}}" {% if c==category %}selected{% endif %}>{{ c }}</option>
              {% endfor %}
            </select>
          </div>
          <div class="col-12 col-md-6">
            <label class="form-label">Province *</label>
            <select name="province" class="form-select" required>
              <option value="">Select</option>
              {% for p in provinces %}
                <option value="{{p}}" {% if p==province %}selected{% endif %}>{{ p }}</option>
              {% endfor %}
            </select>
          </div>
          <div class="col-12">
            <label class="form-label">Description</label>
            <textarea name="description" class="form-control" rows="3" placeholder="Describe your item..."></textarea>
          </div>
          <div class="col-12 col-md-4">
            <label class="form-label">Seller Name</label>
            <input name="seller" class="form-control" value="{{ user.name }}">
          </div>

          <!-- Phone with country code -->
          <div class="col-12 col-md-4">
            <label class="form-label">Phone Country Code *</label>
            <select name="country_code_phone" class="form-select" required>
              {% for code in country_codes %}
                <option value="{{code.code}}" {% if code.code == '+263' %}selected{% endif %}>{{code.country}} ({{code.code}})</option>
              {% endfor %}
            </select>
          </div>
          <div class="col-12 col-md-4">
            <label class="form-label">Phone Number *</label>
            <input name="phone" class="form-control" required>
          </div>

          <!-- WhatsApp with country code -->
          <div class="col-12 col-md-4">
            <label class="form-label">WhatsApp Country Code</label>
            <select name="country_code_whatsapp" class="form-select">
              {% for code in country_codes %}
                <option value="{{code.code}}" {% if code.code == '+263' %}selected{% endif %}>{{code.country}} ({{code.code}})</option>
              {% endfor %}
            </select>
          </div>
          <div class="col-12 col-md-8">
            <label class="form-label">WhatsApp Number</label>
            <input name="whatsapp" class="form-control" placeholder="Leave blank to use phone number">
          </div>

          <div class="col-12 col-md-6">
            <label class="form-label">Email</label>
            <input name="email" class="form-control" value="{{ user.email }}">
          </div>
          <div class="col-12 col-md-6">
            <label class="form-label">Photos (Up to 10)</label>
            <input type="file" name="photos" class="form-control" accept="image/*" multiple>
            <div class="form-text">You can select multiple photos at once.</div>
          </div>
          <div class="col-12">
            <button class="btn btn-danger">Post Listing</button>
            <a href="/" class="btn btn-secondary">Cancel</a>
          </div>
        </form>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    ''', provinces=PROVINCES, categories=CATEGORIES, province=province, category=category, user=user, bg_url=bg_url,
                                  country_codes=COUNTRY_CODES, nav_html=default_nav(user))


# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))

        new_user = User(
            email=email,
            name=name,
            password_hash=generate_password_hash(password)
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    bg_url = url_for('static', filename='img/site-bg.jpg')
    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Register - 263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style> body { background-image: url("{{ bg_url }}"); background-repeat: no-repeat; background-position: center center; background-attachment: fixed; background-size: cover; } </style>
    </head>
    <body class="d-flex align-items-center" style="min-height:100vh;">
      <div class="container" style="max-width:420px;">
        <div class="card shadow-sm">
          <div class="card-body">
            <h3 class="text-danger fw-bold mb-3 text-center">263 Explosion Register</h3>
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% for cat, msg in messages %}
                <div class="alert alert-{{cat}}">{{ msg }}</div>
              {% endfor %}
            {% endwith %}
            <form method="post" class="d-grid gap-3">
              <input type="text" name="name" class="form-control" placeholder="Full Name" required>
              <input type="email" name="email" class="form-control" placeholder="Email" required>
              <input type="password" name="password" class="form-control" placeholder="Password" required>
              <input type="password" name="confirm_password" class="form-control" placeholder="Confirm Password" required>
              <button class="btn btn-danger">Register</button>
            </form>
            <div class="text-center mt-3">
              <a href="{{ url_for('login') }}" class="text-muted">Already have an account? Login</a>
            </div>
          </div>
        </div>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    ''', bg_url=bg_url)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            flash('Welcome back!', 'success')
            next_url = request.args.get('next') or url_for('home')
            return redirect(next_url)
        flash('Invalid email or password.', 'danger')

    bg_url = url_for('static', filename='img/site-bg.jpg')
    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Login - 263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style> body { background-image: url("{{ bg_url }}"); background-repeat: no-repeat; background-position: center center; background-attachment: fixed; background-size: cover; } </style>
    </head>
    <body class="d-flex align-items-center" style="min-height:100vh;">
      <div class="container" style="max-width:420px;">
        <div class="card shadow-sm">
          <div class="card-body">
            <h3 class="text-danger fw-bold mb-3 text-center">263 Explosion Login</h3>
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% for cat, msg in messages %}
                <div class="alert alert-{{cat}}">{{ msg }}</div>
              {% endfor %}
            {% endwith %}
            <form method="post" class="d-grid gap-3">
              <input type="email" name="email" class="form-control" placeholder="Email" required>
              <input type="password" name="password" class="form-control" placeholder="Password" required>
              <button class="btn btn-danger">Login</button>
            </form>
            <div class="text-center mt-3">
              <a href="{{ url_for('register') }}" class="text-muted">Don't have an account? Register</a>
            </div>
          </div>
        </div>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    ''', bg_url=bg_url)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out.', 'info')
    return redirect(url_for('home'))


# Investment routes
@app.route('/invest')
def invest():
    user = current_user()
    bg_url = url_for('static', filename='img/site-bg.jpg')
    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>How to Invest in Zimbabwe - 263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style> body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; background-attachment:fixed; background-size:cover; } </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#investnav"><span class="navbar-toggler-icon"></span></button>
          <div class="collapse navbar-collapse" id="investnav">
            <ul class="navbar-nav ms-auto align-items-center">
              {{ nav_html|safe }}
            </ul>
          </div>
        </div>
      </nav>
      <div class="container py-4">
        <h2 class="text-danger fw-bold mb-3">How to Invest in Zimbabwe</h2>
        <div class="row g-3">
          {% for s in sectors %}
          <div class="col-12 col-md-6 col-lg-4">
            <div class="card h-100 shadow-sm">
              <div class="card-body d-flex flex-column">
                <h5 class="fw-bold text-danger">{{ s }}</h5>
                <p class="small text-muted">Learn about policies, opportunities and partners in {{ s }}.</p>
                <a class="btn btn-outline-danger mt-auto" href="{{ url_for('invest_sector', sector=s) }}">View</a>
              </div>
            </div>
          </div>
          {% endfor %}
        </div>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    ''', sectors=SECTORS, user=user, bg_url=bg_url, nav_html=default_nav(user))


@app.route('/invest/<path:sector>')
def invest_sector(sector):
    user = current_user()
    bg_url = url_for('static', filename='img/site-bg.jpg')
    ideas = [
        "Market size and demand drivers",
        "Key regulations and permits",
        "Local partners and associations",
        "Incentives and tax considerations",
        "Starter checklist"
    ]
    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>{{ sector }} - Invest in Zimbabwe</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style> body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; background-attachment:fixed; background-size:cover; } </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#invsec"><span class="navbar-toggler-icon"></span></button>
          <div class="collapse navbar-collapse" id="invsec">
            <ul class="navbar-nav ms-auto align-items-center">
              {{ nav_html|safe }}
            </ul>
          </div>
        </div>
      </nav>
      <div class="container py-4">
        <h2 class="text-danger fw-bold mb-3">{{ sector }}</h2>
        <ul class="list-group mb-3">
          {% for i in ideas %}<li class="list-group-item">{{ i }}</li>{% endfor %}
        </ul>
        <a class="btn btn-secondary" href="{{ url_for('invest') }}">⬅ Back to Sectors</a>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    ''', ideas=ideas, sector=sector, user=user, bg_url=bg_url, nav_html=default_nav(user))


# Markets routes
@app.route('/markets')
def markets():
    user = current_user()
    bg_url = url_for('static', filename='img/site-bg.jpg')
    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Markets Overview - 263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style> body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; background-attachment:fixed; background-size:cover; } </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#topnavm0"><span class="navbar-toggler-icon"></span></button>
          <div class="collapse navbar-collapse" id="topnavm0">
            <ul class="navbar-nav ms-auto align-items-center">
              {{ nav_html|safe }}
            </ul>
          </div>
        </div>
      </nav>
      <div class="container py-4">
        <h2 class="text-danger fw-bold mb-3">Markets</h2>
        <div class="row g-3">
          <div class="col-12 col-md-6">
            <div class="card h-100 shadow-sm"><div class="card-body">
              <h5 class="fw-bold">Exchange Rates</h5>
              <p class="text-muted small">Indicative live rates (cached).</p>
              <a class="btn btn-outline-danger" href="{{ url_for('markets_currencies') }}">View Exchange Rates</a>
            </div></div>
          </div>
          <div class="col-12 col-md-6">
            <div class="card h-100 shadow-sm"><div class="card-body">
              <h5 class="fw-bold">Metals Prices</h5>
              <p class="text-muted small">Indicative live prices (cached).</p>
              <a class="btn btn-outline-danger" href="{{ url_for('markets_metals') }}">View Metals Prices</a>
            </div></div>
          </div>
        </div>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    ''', user=user, bg_url=bg_url, nav_html=default_nav(user))


@app.route('/markets/currencies')
def markets_currencies():
    user = current_user()
    bg_url = url_for('static', filename='img/site-bg.jpg')
    rates = get_live_currencies()
    last_updated = datetime.fromtimestamp(CACHE["currencies"]["ts"]).strftime("%Y-%m-%d %H:%M")
    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Exchange Rates - 263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style> body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; background-attachment:fixed; background-size:cover; } </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#topnavm1"><span class="navbar-toggler-icon"></span></button>
          <div class="collapse navbar-collapse" id="topnavm1">
            <ul class="navbar-nav ms-auto align-items-center">
              {{ nav_html|safe }}
            </ul>
          </div>
        </div>
      </nav>
      <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h2 class="text-danger fw-bold mb-0">Exchange Rates</h2>
          <div><span class="badge bg-secondary me-2">Last updated {{ last_updated }}</span>
            <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('markets_currencies') }}">Refresh</a></div>
        </div>
        <table class="table table-striped table-bordered bg-white">
          <thead><tr><th>Pair</th><th>Rate</th></tr></thead>
          <tbody>
            {% for r in rates %}<tr><td>{{ r.pair }}</td><td>{{ r.rate }}</td></tr>{% endfor %}
          </tbody>
        </table>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    ''', user=user, bg_url=bg_url, rates=rates, last_updated=last_updated, nav_html=default_nav(user))


@app.route('/markets/metals')
def markets_metals():
    user = current_user()
    bg_url = url_for('static', filename='img/site-bg.jpg')
    metals = get_live_metals()
    last_updated = datetime.fromtimestamp(CACHE["metals"]["ts"]).strftime("%Y-%m-%d %H:%M")
    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Metals Prices - 263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style> body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; background-attachment:fixed; background-size:cover; } </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#topnavm2"><span class="navbar-toggler-icon"></span></button>
          <div class="collapse navbar-collapse" id="topnavm2">
            <ul class="navbar-nav ms-auto align-items-center">
              {{ nav_html|safe }}
            </ul>
          </div>
        </div>
      </nav>
      <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h2 class="text-danger fw-bold mb-0">Metals Prices</h2>
          <div><span class="badge bg-secondary me-2">Last updated {{ last_updated }}</span>
            <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('markets_metals') }}">Refresh</a></div>
        </div>
        <table class="table table-striped table-bordered bg-white">
          <thead><tr><th>Metal</th><th>Price</th></tr></thead>
          <tbody>
            {% for m in metals %}<tr><td>{{ m.metal }}</td><td>{{ m.price }}</td></tr>{% endfor %}
          </tbody>
        </table>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    ''', user=user, bg_url=bg_url, metals=metals, last_updated=last_updated, nav_html=default_nav(user))







