import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_apscheduler import APScheduler
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from scraper import Scraper
from models import db, User, Vendor, PriceData, ScrapeLog
from config import Config
from sqlalchemy import func, select, and_, desc

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Create a single Scraper instance
scraper = Scraper()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Function to create a new user
def create_user(username, password):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user:
            logger.info(f"User {username} already exists")
            return
        
        new_user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        logger.info(f"User {username} created successfully")

# Scraping function
def perform_scrape(scheduled=False):
    logger.info(f"{'Scheduled' if scheduled else 'Manual'} scrape initiated")
    try:
        scraper.scrape()
        success = True
        message = 'Scraping completed successfully.'
        logger.info(message)
    except Exception as e:
        success = False
        message = f"Error during scraping: {str(e)}"
        logger.error(message, exc_info=True)
    
    # Log the scrape attempt
    log_entry = ScrapeLog(timestamp=datetime.now(), success=success, message=message, scheduled=scheduled)
    db.session.add(log_entry)
    db.session.commit()
    
    return success, message

# Scheduled task
@scheduler.task('cron', id='daily_scrape', hour=8, minute=0)
def scheduled_scrape():
    with app.app_context():
        perform_scrape(scheduled=True)

# Routes
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            logger.info(f"User {username} logged in successfully")
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'error')
            logger.warning(f"Failed login attempt for username: {username}")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logger.info(f"User {current_user.username} logged out")
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/scrape', methods=['GET', 'POST'])
@login_required
def scrape_page():
    if request.method == 'POST':
        success, message = perform_scrape()
        flash(message, 'success' if success else 'error')
        return redirect(url_for('scrape_page'))
    
    logs = ScrapeLog.query.order_by(ScrapeLog.timestamp.desc()).all()
    job = scheduler.get_job('daily_scrape')
    is_scheduled = job is not None and job.next_run_time is not None
    
    return render_template('scrape.html', logs=logs, is_scheduled=is_scheduled)

@app.route('/toggle_schedule', methods=['POST'])
@login_required
def toggle_schedule():
    is_scheduled = request.json.get('isScheduled')
    if is_scheduled:
        scheduler.resume_job('daily_scrape')
        logger.info("Scheduled scraping resumed")
    else:
        scheduler.pause_job('daily_scrape')
        logger.info("Scheduled scraping paused")
    return jsonify(success=True)





@app.route('/prices')
@login_required
def prices():
    # Calculate the date 3 months ago from today
    three_months_ago = datetime.now().date() - timedelta(days=90)

    # Subquery to get the latest price for each vendor within the last 3 months
    latest_prices_subquery = (
        select(
            PriceData.vendor_id,
            func.max(PriceData.date).label('max_date')
        )
        .where(PriceData.date >= three_months_ago)
        .group_by(PriceData.vendor_id)
        .subquery()
    )

    # Query to get the latest prices for all vendors, sorted by price
    query = (
        select(Vendor, PriceData)
        .select_from(Vendor)
        .join(PriceData, Vendor.id == PriceData.vendor_id)
        .join(
            latest_prices_subquery,
            and_(
                Vendor.id == latest_prices_subquery.c.vendor_id,
                PriceData.date == latest_prices_subquery.c.max_date
            )
        )
        .order_by(PriceData.price)  # Sort by price, lowest to highest
    )

    latest_prices = db.session.execute(query).all()

    logger.info(f"Prices page accessed by user {current_user.username}")
    return render_template('prices.html', latest_prices=latest_prices)

@app.route('/trends')
@login_required
def trends():
    # Calculate the date 1 year ago from today
    one_year_ago = datetime.now().date() - timedelta(days=365)

    # Query to get price data for all vendors within the last year
    query = (
        select(Vendor.name, PriceData.date, PriceData.price)
        .select_from(Vendor)
        .join(PriceData, Vendor.id == PriceData.vendor_id)
        .where(PriceData.date >= one_year_ago)
        .order_by(Vendor.name, PriceData.date)
    )

    results = db.session.execute(query).fetchall()

    # Process the data for the chart
    vendors = {}
    for row in results:
        vendor_name = row.name
        if vendor_name not in vendors:
            vendors[vendor_name] = {'dates': [], 'prices': []}
        vendors[vendor_name]['dates'].append(row.date.strftime('%Y-%m-%d'))
        vendors[vendor_name]['prices'].append(float(row.price))

    logger.info(f"Trends page accessed by user {current_user.username}")
    return render_template('trends.html', vendors=vendors)



# Scheduled task
@scheduler.task('cron', id='daily_scrape', hour=0, minute=0)
def scheduled_scrape():
    logger.info("Starting scheduled scrape")
    with app.app_context():
        try:
            scraper.scrape()
            logger.info('Scheduled scraping completed successfully.')
        except Exception as e:
            logger.error(f'Error during scheduled scraping: {str(e)}', exc_info=True)

if __name__ == '__main__':
    app.run(debug=True)