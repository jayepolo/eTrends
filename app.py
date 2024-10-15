import logging
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_apscheduler import APScheduler
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from scraper import Scraper
from models import db, User, Vendor, PriceData
from config import Config

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

@app.route('/scrape', methods=['POST'])
@login_required
def manual_scrape():
    logger.info(f"Manual scrape initiated by user {current_user.username}")
    try:
        scraper.scrape()
        flash('Scraping completed successfully.', 'success')
        logger.info("Manual scrape completed successfully")
    except Exception as e:
        error_msg = f"Error during scraping: {str(e)}"
        flash(error_msg, 'error')
        logger.error(error_msg, exc_info=True)
    return redirect(url_for('index'))

@app.route('/stats')
@login_required
def stats():
    vendors = Vendor.query.all()
    latest_prices = PriceData.query.order_by(PriceData.date.desc()).limit(10).all()
    logger.info(f"Stats page accessed by user {current_user.username}")
    return render_template('stats.html', vendors=vendors, latest_prices=latest_prices)

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

    