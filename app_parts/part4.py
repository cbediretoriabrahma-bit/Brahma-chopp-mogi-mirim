@app.route('/checkout', methods=['GET', 'POST'])
@customer_required
def checkout():
    items, subtotal = cart_data()
    if not items: return redirect(url_for('home'))
    methods = [x.strip() for x in setting('payment_methods', 'Pix').split(',') if x.strip()]
    install_fee = setting_float('installation_fee', 0); delivery_fee = setting_float('delivery_fee', 0); slots = [x.strip() for x in setting('delivery_slots', '').split('|') if x.strip()]; event_context = session.get('event_context', {})
    if request.method == 'POST':
        needs_installation = request.form.get('installation') == '1'; fulfillment = request.form.get('fulfillment_type', 'Entrega'); delivery_date = request.form.get('delivery_date', ''); delivery_slot = request.form.get('delivery_slot', ''); delivery_address = request.form.get('delivery_address', '').strip(); event_date = request.form.get('event_date', ''); event_time = request.form.get('event_time', ''); needs_chopper = request.form.get('needs_chopper') == '1'; payment = request.form['payment_method']; notes = request.form.get('notes', '').strip()
        if fulfillment == 'Entrega' and (not delivery_date or not delivery_address): flash('Informe a data e o endereço da entrega.', 'danger'); return redirect(url_for('checkout'))
        if needs_chopper and not event_date: flash('Informe a data do evento para reservar a chopeira.', 'danger'); return redirect(url_for('checkout'))
        con = db(); configured_choppers = con.execute('SELECT COUNT(*) c FROM choppers WHERE active=1').fetchone()['c']; selected_chopper = None
        if needs_chopper and configured_choppers > 0:
            available = con.execute('''SELECT c.* FROM choppers c WHERE c.active=1 AND NOT EXISTS (SELECT 1 FROM chopper_reservations r WHERE r.chopper_id=c.id AND r.event_date=? AND r.status<>'Cancelada') ORDER BY c.id LIMIT 1''', (event_date,)).fetchone()
            if not available: con.close(); flash('Não há chopeira disponível para esta data. Escolha outra data ou finalize sem chopeira.', 'danger'); return redirect(url_for('checkout'))
            selected_chopper = available
        for i in items:
            row = con.execute('SELECT stock FROM products WHERE id=?', (i['id'],)).fetchone() if i['kind'] == 'product' else con.execute('SELECT stock FROM combos WHERE id=?', (i['id'],)).fetchone()
            if not row or (row['stock'] >= 0 and row['stock'] < i['qty']): con.close(); flash(f'Estoque insuficiente para {i["name"]}. Ajuste a quantidade.', 'danger'); return redirect(url_for('cart'))
        fee = install_fee if needs_installation else 0.0; dfee = delivery_fee if fulfillment == 'Entrega' else 0.0; total = subtotal + fee + dfee; chopper_status = 'Não solicitado'
        if needs_chopper: chopper_status = 'Reservada' if selected_chopper else 'A confirmar'
        cur = con.execute('''INSERT INTO orders(customer_id,subtotal,installation_fee,total,payment_method,notes,created_at,fulfillment_type,delivery_date,delivery_slot,delivery_address,event_date,event_time,needs_chopper,chopper_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (session['customer_id'], subtotal, fee + dfee, total, payment, notes, now_iso(), fulfillment, delivery_date, delivery_slot, delivery_address, event_date, event_time, 1 if needs_chopper else 0, chopper_status))
        oid = cur.lastrowid
        for i in items:
            product_id = i['id'] if i['kind'] == 'product' else None
            con.execute('''INSERT INTO order_items(order_id,product_id,product_name,qty,unit_price,line_total,item_type,source_id) VALUES(?,?,?,?,?,?,?,?)''', (oid, product_id, i['name'], i['qty'], i['unit_price'], i['line'], i['kind'], i['id']))
            table = 'products' if i['kind'] == 'product' else 'combos'; con.execute(f'UPDATE {table} SET stock=CASE WHEN stock<0 THEN stock ELSE stock-? END WHERE id=?', (i['qty'], i['id']))
        if selected_chopper: con.execute('''INSERT INTO chopper_reservations(chopper_id,order_id,customer_id,event_date,status,created_at) VALUES(?,?,?,?,?,?)''', (selected_chopper['id'], oid, session['customer_id'], event_date, 'Reservada', now_iso()))
        notify(con, session['customer_id'], f'Pedido #{oid} recebido. Acompanhe o status pela sua conta.'); con.commit(); con.close(); session['cart'] = {}; session.pop('event_context', None); flash(f'Pedido #{oid} criado. Os pontos serão liberados após a confirmação do pagamento.', 'success'); return redirect(url_for('account'))
    return render_template('checkout.html', items=items, subtotal=subtotal, methods=methods, installation_fee=install_fee, delivery_fee=delivery_fee, pix_key=setting('pix_key'), slots=slots, points_estimate=points_for_value(subtotal), event_context=event_context)


@app.post('/order/<int:oid>/reorder')
@customer_required
def reorder(oid):
    con = db(); order = con.execute('SELECT * FROM orders WHERE id=? AND customer_id=?', (oid, session['customer_id'])).fetchone()
    if not order: con.close(); flash('Pedido não encontrado.', 'danger'); return redirect(url_for('account'))
    items = con.execute('SELECT * FROM order_items WHERE order_id=?', (oid,)).fetchall(); cart = session.get('cart', {})
    for item in items:
        kind = item['item_type'] or 'product'; source_id = item['source_id'] or item['product_id']
        if not source_id: continue
        key = f'c:{source_id}' if kind == 'combo' else f'p:{source_id}'; cart[key] = int(cart.get(key, 0)) + int(item['qty'])
    session['cart'] = cart; con.close(); flash(f'Itens do pedido #{oid} adicionados ao carrinho.', 'success'); return redirect(url_for('cart'))


@app.post('/order/<int:oid>/review')
@customer_required
def review_order(oid):
    con = db(); order = con.execute('SELECT * FROM orders WHERE id=? AND customer_id=?', (oid, session['customer_id'])).fetchone()
    if not order or order['order_status'] != 'Entregue': con.close(); flash('A avaliação fica disponível após a entrega.', 'warning'); return redirect(url_for('account'))
    try: rating = min(5, max(1, int(request.form.get('rating', 5))))
    except Exception: rating = 5
    comment = request.form.get('comment', '').strip(); con.execute('''INSERT INTO reviews(order_id,customer_id,rating,comment,created_at) VALUES(?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET rating=excluded.rating,comment=excluded.comment''', (oid, session['customer_id'], rating, comment, now_iso())); con.commit(); con.close(); flash('Obrigado pela avaliação!', 'success'); return redirect(url_for('account'))


@app.post('/loyalty/redeem/<int:rid>')
@customer_required
def redeem_reward(rid):
    expire_points(session['customer_id']); con = db(); reward = con.execute('SELECT * FROM rewards WHERE id=? AND active=1', (rid,)).fetchone()
    if not reward: con.close(); flash('Benefício indisponível.', 'danger'); return redirect(url_for('account'))
    if reward['stock'] == 0: con.close(); flash('Benefício sem estoque no momento.', 'warning'); return redirect(url_for('account'))
    ok = consume_points(con, session['customer_id'], reward['points_cost'], f'Resgate: {reward["name"]}', 'resgate')
    if not ok: con.close(); flash('Você ainda não tem pontos suficientes para este benefício.', 'warning'); return redirect(url_for('account'))
    con.execute('INSERT INTO reward_redemptions(customer_id,reward_id,points_cost,status,created_at) VALUES(?,?,?,?,?)', (session['customer_id'], rid, reward['points_cost'], 'Solicitado', now_iso()))
    if reward['stock'] > 0: con.execute('UPDATE rewards SET stock=stock-1 WHERE id=?', (rid,))
    notify(con, session['customer_id'], f'Benefício "{reward["name"]}" resgatado com sucesso.'); con.commit(); con.close(); flash('Benefício resgatado com sucesso.', 'success'); return redirect(url_for('account'))


@app.route('/account')
@customer_required
def account():
    expire_points(session['customer_id']); con = db(); cid = session['customer_id']; c = con.execute('SELECT * FROM customers WHERE id=?', (cid,)).fetchone()
    orders = con.execute('''SELECT o.*, r.rating review_rating FROM orders o LEFT JOIN reviews r ON r.order_id=o.id WHERE o.customer_id=? ORDER BY o.id DESC''', (cid,)).fetchall(); ledger = con.execute('SELECT * FROM points_ledger WHERE customer_id=? ORDER BY id DESC LIMIT 80', (cid,)).fetchall(); rewards = con.execute('SELECT * FROM rewards WHERE active=1 AND stock<>0 ORDER BY points_cost,id').fetchall(); redemptions = con.execute('''SELECT rr.*, rw.name reward_name FROM reward_redemptions rr JOIN rewards rw ON rw.id=rr.reward_id WHERE rr.customer_id=? ORDER BY rr.id DESC''', (cid,)).fetchall(); favorites = con.execute('''SELECT p.* FROM favorites f JOIN products p ON p.id=f.product_id WHERE f.customer_id=? AND p.active=1 ORDER BY f.created_at DESC''', (cid,)).fetchall(); notifications = con.execute('SELECT * FROM notifications WHERE customer_id=? ORDER BY id DESC LIMIT 20', (cid,)).fetchall(); referrals = con.execute('SELECT COUNT(*) c FROM referrals WHERE referrer_customer_id=?', (cid,)).fetchone()['c']; upcoming = con.execute('''SELECT COALESCE(SUM(remaining_points),0) pts FROM points_ledger WHERE customer_id=? AND points>0 AND remaining_points>0 AND expired=0 AND expires_at<>'' AND expires_at<=?''', (cid, (datetime.now() + timedelta(days=30)).isoformat(timespec='seconds'))).fetchone()['pts']; con.execute("UPDATE notifications SET read_at=? WHERE customer_id=? AND COALESCE(read_at,'')=''", (now_iso(), cid)); con.commit(); con.close(); share_link = url_for('register', ref=c['referral_code'], _external=True)
    return render_template('account.html', c=c, orders=orders, ledger=ledger, rewards=rewards, redemptions=redemptions, favorites=favorites, notifications=notifications, referral_count=referrals, share_link=share_link, upcoming_points=upcoming, points_reais_per_point=setting_float('points_reais_per_point', 10))


# ---------------- ADMIN ----------------
