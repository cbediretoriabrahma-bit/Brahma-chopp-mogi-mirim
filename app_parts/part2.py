def setting(key, default=''):
    con = db()
    row = con.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    con.close()
    return row['value'] if row else default


def setting_float(key, default=0.0):
    try:
        return float(setting(key, str(default)).replace(',', '.'))
    except Exception:
        return float(default)


def setting_int(key, default=0):
    try:
        return int(float(setting(key, str(default))))
    except Exception:
        return int(default)


def money(v):
    return f"R$ {float(v):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


app.jinja_env.filters['money'] = money


def customer_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('customer_id'):
            flash('Entre na sua conta para continuar.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapper


def notify(con, customer_id, message):
    con.execute('INSERT INTO notifications(customer_id,message,created_at) VALUES(?,?,?)', (customer_id, message, now_iso()))


def expire_points(customer_id):
    con = db()
    now = now_iso()
    rows = con.execute('''SELECT * FROM points_ledger WHERE customer_id=? AND points>0 AND remaining_points>0 AND expired=0 AND COALESCE(expires_at,'')<>'' AND expires_at<=?''', (customer_id, now)).fetchall()
    total = sum(r['remaining_points'] for r in rows)
    if total > 0:
        current = con.execute('SELECT points FROM customers WHERE id=?', (customer_id,)).fetchone()['points']
        deducted = min(current, total)
        ids = [r['id'] for r in rows]
        q = ','.join('?' * len(ids))
        con.execute(f'UPDATE points_ledger SET remaining_points=0, expired=1 WHERE id IN ({q})', ids)
        con.execute('UPDATE customers SET points=MAX(points-?,0) WHERE id=?', (deducted, customer_id))
        con.execute('''INSERT INTO points_ledger(customer_id,points,description,created_at,remaining_points,expired,action_type) VALUES(?,?,?,?,0,0,'expiracao')''', (customer_id, -deducted, 'Pontos expirados', now))
        notify(con, customer_id, f'{deducted} ponto(s) expiraram conforme a validade do programa.')
        con.commit()
    con.close()


def award_points(con, customer_id, points, description, order_id=None, action_type='credito'):
    points = int(points)
    if points <= 0:
        return 0
    validity = setting_int('points_validity_days', 365)
    expires = (datetime.now() + timedelta(days=validity)).isoformat(timespec='seconds')
    con.execute('UPDATE customers SET points=points+? WHERE id=?', (points, customer_id))
    con.execute('''INSERT INTO points_ledger(customer_id,order_id,points,description,created_at,expires_at,remaining_points,expired,action_type) VALUES(?,?,?,?,?,?,?,?,?)''', (customer_id, order_id, points, description, now_iso(), expires, points, 0, action_type))
    return points


def consume_points(con, customer_id, points, description, action_type='resgate'):
    points = int(points)
    customer = con.execute('SELECT points FROM customers WHERE id=?', (customer_id,)).fetchone()
    if not customer or customer['points'] < points:
        return False
    need = points
    credits = con.execute('''SELECT * FROM points_ledger WHERE customer_id=? AND points>0 AND remaining_points>0 AND expired=0 ORDER BY CASE WHEN COALESCE(expires_at,'')='' THEN 1 ELSE 0 END, expires_at, id''', (customer_id,)).fetchall()
    for credit in credits:
        if need <= 0:
            break
        use = min(need, credit['remaining_points'])
        con.execute('UPDATE points_ledger SET remaining_points=remaining_points-? WHERE id=?', (use, credit['id']))
        need -= use
    con.execute('UPDATE customers SET points=MAX(points-?,0) WHERE id=?', (points, customer_id))
    con.execute('''INSERT INTO points_ledger(customer_id,points,description,created_at,remaining_points,expired,action_type) VALUES(?,?,?,?,0,0,?)''', (customer_id, -points, description, now_iso(), action_type))
    return True


def reverse_order_points(con, order_row):
    pts = int(order_row['points_awarded'] or 0)
    if pts <= 0:
        return
    credits = con.execute('SELECT id FROM points_ledger WHERE customer_id=? AND order_id=? AND points>0', (order_row['customer_id'], order_row['id'])).fetchall()
    for c in credits:
        con.execute('UPDATE points_ledger SET remaining_points=0 WHERE id=?', (c['id'],))
    current = con.execute('SELECT points FROM customers WHERE id=?', (order_row['customer_id'],)).fetchone()['points']
    deducted = min(current, pts)
    con.execute('UPDATE customers SET points=MAX(points-?,0) WHERE id=?', (deducted, order_row['customer_id']))
    con.execute('UPDATE orders SET points_awarded=0 WHERE id=?', (order_row['id'],))
    con.execute('''INSERT INTO points_ledger(customer_id,order_id,points,description,created_at,remaining_points,expired,action_type) VALUES(?,?,?,?,?,0,0,'estorno')''', (order_row['customer_id'], order_row['id'], -deducted, f'Estorno de pontos do pedido #{order_row["id"]}', now_iso()))


def active_promotion(con, product_id):
    now = datetime.now().strftime('%Y-%m-%dT%H:%M')
    return con.execute('''SELECT * FROM promotions WHERE active=1 AND product_id=? AND starts_at<=? AND ends_at>=? ORDER BY id DESC LIMIT 1''', (product_id, now, now)).fetchone()


def product_view(con, row):
    p = dict(row)
    promo = active_promotion(con, row['id'])
    p['normal_price'] = row['price']
    p['promo_price'] = promo['promo_price'] if promo and promo['promo_price'] is not None else None
    p['effective_price'] = p['promo_price'] if p['promo_price'] is not None else row['price']
    p['promotion_title'] = promo['title'] if promo else ''
    return p


def cart_data():
    cart = session.get('cart', {})
    if not cart:
        return [], 0.0
    con = db()
    items = []
    subtotal = 0.0
    for raw_key, raw_qty in cart.items():
        try:
            qty = max(1, int(raw_qty))
        except Exception:
            qty = 1
        if raw_key.startswith('c:'):
            cid = int(raw_key.split(':', 1)[1])
            c = con.execute('SELECT * FROM combos WHERE id=? AND active=1', (cid,)).fetchone()
            if not c:
                continue
            unit = float(c['price'])
            line = unit * qty
            items.append({'key': raw_key, 'kind': 'combo', 'id': cid, 'name': c['title'], 'qty': qty, 'unit_price': unit, 'line': line, 'row': c})
        else:
            pid = int(raw_key.split(':', 1)[1]) if raw_key.startswith('p:') else int(raw_key)
            p = con.execute('SELECT * FROM products WHERE id=? AND active=1', (pid,)).fetchone()
            if not p:
                continue
            pv = product_view(con, p)
            unit = float(pv['effective_price'])
            line = unit * qty
            items.append({'key': f'p:{pid}', 'kind': 'product', 'id': pid, 'name': p['name'], 'qty': qty, 'unit_price': unit, 'line': line, 'row': p})
        subtotal += line
    con.close()
    return items, subtotal


def points_for_value(value):
    reais_per_point = max(setting_float('points_reais_per_point', 10.0), 0.01)
    return int(math.floor(float(value) / reais_per_point))


def available_choppers(event_date):
    if not event_date:
        return []
    con = db()
    rows = con.execute('''SELECT c.* FROM choppers c WHERE c.active=1 AND NOT EXISTS (SELECT 1 FROM chopper_reservations r WHERE r.chopper_id=c.id AND r.event_date=? AND r.status<>'Cancelada') ORDER BY c.id''', (event_date,)).fetchall()
    con.close()
    return rows


def cart_count_value():
    try:
        return sum(int(v) for v in session.get('cart', {}).values())
    except Exception:
        return 0

