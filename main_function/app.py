from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import re
import os
import uuid
from sqlalchemy import func, desc, and_

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///college_marketplace.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Razorpay configuration (replace with your keys)
app.config['RAZORPAY_KEY_ID'] = 'rzp_test_your_key_id'
app.config['RAZORPAY_KEY_SECRET'] = 'your_secret_key'

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database Models
class College(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    email_domain = db.Column(db.String(50), nullable=False, unique=True)
    users = db.relationship('User', backref='college', lazy=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    phone = db.Column(db.String(15))
    profile_image = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    wallet_balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    products = db.relationship('Product', backref='seller', lazy=True)
    reviews_given = db.relationship('Review', foreign_keys='Review.reviewer_id', backref='reviewer', lazy=True)
    reviews_received = db.relationship('Review', foreign_keys='Review.seller_id', backref='seller_user', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), nullable=False)
    brand = db.Column(db.String(50))
    condition = db.Column(db.String(20), nullable=False)
    original_price = db.Column(db.Float)
    selling_price = db.Column(db.Float, nullable=False)
    commission_rate = db.Column(db.Float, default=0.05)  # 5% default
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_sold = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    images = db.relationship('ProductImage', backref='product', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='product', lazy=True)

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    image_path = db.Column(db.String(200), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SearchLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    search_term = db.Column(db.String(100), nullable=False)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    commission = db.Column(db.Float, nullable=False)
    seller_amount = db.Column(db.Float, nullable=False)
    payment_id = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Helper Functions
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_commission(price, category):
    """Calculate commission based on product category and price"""
    commission_rates = {
        'Books': 0.05,  # 5%
        'Stationary': 0.07,  # 7%
        'Non-Stationary': 0.10  # 10%
    }
    rate = commission_rates.get(category, 0.05)
    return round(price * rate, 2)

def calculate_suggested_price(original_price, condition, brand_tier='medium'):
    """Calculate suggested price based on condition and brand"""
    if not original_price:
        return None
    
    condition_multipliers = {
        'New': 0.95,
        'Like New': 0.85,
        'Good': 0.70,
        'Fair': 0.50,
        'Poor': 0.30
    }
    
    brand_multipliers = {
        'premium': 1.1,
        'medium': 1.0,
        'budget': 0.9
    }
    
    base_price = original_price * condition_multipliers.get(condition, 0.7)
    final_price = base_price * brand_multipliers.get(brand_tier, 1.0)
    
    return round(final_price, 2)

def extract_college_from_email(email):
    """Extract college domain from email"""
    domain = email.split('@')[1].lower()
    return domain

def get_analytics_data(college_id):
    """Get analytics data for dashboard"""
    # Top 5 searched products
    top_searches = db.session.query(
        SearchLog.search_term, 
        func.count(SearchLog.id).label('count')
    ).filter(
        SearchLog.college_id == college_id,
        SearchLog.created_at >= datetime.utcnow() - timedelta(days=30)
    ).group_by(SearchLog.search_term).order_by(desc('count')).limit(5).all()
    
    # Most listed categories
    category_stats = db.session.query(
        Product.category,
        func.count(Product.id).label('count')
    ).join(User).filter(
        User.college_id == college_id,
        Product.created_at >= datetime.utcnow() - timedelta(days=30)
    ).group_by(Product.category).order_by(desc('count')).all()
    
    # Monthly demand (view counts)
    monthly_views = db.session.query(
        Product.category,
        func.sum(Product.view_count).label('total_views')
    ).join(User).filter(
        User.college_id == college_id
    ).group_by(Product.category).order_by(desc('total_views')).all()
    
    return {
        'top_searches': top_searches,
        'category_stats': category_stats,
        'monthly_views': monthly_views
    }

# Routes
@app.route('/')
def index():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return render_template('home.html', user=user, is_admin=user.is_admin if user else False)

@app.route('/search')
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '')
    
    if query:
        # Log search
        search_log = SearchLog(
            user_id=user.id,
            search_term=query,
            college_id=user.college_id
        )
        db.session.add(search_log)
        db.session.commit()
    
    # Build search query
    products_query = Product.query.join(User).filter(
        User.college_id == user.college_id,
        Product.is_sold == False,
        Product.user_id != user.id
    )
    
    if query:
        products_query = products_query.filter(
            db.or_(
                Product.title.contains(query),
                Product.description.contains(query),
                Product.brand.contains(query)
            )
        )
    
    if category:
        products_query = products_query.filter(Product.category == category)
    
    products = products_query.order_by(Product.created_at.desc()).all()
    
    return render_template('search.html', products=products, query=query, category=category, user=user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email'].lower()
        password = request.form['password']
        phone = request.form['phone']
        
        # Validate college email
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(edu|ac\.in)$', email):
            flash('Please use a valid college email address (.edu or .ac.in)')
            return render_template('register.html')
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return render_template('register.html')
        
        # Get or create college
        domain = extract_college_from_email(email)
        college = College.query.filter_by(email_domain=domain).first()
        
        if not college:
            college_name = request.form.get('college_name', domain.split('.')[0].title())
            college = College(name=college_name, email_domain=domain)
            db.session.add(college)
            db.session.commit()
        
        # Create user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            college_id=college.id,
            phone=phone
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    # Get user's reviews received
    reviews = Review.query.filter_by(seller_id=user.id).order_by(Review.created_at.desc()).all()
    
    # Calculate average rating
    avg_rating = db.session.query(func.avg(Review.rating)).filter_by(seller_id=user.id).scalar()
    avg_rating = round(avg_rating, 1) if avg_rating else 0
    
    return render_template('profile.html', user=user, reviews=reviews, avg_rating=avg_rating)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        user.username = request.form['username']
        user.phone = request.form['phone']
        
        # Handle profile image upload
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                user.profile_image = filename
        
        # Handle email change (requires validation)
        new_email = request.form['email'].lower()
        if new_email != user.email:
            if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(edu|ac\.in)$', new_email):
                if not User.query.filter_by(email=new_email).first():
                    user.email = new_email
                else:
                    flash('Email already in use')
                    return render_template('edit_profile.html', user=user)
            else:
                flash('Please use a valid college email')
                return render_template('edit_profile.html', user=user)
        
        db.session.commit()
        flash('Profile updated successfully!')
        return redirect(url_for('profile'))
    
    return render_template('edit_profile.html', user=user)

@app.route('/sell', methods=['GET', 'POST'])
def sell_product():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        brand = request.form['brand']
        condition = request.form['condition']
        original_price = float(request.form['original_price']) if request.form['original_price'] else None
        selling_price = float(request.form['selling_price'])
        
        # Calculate commission
        commission_rate = calculate_commission(selling_price, category) / selling_price
        
        product = Product(
            title=title,
            description=description,
            category=category,
            brand=brand,
            condition=condition,
            original_price=original_price,
            selling_price=selling_price,
            commission_rate=commission_rate,
            user_id=session['user_id']
        )
        
        db.session.add(product)
        db.session.commit()
        
        # Handle image uploads
        uploaded_files = request.files.getlist('images')
        for i, file in enumerate(uploaded_files):
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                
                product_image = ProductImage(
                    product_id=product.id,
                    image_path=filename,
                    is_primary=(i == 0)  # First image is primary
                )
                db.session.add(product_image)
        
        db.session.commit()
        flash('Product listed successfully!')
        return redirect(url_for('index'))
    
    return render_template('sell.html')

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    product = Product.query.get_or_404(product_id)
    user = User.query.get(session['user_id'])
    
    # Check if user is from same college
    if product.seller.college_id != user.college_id:
        flash('You can only view products from your college')
        return redirect(url_for('index'))
    
    # Increment view count
    product.view_count += 1
    db.session.commit()
    
    # Get reviews for this product
    reviews = Review.query.filter_by(product_id=product_id).order_by(Review.created_at.desc()).all()
    
    # Calculate average rating
    avg_rating = db.session.query(func.avg(Review.rating)).filter_by(product_id=product_id).scalar()
    avg_rating = round(avg_rating, 1) if avg_rating else 0
    
    # Calculate commission and final amounts
    commission = calculate_commission(product.selling_price, product.category)
    seller_amount = product.selling_price - commission
    
    return render_template('product_detail.html', 
                         product=product, 
                         reviews=reviews, 
                         avg_rating=avg_rating,
                         commission=commission,
                         seller_amount=seller_amount)

@app.route('/buy_now/<int:product_id>')
def buy_now(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    product = Product.query.get_or_404(product_id)
    user = User.query.get(session['user_id'])
    
    if product.is_sold:
        flash('This product is already sold')
        return redirect(url_for('product_detail', product_id=product_id))
    
    if product.user_id == user.id:
        flash('You cannot buy your own product')
        return redirect(url_for('product_detail', product_id=product_id))
    
    # Calculate amounts
    commission = calculate_commission(product.selling_price, product.category)
    seller_amount = product.selling_price - commission
    
    return render_template('payment.html', 
                         product=product, 
                         commission=commission,
                         seller_amount=seller_amount,
                         razorpay_key=app.config['RAZORPAY_KEY_ID'])

@app.route('/process_payment', methods=['POST'])
def process_payment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    product_id = request.form['product_id']
    payment_id = request.form.get('payment_id')
    
    product = Product.query.get_or_404(product_id)
    user = User.query.get(session['user_id'])
    
    # Calculate amounts
    commission = calculate_commission(product.selling_price, product.category)
    seller_amount = product.selling_price - commission
    
    # Create transaction record
    transaction = Transaction(
        product_id=product.id,
        buyer_id=user.id,
        seller_id=product.user_id,
        amount=product.selling_price,
        commission=commission,
        seller_amount=seller_amount,
        payment_id=payment_id,
        status='completed'
    )
    
    # Update product status
    product.is_sold = True
    
    # Update seller's wallet
    seller = User.query.get(product.user_id)
    seller.wallet_balance += seller_amount
    
    db.session.add(transaction)
    db.session.commit()
    
    flash('Payment successful! Product purchased.')
    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/add_review/<int:product_id>', methods=['POST'])
def add_review(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    product = Product.query.get_or_404(product_id)
    user = User.query.get(session['user_id'])
    
    # Check if user has already reviewed this product
    existing_review = Review.query.filter_by(
        product_id=product_id, 
        reviewer_id=user.id
    ).first()
    
    if existing_review:
        flash('You have already reviewed this product')
        return redirect(url_for('product_detail', product_id=product_id))
    
    rating = int(request.form['rating'])
    comment = request.form['comment']
    
    review = Review(
        product_id=product_id,
        reviewer_id=user.id,
        seller_id=product.user_id,
        rating=rating,
        comment=comment
    )
    
    db.session.add(review)
    db.session.commit()
    
    flash('Review added successfully!')
    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/my_products')
def my_products():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    products = Product.query.filter_by(user_id=session['user_id']).order_by(Product.created_at.desc()).all()
    return render_template('my_products.html', products=products)

@app.route('/analytics')
def analytics():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    analytics_data = get_analytics_data(user.college_id)
    
    return render_template('analytics.html', analytics=analytics_data, user=user)

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    # Get admin statistics
    total_users = User.query.count()
    total_products = Product.query.count()
    total_transactions = Transaction.query.filter_by(status='completed').count()
    total_commission = db.session.query(func.sum(Transaction.commission)).filter_by(status='completed').scalar() or 0
    
    # Recent transactions
    recent_transactions = Transaction.query.filter_by(status='completed').order_by(Transaction.created_at.desc()).limit(10).all()
    
    return render_template('admin.html', 
                         total_users=total_users,
                         total_products=total_products,
                         total_transactions=total_transactions,
                         total_commission=total_commission,
                         recent_transactions=recent_transactions)

@app.route('/toggle_featured/<int:product_id>')
def toggle_featured(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    product = Product.query.get_or_404(product_id)
    product.is_featured = not product.is_featured
    db.session.commit()
    
    status = 'featured' if product.is_featured else 'unfeatured'
    flash(f'Product {status} successfully!')
    return redirect(url_for('admin_dashboard'))

# API Routes
@app.route('/calculate_price', methods=['POST'])
def calculate_price():
    """API endpoint to calculate suggested price"""
    data = request.get_json()
    original_price = data.get('original_price')
    condition = data.get('condition')
    brand_tier = data.get('brand_tier', 'medium')
    
    if original_price:
        suggested_price = calculate_suggested_price(float(original_price), condition, brand_tier)
        return jsonify({'suggested_price': suggested_price})
    
    return jsonify({'error': 'Invalid data'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Add some sample colleges if none exist
        if not College.query.first():
            colleges = [
                College(name='MIT', email_domain='mit.edu'),
                College(name='Stanford University', email_domain='stanford.edu'),
                College(name='IIT Delhi', email_domain='iitd.ac.in'),
                College(name='IIT Bombay', email_domain='iitb.ac.in'),
                College(name='IIIT nagpur', email_domain='iiitn.ac.in'),

            ]
            for college in colleges:
                db.session.add(college)
            
            # Create admin user
            admin_user = User(
                username='admin',
                email='admin@mit.edu',
                password_hash=generate_password_hash('admin123'),
                college_id=1,
                is_admin=True
            )
            db.session.add(admin_user)
            db.session.commit()
    
    app.run(debug=True)
