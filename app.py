import os, sqlite3, math, uuid
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'loja.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png','jpg','jpeg','webp'}

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY','troque-esta-chave')
app.config['MAX_CONTENT_LENGTH'] = 6 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD','1234')


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    con = db()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        price REAL NOT NULL DEFAULT 0,
        stock INTEGER NOT NULL DEFAULT 0,
        image TEXT DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        email TEXT DEFAULT '',
        password_hash TEXT NOT NULL,
        points INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        subtotal REAL NOT NULL,
        installation_fee REAL NOT NULL DEFAULT 0,
        total REAL NOT NULL,
        payment_method TEXT NOT NULL,
        payment_status TEXT NOT NULL DEFAULT 'Pendente',
        order_status TEXT NOT NULL DEFAULT 'Recebido',
        notes TEXT DEFAULT '',
        points_awarded INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    );
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER,
        product_name TEXT NOT NULL,
        qty INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        line_total REAL NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    );
    CREATE TABLE IF NOT EXISTS points_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        order_id INTEGER,
        points INTEGER NOT NULL,
        description TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    ''')
    defaults = {
        'installation_fee':'59.00',
        'pix_key':'19 97401-9632',
        'payment_methods':'Pix,Cartão de crédito,Cartão de débito,Dinheiro',
        'whatsapp':'5519974019632',
    }
    for k,v in defaults.items():
        con.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
    count = con.execute('SELECT COUNT(*) c FROM products').fetchone()['c']
    if count == 0:
        now=datetime.now().isoformat(timespec='seconds')
        seed=[
            ('Barril Chopp Brahma 30L','Chopp Brahma gelado para seu evento.',495.00,20,''),
            ('Barril Chopp Brahma 50L','Ideal para festas maiores e confraternizações.',825.00,15,''),
            ('Copo 400 ml','Copo para servir seu chopp.',3.50,200,''),
            ('Copo 700 ml','Copo grande para servir seu chopp.',5.00,150,''),
        ]
        con.executemany('INSERT INTO products(name,description,price,stock,image,created_at) VALUES(?,?,?,?,?,?)',[(a,b,c,d,e,now) for a,b,c,d,e in seed])
    con.commit(); con.close()


def setting(key, default=''):
    con=db(); row=con.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone(); con.close()
    return row['value'] if row else default


def money(v):
    return f"R$ {v:,.2f}".replace(',', 'X').replace('.', ',').replace('X','.')
app.jinja_env.filters['money']=money


def customer_required(f):
    @wraps(f)
    def wrapper(*args,**kwargs):
        if not session.get('customer_id'):
            flash('Entre na sua conta para continuar.','warning')
            return redirect(url_for('login'))
        return f(*args,**kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args,**kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return f(*args,**kwargs)
    return wrapper


def cart_data():
    cart=session.get('cart',{})
    if not cart: return [],0
    ids=[int(i) for i in cart.keys()]
    con=db(); qs=','.join('?'*len(ids))
    rows=con.execute(f'SELECT * FROM products WHERE id IN ({qs})',ids).fetchall(); con.close()
    items=[]; subtotal=0
    for p in rows:
        qty=max(1,int(cart.get(str(p['id']),1)))
        line=p['price']*qty; subtotal+=line
        items.append({'p':p,'qty':qty,'line':line})
    return items,subtotal

@app.context_processor
def globals_ctx():
    return dict(store_name='Chopp Brahma Mogi Mirim', slogan='Aqui tem oferta de verdade', address='Av. 22 de Outubro, 826 - Mogi Mirim/SP', phone='(19) 3806-2786', whatsapp='(19) 97401-9632', customer_logged=bool(session.get('customer_id')), cart_count=sum(session.get('cart',{}).values()) if session.get('cart') else 0)

@app.route('/')
def home():
    con=db(); products=con.execute('SELECT * FROM products WHERE active=1 ORDER BY id DESC').fetchall(); con.close()
    return render_template('home.html',products=products)

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        name=request.form['name'].strip(); phone=request.form['phone'].strip(); email=request.form.get('email','').strip(); password=request.form['password']
        if len(password)<4:
            flash('A senha precisa ter pelo menos 4 caracteres.','danger'); return redirect(url_for('register'))
        con=db()
        try:
            cur=con.execute('INSERT INTO customers(name,phone,email,password_hash,created_at) VALUES(?,?,?,?,?)',(name,phone,email,generate_password_hash(password),datetime.now().isoformat(timespec='seconds')))
            con.commit(); session['customer_id']=cur.lastrowid; session['customer_name']=name
            flash('Cadastro realizado!','success'); return redirect(url_for('home'))
        except sqlite3.IntegrityError:
            flash('Esse telefone já está cadastrado.','danger')
        finally: con.close()
    return render_template('register.html')

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        phone=request.form['phone'].strip(); password=request.form['password']
        con=db(); c=con.execute('SELECT * FROM customers WHERE phone=?',(phone,)).fetchone(); con.close()
        if c and check_password_hash(c['password_hash'],password):
            session['customer_id']=c['id']; session['customer_name']=c['name']; return redirect(url_for('home'))
        flash('Telefone ou senha inválidos.','danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('customer_id',None); session.pop('customer_name',None); return redirect(url_for('home'))

@app.post('/cart/add/<int:pid>')
def cart_add(pid):
    cart=session.get('cart',{}); cart[str(pid)]=cart.get(str(pid),0)+1; session['cart']=cart
    flash('Produto adicionado ao carrinho.','success'); return redirect(request.referrer or url_for('home'))

@app.route('/cart',methods=['GET','POST'])
def cart():
    if request.method=='POST':
        new={}
        for k,v in request.form.items():
            if k.startswith('qty_'):
                pid=k.split('_',1)[1]
                try: q=int(v)
                except: q=1
                if q>0: new[pid]=q
        session['cart']=new; flash('Carrinho atualizado.','success')
    items,subtotal=cart_data()
    return render_template('cart.html',items=items,subtotal=subtotal,installation_fee=float(setting('installation_fee','0')))

@app.route('/checkout',methods=['GET','POST'])
@customer_required
def checkout():
    items,subtotal=cart_data()
    if not items: return redirect(url_for('home'))
    methods=[x.strip() for x in setting('payment_methods','Pix').split(',') if x.strip()]
    install_fee=float(setting('installation_fee','0'))
    if request.method=='POST':
        needs=request.form.get('installation')=='1'
        fee=install_fee if needs else 0.0
        payment=request.form['payment_method']; notes=request.form.get('notes','').strip(); total=subtotal+fee
        con=db()
        # check stock
        for i in items:
            current=con.execute('SELECT stock FROM products WHERE id=?',(i['p']['id'],)).fetchone()['stock']
            if current < i['qty']:
                con.close(); flash(f"Estoque insuficiente para {i['p']['name']}. CADASTRE/ajuste o estoque no painel.",'danger'); return redirect(url_for('cart'))
        cur=con.execute('INSERT INTO orders(customer_id,subtotal,installation_fee,total,payment_method,notes,created_at) VALUES(?,?,?,?,?,?,?)',(session['customer_id'],subtotal,fee,total,payment,notes,datetime.now().isoformat(timespec='seconds')))
        oid=cur.lastrowid
        for i in items:
            p=i['p']; con.execute('INSERT INTO order_items(order_id,product_id,product_name,qty,unit_price,line_total) VALUES(?,?,?,?,?,?)',(oid,p['id'],p['name'],i['qty'],p['price'],i['line']))
            con.execute('UPDATE products SET stock=stock-? WHERE id=?',(i['qty'],p['id']))
        con.commit(); con.close(); session['cart']={}
        flash(f'Pedido #{oid} criado. Os pontos serão creditados quando o pagamento for marcado como Pago.','success')
        return redirect(url_for('account'))
    return render_template('checkout.html',items=items,subtotal=subtotal,methods=methods,installation_fee=install_fee,pix_key=setting('pix_key'))

@app.route('/account')
@customer_required
def account():
    con=db(); c=con.execute('SELECT * FROM customers WHERE id=?',(session['customer_id'],)).fetchone(); orders=con.execute('SELECT * FROM orders WHERE customer_id=? ORDER BY id DESC',(c['id'],)).fetchall(); ledger=con.execute('SELECT * FROM points_ledger WHERE customer_id=? ORDER BY id DESC',(c['id'],)).fetchall(); con.close()
    return render_template('account.html',c=c,orders=orders,ledger=ledger)

@app.route('/admin',methods=['GET','POST'])
def admin_login():
    if session.get('admin'): return redirect(url_for('admin_dashboard'))
    if request.method=='POST':
        if request.form['password']==ADMIN_PASSWORD:
            session['admin']=True; return redirect(url_for('admin_dashboard'))
        flash('Senha administrativa incorreta.','danger')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin',None); return redirect(url_for('home'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    con=db();
    stats={
      'orders':con.execute('SELECT COUNT(*) c FROM orders').fetchone()['c'],
      'sales':con.execute("SELECT COALESCE(SUM(total),0) s FROM orders WHERE payment_status='Pago'").fetchone()['s'],
      'customers':con.execute('SELECT COUNT(*) c FROM customers').fetchone()['c'],
      'pending':con.execute("SELECT COUNT(*) c FROM orders WHERE payment_status!='Pago'").fetchone()['c']}
    orders=con.execute('''SELECT o.*, c.name customer_name, c.phone customer_phone FROM orders o JOIN customers c ON c.id=o.customer_id ORDER BY o.id DESC LIMIT 30''').fetchall(); con.close()
    return render_template('admin_dashboard.html',stats=stats,orders=orders)

@app.route('/admin/products')
@admin_required
def admin_products():
    con=db(); products=con.execute('SELECT * FROM products ORDER BY id DESC').fetchall(); con.close(); return render_template('admin_products.html',products=products)


def save_upload(file):
    if not file or not file.filename: return ''
    ext=file.filename.rsplit('.',1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS: return ''
    name=f"{uuid.uuid4().hex}.{ext}"; file.save(os.path.join(UPLOAD_DIR,name)); return name

@app.route('/admin/product/new',methods=['GET','POST'])
@admin_required
def admin_product_new():
    if request.method=='POST':
        image=save_upload(request.files.get('image'))
        con=db(); con.execute('INSERT INTO products(name,description,price,stock,image,active,created_at) VALUES(?,?,?,?,?,?,?)',(request.form['name'],request.form.get('description',''),float(request.form['price'].replace(',','.')),int(request.form['stock']),image,1 if request.form.get('active') else 0,datetime.now().isoformat(timespec='seconds'))); con.commit(); con.close(); flash('Produto cadastrado.','success'); return redirect(url_for('admin_products'))
    return render_template('admin_product_form.html',p=None)

@app.route('/admin/product/<int:pid>',methods=['GET','POST'])
@admin_required
def admin_product_edit(pid):
    con=db(); p=con.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
    if request.method=='POST':
        image=p['image']; new=save_upload(request.files.get('image')); image=new or image
        con.execute('UPDATE products SET name=?,description=?,price=?,stock=?,image=?,active=? WHERE id=?',(request.form['name'],request.form.get('description',''),float(request.form['price'].replace(',','.')),int(request.form['stock']),image,1 if request.form.get('active') else 0,pid)); con.commit(); con.close(); flash('Produto atualizado.','success'); return redirect(url_for('admin_products'))
    con.close(); return render_template('admin_product_form.html',p=p)

@app.route('/admin/order/<int:oid>',methods=['GET','POST'])
@admin_required
def admin_order(oid):
    con=db(); o=con.execute('''SELECT o.*,c.name customer_name,c.phone customer_phone,c.points customer_points FROM orders o JOIN customers c ON c.id=o.customer_id WHERE o.id=?''',(oid,)).fetchone(); items=con.execute('SELECT * FROM order_items WHERE order_id=?',(oid,)).fetchall()
    if request.method=='POST':
        oldpay=o['payment_status']; newpay=request.form['payment_status']; status=request.form['order_status']
        con.execute('UPDATE orders SET payment_status=?, order_status=? WHERE id=?',(newpay,status,oid))
        # Credit points once when order first becomes paid.
        if newpay=='Pago' and oldpay!='Pago' and o['points_awarded']==0:
            pts=int(math.floor(o['total']/100.0)*10)
            if pts>0:
                con.execute('UPDATE customers SET points=points+? WHERE id=?',(pts,o['customer_id']))
                con.execute('UPDATE orders SET points_awarded=? WHERE id=?',(pts,oid))
                con.execute('INSERT INTO points_ledger(customer_id,order_id,points,description,created_at) VALUES(?,?,?,?,?)',(o['customer_id'],oid,pts,f'Pontos do pedido #{oid}',datetime.now().isoformat(timespec='seconds')))
        con.commit(); con.close(); flash('Pedido atualizado.','success'); return redirect(url_for('admin_order',oid=oid))
    con.close(); return render_template('admin_order.html',o=o,items=items)

@app.route('/admin/customers')
@admin_required
def admin_customers():
    con=db(); customers=con.execute('SELECT * FROM customers ORDER BY id DESC').fetchall(); con.close(); return render_template('admin_customers.html',customers=customers)

@app.route('/admin/customer/<int:cid>')
@admin_required
def admin_customer(cid):
    con=db(); c=con.execute('SELECT * FROM customers WHERE id=?',(cid,)).fetchone(); orders=con.execute('SELECT * FROM orders WHERE customer_id=? ORDER BY id DESC',(cid,)).fetchall(); ledger=con.execute('SELECT * FROM points_ledger WHERE customer_id=? ORDER BY id DESC',(cid,)).fetchall(); con.close(); return render_template('admin_customer.html',c=c,orders=orders,ledger=ledger)

@app.route('/admin/settings',methods=['GET','POST'])
@admin_required
def admin_settings():
    if request.method=='POST':
        con=db()
        for k in ['installation_fee','pix_key','payment_methods','whatsapp']:
            con.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,request.form.get(k,'')))
        con.commit(); con.close(); flash('Configurações salvas.','success'); return redirect(url_for('admin_settings'))
    return render_template('admin_settings.html',installation_fee=setting('installation_fee'),pix_key=setting('pix_key'),payment_methods=setting('payment_methods'),whatsapp_admin=setting('whatsapp'))

@app.route('/manifest.json')
def manifest():
    return jsonify({"name":"Chopp Brahma Mogi Mirim","short_name":"Chopp Brahma","start_url":"/","display":"standalone","background_color":"#f4ead7","theme_color":"#d71920","icons":[{"src":"/static/capa_brahma.jpg","sizes":"512x512","type":"image/jpeg"}]})

@app.route('/service-worker.js')
def sw():
    return app.send_static_file('service-worker.js')

if __name__=='__main__':
    init_db(); app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')),debug=True)
else:
    init_db()
