from flask import Flask, render_template_string, request, url_for, session, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import time
import requests
from datetime import datetime

app = Flask(__name__)

# Database configuration for Render
database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Fallback for local development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

db = SQLAlchemy(app)

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
    {"metal": "Nickel (t)", "price": "-"}
]

CACHE = {"currencies": {"ts": 0, "data": MARKET_CURRENCIES}, "metals": {"ts": 0, "data": MARKET_METALS}}


# Database Models
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
    photo = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Sponsor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    image = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)


# Create tables
with app.app_context():
    db.create_all()


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
    return '''
      <li class="nav-item dropdown">
        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">How to Invest in Zimbabwe</a>
        <ul class="dropdown-menu dropdown-menu-end">
          {% for s in sectors %}<li><a class="dropdown-item" href="{{ url_for('invest_sector', sector=s) }}">{{ s }}</a></li>{% endfor %}
          <li><hr class="dropdown-divider"></li>
          <li><a class="dropdown-item" href="{{ url_for('invest') }}">Overview</a></li>
        </ul>
      </li>
      <li class="nav-item dropdown">
        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Markets</a>
        <ul class="dropdown-menu dropdown-menu-end">
          <li><a class="dropdown-item" href="{{ url_for('markets_currencies') }}">Exchange Rates</a></li>
          <li><a class="dropdown-item" href="{{ url_for('markets_metals') }}">Metals Prices</a></li>
          <li><hr class="dropdown-divider"></li>
          <li><a class="dropdown-item" href="{{ url_for('markets') }}">Overview</a></li>
        </ul>
      </li>
      {% if user %}
        <li class="nav-item me-2"><a href="{{ url_for('post_listing') }}" class="btn btn-outline-warning btn-sm">Post</a></li>
        <li class="nav-item"><span class="text-white-50 small me-2">Welcome, {{ user.name }}</span></li>
        <li class="nav-item"><a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">Logout</a></li>
      {% else %}
        <li class="nav-item"><a href="{{ url_for('login') }}" class="btn btn-danger btn-sm">Login</a></li>
      {% endif %}
    '''


# Initialize default data
def init_default_data():
    # Default sponsors
    if Sponsor.query.count() == 0:
        default_sponsors = [
            {"name": "Econet Wireless", "image": "econet.jpg", "url": "https://www.econet.co.zw"},
            {"name": "CBZ Bank", "image": "cbz.jpg", "url": "https://www.cbz.co.zw"},
            {"name": "Delta Beverages", "image": "delta.jpg", "url": "https://www.delta.co.zw"},
            {"name": "OK Zimbabwe", "image": "ok_zimbabwe.jpg", "url": "https://www.okzim.co.zw"},
            {"name": "NMB Bank", "image": "nmb.jpg", "url": "https://www.nmbz.co.zw"},
            {"name": "TelOne", "image": "telone.jpg", "url": "https://www.telone.co.zw"}
        ]
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


# Call initialization
with app.app_context():
    init_default_data()


# Market data functions (unchanged)
def get_live_currencies(ttl=600):
    now = time.time()
    if now - CACHE["currencies"]["ts"] < ttl:
        return CACHE["currencies"]["data"]
    try:
        resp = requests.get(
            "https://api.exchangerate.host/latest",
            params={"base": "USD", "symbols": "ZWL,GBP,EUR,ZAR,BWP,CNY"},
            timeout=8
        )
        data = resp.json()
        rates = data.get("rates", {}) or {}
        out = [
            {"pair": "USD/ZWL", "rate": f"{rates.get('ZWL', 0):,.2f}"} if rates.get('ZWL') else {"pair": "USD/ZWL",
                                                                                                 "rate": "N/A"},
            {"pair": "ZAR/USD", "rate": f"{1 / rates.get('ZAR'):,.4f}"} if rates.get('ZAR') else {"pair": "ZAR/USD",
                                                                                                  "rate": "N/A"},
            {"pair": "GBP/USD", "rate": f"{1 / rates.get('GBP'):,.4f}"} if rates.get('GBP') else {"pair": "GBP/USD",
                                                                                                  "rate": "N/A"},
            {"pair": "EUR/USD", "rate": f"{1 / rates.get('EUR'):,.4f}"} if rates.get('EUR') else {"pair": "EUR/USD",
                                                                                                  "rate": "N/A"},
            {"pair": "BWP/USD", "rate": f"{1 / rates.get('BWP'):,.4f}"} if rates.get('BWP') else {"pair": "BWP/USD",
                                                                                                  "rate": "N/A"},
            {"pair": "CNY/USD", "rate": f"{1 / rates.get('CNY'):,.4f}"} if rates.get('CNY') else {"pair": "CNY/USD",
                                                                                                  "rate": "N/A"},
        ]
        CACHE["currencies"] = {"ts": now, "data": out}
        return out
    except Exception:
        return CACHE["currencies"]["data"]


def get_live_metals(ttl=600):
    now = time.time()
    if now - CACHE["metals"]["ts"] < ttl:
        return CACHE["metals"]["data"]
    key = os.getenv("METALS_API_KEY")
    try:
        metals = [
            ("Gold (oz)", "XAU"),
            ("Silver (oz)", "XAG"),
            ("Platinum (oz)", "XPT"),
            ("Palladium (oz)", "XPD"),
        ]
        out = []
        if key:
            r = requests.get(
                "https://metals-api.com/api/latest",
                params={"access_key": key, "base": "USD", "symbols": ",".join([m for _, m in metals])},
                timeout=8
            )
            j = r.json()
            rates = j.get("rates", {}) or {}
            for name, sym in metals:
                price = rates.get(f"USD{sym}") or rates.get(sym)
                out.append({"metal": name, "price": f"${price:,.2f}" if price else "N/A"})
        else:
            alt = os.getenv("METALPRICEAPI_KEY")
            if alt:
                r = requests.get(
                    "https://api.metalpriceapi.com/v1/latest",
                    params={"api_key": alt, "base": "USD", "currencies": "XAU,XAG,XPT,XPD"},
                    timeout=8
                )
                j = r.json()
                rates = j.get("rates", {}) or {}
                for name, sym in metals:
                    price = rates.get(f"USD{sym}") or rates.get(sym)
                    out.append({"metal": name, "price": f"${price:,.2f}" if price else "N/A"})
            else:
                out = MARKET_METALS
        out.append({"metal": "Nickel (t)", "price": "N/A"})
        CACHE["metals"] = {"ts": now, "data": out}
        return out
    except Exception:
        return CACHE["metals"]["data"]


# Routes
@app.route('/')
def home():
    q = request.args.get('q', '').strip().lower()
    province_filter = request.args.get('province', '')
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
        results = results.order_by(Listing.created_at.desc()).all()
    else:
        # Show recent listings when no search
        results = Listing.query.order_by(Listing.created_at.desc()).limit(12).all()

    user = current_user()
    bg_url = url_for('static', filename='img/site-bg.jpg')
    sponsors = get_sponsors_from_db()

    return render_template_string(f'''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body {{ background-image: url("{{{{ bg_url }}}}"); background-repeat: no-repeat; background-position: center center; 
background-attachment: fixed; background-size: cover; color: white; }}
        .overlay {{ background:rgba(0,0,0,.6); min-height:100vh; padding-top:70px; }}
        .province-card {{ background:#fff; color:#000; border-radius:12px; padding:1rem; font-weight:700; text-transform:uppercase; 
text-decoration:none; display:block; transition:.25s; }}
        .province-card:hover {{ background:#dc3545; color:#fff; transform:scale(1.05); }}
        .search-bar {{ background:#fff; border-radius:12px; padding:10px; max-width:900px; margin:20px auto; }}
        .sponsors-section {{ background: rgba(255,255,255,0.95); border-radius: 15px; padding: 2rem; margin: 2rem auto; max-width: 1200px; 
}}
        .sponsor-img {{ max-height: 120px; object-fit: contain; padding: 10px; }}
        .carousel-control-prev, .carousel-control-next {{ width: 5%; }}
        .carousel-indicators button {{ background-color: #dc3545; }}
        .listing-price {{ color: #dc3545; font-weight: bold; }}
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
              {default_nav('user')}
            </ul>
          </div>
        </div>
      </nav>
      <div class="overlay text-center">
        <h1 class="fw-bold text-danger mb-1">263 Explosion</h1>
        <p class="lead">Zimbabwe's #1 Online Classifieds Platform</p>
        {{% with messages = get_flashed_messages(with_categories=true) %}}
          {{% for cat, msg in messages %}}
            <div class="alert alert-{{{{cat}}}} w-75 mx-auto">{{{{ msg }}}}</div>
          {{% endfor %}}
        {{% endwith %}}
        <form method="get" class="search-bar d-flex flex-wrap shadow-sm" enctype="multipart/form-data">
          <input class="form-control me-2 mb-2" name="q" placeholder="Search cars, houses, jobs…" value="{{{{ request.args.get('q','') 
}}}}">
          <select name="province" class="form-select me-2 mb-2" style="max-width:220px;">
            <option value="">All Provinces</option>
            {{% for p in provinces %}}
              <option value="{{{{p}}}}" {{% if p==request.args.get('province') %}}selected{{% endif %}}>{{{{p}}}}</option>
            {{% endfor %}}
          </select>
          <button class="btn btn-danger mb-2">Search</button>
        </form>
        {{% if request.args.get('q') or not request.args.get('q') %}}
          <div class="container bg-white text-dark rounded py-3 mt-3" style="max-width:1200px;">
            <h5 class="mb-3">
              {{% if request.args.get('q') %}}
                Search results for "{{{{ request.args.get('q') }}}}"
              {{% else %}}
                Recent Listings
              {{% endif %}}
            </h5>
            {{% if results %}}
              <div class="row g-3">
              {{% for r in results %}}
                <div class="col-12 col-md-6 col-lg-4">
                  <div class="card shadow-sm h-100">
                    {{% if r.photo %}}
                      <img src="{{{{ url_for('static', filename='uploads/' + r.photo) }}}}" class="card-img-top" alt="photo" style="height: 
200px; object-fit: cover;">
                    {{% endif %}}
                    <div class="card-body">
                      <h5 class="mb-1">{{{{ r.title }}}}</h5>
                      {{% if r.price %}}<div class="listing-price mb-1">${{{{ r.price }}}}</div>{{% endif %}}
                      <small class="text-muted">{{{{ r.category }}}} — {{{{ r.province }}}}</small>
                      {{% if r.description %}}<p class="small mt-2">{{{{ r.description[:100] }}}}{{{{ '...' if r.description|length > 100 
else '' }}}}</p>{{% endif %}}
                      <div class="d-flex flex-wrap gap-2 mt-2">
                        <a class="btn btn-sm btn-success" target="_blank" href="https://wa.me/{{{{ r.whatsapp|replace('+','')|replace(' 
','') }}}}">WhatsApp</a>
                        <a class="btn btn-sm btn-outline-primary" href="tel:{{{{ r.phone }}}}">Call</a>
                        <a class="btn btn-sm btn-outline-secondary" href="mailto:{{{{ r.email }}}}">Email</a>
                      </div>
                    </div>
                  </div>
                </div>
              {{% endfor %}}
              </div>
            {{% else %}}
              <div class="text-muted">No results found.</div>
            {{% endif %}}
          </div>
        {{% endif %}}
        <hr class="w-75 my-4">
        <p class="h5">Choose a province or district</p>
        <div class="container mt-3">
          <div class="row justify-content-center g-3">
            {{% for p in provinces %}}
              <div class="col-6 col-md-3"><a class="province-card shadow-sm" href="{{{{ url_for('province_page', province=p) }}}}">{{{{ p 
}}}}</a></div>
            {{% endfor %}}
          </div>
        </div>

        <!-- Sponsors Section -->
        {{% if sponsors %}}
        <div class="sponsors-section">
          <h3 class="text-danger mb-4">Our Valued Partners & Sponsors</h3>
          <div id="sponsorsCarousel" class="carousel slide" data-bs-ride="carousel">
            <div class="carousel-indicators">
              {{% for i in range((sponsors|length + 2) // 3) %}}
                <button type="button" data-bs-target="#sponsorsCarousel" data-bs-slide-to="{{{{ i }}}}" class="{{{{ 'active' if i==0 else 
'' }}}}"></button>
              {{% endfor %}}
            </div>
            <div class="carousel-inner">
              {{% for i in range(0, sponsors|length, 3) %}}
                <div class="carousel-item {{{{ 'active' if i==0 else '' }}}}">
                  <div class="row justify-content-center">
                    {{% for sponsor in sponsors[i:i+3] %}}
                      <div class="col-md-4 text-center">
                        <a href="{{{{ sponsor.url }}}}" target="_blank">
                          <img src="{{{{ url_for('static', filename='img/sponsors/' + sponsor.image) }}}}" 
                               class="sponsor-img img-fluid" 
                               alt="{{{{ sponsor.name }}}}"
                               title="{{{{ sponsor.name }}}}">
                        </a>
                      </div>
                    {{% endfor %}}
                  </div>
                </div>
              {{% endfor %}}
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
        </div>
        {{% endif %}}
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    ''', provinces=PROVINCES, results=results, user=user, bg_url=bg_url, sectors=SECTORS, sponsors=sponsors)


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
        body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; 
background-attachment:fixed; background-size:cover; }
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
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">How to Invest in Zimbabwe</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  {% for s in sectors %}<li><a class="dropdown-item" href="{{ url_for('invest_sector', sector=s) }}">{{ s }}</a></li>{% 
endfor %}
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('invest') }}">Overview</a></li>
                </ul>
              </li>
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Markets</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  <li><a class="dropdown-item" href="{{ url_for('markets_currencies') }}">Exchange Rates</a></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets_metals') }}">Metals Prices</a></li>
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets') }}">Overview</a></li>
                </ul>
              </li>
              {% if user %}
                <li class="nav-item me-2"><a href="{{ url_for('post_listing') }}" class="btn btn-outline-warning btn-sm">Post</a></li>
                <li class="nav-item"><a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">Logout</a></li>
              {% else %}
                <li class="nav-item"><a href="{{ url_for('login') }}" class="btn btn-danger btn-sm">Login</a></li>
              {% endif %}
            </ul>
          </div>
        </div>
      </nav>
      <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h2 class="text-danger fw-bold">263 Explosion — {{ province }}</h2>
          {% if user %}<a href="{{ url_for('post_listing', province=province) }}" class="btn btn-danger">Post in {{ province }}</a>{% endif 
%}
        </div>
        <p class="lead">Pick a category</p>
        <div class="row g-3 justify-content-start mb-4">
          {% for cat in prov_cats %}
            <div class="col-6 col-md-3">
              <div class="card shadow-sm h-100">
                <div class="card-body d-flex flex-column">
                  <h5 class="fw-bold text-danger">{{ cat }}</h5>
                  <p class="small text-muted">Browse {{ cat }} in {{ province }}</p>
                  <a class="btn btn-outline-danger btn-sm mt-auto" href="{{ url_for('category_page', province=province, category=cat) 
}}">View</a>
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
                <div class="card shadow-sm h-100">
                  {% if item.photo %}
                    <img src="{{ url_for('static', filename='uploads/' + item.photo) }}" class="card-img-top" alt="photo" style="height: 
200px; object-fit: cover;">
                  {% endif %}
                  <div class="card-body">
                    <span class="badge text-bg-danger float-end">{{ item.category }}</span>
                    <h5 class="mb-1">{{ item.title }}</h5>
                    {% if item.price %}<div class="text-success fw-bold mb-1">${{ item.price }}</div>{% endif %}
                    <small class="text-muted">{{ item.province }} · Seller: {{ item.seller_user.name }}</small>
                    {% if item.description %}<p class="small mt-2">{{ item.description[:100] }}{{ '...' if item.description|length > 100 
else '' }}</p>{% endif %}
                    <div class="d-flex flex-wrap gap-2 mt-2">
                      <a class="btn btn-sm btn-success" target="_blank" href="https://wa.me/{{ item.whatsapp|replace('+','')|replace(' 
','') }}">WhatsApp</a>
                      <a class="btn btn-sm btn-outline-primary" href="tel:{{ item.phone }}">Call</a>
                      <a class="btn btn-sm btn-outline-secondary" href="mailto:{{ item.email }}">Email</a>
                    </div>
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
    </body>
    </html>
    ''', province=province, prov_cats=prov_cats, province_listings=province_listings, user=user, bg_url=bg_url,
                                  sectors=SECTORS)


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
        body { background-image: url("{{ bg_url }}"); background-repeat: no-repeat; background-position: center center; 
background-attachment: fixed; background-size: cover; }
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
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">How to Invest in Zimbabwe</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  {% for s in sectors %}<li><a class="dropdown-item" href="{{ url_for('invest_sector', sector=s) }}">{{ s }}</a></li>{% 
endfor %}
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('invest') }}">Overview</a></li>
                </ul>
              </li>
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Markets</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  <li><a class="dropdown-item" href="{{ url_for('markets_currencies') }}">Exchange Rates</a></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets_metals') }}">Metals Prices</a></li>
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets') }}">Overview</a></li>
                </ul>
              </li>
              {% if user %}
                <li class="nav-item me-2"><a href="{{ url_for('post_listing') }}" class="btn btn-outline-warning btn-sm">Post</a></li>
                <li class="nav-item"><a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">Logout</a></li>
              {% else %}
                <li class="nav-item"><a href="{{ url_for('login') }}" class="btn btn-danger btn-sm">Login</a></li>
              {% endif %}
            </ul>
          </div>
        </div>
      </nav>
      <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h3 class="text-danger fw-bold">{{ category }} — {{ province }}</h3>
          {% if user %}<a href="{{ url_for('post_listing', province=province, category=category) }}" class="btn btn-danger">Post {{ 
category }}</a>{% endif %}
        </div>
        {% if matches %}
          <div class="row g-3">
            {% for item in matches %}
              <div class="col-12 col-md-6 col-lg-4">
                <div class="card shadow-sm h-100">
                  {% if item.photo %}
                    <img src="{{ url_for('static', filename='uploads/' + item.photo) }}" class="card-img-top" alt="photo" style="height: 
200px; object-fit: cover;">
                  {% endif %}
                  <div class="card-body">
                    <h5 class="mb-1">{{ item.title }}</h5>
                    {% if item.price %}<div class="text-success fw-bold mb-1">${{ item.price }}</div>{% endif %}
                    <small class="text-muted">{{ item.category }} · {{ item.province }} · Seller: {{ item.seller_user.name }}</small>
                    {% if item.description %}<p class="small mt-2">{{ item.description[:100] }}{{ '...' if item.description|length > 100 
else '' }}</p>{% endif %}
                    <div class="d-flex flex-wrap gap-2 mt-2">
                      <a class="btn btn-sm btn-success" target="_blank" href="https://wa.me/{{ item.whatsapp|replace('+','')|replace(' 
','') }}">WhatsApp</a>
                      <a class="btn btn-sm btn-outline-primary" href="tel:{{ item.phone }}">Call</a>
                      <a class="btn btn-sm btn-outline-secondary" href="mailto:{{ item.email }}">Email</a>
                    </div>
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
    </body>
    </html>
    ''', province=province, category=category, matches=matches, user=user, bg_url=bg_url, sectors=SECTORS)


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

        photo_file = request.files.get('photo')
        filename = None
        if photo_file and photo_file.filename:
            ext = os.path.splitext(photo_file.filename)[1].lower()
            if ext in ALLOWED_EXT:
                safe = secure_filename(photo_file.filename)
                filename = f"{int(time.time())}_{safe}"
                photo_file.save(os.path.join('static/uploads', filename))
            else:
                flash('Unsupported image type.', 'danger')
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
            photo=filename,
            user_id=user.id
        )

        db.session.add(new_listing)
        db.session.commit()

        flash('Listing posted successfully!', 'success')
        return redirect(url_for('category_page', province=sel_province, category=sel_category))

    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Post Listing - 263 Explosion</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; 
background-attachment:fixed; background-size:cover; }
      </style>
    </head>
    <body>
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
          <div class="col-12 col-md-4">
            <label class="form-label">Phone *</label>
            <input name="phone" class="form-control" required>
          </div>
          <div class="col-12 col-md-4">
            <label class="form-label">WhatsApp</label>
            <input name="whatsapp" class="form-control">
          </div>
          <div class="col-12 col-md-6">
            <label class="form-label">Email</label>
            <input name="email" class="form-control" value="{{ user.email }}">
          </div>
          <div class="col-12 col-md-6">
            <label class="form-label">Photo</label>
            <input type="file" name="photo" class="form-control" accept="image/*">
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
                                  sectors=SECTORS)


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
      <style> body { background-image: url("{{ bg_url }}"); background-repeat: no-repeat; background-position: center center; 
background-attachment: fixed; background-size: cover; } </style>
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
    ''', bg_url=bg_url, sectors=SECTORS)


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
      <style> body { background-image: url("{{ bg_url }}"); background-repeat: no-repeat; background-position: center center; 
background-attachment: fixed; background-size: cover; } </style>
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
            <div class="text-muted small mt-3">
              Demo accounts:<br>
              • admin@263explosion.com / <code>test123</code><br>
              • user@263explosion.com / <code>263explosion</code>
            </div>
          </div>
        </div>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    ''', bg_url=bg_url, sectors=SECTORS)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out.', 'info')
    return redirect(url_for('home'))


# Keep all your other routes (invest, markets, etc.) the same as before
# [Include your existing invest, markets_currencies, markets_metals, invest_sector routes here]
# They remain unchanged from your original code

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
      <style> body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; 
background-attachment:fixed; background-size:cover; } </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#investnav"><span 
class="navbar-toggler-icon"></span></button>
          <div class="collapse navbar-collapse" id="investnav">
            <ul class="navbar-nav ms-auto align-items-center">
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">How to Invest in Zimbabwe</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  {% for s in sectors %}<li><a class="dropdown-item" href="{{ url_for('invest_sector', sector=s) }}">{{ s }}</a></li>{% 
endfor %}
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('invest') }}">Overview</a></li>
                </ul>
              </li>
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Markets</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  <li><a class="dropdown-item" href="{{ url_for('markets_currencies') }}">Exchange Rates</a></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets_metals') }}">Metals Prices</a></li>
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets') }}">Overview</a></li>
                </ul>
              </li>
              {% if user %}<li class="nav-item"><a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">Logout</a></li>{% 
else %}<li class="nav-item"><a href="{{ url_for('login') }}" class="btn btn-danger btn-sm">Login</a></li>{% endif %}
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
    ''', sectors=SECTORS, user=user, bg_url=bg_url)


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
      <style> body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; 
background-attachment:fixed; background-size:cover; } </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#invsec"><span 
class="navbar-toggler-icon"></span></button>
          <div class="collapse navbar-collapse" id="invsec">
            <ul class="navbar-nav ms-auto align-items-center">
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">How to Invest in Zimbabwe</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  {% for s in sectors %}<li><a class="dropdown-item" href="{{ url_for('invest_sector', sector=s) }}">{{ s }}</a></li>{% 
endfor %}
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('invest') }}">Overview</a></li>
                </ul>
              </li>
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Markets</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  <li><a class="dropdown-item" href="{{ url_for('markets_currencies') }}">Exchange Rates</a></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets_metals') }}">Metals Prices</a></li>
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets') }}">Overview</a></li>
                </ul>
              </li>
              {% if user %}<li class="nav-item"><a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">Logout</a></li>{% 
else %}<li class="nav-item"><a href="{{ url_for('login') }}" class="btn btn-danger btn-sm">Login</a></li>{% endif %}
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
    ''', sectors=SECTORS, ideas=ideas, sector=sector, user=user, bg_url=bg_url)


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
      <style> body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; 
background-attachment:fixed; background-size:cover; } </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#topnavm0"><span 
class="navbar-toggler-icon"></span></button>
          <div class="collapse navbar-collapse" id="topnavm0">
            <ul class="navbar-nav ms-auto align-items-center">
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">How to Invest in Zimbabwe</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  {% for s in sectors %}<li><a class="dropdown-item" href="{{ url_for('invest_sector', sector=s) }}">{{ s }}</a></li>{% 
endfor %}
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('invest') }}">Overview</a></li>
                </ul>
              </li>
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Markets</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  <li><a class="dropdown-item" href="{{ url_for('markets_currencies') }}">Exchange Rates</a></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets_metals') }}">Metals Prices</a></li>
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets') }}">Overview</a></li>
                </ul>
              </li>
              {% if user %}<li class="nav-item"><a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">Logout</a></li>{% 
else %}<li class="nav-item"><a href="{{ url_for('login') }}" class="btn btn-danger btn-sm">Login</a></li>{% endif %}
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
    ''', sectors=SECTORS, user=user, bg_url=bg_url)


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
      <style> body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; 
background-attachment:fixed; background-size:cover; } </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#topnavm1"><span 
class="navbar-toggler-icon"></span></button>
          <div class="collapse navbar-collapse" id="topnavm1">
            <ul class="navbar-nav ms-auto align-items-center">
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">How to Invest in Zimbabwe</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  {% for s in sectors %}<li><a class="dropdown-item" href="{{ url_for('invest_sector', sector=s) }}">{{ s }}</a></li>{% 
endfor %}
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('invest') }}">Overview</a></li>
                </ul>
              </li>
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Markets</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  <li><a class="dropdown-item" href="{{ url_for('markets_currencies') }}">Exchange Rates</a></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets_metals') }}">Metals Prices</a></li>
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets') }}">Overview</a></li>
                </ul>
              </li>
              {% if user %}<li class="nav-item"><a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">Logout</a></li>{% 
else %}<li class="nav-item"><a href="{{ url_for('login') }}" class="btn btn-danger btn-sm">Login</a></li>{% endif %}
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
    ''', sectors=SECTORS, user=user, bg_url=bg_url, rates=rates, last_updated=last_updated)


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
      <style> body { background-image:url("{{ bg_url }}"); background-repeat:no-repeat; background-position:center center; 
background-attachment:fixed; background-size:cover; } </style>
    </head>
    <body>
      <nav class="navbar navbar-expand bg-dark navbar-dark">
        <div class="container">
          <a class="navbar-brand fw-bold text-danger" href="/">263 Explosion</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#topnavm2"><span 
class="navbar-toggler-icon"></span></button>
          <div class="collapse navbar-collapse" id="topnavm2">
            <ul class="navbar-nav ms-auto align-items-center">
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">How to Invest in Zimbabwe</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  {% for s in sectors %}<li><a class="dropdown-item" href="{{ url_for('invest_sector', sector=s) }}">{{ s }}</a></li>{% 
endfor %}
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('invest') }}">Overview</a></li>
                </ul>
              </li>
              <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Markets</a>
                <ul class="dropdown-menu dropdown-menu-end">
                  <li><a class="dropdown-item" href="{{ url_for('markets_currencies') }}">Exchange Rates</a></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets_metals') }}">Metals Prices</a></li>
                  <li><hr class="dropdown-divider"></li>
                  <li><a class="dropdown-item" href="{{ url_for('markets') }}">Overview</a></li>
                </ul>
              </li>
              {% if user %}<li class="nav-item"><a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">Logout</a></li>{% 
else %}<li class="nav-item"><a href="{{ url_for('login') }}" class="btn btn-danger btn-sm">Login</a></li>{% endif %}
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
    ''', sectors=SECTORS, user=user, bg_url=bg_url, metals=metals, last_updated=last_updated)







