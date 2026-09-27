@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin'): return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        if request.form['password'] == ADMIN_PASSWORD: session['admin'] = True; return redirect(url_for('admin_dashboard'))
        flash('Senha administrativa incorreta.', 'danger')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None); return redirect(url_for('home'))


def period_start(period):
    now = datetime.now()
    if period == 'today': return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == '7': return now - timedelta(days=7)
    if period == '30': return now - timedelta(days=30)
    if period == 'month': return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return None


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    period = request.args.get('period', 'month'); start = period_start(period); con = db(); where = "WHERE payment_status='Pago'"; params = []
    if start: where += ' AND created_at>=?'; params.append(start.isoformat(timespec='seconds'))
    sales_row = con.execute(f'SELECT COUNT(*) orders, COALESCE(SUM(total),0) sales FROM orders {where}', params).fetchone(); customers = con.execute('SELECT COUNT(*) c FROM customers').fetchone()['c']; pending = con.execute("SELECT COUNT(*) c FROM orders WHERE payment_status NOT IN ('Pago','Cancelado','Estornado')").fetchone()['c']; ticket = (sales_row['sales'] / sales_row['orders']) if sales_row['orders'] else 0
    best = con.execute(f'''SELECT oi.product_name, SUM(oi.qty) qty FROM order_items oi JOIN orders o ON o.id=oi.order_id {where.replace('payment_status', 'o.payment_status').replace('created_at', 'o.created_at')} GROUP BY oi.product_name ORDER BY qty DESC LIMIT 1''', params).fetchone(); liters = 0
    paid_items = con.execute(f'''SELECT oi.product_name,oi.qty FROM order_items oi JOIN orders o ON o.id=oi.order_id {where.replace('payment_status', 'o.payment_status').replace('created_at', 'o.created_at')}''', params).fetchall()
    for item in paid_items:
        m = re.search(r'(\d+)\s*[lL]\b', item['product_name'])
        if m: liters += int(m.group(1)) * int(item['qty'])
    low_threshold = setting_int('low_stock_threshold', 5); low_stock = con.execute('SELECT * FROM products WHERE active=1 AND stock<=? ORDER BY stock,name', (low_threshold,)).fetchall(); today = datetime.now().date().isoformat(); deliveries_today = con.execute("SELECT COUNT(*) c FROM orders WHERE fulfillment_type='Entrega' AND delivery_date=? AND order_status<>'Cancelado'", (today,)).fetchone()['c']; reservations = con.execute("SELECT COUNT(*) c FROM chopper_reservations WHERE event_date>=? AND status<>'Cancelada'", (today,)).fetchone()['c']; orders = con.execute('''SELECT o.*, c.name customer_name, c.phone customer_phone FROM orders o JOIN customers c ON c.id=o.customer_id ORDER BY o.id DESC LIMIT 40''').fetchall(); stats = {'orders': sales_row['orders'], 'sales': sales_row['sales'], 'customers': customers, 'pending': pending, 'ticket': ticket, 'liters': liters, 'best_product': best['product_name'] if best else '-', 'deliveries_today': deliveries_today, 'reservations': reservations}; con.close(); return render_template('admin_dashboard.html', stats=stats, orders=orders, low_stock=low_stock, period=period)


@app.route('/admin/products')
@admin_required
def admin_products():
    con = db(); products = con.execute('SELECT * FROM products ORDER BY id DESC').fetchall(); con.close(); return render_template('admin_products.html', products=products)


def save_upload(file):
    if not file or not file.filename: return ''
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS: return ''
    name = f'{uuid.uuid4().hex}.{ext}'; file.save(os.path.join(UPLOAD_DIR, name)); return name


@app.route('/admin/product/new', methods=['GET', 'POST'])
@admin_required
def admin_product_new():
    if request.method == 'POST':
        image = save_upload(request.files.get('image')); con = db(); con.execute('INSERT INTO products(name,description,price,stock,image,active,created_at) VALUES(?,?,?,?,?,?,?)', (request.form['name'], request.form.get('description', ''), float(request.form['price'].replace(',', '.')), int(request.form['stock']), image, 1 if request.form.get('active') else 0, now_iso())); con.commit(); con.close(); flash('Produto cadastrado.', 'success'); return redirect(url_for('admin_products'))
    return render_template('admin_product_form.html', p=None)


@app.route('/admin/product/<int:pid>', methods=['GET', 'POST'])
@admin_required
def admin_product_edit(pid):
    con = db(); p = con.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    if request.method == 'POST':
        image = p['image']; new = save_upload(request.files.get('image')); image = new or image; con.execute('UPDATE products SET name=?,description=?,price=?,stock=?,image=?,active=? WHERE id=?', (request.form['name'], request.form.get('description', ''), float(request.form['price'].replace(',', '.')), int(request.form['stock']), image, 1 if request.form.get('active') else 0, pid)); con.commit(); con.close(); flash('Produto atualizado.', 'success'); return redirect(url_for('admin_products'))
    con.close(); return render_template('admin_product_form.html', p=p)


def process_referral_bonus(con, customer_id):
    ref = con.execute("SELECT * FROM referrals WHERE referred_customer_id=? AND status='Pendente'", (customer_id,)).fetchone()
    if not ref: return
    paid_count = con.execute("SELECT COUNT(*) c FROM orders WHERE customer_id=? AND payment_status='Pago'", (customer_id,)).fetchone()['c']
    if paid_count < 1: return
    referrer_bonus = setting_int('referrer_bonus_points', 0); referred_bonus = setting_int('referred_bonus_points', 0)
    if referrer_bonus > 0: award_points(con, ref['referrer_customer_id'], referrer_bonus, 'Bônus por indicação', action_type='indicacao'); notify(con, ref['referrer_customer_id'], f'Você ganhou {referrer_bonus} ponto(s) por uma indicação concluída.')
    if referred_bonus > 0: award_points(con, customer_id, referred_bonus, 'Bônus por indicação recebida', action_type='indicacao'); notify(con, customer_id, f'Você ganhou {referred_bonus} ponto(s) por entrar através de uma indicação.')
    con.execute("UPDATE referrals SET status='Concluído' WHERE id=?", (ref['id'],))

