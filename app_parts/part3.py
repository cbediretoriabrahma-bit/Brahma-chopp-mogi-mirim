@app.context_processor
def globals_ctx():
    return dict(store_name='Chopp Brahma Mogi Mirim', slogan='Aqui tem oferta de verdade', address='Av. 22 de Outubro, 826 - Mogi Mirim/SP', phone='(19) 3806-2786', whatsapp='(19) 97401-9632', whatsapp_number=setting('whatsapp', '5519974019632'), customer_logged=bool(session.get('customer_id')), customer_name=session.get('customer_name', ''), cart_count=cart_count_value())


@app.route('/')
def home():
    con = db()
    products_raw = con.execute('SELECT * FROM products WHERE active=1 ORDER BY id DESC').fetchall()
    products = [product_view(con, p) for p in products_raw]
    combos = con.execute('SELECT * FROM combos WHERE active=1 AND stock<>0 ORDER BY id DESC').fetchall()
    now = datetime.now().strftime('%Y-%m-%dT%H:%M')
    promotions = con.execute('''SELECT pr.*, p.name product_name FROM promotions pr LEFT JOIN products p ON p.id=pr.product_id WHERE pr.active=1 AND pr.starts_at<=? AND pr.ends_at>=? ORDER BY pr.id DESC LIMIT 6''', (now, now)).fetchall()
    favorites = set()
    if session.get('customer_id'):
        favorites = {r['product_id'] for r in con.execute('SELECT product_id FROM favorites WHERE customer_id=?', (session['customer_id'],)).fetchall()}
    con.close()
    return render_template('home.html', products=products, combos=combos, promotions=promotions, favorites=favorites)


@app.route('/register', methods=['GET', 'POST'])
def register():
    referral_prefill = request.args.get('ref', '').strip().upper()
    if request.method == 'POST':
        name = request.form['name'].strip(); phone = request.form['phone'].strip(); email = request.form.get('email', '').strip(); password = request.form['password']; ref_code = request.form.get('referral_code', '').strip().upper()
        if len(password) < 4:
            flash('A senha precisa ter pelo menos 4 caracteres.', 'danger'); return redirect(url_for('register', ref=ref_code))
        con = db()
        try:
            cur = con.execute('INSERT INTO customers(name,phone,email,password_hash,referred_by_code,created_at) VALUES(?,?,?,?,?,?)', (name, phone, email, generate_password_hash(password), ref_code, now_iso()))
            cid = cur.lastrowid; own_code = f'BRAHMA{cid:05d}'; con.execute('UPDATE customers SET referral_code=? WHERE id=?', (own_code, cid))
            if ref_code:
                referrer = con.execute('SELECT id FROM customers WHERE referral_code=? AND id<>?', (ref_code, cid)).fetchone()
                if referrer:
                    con.execute('INSERT OR IGNORE INTO referrals(referrer_customer_id,referred_customer_id,code,created_at) VALUES(?,?,?,?)', (referrer['id'], cid, ref_code, now_iso()))
            con.commit(); session['customer_id'] = cid; session['customer_name'] = name; flash('Cadastro realizado!', 'success'); return redirect(url_for('home'))
        except sqlite3.IntegrityError:
            flash('Esse telefone já está cadastrado.', 'danger')
        finally:
            con.close()
    return render_template('register.html', referral_prefill=referral_prefill)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone'].strip(); password = request.form['password']; con = db(); c = con.execute('SELECT * FROM customers WHERE phone=?', (phone,)).fetchone(); con.close()
        if c and check_password_hash(c['password_hash'], password):
            session['customer_id'] = c['id']; session['customer_name'] = c['name']; return redirect(url_for('home'))
        flash('Telefone ou senha inválidos.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('customer_id', None); session.pop('customer_name', None); return redirect(url_for('home'))


@app.post('/cart/add/<int:pid>')
def cart_add(pid):
    cart = session.get('cart', {}); old_qty = cart.pop(str(pid), 0); key = f'p:{pid}'; cart[key] = int(cart.get(key, 0)) + int(old_qty) + 1; session['cart'] = cart; flash('Produto adicionado ao carrinho.', 'success'); return redirect(request.referrer or url_for('home'))


@app.post('/cart/add-combo/<int:cid>')
def cart_add_combo(cid):
    cart = session.get('cart', {}); key = f'c:{cid}'; cart[key] = int(cart.get(key, 0)) + 1; session['cart'] = cart; flash('Combo adicionado ao carrinho.', 'success'); return redirect(request.referrer or url_for('home'))


@app.route('/cart', methods=['GET', 'POST'])
def cart():
    if request.method == 'POST':
        new = {}
        for k, v in request.form.items():
            if not k.startswith('qty__'): continue
            key = k.split('qty__', 1)[1]
            try: q = int(v)
            except Exception: q = 1
            if q > 0: new[key] = q
        session['cart'] = new; flash('Carrinho atualizado.', 'success')
    items, subtotal = cart_data(); con = db(); ids = [i['id'] for i in items if i['kind'] == 'product']
    if ids:
        qs = ','.join('?' * len(ids)); suggestions = con.execute(f'SELECT * FROM products WHERE active=1 AND stock>0 AND id NOT IN ({qs}) ORDER BY id DESC LIMIT 4', ids).fetchall()
    else:
        suggestions = con.execute('SELECT * FROM products WHERE active=1 AND stock>0 ORDER BY id DESC LIMIT 4').fetchall()
    con.close()
    return render_template('cart.html', items=items, subtotal=subtotal, installation_fee=setting_float('installation_fee', 0), points_estimate=points_for_value(subtotal), suggestions=suggestions)


@app.route('/event', methods=['GET', 'POST'])
def event_planner():
    result = None
    if request.method == 'POST':
        try: people = max(1, int(request.form.get('people', 1)))
        except Exception: people = 1
        duration = request.form.get('duration', '4'); event_type = request.form.get('event_type', 'Festa'); event_date = request.form.get('event_date', ''); event_time = request.form.get('event_time', '')
        liters_per_person = max(setting_float('event_liters_per_person', 1.0), 0.1); target = int(math.ceil(people * liters_per_person)); con = db(); p30 = con.execute("SELECT * FROM products WHERE active=1 AND lower(name) LIKE '%30l%' ORDER BY id LIMIT 1").fetchone(); p50 = con.execute("SELECT * FROM products WHERE active=1 AND lower(name) LIKE '%50l%' ORDER BY id LIMIT 1").fetchone(); con.close()
        options = []
        for n50 in range(0, math.ceil(target / 50) + 2):
            for n30 in range(0, math.ceil(target / 30) + 2):
                total = n50 * 50 + n30 * 30
                if total >= target and total > 0: options.append((total - target, n50 + n30, total, n50, n30))
        options.sort(); _, _, total_liters, n50, n30 = options[0]; suggestion = []
        if n50 and p50: suggestion.append({'product': p50, 'qty': n50})
        if n30 and p30: suggestion.append({'product': p30, 'qty': n30})
        result = {'people': people, 'duration': duration, 'event_type': event_type, 'event_date': event_date, 'event_time': event_time, 'target_liters': target, 'suggested_liters': total_liters, 'suggestion': suggestion}
        if request.form.get('add_to_cart') == '1' and suggestion:
            cart = session.get('cart', {})
            for s in suggestion:
                key = f'p:{s["product"]["id"]}'; cart[key] = int(cart.get(key, 0)) + int(s['qty'])
            session['cart'] = cart; session['event_context'] = {'event_date': event_date, 'event_time': event_time, 'event_type': event_type}; flash('Sugestão do evento adicionada ao carrinho.', 'success'); return redirect(url_for('cart'))
    return render_template('event.html', result=result)


@app.post('/favorite/<int:pid>')
@customer_required
def favorite_toggle(pid):
    con = db(); row = con.execute('SELECT 1 FROM favorites WHERE customer_id=? AND product_id=?', (session['customer_id'], pid)).fetchone()
    if row:
        con.execute('DELETE FROM favorites WHERE customer_id=? AND product_id=?', (session['customer_id'], pid)); flash('Produto removido dos favoritos.', 'success')
    else:
        con.execute('INSERT OR IGNORE INTO favorites(customer_id,product_id,created_at) VALUES(?,?,?)', (session['customer_id'], pid, now_iso())); flash('Produto salvo nos favoritos.', 'success')
    con.commit(); con.close(); return redirect(request.referrer or url_for('home'))


@app.get('/api/chopper-availability')
def chopper_availability_api():
    date = request.args.get('date', ''); con = db(); configured = con.execute('SELECT COUNT(*) c FROM choppers WHERE active=1').fetchone()['c']; con.close(); available = available_choppers(date) if date else []
    if configured == 0: return jsonify({'configured': 0, 'available': 0, 'message': 'Disponibilidade será confirmada pela equipe.'})
    return jsonify({'configured': configured, 'available': len(available), 'message': 'Chopeira disponível.' if available else 'Chopeira indisponível para esta data.'})

