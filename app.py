# app.py - Mahalakshmi Stores - Complete Grocery Shop Application

from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import random
import json

app = Flask(__name__)
app.secret_key = 'mahalakshmi_super_secret_key_2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mahalakshmi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.permanent_session_lifetime = timedelta(days=7)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

# ==================== DATABASE MODELS ====================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    address = db.Column(db.String(500))
    role = db.Column(db.String(20), default='customer')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float)
    unit = db.Column(db.String(20), default='kg')
    image_url = db.Column(db.String(500))
    stock = db.Column(db.Integer, default=100)
    discount = db.Column(db.Integer, default=0)
    offer_tag = db.Column(db.String(100))
    is_featured = db.Column(db.Boolean, default=False)
    is_bogo = db.Column(db.Boolean, default=False)

class Cart(db.Model):
    __tablename__ = 'cart'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    customer_name = db.Column(db.String(100))
    customer_email = db.Column(db.String(120))
    customer_phone = db.Column(db.String(15))
    delivery_address = db.Column(db.String(500))
    items = db.Column(db.Text)
    subtotal = db.Column(db.Float)
    discount_amount = db.Column(db.Float, default=0)
    delivery_charge = db.Column(db.Float, default=0)
    total = db.Column(db.Float)
    payment_method = db.Column(db.String(50))
    payment_status = db.Column(db.String(50), default='pending')
    order_status = db.Column(db.String(50), default='confirmed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied!', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def generate_order_number():
    return f"MAHA{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

def get_cart():
    if current_user.is_authenticated:
        cart_items = Cart.query.filter_by(user_id=current_user.id).all()
        cart = {}
        for item in cart_items:
            product = Product.query.get(item.product_id)
            if product:
                cart[str(item.product_id)] = {
                    'name': product.name,
                    'price': product.price,
                    'quantity': item.quantity,
                    'image_url': product.image_url,
                    'unit': product.unit,
                    'is_bogo': product.is_bogo
                }
        return cart
    return session.get('cart', {})

def save_cart(cart):
    if current_user.is_authenticated:
        Cart.query.filter_by(user_id=current_user.id).delete()
        for product_id, item in cart.items():
            cart_item = Cart(user_id=current_user.id, product_id=int(product_id), quantity=item['quantity'])
            db.session.add(cart_item)
        db.session.commit()
    else:
        session['cart'] = cart

def calculate_cart_total(cart):
    subtotal = 0
    bogo_savings = 0
    for pid, item in cart.items():
        product = Product.query.get(int(pid))
        if product:
            if item.get('is_bogo', False):
                free_items = item['quantity'] // 2
                paid_items = item['quantity'] - free_items
                subtotal += product.price * paid_items
                bogo_savings += product.price * free_items
            else:
                subtotal += product.price * item['quantity']
    
    discount_amount = 0
    if subtotal >= 1000:
        discount_amount = subtotal * 0.10
    elif subtotal >= 500:
        discount_amount = subtotal * 0.05
    
    delivery_charge = 0 if subtotal >= 100 else 40
    total = subtotal - discount_amount + delivery_charge
    
    return subtotal, discount_amount, delivery_charge, total, bogo_savings

# ==================== INITIAL DATA ====================

def init_data():
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        # Create Admin
        admin = User(username='admin', email='admin@mahalakshmi.com', phone='9999999999', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        
        # Create Demo Customer
        customer = User(username='customer', email='customer@mahalakshmi.com', phone='8888888888', role='customer')
        customer.set_password('customer123')
        db.session.add(customer)
        db.session.commit()
        
        # All Products
        products = [
            # VEGETABLES
            ('Fresh Potatoes', 'vegetables', 40, 55, 'kg', 'https://m.media-amazon.com/images/I/41QKCkQ2A5L.jpg', 15, 'Fresh Harvest', True, False),
            ('Red Onions', 'vegetables', 35, 50, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR_c4mzTsqYoLWHNziM4mHQEEp6-qCek6H7bQ&s', 20, 'Big Size', True, False),
            ('Ripe Tomatoes', 'vegetables', 45, 60, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQBjOIXABq8vIUuH-6s5LTDadGcb0K_FjlxBA&s', 10, 'Farm Fresh', True, False),
            ('Fresh Ginger', 'vegetables', 80, 110, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSyLoPpyrsG9q0sxEiJTyGBh35fLCu721dAvg&s', 15, 'Organic', True, False),
            ('Fresh Garlic', 'vegetables', 200, 260, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ7cWLZUvaUOMNXnMcDp20vUsLogSr_8LqtYg&s', 15, 'Premium', True, False),
            ('Coconut', 'vegetables', 45, 60, 'piece', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTYaLOCjyabXT2IT0MdbKr4_d_kqARuIPlKgA&s', 15, 'Fresh', True, False),
            ('Green Capsicum', 'vegetables', 60, 80, 'kg', 'https://fpsstore.in/cdn/shop/products/Capsicum-750x750_1.jpg', 25, 'Crispy', True, False),
            ('Fresh Carrots', 'vegetables', 50, 70, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcT11cHXpvlzv3zBhbMMcqx22xk4yB5pu4TrdQ&s', 15, 'Organic', True, False),
            ('Brinjal', 'vegetables', 35, 50, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQErdxtZ50sAmQ4rMvS2i8L9TWoyW0s3JE_5Q&s', 15, 'Purple', True, False),
            ('Cabbage', 'vegetables', 30, 45, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSv16mQSx3cF7qBs4FbJKowZc0BnvzdtAtFfQ&s', 20, 'Crispy', True, False),
            ('Cauliflower', 'vegetables', 40, 60, 'piece', 'https://m.media-amazon.com/images/I/91EdPVzD99L.jpg', 20, 'Fresh', True, False),
            ('Ladyfinger', 'vegetables', 50, 70, 'kg', 'https://kazeliving.com/cdn/shop/files/e1e15e94-e122-44df-bcec-1a7cff43da4b_7eb629e7-699e-4f67-b664-40196cb4ddc9.jpg', 20, 'Tender', True, False),
            ('Spinach', 'vegetables', 25, 40, 'bunch', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSviTOW8Si4rzlD-SXL5QYo8HtxsKi2bwXFAw&s', 25, 'Leafy Green', True, False),
            ('Beetroot', 'vegetables', 45, 60, 'kg', 'https://www.oifood.in/files/products/c401b43a628d3c11ef07a5ba08a766ab.jpg', 15, 'Fresh', True, False),
            ('Pumpkin', 'vegetables', 35, 50, 'kg', 'https://m.media-amazon.com/images/I/41ihR4-LqeL._AC_UF1000,1000_QL80_.jpg', 15, 'Sweet', True, False),
            ('Bottle Gourd', 'vegetables', 35, 50, 'kg', 'https://www.jiomart.com/images/product/original/rvxnx2wl4x/paryavaraan-bottle-gourd-long-vegetable-seeds-for-summer-season-home-gardening-pack-of-15-seeds-by-paryavaraan-product-images-orvxnx2wl4x-p606511284-0-202312041927.jpg', 15, 'Healthy', True, False),
            ('Bitter Gourd', 'vegetables', 45, 65, 'kg', 'https://www.greendna.in/cdn/shop/products/bg_650x.jpg', 20, 'Organic', True, False),
            ('Ridge Gourd', 'vegetables', 40, 55, 'kg', 'https://www.jiomart.com/images/product/original/590000178/turai-ridge-gourd-500-g-product-images-o590000178-p590000178-0-202410011802.jpg', 15, 'Fresh', True, False),
            ('Drumstick', 'vegetables', 60, 80, 'kg', 'https://m.media-amazon.com/images/I/61Oa2hI3wqL._AC_UF1000,1000_QL80_.jpg', 20, 'Organic', True, False),
            ('Snake Gourd', 'vegetables', 45, 60, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ165RrSobdCOCUnhtJWT_jcg-DROeTTPS09Q&s', 15, 'Fresh', True, False),
            ('Ash Gourd', 'vegetables', 30, 45, 'kg', 'https://freshbinge.com/wp-content/uploads/2025/08/Ash-Gourd-WS-1WP.webp', 20, 'Fresh', True, False),
            ('Cluster Beans', 'vegetables', 50, 65, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSoRQWql9MJW8WNQyx4dF74NaoGxhHLUyywSA&s', 15, 'Fresh', True, False),
            ('Broad Beans', 'vegetables', 55, 70, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQPg9-2-0GfoyplBV5S50H1IGQW4m-b4y58pg&s', 15, 'Fresh', True, False),
            ('Raw Banana', 'vegetables', 35, 50, 'kg', 'https://www.orgpick.com/cdn/shop/products/banana.jpg', 20, 'Fresh', True, False),
            ('Raw Papaya', 'vegetables', 40, 55, 'kg', 'https://www.bbassets.com/media/uploads/p/xl/40047629_8-fresho-papaya-raw-organically-grown.jpg', 15, 'Green', True, False),
            ('Jackfruit', 'vegetables', 80, 110, 'kg', 'https://maatarafruitscompany.com/wp-content/uploads/2022/12/ab281eae-acf3-4b4d-9520-9c9c82e0195f.jpg', 20, 'Fresh', True, False),
            ('Turnip', 'vegetables', 35, 50, 'kg', 'https://www.earthytales.in/uploads/products/3x/turnip.png', 15, 'Fresh', True, False),
            ('Radish', 'vegetables', 35, 50, 'kg', 'https://beejwala.com/cdn/shop/products/radish-3_compressed.jpg', 15, 'Crispy', True, False),
            ('Sweet Corn', 'vegetables', 50, 70, 'kg', 'https://lh5.googleusercontent.com/proxy/GbS8Sytqrirx0cVt9MZ0HQSVIGsQzbMk_XlBZf4flasKXCroXph2WEwbwaL299pz9KeKdA4nT4Ns1tpZSNzTdYH3pGiJubqiQTlqNcYRO5zuvK3pK3DA8q09_nnvl1oqyd0Ayn1N_lVTD0PvM1fn1pEsxAeNJQ', 20, 'Sweet', True, False),
            ('Green Peas', 'vegetables', 60, 80, 'kg', 'https://onlyhydroponics.in/cdn/shop/products/green-peas-320.jpg', 20, 'Fresh Frozen', True, False),
            ('French Beans', 'vegetables', 55, 75, 'kg', 'https://www.jiomart.com/images/product/original/590003549/french-beans-500-g-product-images-o590003549-p590003549-0-202411061150.jpg', 15, 'Tender', True, False),
            
            # SPICES & MASALA
            ('Salt', 'masala', 20, 30, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQsux3jqvc-1q5syPLyqjcIrgTp37N2LRDSBw&s', 15, 'Iodized', True, False),
            ('Sugar', 'masala', 45, 60, 'kg', 'https://www.trivenigroup.com/triveni-sugar/images/white-sugar-img1.webp', 15, 'Pure', True, False),
            ('Turmeric Powder', 'masala', 80, 110, '500g', 'https://aachifoods.com/cdn/shop/files/turmeric-powder-200g.webp', 20, 'Organic', True, False),
            ('Red Chili Powder', 'masala', 120, 160, '500g', 'https://m.media-amazon.com/images/I/71R2cgmPBgL._AC_UF894,1000_QL80_.jpg', 20, 'Spicy', True, False),
            ('Coriander Powder', 'masala', 90, 120, '500g', 'https://m.media-amazon.com/images/I/7177FWzjFiL.jpg', 20, 'Pure', True, False),
            ('Garam Masala', 'masala', 150, 200, '500g', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSSiQ-5IG_YEhu8M_M7JXqV4yv-f7Rf-ZygoQ&s', 20, 'Aromatic', True, False),
            ('Cumin Seeds', 'masala', 120, 160, '500g', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTnVriOYiylS_ZqbRngEh9USE5Idr2kSIX99A&s', 20, 'Premium', True, False),
            ('Mustard Seeds', 'masala', 80, 110, '500g', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQqu5KwP3ek0KqRUuzXWoRRjABbsxM5m2wZyg&s', 15, 'Brown', True, False),
            ('Fennel Seeds', 'masala', 100, 130, '500g', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ2iUvmw_gQlMqGgsEHjlXOuTDWKNbyaaqS-g&s', 15, 'Sweet', True, False),
            ('Fenugreek Seeds', 'masala', 70, 95, '500g', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRV8TsFH0GglBpKw2SyxEL0Kn1x2_elvvMyvg&s', 15, 'Organic', True, False),
            ('Hing', 'masala', 180, 240, '250g', 'https://www.greendna.in/cdn/shop/files/hing1_959x.webp', 15, 'Pure', True, False),
            ('Cloves', 'masala', 250, 320, '250g', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQJnWVya8zHy7ocI3P2nFyxDETwA45o6OCGsg&s', 20, 'Aromatic', True, False),
            ('Black Pepper', 'masala', 200, 260, '500g', 'https://m.media-amazon.com/images/I/61bv6tKoW8L._AC_UF894,1000_QL80_.jpg', 20, 'Whole', True, False),
            ('Green Cardamom', 'masala', 400, 520, '250g', 'https://navvayd.com/cdn/shop/files/ChatGPTImageSep10_2025_06_15_35PM.png', 20, 'Premium', True, False),
            ('Cinnamon', 'masala', 180, 240, '500g', 'https://m.media-amazon.com/images/I/51QdNxD69wL.jpg', 15, 'Dalchini', True, False),
            ('Bay Leaf', 'masala', 150, 200, '100g', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQfjFYN1uqr9-9o09pzM7WT7Np19t6FtY4Klg&s', 15, 'Tej Patta', True, False),
            ('Star Anise', 'masala', 280, 360, '250g', 'https://5.imimg.com/data5/SELLER/Default/2020/9/ZY/FB/RC/40990596/star-anise-500x500-500x500.jpg', 15, 'Chakra Phool', True, False),
            ('Chaat Masala', 'masala', 85, 110, '500g', 'https://m.media-amazon.com/images/I/615wFPgPWHL._AC_UF894,1000_QL80_.jpg', 15, 'Tangy', True, False),
            ('Amchur Powder', 'masala', 95, 120, '500g', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRIxzLGJz1VZ92qKS5L8_VZ4rtZLf_oW6PXjA&s', 15, 'Dry Mango', True, False),
            
            # OILS with BOGO offer
            ('Sunflower Oil', 'oils', 110, 140, 'litre', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTadQaYf32piixIjn6yxUuHWFKw8PV6V8nZYQ&s', 15, 'Buy 1 Get 1 Free', True, True),
            ('Soybean Oil', 'oils', 100, 130, 'litre', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRv-3YaGTO_7OuBM9enEEteD57tzDf9gOQp-w&s', 15, 'Healthy', True, False),
            ('Rice Bran Oil', 'oils', 120, 155, 'litre', 'https://m.media-amazon.com/images/I/61Jb7TOqaeL.jpg', 15, 'Heart Healthy', True, False),
            ('Coconut Oil', 'oils', 180, 230, 'litre', 'https://images.unsplash.com/photo-1601050690597-df0568f70950', 15, 'Pure Cold Pressed', True, False),
            
            # PICKLES
            ('Mango Pickle', 'pickles', 120, 160, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTStKVpjMQ_nPeOTEF39g6MLTjvsRWG7cZN1g&s', 20, 'Aam Ka Achar', True, False),
            ('Lemon Pickle', 'pickles', 110, 145, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSBzwzR2hFsu5-a8_XgSOMH0OmaHPbOvFsFhA&s', 15, 'Nimbu Achar', True, False),
            ('Mixed Pickle', 'pickles', 130, 170, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSywyW85xFnRVneAyJeoE54F0xyJUcNkvsHWg&s', 15, 'Mix Achar', True, False),
            ('Garlic Pickle', 'pickles', 140, 180, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQfGPSPPXrBwB6VcReC6ApCVLtK9aooWpiUvA&s', 15, 'Lasun Achar', True, False),
            ('Green Chili Pickle', 'pickles', 130, 165, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQIMxyNDSdHtd6aG4liS8MwOMatpG7zqU_Nlw&s', 15, 'Hari Mirch', True, False),
            ('Red Chili Pickle', 'pickles', 140, 180, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRNn_BolT8DhkkJQB6CbDvsAbv5yuah9a5bgA&s', 15, 'Lal Mirch', True, False),
            ('Tamarind Pickle', 'pickles', 120, 155, 'kg', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRRaT6UZBFd7ngHRVaR36R7zlyHS-b4SfHqRg&s', 15, 'Imli Achar', True, False),
            ('Amla Pickle', 'pickles', 150, 195, 'kg', 'https://www.naturestrunk.com/cdn/shop/files/Traditional_Amla_Pickle_Indian_Gooseberry_Pickle_394x.jpg', 15, 'Gooseberry', True, False),
        ]
        
        for p in products:
            product = Product(
                name=p[0], category=p[1], price=p[2], original_price=p[3],
                unit=p[4], image_url=p[5], stock=100, discount=p[6],
                offer_tag=p[7], is_featured=p[8], is_bogo=p[9]
            )
            db.session.add(product)
        
        db.session.commit()
        print(f"✅ Added {len(products)} products!")
        print("👑 Admin: admin@mahalakshmi.com / admin123")
        print("👤 Customer: customer@mahalakshmi.com / customer123")

# ==================== ROUTES ====================

@app.route('/')
def splash():
    return render_template_string(SPLASH_TEMPLATE)

@app.route('/welcome')
def welcome():
    return render_template_string(WELCOME_TEMPLATE)

@app.route('/login-page')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    user = User.query.filter_by(email=email).first()
    
    if user and user.check_password(password):
        login_user(user)
        if user.role == 'admin':
            return jsonify({'success': True, 'redirect': url_for('admin_dashboard')})
        return jsonify({'success': True, 'redirect': url_for('index')})
    return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/signup-page')
def signup_page():
    return render_template_string(SIGNUP_TEMPLATE)

@app.route('/signup', methods=['POST'])
def signup():
    username = request.form.get('username')
    email = request.form.get('email')
    phone = request.form.get('phone')
    password = request.form.get('password')
    address = request.form.get('address', '')
    
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email already registered'})
    
    user = User(username=username, email=email, phone=phone, address=address, role='customer')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Registration successful!'})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return jsonify({'success': True, 'redirect': url_for('welcome')})

@app.route('/index')
@login_required
def index():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    products = Product.query.all()
    cart = get_cart()
    cart_count = sum(item['quantity'] for item in cart.values())
    
    categories = ['vegetables', 'masala', 'oils', 'pickles']
    products_by_category = {}
    for cat in categories:
        products_by_category[cat] = [p for p in products if p.category == cat]
    
    featured_products = [p for p in products if p.is_featured][:12]
    bogo_products = [p for p in products if p.is_bogo]
    
    return render_template_string(HOME_TEMPLATE, 
                                  products_by_category=products_by_category,
                                  featured_products=featured_products,
                                  bogo_products=bogo_products,
                                  cart_count=cart_count,
                                  categories=categories)

@app.route('/add-to-cart', methods=['POST'])
@login_required
def add_to_cart():
    product_id = str(request.form.get('product_id'))
    quantity = int(request.form.get('quantity', 1))
    
    cart = get_cart()
    if product_id in cart:
        cart[product_id]['quantity'] += quantity
    else:
        product = Product.query.get(int(product_id))
        cart[product_id] = {
            'name': product.name,
            'price': product.price,
            'quantity': quantity,
            'image_url': product.image_url,
            'unit': product.unit,
            'is_bogo': product.is_bogo
        }
    
    save_cart(cart)
    subtotal, discount_amt, delivery, total, bogo_savings = calculate_cart_total(cart)
    cart_count = sum(item['quantity'] for item in cart.values())
    
    return jsonify({
        'success': True,
        'cart_count': cart_count,
        'subtotal': subtotal,
        'discount': discount_amt,
        'delivery': delivery,
        'total': total,
        'bogo_savings': bogo_savings
    })

@app.route('/update-cart', methods=['POST'])
@login_required
def update_cart():
    product_id = str(request.form.get('product_id'))
    quantity = int(request.form.get('quantity'))
    
    cart = get_cart()
    if quantity <= 0:
        cart.pop(product_id, None)
    else:
        if product_id in cart:
            cart[product_id]['quantity'] = quantity
    
    save_cart(cart)
    subtotal, discount_amt, delivery, total, bogo_savings = calculate_cart_total(cart)
    cart_count = sum(item['quantity'] for item in cart.values())
    
    return jsonify({
        'success': True,
        'cart_count': cart_count,
        'subtotal': subtotal,
        'discount': discount_amt,
        'delivery': delivery,
        'total': total,
        'bogo_savings': bogo_savings
    })

@app.route('/get-cart')
@login_required
def get_cart_json():
    cart = get_cart()
    cart_items = []
    for pid, item in cart.items():
        product = Product.query.get(int(pid))
        if product:
            cart_items.append({
                'id': pid,
                'name': item['name'],
                'price': item['price'],
                'quantity': item['quantity'],
                'total': item['price'] * item['quantity'],
                'image_url': item['image_url'],
                'unit': item['unit'],
                'is_bogo': item.get('is_bogo', False)
            })
    
    subtotal, discount_amt, delivery, total, bogo_savings = calculate_cart_total(cart)
    return jsonify({
        'items': cart_items,
        'subtotal': subtotal,
        'discount': discount_amt,
        'delivery': delivery,
        'total': total,
        'bogo_savings': bogo_savings,
        'count': sum(item['quantity'] for item in cart.values())
    })

@app.route('/checkout')
@login_required
def checkout():
    return render_template_string(CHECKOUT_TEMPLATE)

@app.route('/place-order', methods=['POST'])
@login_required
def place_order():
    cart = get_cart()
    if not cart:
        return jsonify({'success': False, 'message': 'Cart is empty'})
    
    name = request.form.get('name')
    phone = request.form.get('phone')
    address = request.form.get('address')
    payment_method = request.form.get('payment_method')
    
    subtotal, discount_amt, delivery, total, bogo_savings = calculate_cart_total(cart)
    order_number = generate_order_number()
    items_json = json.dumps(cart)
    
    order = Order(
        order_number=order_number,
        user_id=current_user.id,
        customer_name=name,
        customer_email=current_user.email,
        customer_phone=phone,
        delivery_address=address,
        items=items_json,
        subtotal=subtotal,
        discount_amount=discount_amt,
        delivery_charge=delivery,
        total=total,
        payment_method=payment_method,
        payment_status='pending',
        order_status='confirmed'
    )
    db.session.add(order)
    db.session.commit()
    
    # Clear cart
    if current_user.is_authenticated:
        Cart.query.filter_by(user_id=current_user.id).delete()
    else:
        session['cart'] = {}
    db.session.commit()
    
    return jsonify({'success': True, 'redirect': url_for('order_success', order_id=order.id)})

@app.route('/order-success/<int:order_id>')
@login_required
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template_string(ORDER_SUCCESS_TEMPLATE, order=order)

@app.route('/my-orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template_string(MY_ORDERS_TEMPLATE, orders=orders)

@app.route('/track-order/<int:order_id>')
@login_required
def track_order(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template_string(TRACK_ORDER_TEMPLATE, order=order)

# ==================== ADMIN ROUTES ====================

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_users = User.query.filter_by(role='customer').count()
    total_products = Product.query.count()
    total_orders = Order.query.count()
    total_revenue = db.session.query(db.func.sum(Order.total)).scalar() or 0
    pending_orders = Order.query.filter_by(order_status='confirmed').count()
    
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    products = Product.query.all()
    
    return render_template_string(ADMIN_TEMPLATE,
                                  total_users=total_users,
                                  total_products=total_products,
                                  total_orders=total_orders,
                                  total_revenue=total_revenue,
                                  pending_orders=pending_orders,
                                  recent_orders=recent_orders,
                                  products=products,
                                  active_page='dashboard')

@app.route('/admin/add-product', methods=['POST'])
@login_required
@admin_required
def admin_add_product():
    product = Product(
        name=request.form.get('name'),
        category=request.form.get('category'),
        price=float(request.form.get('price')),
        original_price=float(request.form.get('original_price', 0)),
        unit=request.form.get('unit'),
        image_url=request.form.get('image_url'),
        stock=int(request.form.get('stock')),
        discount=int(request.form.get('discount', 0)),
        offer_tag=request.form.get('offer_tag'),
        is_featured=request.form.get('is_featured') == 'on',
        is_bogo=request.form.get('is_bogo') == 'on'
    )
    db.session.add(product)
    db.session.commit()
    flash('Product added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit-product/<int:pid>', methods=['POST'])
@login_required
@admin_required
def admin_edit_product(pid):
    product = Product.query.get_or_404(pid)
    product.name = request.form.get('name')
    product.category = request.form.get('category')
    product.price = float(request.form.get('price'))
    product.original_price = float(request.form.get('original_price', 0))
    product.unit = request.form.get('unit')
    product.image_url = request.form.get('image_url')
    product.stock = int(request.form.get('stock'))
    product.discount = int(request.form.get('discount', 0))
    product.offer_tag = request.form.get('offer_tag')
    product.is_featured = request.form.get('is_featured') == 'on'
    product.is_bogo = request.form.get('is_bogo') == 'on'
    db.session.commit()
    flash('Product updated!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-product/<int:pid>')
@login_required
@admin_required
def admin_delete_product(pid):
    product = Product.query.get_or_404(pid)
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-order/<int:oid>', methods=['POST'])
@login_required
@admin_required
def admin_update_order(oid):
    order = Order.query.get_or_404(oid)
    order.order_status = request.form.get('status')
    order.payment_status = request.form.get('payment_status')
    db.session.commit()
    flash('Order updated!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template_string(ADMIN_USERS_TEMPLATE, users=users)

@app.route('/admin/toggle-user/<int:uid>')
@login_required
@admin_required
def admin_toggle_user(uid):
    user = User.query.get_or_404(uid)
    user.is_active = not user.is_active
    db.session.commit()
    flash(f'User {user.username} {"activated" if user.is_active else "deactivated"}!', 'success')
    return redirect(url_for('admin_users'))

# ==================== TEMPLATES ====================

SPLASH_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mahalakshmi Stores</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }
        .splash-screen { text-align: center; animation: fadeInUp 1s ease; }
        .logo { font-size: 5rem; margin-bottom: 20px; animation: bounce 1s ease infinite; }
        .title { font-size: 2.5rem; color: white; margin-bottom: 10px; letter-spacing: 2px; }
        .subtitle { font-size: 1rem; color: rgba(255,255,255,0.8); margin-bottom: 30px; }
        .loader { width: 50px; height: 50px; border: 3px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: white; animation: spin 1s ease-in-out infinite; margin: 20px auto; }
        .loading-text { color: white; margin-top: 20px; font-size: 0.9rem; }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="splash-screen">
        <div class="logo">🛒</div>
        <div class="title">Mahalakshmi Stores</div>
        <div class="subtitle">Fresh Groceries Delivered to Your Doorstep</div>
        <div class="loader"></div>
        <div class="loading-text">Loading your grocery store...</div>
    </div>
    <script> setTimeout(() => { window.location.href = '/welcome'; }, 2500); </script>
</body>
</html>
'''

WELCOME_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome - Mahalakshmi Stores</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .welcome-container {
            background: white;
            border-radius: 30px;
            padding: 50px;
            max-width: 550px;
            width: 90%;
            text-align: center;
            box-shadow: 0 25px 50px rgba(0,0,0,0.3);
            animation: fadeInUp 0.8s ease;
        }
        .logo { font-size: 4rem; margin-bottom: 20px; }
        h1 { color: #333; margin-bottom: 10px; }
        p { color: #666; margin-bottom: 30px; }
        .btn-group { display: flex; gap: 15px; justify-content: center; flex-wrap: wrap; }
        .btn {
            padding: 12px 30px;
            border: none;
            border-radius: 50px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.3s;
            text-decoration: none;
            display: inline-block;
        }
        .btn-login { background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); color: white; }
        .btn-signup { background: #27ae60; color: white; }
        .btn:hover { transform: translateY(-3px); box-shadow: 0 10px 20px rgba(0,0,0,0.2); }
        .features { margin-top: 30px; display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; }
        .feature { text-align: center; font-size: 0.8rem; color: #666; }
        .feature span { font-size: 1.5rem; display: block; margin-bottom: 5px; }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <div class="welcome-container">
        <div class="logo">🛒🍅🌶️</div>
        <h1>Welcome to Mahalakshmi Stores!</h1>
        <p>Your one-stop shop for fresh vegetables, spices, oils, pickles and more!</p>
        <div class="btn-group">
            <a href="/login-page" class="btn btn-login">Login</a>
            <a href="/signup-page" class="btn btn-signup">Sign Up</a>
        </div>
        <div class="features">
            <div class="feature"><span>🚚</span> Free Delivery<br>above ₹100</div>
            <div class="feature"><span>🔄</span> Easy Returns<br>30 days policy</div>
            <div class="feature"><span>⭐</span> Fresh &<br>Quality Products</div>
            <div class="feature"><span>💳</span> Secure<br>Payments</div>
            <div class="feature"><span>🎁</span> Buy 1 Get 1<br>On Select Items</div>
        </div>
    </div>
</body>
</html>
'''

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Mahalakshmi Stores</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            background: white;
            border-radius: 30px;
            padding: 40px;
            width: 100%;
            max-width: 400px;
            margin: 20px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.3);
            animation: fadeInUp 0.6s ease;
        }
        .logo { text-align: center; font-size: 3rem; margin-bottom: 20px; }
        h2 { text-align: center; color: #333; margin-bottom: 10px; }
        .subtitle { text-align: center; color: #666; margin-bottom: 30px; font-size: 0.9rem; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: 500; color: #555; }
        input {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            font-size: 1rem;
            transition: all 0.3s;
        }
        input:focus { outline: none; border-color: #e74c3c; box-shadow: 0 0 0 3px rgba(231,76,60,0.1); }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.3s;
        }
        button:hover { transform: translateY(-2px); }
        .signup-link { text-align: center; margin-top: 20px; }
        .signup-link a { color: #e74c3c; text-decoration: none; }
        .error-message { color: #e74c3c; text-align: center; margin-bottom: 15px; font-size: 0.9rem; }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">🛒</div>
        <h2>Welcome Back!</h2>
        <div class="subtitle">Login to your Mahalakshmi Stores account</div>
        <div id="errorMsg" class="error-message"></div>
        <form id="loginForm">
            <div class="form-group"><label>Email Address</label><input type="email" id="email" required placeholder="Enter your email"></div>
            <div class="form-group"><label>Password</label><input type="password" id="password" required placeholder="Enter your password"></div>
            <button type="submit">Login →</button>
        </form>
        <div class="signup-link">Don't have an account? <a href="/signup-page">Sign up here</a></div>
        <div class="signup-link"><small>Demo: customer@mahalakshmi.com / customer123</small></div>
    </div>
    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const response = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'email=' + encodeURIComponent(document.getElementById('email').value) + '&password=' + encodeURIComponent(document.getElementById('password').value)
            });
            const data = await response.json();
            if (data.success) { window.location.href = data.redirect; }
            else { document.getElementById('errorMsg').innerText = data.message; }
        });
    </script>
</body>
</html>
'''

SIGNUP_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign Up - Mahalakshmi Stores</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .signup-container {
            background: white;
            border-radius: 30px;
            padding: 40px;
            width: 100%;
            max-width: 500px;
            margin: 20px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.3);
            animation: fadeInUp 0.6s ease;
        }
        .logo { text-align: center; font-size: 3rem; margin-bottom: 20px; }
        h2 { text-align: center; color: #333; margin-bottom: 10px; }
        .subtitle { text-align: center; color: #666; margin-bottom: 30px; font-size: 0.9rem; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: 500; color: #555; }
        input, textarea {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            font-size: 1rem;
            transition: all 0.3s;
        }
        textarea { resize: vertical; font-family: inherit; }
        input:focus, textarea:focus { outline: none; border-color: #27ae60; }
        button {
            width: 100%;
            padding: 14px;
            background: #27ae60;
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.3s;
        }
        button:hover { transform: translateY(-2px); }
        .login-link { text-align: center; margin-top: 20px; }
        .login-link a { color: #27ae60; text-decoration: none; }
        .error-message { color: #e74c3c; text-align: center; margin-bottom: 15px; font-size: 0.9rem; }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <div class="signup-container">
        <div class="logo">🛒</div>
        <h2>Create Account</h2>
        <div class="subtitle">Join Mahalakshmi Stores for fresh groceries</div>
        <div id="errorMsg" class="error-message"></div>
        <form id="signupForm">
            <div class="form-group"><label>Username</label><input type="text" id="username" required placeholder="Choose a username"></div>
            <div class="form-group"><label>Email Address</label><input type="email" id="email" required placeholder="Enter your email"></div>
            <div class="form-group"><label>Phone Number</label><input type="tel" id="phone" required placeholder="Enter your phone number"></div>
            <div class="form-group"><label>Delivery Address</label><textarea id="address" rows="2" placeholder="Enter your full address"></textarea></div>
            <div class="form-group"><label>Password</label><input type="password" id="password" required placeholder="Create a password (min 6 characters)"></div>
            <button type="submit">Create Account →</button>
        </form>
        <div class="login-link">Already have an account? <a href="/login-page">Login here</a></div>
    </div>
    <script>
        document.getElementById('signupForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const response = await fetch('/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'username=' + encodeURIComponent(document.getElementById('username').value) + '&email=' + encodeURIComponent(document.getElementById('email').value) + '&phone=' + encodeURIComponent(document.getElementById('phone').value) + '&password=' + encodeURIComponent(document.getElementById('password').value) + '&address=' + encodeURIComponent(document.getElementById('address').value)
            });
            const data = await response.json();
            if (data.success) { alert(data.message); window.location.href = '/login-page'; }
            else { document.getElementById('errorMsg').innerText = data.message; }
        });
    </script>
</body>
</html>
'''
HOME_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mahalakshmi Stores - Fresh Grocery Delivery</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8f9fa; }
        
        .header { background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); color: white; padding: 15px 20px; position: sticky; top: 0; z-index: 1000; box-shadow: 0 2px 15px rgba(0,0,0,0.1); }
        .header-content { max-width: 1400px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; }
        .logo { font-size: 1.5rem; font-weight: bold; cursor: pointer; display: flex; align-items: center; gap: 10px; }
        .logo span { font-size: 2rem; }
        
        /* Premium Hero Banner with Beautiful Background Image */
        .hero-banner {
            width: 100%;
            height: 600px;
            position: relative;
            background: linear-gradient(135deg, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.4) 100%), url('https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=1600');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        
        /* Animated Overlay Effect */
        .hero-banner::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            animation: shine 8s infinite;
        }
        
        @keyframes shine {
            0% { left: -100%; }
            20% { left: 100%; }
            100% { left: 100%; }
        }
        
        /* Floating Elements */
        .floating-elements {
            position: absolute;
            width: 100%;
            height: 100%;
            pointer-events: none;
        }
        
        .float-item {
            position: absolute;
            font-size: 3rem;
            filter: drop-shadow(0 5px 15px rgba(0,0,0,0.3));
            animation: floatSlow 15s ease-in-out infinite;
            opacity: 0.7;
        }
        
        .float-item:nth-child(1) { top: 15%; left: 5%; animation-delay: 0s; }
        .float-item:nth-child(2) { top: 70%; left: 8%; animation-delay: 2s; }
        .float-item:nth-child(3) { top: 25%; right: 5%; animation-delay: 4s; }
        .float-item:nth-child(4) { bottom: 20%; right: 10%; animation-delay: 1s; }
        .float-item:nth-child(5) { top: 50%; left: 15%; animation-delay: 3s; }
        .float-item:nth-child(6) { bottom: 40%; right: 20%; animation-delay: 5s; }
        
        @keyframes floatSlow {
            0%, 100% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-25px) rotate(5deg); }
        }
        
        /* Banner Content */
        .banner-content {
            position: relative;
            z-index: 10;
            text-align: center;
            color: white;
            max-width: 900px;
            padding: 30px;
            background: rgba(0,0,0,0.3);
            backdrop-filter: blur(5px);
            border-radius: 30px;
            margin: 20px;
            animation: fadeInScale 0.8s ease;
        }
        
        @keyframes fadeInScale {
            from { opacity: 0; transform: scale(0.9); }
            to { opacity: 1; transform: scale(1); }
        }
        
        .banner-content h1 {
            font-size: 3.5rem;
            margin-bottom: 20px;
            text-shadow: 3px 3px 8px rgba(0,0,0,0.4);
            letter-spacing: 1px;
        }
        
        .banner-content p {
            font-size: 1.3rem;
            margin-bottom: 30px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .offer-badge {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            justify-content: center;
            margin-bottom: 30px;
        }
        
        .offer-tag {
            background: linear-gradient(135deg, #ff6b35, #ff8c42);
            padding: 10px 25px;
            border-radius: 50px;
            font-weight: bold;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            transition: all 0.3s;
        }
        
        .offer-tag:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        }
        
        .shop-now-btn {
            display: inline-block;
            padding: 15px 45px;
            background: linear-gradient(135deg, #e74c3c, #c0392b);
            color: white;
            font-size: 1.2rem;
            font-weight: bold;
            border: none;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s;
            text-decoration: none;
            box-shadow: 0 5px 20px rgba(0,0,0,0.3);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); box-shadow: 0 5px 20px rgba(0,0,0,0.3); }
            50% { transform: scale(1.05); box-shadow: 0 8px 30px rgba(231,76,60,0.5); }
        }
        
        .shop-now-btn:hover {
            transform: scale(1.05);
            background: linear-gradient(135deg, #c0392b, #e74c3c);
        }
        
        .features-bar { background: white; padding: 40px 20px; display: flex; justify-content: center; gap: 50px; flex-wrap: wrap; box-shadow: 0 5px 20px rgba(0,0,0,0.05); }
        .feature-item { text-align: center; transition: all 0.3s; cursor: pointer; padding: 15px; border-radius: 20px; }
        .feature-item:hover { transform: translateY(-8px); background: linear-gradient(135deg, #fff5f5, #ffe8e8); }
        .feature-icon { font-size: 2.5rem; margin-bottom: 10px; }
        .feature-title { font-weight: bold; color: #333; margin-bottom: 5px; }
        .feature-desc { font-size: 0.8rem; color: #666; }
        
        .categories-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 25px; margin: 40px 0; }
        .category-card { background: white; padding: 30px 20px; text-align: center; border-radius: 20px; cursor: pointer; transition: all 0.3s; box-shadow: 0 5px 20px rgba(0,0,0,0.08); }
        .category-card:hover { transform: translateY(-10px); background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); color: white; box-shadow: 0 15px 35px rgba(231,76,60,0.3); }
        .category-card:hover .category-icon { transform: scale(1.1); }
        .category-icon { font-size: 3.5rem; margin-bottom: 15px; transition: transform 0.3s; }
        .category-name { font-weight: bold; font-size: 1.1rem; }
        
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .section-title { font-size: 2rem; margin: 50px 0 30px; display: flex; align-items: center; gap: 15px; }
        .section-title span { background: #e74c3c; width: 60px; height: 4px; border-radius: 2px; }
        .products-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 25px; }
        .product-card { background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 5px 20px rgba(0,0,0,0.08); transition: all 0.3s; position: relative; }
        .product-card:hover { transform: translateY(-8px); box-shadow: 0 20px 40px rgba(0,0,0,0.15); }
        .product-image { height: 200px; background-size: cover; background-position: center; position: relative; transition: transform 0.5s; }
        .product-card:hover .product-image { transform: scale(1.05); }
        .discount-badge { position: absolute; top: 10px; left: 10px; background: #e74c3c; color: white; padding: 5px 12px; border-radius: 20px; font-size: 0.7rem; font-weight: bold; z-index: 2; }
        .bogo-badge { position: absolute; top: 10px; right: 10px; background: #27ae60; color: white; padding: 5px 12px; border-radius: 20px; font-size: 0.7rem; font-weight: bold; z-index: 2; }
        .product-info { padding: 15px; }
        .product-name { font-size: 1rem; font-weight: 600; margin-bottom: 5px; }
        .product-unit { font-size: 0.75rem; color: #666; margin-bottom: 10px; }
        .price-row { display: flex; align-items: center; gap: 10px; margin-bottom: 15px; }
        .current-price { font-size: 1.3rem; font-weight: bold; color: #e74c3c; }
        .original-price { font-size: 0.8rem; text-decoration: line-through; color: #999; }
        .add-btn { width: 100%; padding: 12px; background: #e74c3c; color: white; border: none; border-radius: 30px; cursor: pointer; font-weight: 600; transition: all 0.3s; }
        .add-btn:hover { background: #c0392b; transform: scale(1.02); }
        
        .cart-sidebar { position: fixed; right: -400px; top: 0; width: 400px; height: 100vh; background: white; box-shadow: -5px 0 30px rgba(0,0,0,0.2); z-index: 2000; transition: right 0.3s; display: flex; flex-direction: column; }
        .cart-sidebar.open { right: 0; }
        .cart-header { padding: 20px; background: #e74c3c; color: white; display: flex; justify-content: space-between; align-items: center; }
        .cart-items { flex: 1; overflow-y: auto; padding: 20px; }
        .cart-item { display: flex; gap: 15px; padding: 15px 0; border-bottom: 1px solid #eee; }
        .cart-item-image { width: 70px; height: 70px; background-size: cover; background-position: center; border-radius: 12px; }
        .cart-item-details { flex: 1; }
        .cart-item-name { font-weight: 600; }
        .cart-item-price { color: #e74c3c; font-weight: bold; }
        .cart-item-quantity { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
        .cart-qty-btn { width: 30px; height: 30px; border-radius: 50%; border: 1px solid #ddd; background: white; cursor: pointer; font-weight: bold; transition: all 0.3s; }
        .cart-qty-btn:hover { background: #e74c3c; color: white; border-color: #e74c3c; }
        .cart-footer { padding: 20px; border-top: 1px solid #eee; }
        .cart-total { display: flex; justify-content: space-between; font-size: 1.3rem; font-weight: bold; margin-bottom: 15px; }
        .checkout-btn { width: 100%; padding: 15px; background: #e74c3c; color: white; border: none; border-radius: 30px; font-weight: bold; cursor: pointer; transition: all 0.3s; }
        .checkout-btn:hover { background: #c0392b; transform: scale(1.02); }
        .overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 1999; display: none; }
        .overlay.show { display: block; }
        
        .cart-icon { position: relative; cursor: pointer; background: rgba(255,255,255,0.2); padding: 10px 18px; border-radius: 30px; display: flex; align-items: center; gap: 8px; transition: all 0.3s; }
        .cart-icon:hover { background: rgba(255,255,255,0.3); transform: scale(1.02); }
        .cart-count { position: absolute; top: -8px; right: -8px; background: #f39c12; color: white; border-radius: 50%; padding: 2px 8px; font-size: 0.7rem; min-width: 20px; text-align: center; }
        .user-menu { display: flex; align-items: center; gap: 15px; }
        .user-name { background: rgba(255,255,255,0.2); padding: 8px 18px; border-radius: 30px; }
        .logout-btn { background: rgba(255,255,255,0.2); padding: 8px 18px; border-radius: 30px; text-decoration: none; color: white; transition: all 0.3s; }
        .logout-btn:hover { background: rgba(255,255,255,0.3); }
        
        .footer { background: #1a1a2e; color: white; padding: 50px 20px; margin-top: 50px; text-align: center; }
        .toast { position: fixed; bottom: 30px; right: 30px; background: #27ae60; color: white; padding: 12px 24px; border-radius: 10px; z-index: 3000; animation: slideIn 0.3s ease; }
        .fab { position: fixed; bottom: 30px; right: 30px; background: #e74c3c; width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.8rem; cursor: pointer; box-shadow: 0 5px 20px rgba(0,0,0,0.2); transition: all 0.3s; z-index: 1000; }
        .fab:hover { transform: scale(1.1); background: #c0392b; }
        @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        @media (max-width: 768px) { .products-grid { grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); } .cart-sidebar { width: 100%; } .hero-banner { height: 500px; background-attachment: scroll; } .banner-content h1 { font-size: 1.8rem; } .banner-content p { font-size: 1rem; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="logo" onclick="location.href='/index'"><span>🛒</span> Mahalakshmi Stores</div>
            <div class="user-menu">
                <span class="user-name">👋 {{ current_user.username }}</span>
                <div class="cart-icon" onclick="toggleCart()">🛒 Cart <span id="cartCount" class="cart-count">{{ cart_count }}</span></div>
                <a href="/my-orders" style="color: white; text-decoration: none;">📋 Orders</a>
                <a href="/logout" class="logout-btn" onclick="event.preventDefault(); logout()">🚪 Logout</a>
            </div>
        </div>
    </div>

    <!-- Premium Hero Banner with Beautiful Background -->
    <div class="hero-banner">
        <div class="floating-elements">
            <div class="float-item">🍅</div>
            <div class="float-item">🥬</div>
            <div class="float-item">🍎</div>
            <div class="float-item">🥕</div>
            <div class="float-item">🍊</div>
            <div class="float-item">🥦</div>
        </div>
        <div class="banner-content">
            <h1>Fresh Groceries Delivered to Your Doorstep</h1>
            <p>Quality products at the best prices, delivered fast and fresh!</p>
            <div class="offer-badge">
                <div class="offer-tag">🚚 Free Delivery above ₹100</div>
                <div class="offer-tag">🎁 Buy 1 Get 1 Free</div>
                <div class="offer-tag">✨ 20% off First Order</div>
            </div>
            <button class="shop-now-btn" onclick="document.getElementById('vegetables').scrollIntoView({behavior: 'smooth'})">Shop Now →</button>
        </div>
    </div>

    <div class="features-bar">
        <div class="feature-item"><div class="feature-icon">🚚</div><div class="feature-title">Free Delivery</div><div class="feature-desc">On orders above ₹100</div></div>
        <div class="feature-item"><div class="feature-icon">🔄</div><div class="feature-title">Easy Returns</div><div class="feature-desc">30 days return policy</div></div>
        <div class="feature-item"><div class="feature-icon">💳</div><div class="feature-title">Secure Payment</div><div class="feature-desc">COD/UPI/Card</div></div>
        <div class="feature-item"><div class="feature-icon">⭐</div><div class="feature-title">Quality Guarantee</div><div class="feature-desc">100% fresh products</div></div>
        <div class="feature-item"><div class="feature-icon">🎁</div><div class="feature-title">Buy 1 Get 1</div><div class="feature-desc">On select items</div></div>
        <div class="feature-item"><div class="feature-icon">⏱️</div><div class="feature-title">Quick Delivery</div><div class="feature-desc">Within 2 hours</div></div>
    </div>

    <div class="container">
        <div class="categories-grid">
            {% for cat in categories %}
            <div class="category-card" onclick="document.getElementById('{{ cat }}').scrollIntoView({behavior: 'smooth'})">
                <div class="category-icon">{% if cat == 'vegetables' %}🥬{% elif cat == 'masala' %}🌶️{% elif cat == 'oils' %}🛢️{% else %}🥒{% endif %}</div>
                <div class="category-name">{{ cat|capitalize }}</div>
            </div>
            {% endfor %}
        </div>

        {% if bogo_products %}
        <div class="section-title"><span></span> 🔥 Buy 1 Get 1 Free 🔥 <span></span></div>
        <div class="products-grid">
            {% for product in bogo_products %}
            <div class="product-card">
                <div class="product-image" style="background-image: url('{{ product.image_url }}'); background-size: cover; background-position: center;"><div class="bogo-badge">Buy 1 Get 1</div></div>
                <div class="product-info">
                    <div class="product-name">{{ product.name }}</div>
                    <div class="product-unit">{{ product.unit }}</div>
                    <div class="price-row"><span class="current-price">₹{{ product.price }}</span>{% if product.original_price %}<span class="original-price">₹{{ product.original_price }}</span>{% endif %}</div>
                    <button class="add-btn" onclick="addToCart({{ product.id }})">Add to Cart 🛒</button>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% for cat in categories %}
        <div class="section-title" id="{{ cat }}"><span></span> {% if cat == 'vegetables' %}🥬{% elif cat == 'masala' %}🌶️{% elif cat == 'oils' %}🛢️{% else %}🥒{% endif %} {{ cat|capitalize }} <span></span></div>
        <div class="products-grid">
            {% for product in products_by_category[cat] %}
            <div class="product-card">
                <div class="product-image" style="background-image: url('{{ product.image_url }}'); background-size: cover; background-position: center;">{% if product.discount > 0 %}<div class="discount-badge">{{ product.discount }}% OFF</div>{% endif %}</div>
                <div class="product-info">
                    <div class="product-name">{{ product.name }}</div>
                    <div class="product-unit">{{ product.unit }}</div>
                    <div class="price-row"><span class="current-price">₹{{ product.price }}</span>{% if product.original_price %}<span class="original-price">₹{{ product.original_price }}</span>{% endif %}</div>
                    <button class="add-btn" onclick="addToCart({{ product.id }})">Add to Cart 🛒</button>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endfor %}
    </div>

    <div class="overlay" id="cartOverlay" onclick="toggleCart()"></div>
    <div class="cart-sidebar" id="cartSidebar">
        <div class="cart-header"><h3>Your Cart 🛒</h3><button onclick="toggleCart()" style="background: none; border: none; color: white; font-size: 1.8rem; cursor: pointer;">×</button></div>
        <div class="cart-items" id="cartItemsContainer"><div style="text-align: center; padding: 40px;">Loading cart...</div></div>
        <div class="cart-footer" id="cartFooter" style="display: none;">
            <div class="cart-total"><span>Total:</span><span id="cartTotal">₹0</span></div>
            <button class="checkout-btn" onclick="proceedToCheckout()">Proceed to Checkout →</button>
        </div>
    </div>

    <div class="fab" onclick="toggleCart()">🛒<span id="fabCount" class="cart-count" style="top: -5px; right: -5px;">{{ cart_count }}</span></div>
    <div class="footer">
        <p><strong>Mahalakshmi Stores</strong> - Your Trusted Grocery Partner</p>
        <p>📞 +91 98765 43210 | 📧 support@mahalakshmi.com</p>
        <p>📍 Serving since 2024 | Quality you can trust</p>
        <p style="margin-top: 20px; font-size: 0.8rem;">© 2024 Mahalakshmi Stores. All Rights Reserved.</p>
    </div>

    <script>
        let cart = {};
        async function loadCart() {
            const response = await fetch('/get-cart');
            const data = await response.json();
            cart = {};
            data.items.forEach(item => { cart[item.id] = item; });
            updateCartUI();
        }
        async function addToCart(productId) {
            const response = await fetch('/add-to-cart', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: 'product_id=' + productId + '&quantity=1' });
            const data = await response.json();
            if (data.success) { await loadCart(); showToast('Added to cart! 🛒'); document.getElementById('cartCount').innerText = data.cart_count; document.getElementById('fabCount').innerText = data.cart_count; }
        }
        async function updateCartQuantity(productId, newQuantity) {
            const response = await fetch('/update-cart', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: 'product_id=' + productId + '&quantity=' + newQuantity });
            const data = await response.json();
            if (data.success) { await loadCart(); document.getElementById('cartCount').innerText = data.cart_count; document.getElementById('fabCount').innerText = data.cart_count; }
        }
        function updateCartUI() {
            const container = document.getElementById('cartItemsContainer');
            const footer = document.getElementById('cartFooter');
            const items = Object.values(cart);
            if (items.length === 0) { container.innerHTML = '<div style="text-align: center; padding: 40px;">Your cart is empty! 🛒</div>'; footer.style.display = 'none'; return; }
            let subtotal = 0;
            container.innerHTML = items.map(item => { subtotal += item.total; return `<div class="cart-item"><div class="cart-item-image" style="background-image: url('${item.image_url}');"></div><div class="cart-item-details"><div class="cart-item-name">${item.name}</div><div class="cart-item-price">₹${item.price} / ${item.unit}</div><div class="cart-item-quantity"><button class="cart-qty-btn" onclick="updateCartQuantity(${item.id}, ${item.quantity - 1})">-</button><span>${item.quantity}</span><button class="cart-qty-btn" onclick="updateCartQuantity(${item.id}, ${item.quantity + 1})">+</button><span style="margin-left: auto; font-weight: bold;">₹${item.total}</span></div></div></div>`; }).join('');
            const response = fetch('/get-cart').then(r => r.json()).then(data => { document.getElementById('cartTotal').innerHTML = `₹${data.total}`; footer.style.display = 'block'; });
        }
        function toggleCart() { document.getElementById('cartSidebar').classList.toggle('open'); document.getElementById('cartOverlay').classList.toggle('show'); }
        function proceedToCheckout() { window.location.href = '/checkout'; }
        function showToast(message) { const toast = document.createElement('div'); toast.className = 'toast'; toast.innerText = message; document.body.appendChild(toast); setTimeout(() => toast.remove(), 3000); }
        async function logout() { const response = await fetch('/logout'); const data = await response.json(); if (data.success) window.location.href = data.redirect; }
        loadCart();
    </script>
</body>
</html>
'''


CHECKOUT_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Checkout - Mahalakshmi Stores</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8f9fa; }
        .header { background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); color: white; padding: 15px 20px; }
        .header-content { max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 1.5rem; font-weight: bold; cursor: pointer; }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 20px; display: grid; grid-template-columns: 1fr 380px; gap: 30px; }
        .checkout-form { background: white; border-radius: 16px; padding: 30px; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; margin-bottom: 8px; font-weight: 500; }
        .form-group input, .form-group textarea { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 10px; font-size: 1rem; }
        .payment-methods { display: flex; gap: 15px; flex-wrap: wrap; margin-top: 10px; }
        .payment-option { flex: 1; padding: 15px; border: 2px solid #ddd; border-radius: 12px; text-align: center; cursor: pointer; transition: all 0.3s; min-width: 100px; }
        .payment-option.selected { border-color: #e74c3c; background: #fdeaea; }
        .payment-option .icon { font-size: 1.5rem; display: block; margin-bottom: 5px; }
        .order-summary { background: white; border-radius: 16px; padding: 30px; height: fit-content; position: sticky; top: 20px; }
        .summary-row { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #eee; }
        .summary-total { font-size: 1.3rem; font-weight: bold; color: #e74c3c; }
        .place-order-btn { width: 100%; padding: 14px; background: #e74c3c; color: white; border: none; border-radius: 30px; font-size: 1rem; font-weight: bold; cursor: pointer; margin-top: 20px; }
        .back-link { display: inline-block; margin-top: 20px; color: #e74c3c; text-decoration: none; }
        @media (max-width: 768px) { .container { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content"><div class="logo" onclick="location.href='/index'">🛒 Mahalakshmi Stores</div><div>Checkout</div></div>
    </div>
    <div class="container">
        <form class="checkout-form" id="checkoutForm">
            <h3>Delivery Details 📍</h3>
            <div class="form-group"><label>Full Name *</label><input type="text" id="name" value="{{ current_user.username }}" required></div>
            <div class="form-group"><label>Phone Number *</label><input type="tel" id="phone" value="{{ current_user.phone }}" required></div>
            <div class="form-group"><label>Delivery Address *</label><textarea id="address" rows="2" required>{{ current_user.address or '' }}</textarea></div>
            <div class="form-group"><label>Payment Method *</label>
                <div class="payment-methods">
                    <div class="payment-option selected" onclick="selectPayment('cod')" data-method="cod"><span class="icon">💵</span> Cash on Delivery</div>
                    <div class="payment-option" onclick="selectPayment('upi')" data-method="upi"><span class="icon">📱</span> UPI / GPay</div>
                    <div class="payment-option" onclick="selectPayment('card')" data-method="card"><span class="icon">💳</span> Credit/Debit Card</div>
                </div>
                <input type="hidden" id="paymentMethod" value="cod">
            </div>
            <button type="submit" class="place-order-btn">Place Order →</button>
            <a href="/index" class="back-link">← Back to Shopping</a>
        </form>
        <div class="order-summary"><h3>Order Summary</h3><div id="summary"></div></div>
    </div>
    <script>
        function selectPayment(method) { document.querySelectorAll('.payment-option').forEach(opt => opt.classList.remove('selected')); document.querySelector(`.payment-option[data-method="${method}"]`).classList.add('selected'); document.getElementById('paymentMethod').value = method; }
        async function loadCart() { const response = await fetch('/get-cart'); const data = await response.json(); document.getElementById('summary').innerHTML = `<div class="summary-row"><span>Subtotal</span><span>₹${data.subtotal}</span></div>${data.discount > 0 ? `<div class="summary-row"><span>Discount</span><span>-₹${data.discount}</span></div>` : ''}${data.bogo_savings > 0 ? `<div class="summary-row"><span>BOGO Savings</span><span>-₹${data.bogo_savings}</span></div>` : ''}<div class="summary-row"><span>Delivery Charge</span><span>₹${data.delivery}</span></div><div class="summary-row summary-total"><span>Total</span><span>₹${data.total}</span></div>`; }
        document.getElementById('checkoutForm').addEventListener('submit', async (e) => { e.preventDefault(); const response = await fetch('/place-order', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: 'name=' + encodeURIComponent(document.getElementById('name').value) + '&phone=' + encodeURIComponent(document.getElementById('phone').value) + '&address=' + encodeURIComponent(document.getElementById('address').value) + '&payment_method=' + encodeURIComponent(document.getElementById('paymentMethod').value) }); const data = await response.json(); if (data.success) window.location.href = data.redirect; });
        loadCart();
    </script>
</body>
</html>
'''

ORDER_SUCCESS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Order Success - Mahalakshmi Stores</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8f9fa; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .success-container { background: white; border-radius: 30px; padding: 50px; max-width: 500px; width: 90%; text-align: center; box-shadow: 0 25px 50px rgba(0,0,0,0.1); animation: fadeInUp 0.6s ease; }
        .success-icon { font-size: 5rem; color: #27ae60; margin-bottom: 20px; }
        h2 { color: #333; margin-bottom: 10px; }
        p { color: #666; margin-bottom: 30px; }
        .btn { display: inline-block; padding: 12px 30px; background: #e74c3c; color: white; text-decoration: none; border-radius: 50px; margin: 10px; transition: transform 0.3s; }
        .btn:hover { transform: translateY(-3px); }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <div class="success-container">
        <div class="success-icon">✅</div>
        <h2>Order Placed Successfully!</h2>
        <p>Order #{{ order.order_number }}<br>Total: ₹{{ order.total }}<br>We'll deliver to: {{ order.delivery_address }}</p>
        <a href="/index" class="btn">Continue Shopping</a>
        <a href="/my-orders" class="btn" style="background: #27ae60;">View Orders</a>
    </div>
</body>
</html>
'''

MY_ORDERS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Orders - Mahalakshmi Stores</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8f9fa; }
        .header { background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); color: white; padding: 15px 20px; }
        .header-content { max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 1.5rem; font-weight: bold; cursor: pointer; }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 20px; }
        .order-card { background: white; border-radius: 16px; padding: 20px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; }
        .status { padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; color: white; }
        .status-confirmed { background: #f39c12; }
        .status-delivered { background: #27ae60; }
        .status-cancelled { background: #e74c3c; }
        .track-btn { background: #e74c3c; color: white; padding: 8px 20px; border: none; border-radius: 30px; cursor: pointer; text-decoration: none; display: inline-block; }
        @media (max-width: 768px) { .order-card { flex-direction: column; text-align: center; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content"><div class="logo" onclick="location.href='/index'">🛒 Mahalakshmi Stores</div><div>My Orders</div><a href="/index" style="color: white;">← Back</a></div>
    </div>
    <div class="container">
        <h2>📋 My Orders</h2>
        {% if orders %}
            {% for order in orders %}
            <div class="order-card">
                <div><strong>Order #{{ order.order_number }}</strong><br><small>{{ order.created_at.strftime('%d %b %Y, %I:%M %p') }}</small></div>
                <div><span class="status status-{{ order.order_status }}">{{ order.order_status|capitalize }}</span></div>
                <div><strong>₹{{ order.total }}</strong></div>
                <div><a href="/track-order/{{ order.id }}" class="track-btn">Track Order →</a></div>
            </div>
            {% endfor %}
        {% else %}<p style="text-align: center; padding: 40px;">No orders yet! <a href="/index" style="color: #e74c3c;">Start Shopping</a></p>{% endif %}
    </div>
</body>
</html>
'''

TRACK_ORDER_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Track Order - Mahalakshmi Stores</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8f9fa; }
        .header { background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); color: white; padding: 15px 20px; }
        .header-content { max-width: 800px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
        .container { max-width: 800px; margin: 30px auto; padding: 0 20px; }
        .tracking-card { background: white; border-radius: 20px; padding: 30px; margin-bottom: 20px; }
        .delivery-message { background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); color: white; padding: 20px; border-radius: 16px; text-align: center; margin-bottom: 30px; }
        .status-timeline { display: flex; justify-content: space-between; margin: 40px 0; position: relative; flex-wrap: wrap; }
        .status-step { text-align: center; flex: 1; min-width: 80px; }
        .status-icon { width: 50px; height: 50px; background: #e0e0e0; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 10px; font-size: 1.2rem; }
        .status-step.completed .status-icon { background: #27ae60; color: white; }
        .status-step.active .status-icon { background: #f39c12; color: white; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
        @media (max-width: 600px) { .status-step { font-size: 0.7rem; } .status-icon { width: 40px; height: 40px; font-size: 0.9rem; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content"><div class="logo" onclick="location.href='/index'">🛒 Mahalakshmi Stores</div><div>Track Order</div><a href="/my-orders" style="color: white;">← Back</a></div>
    </div>
    <div class="container">
        <div class="tracking-card">
            <h2>Order #{{ order.order_number }}</h2>
            <p>Placed on: {{ order.created_at.strftime('%d %b %Y, %I:%M %p') }}</p>
            <div class="delivery-message"><span style="font-size: 2rem;">🚚</span><p style="margin-top: 10px;">{{ "Your order is confirmed and will be delivered soon!" if order.order_status == 'confirmed' else "Your order is out for delivery!" if order.order_status == 'out_for_delivery' else "Order delivered! Enjoy your shopping!" }}</p></div>
            <div class="status-timeline">
                <div class="status-step {% if order.order_status in ['confirmed', 'out_for_delivery', 'delivered'] %}completed{% endif %}"><div class="status-icon">✓</div><div>Confirmed</div></div>
                <div class="status-step {% if order.order_status in ['out_for_delivery', 'delivered'] %}completed{% elif order.order_status == 'confirmed' %}active{% endif %}"><div class="status-icon">🛒</div><div>Preparing</div></div>
                <div class="status-step {% if order.order_status == 'delivered' %}completed{% elif order.order_status == 'out_for_delivery' %}active{% endif %}"><div class="status-icon">🚚</div><div>Out for Delivery</div></div>
                <div class="status-step {% if order.order_status == 'delivered' %}active{% endif %}"><div class="status-icon">🏠</div><div>Delivered</div></div>
            </div>
            <div style="text-align: center; margin-top: 20px;"><a href="/index" style="color: #e74c3c;">← Continue Shopping</a></div>
        </div>
    </div>
</body>
</html>
'''

ADMIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Panel - Mahalakshmi Stores</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; }
        .admin-container { display: flex; }
        .sidebar { width: 260px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; min-height: 100vh; position: fixed; }
        .sidebar-header { padding: 20px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .sidebar-nav { padding: 20px 0; }
        .nav-item { padding: 12px 25px; display: flex; align-items: center; gap: 12px; text-decoration: none; color: rgba(255,255,255,0.8); transition: all 0.3s; }
        .nav-item:hover, .nav-item.active { background: rgba(255,255,255,0.1); color: white; }
        .main-content { flex: 1; margin-left: 260px; padding: 20px; }
        .top-bar { background: white; padding: 15px 25px; border-radius: 12px; margin-bottom: 25px; display: flex; justify-content: space-between; align-items: center; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 16px; }
        .stat-card .value { font-size: 2rem; font-weight: bold; color: #e74c3c; }
        .card { background: white; border-radius: 16px; padding: 20px; margin-bottom: 20px; overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        .btn { padding: 6px 12px; border: none; border-radius: 8px; cursor: pointer; }
        .btn-primary { background: #e74c3c; color: white; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-warning { background: #f39c12; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .form-group { margin-bottom: 15px; }
        .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px; }
        @media (max-width: 768px) { .sidebar { transform: translateX(-100%); } .main-content { margin-left: 0; } }
    </style>
</head>
<body>
    <div class="admin-container">
        <div class="sidebar">
            <div class="sidebar-header"><span style="font-size: 2rem;">🛒</span><h3>Mahalakshmi Stores</h3></div>
            <div class="sidebar-nav">
                <a href="/admin" class="nav-item {% if active_page == 'dashboard' %}active{% endif %}">📊 Dashboard</a>
                <a href="/admin#products" class="nav-item">📦 Products</a>
                <a href="/admin#orders" class="nav-item">📋 Orders</a>
                <a href="/admin/users" class="nav-item">👥 Users</a>
                <a href="/index" class="nav-item">🏠 View Store</a>
                <a href="/logout" class="nav-item">🚪 Logout</a>
            </div>
        </div>
        <div class="main-content">
            <div class="top-bar"><h2>Admin Dashboard</h2><div>Welcome, {{ current_user.username }}</div></div>
            
            <div class="stats-grid">
                <div class="stat-card"><h3>Total Users</h3><div class="value">{{ total_users }}</div></div>
                <div class="stat-card"><h3>Total Products</h3><div class="value">{{ total_products }}</div></div>
                <div class="stat-card"><h3>Total Orders</h3><div class="value">{{ total_orders }}</div></div>
                <div class="stat-card"><h3>Total Revenue</h3><div class="value">₹{{ "%.2f"|format(total_revenue) }}</div></div>
                <div class="stat-card"><h3>Pending Orders</h3><div class="value">{{ pending_orders }}</div></div>
            </div>

            <!-- Add Product Form -->
            <div class="card" id="products"><h3>➕ Add New Product</h3>
                <form method="POST" action="/admin/add-product" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr)); gap: 15px;">
                    <input type="text" name="name" placeholder="Product Name" required><input type="text" name="category" placeholder="Category" required>
                    <input type="number" name="price" placeholder="Price" step="0.01" required><input type="number" name="original_price" placeholder="Original Price" step="0.01">
                    <input type="text" name="unit" placeholder="Unit (kg/litre/pack)" required><input type="text" name="image_url" placeholder="Image URL">
                    <input type="number" name="stock" placeholder="Stock"><input type="number" name="discount" placeholder="Discount %">
                    <input type="text" name="offer_tag" placeholder="Offer Tag"><label><input type="checkbox" name="is_featured"> Featured</label><label><input type="checkbox" name="is_bogo"> Buy 1 Get 1</label>
                    <button type="submit" class="btn btn-primary">Add Product</button>
                </form>
            </div>

            <!-- Products List -->
            <div class="card"><h3>📦 All Products ({{ products|length }})</h3>
                <table><thead><tr><th>ID</th><th>Name</th><th>Category</th><th>Price</th><th>Stock</th><th>Actions</th></tr></thead>
                <tbody>{% for product in products %}<tr><td>{{ product.id }}</td><td>{{ product.name }}</td><td>{{ product.category }}</td><td>₹{{ product.price }}</td><td>{{ product.stock }}</td>
                <td><form method="POST" action="/admin/edit-product/{{ product.id }}" style="display: inline;"><input type="hidden" name="name" value="{{ product.name }}"><input type="hidden" name="category" value="{{ product.category }}"><input type="hidden" name="price" value="{{ product.price }}"><input type="hidden" name="original_price" value="{{ product.original_price or 0 }}"><input type="hidden" name="unit" value="{{ product.unit }}"><input type="hidden" name="image_url" value="{{ product.image_url or '' }}"><input type="hidden" name="stock" value="{{ product.stock }}"><input type="hidden" name="discount" value="{{ product.discount }}"><input type="hidden" name="offer_tag" value="{{ product.offer_tag or '' }}"><input type="hidden" name="is_featured" value="{{ 'on' if product.is_featured else '' }}"><input type="hidden" name="is_bogo" value="{{ 'on' if product.is_bogo else '' }}"><button type="submit" class="btn btn-warning">Edit</button></form><a href="/admin/delete-product/{{ product.id }}" class="btn btn-danger" onclick="return confirm('Delete?')">Delete</a></td></tr>{% endfor %}</tbody>
                </table>
            </div>

            <!-- Orders -->
            <div class="card" id="orders"><h3>📋 Recent Orders</h3>
                <table><thead><tr><th>Order #</th><th>Customer</th><th>Amount</th><th>Status</th><th>Payment</th><th>Action</th></tr></thead>
                <tbody>{% for order in recent_orders %}<tr><td>{{ order.order_number }}</td><td>{{ order.customer_name }}</td><td>₹{{ order.total }}</td><td>{{ order.order_status }}</td><td>{{ order.payment_status }}</td>
                <td><form method="POST" action="/admin/update-order/{{ order.id }}"><select name="status"><option value="confirmed" {% if order.order_status=='confirmed' %}selected{% endif %}>Confirmed</option><option value="out_for_delivery" {% if order.order_status=='out_for_delivery' %}selected{% endif %}>Out for Delivery</option><option value="delivered" {% if order.order_status=='delivered' %}selected{% endif %}>Delivered</option><option value="cancelled" {% if order.order_status=='cancelled' %}selected{% endif %}>Cancelled</option></select><select name="payment_status"><option value="pending" {% if order.payment_status=='pending' %}selected{% endif %}>Pending</option><option value="success" {% if order.payment_status=='success' %}selected{% endif %}>Success</option></select><button type="submit" class="btn btn-primary">Update</button></form></td></tr>{% endfor %}</tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
'''

ADMIN_USERS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Users - Admin Panel</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; }
        .admin-container { display: flex; }
        .sidebar { width: 260px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; min-height: 100vh; position: fixed; }
        .sidebar-header { padding: 20px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .sidebar-nav { padding: 20px 0; }
        .nav-item { padding: 12px 25px; display: flex; align-items: center; gap: 12px; text-decoration: none; color: rgba(255,255,255,0.8); transition: all 0.3s; }
        .nav-item:hover { background: rgba(255,255,255,0.1); color: white; }
        .main-content { flex: 1; margin-left: 260px; padding: 20px; }
        .top-bar { background: white; padding: 15px 25px; border-radius: 12px; margin-bottom: 25px; }
        .card { background: white; border-radius: 16px; padding: 20px; overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        .btn { padding: 6px 12px; border: none; border-radius: 8px; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn-warning { background: #f39c12; color: white; }
        .btn-primary { background: #e74c3c; color: white; }
        @media (max-width: 768px) { .sidebar { transform: translateX(-100%); } .main-content { margin-left: 0; } }
    </style>
</head>
<body>
    <div class="admin-container">
        <div class="sidebar">
            <div class="sidebar-header"><span style="font-size: 2rem;">🛒</span><h3>Mahalakshmi Stores</h3></div>
            <div class="sidebar-nav">
                <a href="/admin" class="nav-item">📊 Dashboard</a>
                <a href="/admin/users" class="nav-item" style="background: rgba(255,255,255,0.1);">👥 Users</a>
                <a href="/index" class="nav-item">🏠 View Store</a>
                <a href="/logout" class="nav-item">🚪 Logout</a>
            </div>
        </div>
        <div class="main-content">
            <div class="top-bar"><h2>User Management</h2></div>
            <div class="card">
                <h3>👥 All Users</h3>
                <table>
                    <thead><tr><th>ID</th><th>Username</th><th>Email</th><th>Phone</th><th>Role</th><th>Status</th><th>Action</th></tr></thead>
                    <tbody>{% for user in users %}<tr><td>{{ user.id }}</td><td>{{ user.username }}</td><td>{{ user.email }}</td><td>{{ user.phone }}</td><td>{{ user.role }}</td><td>{{ "Active" if user.is_active else "Inactive" }}</td><td><a href="/admin/toggle-user/{{ user.id }}" class="btn btn-warning">{{ "Deactivate" if user.is_active else "Activate" }}</a></td></tr>{% endfor %}</tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
'''

if __name__ == '__main__':
    init_data()
    app.run(debug=True, host='0.0.0.0', port=5000)