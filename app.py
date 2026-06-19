from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'super_secret_royal_ararat_key' # Սեսիայի համար

# Render-ի և լոկալ համակարգչի համատեղելիության համար
if os.path.exists('/opt/render/project/src'):
    PERSISTENT_DIR = '/opt/render/project/src/instance'
else:
    PERSISTENT_DIR = os.path.join(os.getcwd(), 'instance')

if not os.path.exists(PERSISTENT_DIR):
    os.makedirs(PERSISTENT_DIR)

DB_PATH = os.path.join(PERSISTENT_DIR, 'restaurant.db')
UPLOAD_FOLDER = 'static/uploads'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Պատվերներ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_type TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            guests INTEGER DEFAULT 1,
            event_type TEXT,
            zone_type TEXT,
            table_number TEXT,
            status TEXT DEFAULT 'Նոր'
        )
    ''')
    
    # Զամբյուղի ուտեստներ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            dish_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
        )
    ''')
    
    # Ուտեստների աղյուսակ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menu_dishes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            image_url TEXT NOT NULL,
            description TEXT,
            category TEXT DEFAULT 'Տաք Ուտեստներ'
        )
    ''')
    
    try:
        cursor.execute("ALTER TABLE bookings ADD COLUMN status TEXT DEFAULT 'Նոր';")
    except sqlite3.OperationalError:
        pass

    # ---------------------------------------------------------
    # ԱՎՏՈՄԱՏ ՄԵՆՅՈՒԻ ԼՑՆՈՒՄ (ԲՈԼՈՐ ԲԱԺԻՆՆԵՐՈՎ)
    # ---------------------------------------------------------
    cursor.execute("SELECT COUNT(*) FROM menu_dishes")
    if cursor.fetchone()[0] == 0:
        sample_dishes = [
            # Տաք Ուտեստներ
            ("Արարատյան Խորոված", 4500, "https://images.unsplash.com/photo-1544025162-d76694265947?w=500", "Ընտիր խոզի միջուկ՝ հատուկ համեմունքներով", "Տաք Ուտեստներ"),
            ("Քյուֆթա", 3800, "https://images.unsplash.com/photo-1608897013039-887f21d8c804?w=500", "Ավանդական էջմիածնի քյուֆթա՝ հալած կարագով", "Տաք Ուտեստներ"),
            
            # Աղցաններ
            ("Ամառային Աղցան", 1500, "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=500", "Թարմ լոլիկ, վարունգ, կանաչի և ձիթայուղ", "Աղցաններ"),
            ("Հունական Աղցան", 2200, "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=500", "Ֆետա պանիր, ձիթապտուղ, թարմ բանջարեղեն", "Աղցաններ"),

            # Նախուտեստներ
            ("Հայկական Պանրի Տեսականի", 3000, "https://images.unsplash.com/photo-1533777857889-4be7c70b33f7?w=500", "Լոռի, Չանախ, Մոցարելլա՝ թարմ կանաչիով", "Նախուտեստներ"),
            ("Մսային Ասորտի", 4000, "https://images.unsplash.com/photo-1544025162-d76694265947?w=500", "Բաստուրմա, Սուջուխ, Խոզապուխտ", "Նախուտեստներ"),

            # Խավարտներ
            ("Կարտոֆիլ Ֆրի", 1000, "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=500", "Ոսկեգույն, խրթխրթան կարտոֆիլ", "Խավարտներ"),

            # Ըմպելիքներ
            ("Տնական Թան", 600, "https://images.unsplash.com/photo-1541658016709-82535e94bc69?w=500", "Թարմ մածունով և դաղձով", "Ըմպելիքներ"),
            ("Բնական Հյութ", 1200, "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=500", "Նռան կամ նարնջի թարմ քամած հյութ", "Ըմպելիքներ"),

            # Աղանդեր
            ("Գաթա Երևանյան", 1200, "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=500", "Խրթխրթան շերտավոր խմոր՝ քաղցր խորիզով", "Աղանդեր"),
            ("Փախլավա", 1500, "https://images.unsplash.com/photo-1519676867240-f03562e64548?w=500", "Ընկույզով և մեղրով ավանդական փախլավա", "Աղանդեր")
        ]
        cursor.executemany('''
            INSERT INTO menu_dishes (name, price, image_url, description, category)
            VALUES (?, ?, ?, ?, ?)
        ''', sample_dishes)

    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Վերցնում ենք բոլոր ուտեստները
    cursor.execute("SELECT * FROM menu_dishes")
    custom_dishes = [dict(row) for row in cursor.fetchall()]
    
    # 2. Ավտոմատ գտնում ենք բոլոր ունիկալ կատեգորիաները, որոնք կան բազայում
    # Օգտագործում ենք `set`, որպեսզի կրկնություններ չլինեն
    categories = sorted(list(set(dish['category'] for dish in custom_dishes if dish['category'])))
    
    conn.close()
    
    # HTML-ին փոխանցում ենք թե՛ ուտեստները, թե՛ ավտոմատ հավաքված կատեգորիաները
    return render_template('index.html', custom_dishes=custom_dishes, categories=categories)

@app.route('/book', methods=['POST'])
def book_order():
    try:
        data = request.get_json()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        cursor.execute('''
            INSERT INTO bookings (order_type, name, phone, date, time, guests, event_type, zone_type, table_number, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Նոր')
        ''', (data.get('order_type'), data.get('name'), data.get('phone'), data.get('date'), data.get('time'),
              int(data.get('guests', 1) or 1), data.get('event_type', ''), data.get('zone_type', ''), data.get('table_number', '')))
        
        booking_id = cursor.lastrowid
        cart_items = data.get('cart_items', [])
        for item in cart_items:
            cursor.execute('''
                INSERT INTO order_items (booking_id, dish_name, price, quantity)
                VALUES (?, ?, ?, ?)
            ''', (booking_id, item.get('name'), int(item.get('price', 0)), int(item.get('qty', 1))))
            
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- ԼՈԳԻՆԻ ԲԱԺԻՆ ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == '123':
            session['logged_in'] = True
            return redirect(url_for('admin_panel'))
        return "Սխալ տվյալներ։ Հետ գնացեք ու նորից փորձեք։"
    return '''
        <style>
            body { background: #0d0d0d; color: white; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; }
            form { background: #111; padding: 30px; border: 1px solid #dfb73c; display: flex; flex-direction: column; gap: 15px; width: 300px; }
            input { padding: 10px; background: #222; border: 1px solid #333; color: white; }
            button { padding: 10px; background: #dfb73c; border: none; font-weight: bold; cursor: pointer; }
        </style>
        <form method="POST">
            <h2 style="color:#dfb73c; text-align:center;">ROYAL LOGIN</h2>
            <input type="text" name="username" placeholder="Օգտանուն" required>
            <input type="password" name="password" placeholder="Գաղտնաբառ" required>
            <button type="submit">ՄՈՒՏՔ</button>
        </form>
    '''

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

# --- ԱԴՄԻՆԻ ԲԱԺԻՆՆԵՐ ---
@app.route('/admin')
def admin_panel():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM bookings ORDER BY id DESC")
    bookings = [dict(row) for row in cursor.fetchall()]
    
    orders_list = []
    for b in bookings:
        cursor.execute("SELECT dish_name AS name, quantity AS qty, price FROM order_items WHERE booking_id = ?", (b['id'],))
        cart_items = [dict(item_row) for item_row in cursor.fetchall()]
        
        total_price = sum(item['price'] * item['qty'] for item in cart_items)
        
        b['cart_items'] = cart_items
        b['total_price'] = total_price
        orders_list.append(b)
        
    cursor.execute("SELECT * FROM menu_dishes ORDER BY id DESC")
    dishes_list = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('admin.html', orders=orders_list, custom_dishes=dishes_list)

@app.route('/admin/update-status', methods=['POST'])
def update_status():
    if not session.get('logged_in'): return jsonify({"status": "unauthorized"}), 401
    data = request.get_json()
    booking_id = data.get('id')
    new_status = data.get('status')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE bookings SET status = ? WHERE id = ?", (new_status, booking_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/admin/delete-order', methods=['POST'])
def delete_order_api():
    if not session.get('logged_in'): return jsonify({"status": "unauthorized"}), 401
    data = request.get_json()
    booking_id = data.get('id')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/admin/add-dish', methods=['POST'])
def add_dish():
    if not session.get('logged_in'): return redirect(url_for('login'))
    name = request.form.get('name')
    price = request.form.get('price')
    category = request.form.get('category')
    description = request.form.get('description')
    
    file = request.files.get('image_file')
    image_url = 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500'
    
    if file and file.filename != '':
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        image_url = f'/{UPLOAD_FOLDER}/{file.filename}'

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO menu_dishes (name, price, image_url, description, category)
        VALUES (?, ?, ?, ?, ?)
    ''', (name, int(price), image_url, description, category))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/delete-dish', methods=['POST'])
def delete_dish():
    if not session.get('logged_in'): return jsonify({"status": "unauthorized"}), 401
    data = request.get_json()
    dish_name = data.get('name')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menu_dishes WHERE name = ?", (dish_name,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

init_db()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)