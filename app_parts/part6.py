@app.route('/admin/order/<int:oid>', methods=['GET', 'POST'])
@admin_required
def admin_order(oid):
    con = db(); o = con.execute('''SELECT o.*,c.name customer_name,c.phone customer_phone,c.points customer_points FROM orders o JOIN customers c ON c.id=o.customer_id WHERE o.id=?''', (oid,)).fetchone()
    if not o: con.close(); return redirect(url_for('admin_dashboard'))
    items = con.execute('SELECT * FROM order_items WHERE order_id=?', (oid,)).fetchall(); reservation = con.execute('''SELECT r.*,c.name chopper_name FROM chopper_reservations r JOIN choppers c ON c.id=r.chopper_id WHERE r.order_id=? LIMIT 1''', (oid,)).fetchone()
    if request.method == 'POST':
        oldpay = o['payment_status']; oldstatus = o['order_status']; newpay = request.form['payment_status']; status = request.form['order_status']; con.execute('UPDATE orders SET payment_status=?, order_status=? WHERE id=?', (newpay, status, oid))
        if newpay == 'Pago' and oldpay != 'Pago' and int(o['points_awarded'] or 0) == 0:
            pts = points_for_value(o['total'])
            if pts > 0: award_points(con, o['customer_id'], pts, f'Pontos do pedido #{oid}', oid, 'compra'); con.execute('UPDATE orders SET points_awarded=? WHERE id=?', (pts, oid)); notify(con, o['customer_id'], f'Pagamento do pedido #{oid} confirmado. Você ganhou {pts} ponto(s)!')
            process_referral_bonus(con, o['customer_id'])
        elif oldpay == 'Pago' and newpay in ('Cancelado', 'Estornado'):
            reverse_order_points(con, o); notify(con, o['customer_id'], f'Pagamento do pedido #{oid} foi {newpay.lower()}. Os pontos deste pedido foram ajustados.')
        if status != oldstatus: notify(con, o['customer_id'], f'Pedido #{oid}: status atualizado para {status}.')
        if status == 'Cancelado': con.execute("UPDATE chopper_reservations SET status='Cancelada' WHERE order_id=?", (oid,)); con.execute("UPDATE orders SET chopper_status=CASE WHEN needs_chopper=1 THEN 'Cancelada' ELSE chopper_status END WHERE id=?", (oid,))
        con.commit(); con.close(); flash('Pedido atualizado.', 'success'); return redirect(url_for('admin_order', oid=oid))
    con.close(); return render_template('admin_order.html', o=o, items=items, reservation=reservation)


@app.route('/admin/customers')
@admin_required
def admin_customers():
    con = db(); customers = con.execute('SELECT * FROM customers ORDER BY id DESC').fetchall(); con.close(); return render_template('admin_customers.html', customers=customers)


@app.route('/admin/customer/<int:cid>')
@admin_required
def admin_customer(cid):
    con = db(); c = con.execute('SELECT * FROM customers WHERE id=?', (cid,)).fetchone(); orders = con.execute('SELECT * FROM orders WHERE customer_id=? ORDER BY id DESC', (cid,)).fetchall(); ledger = con.execute('SELECT * FROM points_ledger WHERE customer_id=? ORDER BY id DESC', (cid,)).fetchall(); redemptions = con.execute('''SELECT rr.*,rw.name reward_name FROM reward_redemptions rr JOIN rewards rw ON rw.id=rr.reward_id WHERE rr.customer_id=? ORDER BY rr.id DESC''', (cid,)).fetchall(); con.close(); return render_template('admin_customer.html', c=c, orders=orders, ledger=ledger, redemptions=redemptions)


@app.post('/admin/customer/<int:cid>/points')
@admin_required
def admin_customer_points(cid):
    try: delta = int(request.form.get('points', '0'))
    except Exception: delta = 0
    reason = request.form.get('reason', 'Ajuste administrativo').strip() or 'Ajuste administrativo'; con = db()
    if delta > 0: award_points(con, cid, delta, reason, action_type='ajuste')
    elif delta < 0: consume_points(con, cid, min(abs(delta), con.execute('SELECT points FROM customers WHERE id=?', (cid,)).fetchone()['points']), reason, 'ajuste')
    con.commit(); con.close(); flash('Pontuação ajustada.', 'success'); return redirect(url_for('admin_customer', cid=cid))


@app.route('/admin/promotions', methods=['GET', 'POST'])
@admin_required
def admin_promotions():
    con = db()
    if request.method == 'POST':
        con.execute('''INSERT INTO promotions(title,product_id,promo_price,starts_at,ends_at,qty_limit,active,created_at) VALUES(?,?,?,?,?,?,1,?)''', (request.form['title'].strip(), int(request.form['product_id']), float(request.form['promo_price'].replace(',', '.')), request.form['starts_at'], request.form['ends_at'], int(request.form.get('qty_limit') or 0), now_iso())); con.commit(); con.close(); flash('Promoção criada.', 'success'); return redirect(url_for('admin_promotions'))
    promotions = con.execute('''SELECT pr.*,p.name product_name FROM promotions pr LEFT JOIN products p ON p.id=pr.product_id ORDER BY pr.id DESC''').fetchall(); products = con.execute('SELECT * FROM products WHERE active=1 ORDER BY name').fetchall(); con.close(); return render_template('admin_promotions.html', promotions=promotions, products=products)


@app.post('/admin/promotion/<int:pid>/toggle')
@admin_required
def admin_promotion_toggle(pid):
    con = db(); con.execute('UPDATE promotions SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?', (pid,)); con.commit(); con.close(); return redirect(url_for('admin_promotions'))


@app.route('/admin/combos', methods=['GET', 'POST'])
@admin_required
def admin_combos():
    con = db()
    if request.method == 'POST':
        con.execute('INSERT INTO combos(title,description,original_price,price,stock,active,created_at) VALUES(?,?,?,?,?,1,?)', (request.form['title'].strip(), request.form.get('description', '').strip(), float(request.form['original_price'].replace(',', '.')), float(request.form['price'].replace(',', '.')), int(request.form['stock']), now_iso())); con.commit(); con.close(); flash('Combo criado.', 'success'); return redirect(url_for('admin_combos'))
    combos = con.execute('SELECT * FROM combos ORDER BY id DESC').fetchall(); con.close(); return render_template('admin_combos.html', combos=combos)


@app.post('/admin/combo/<int:cid>/toggle')
@admin_required
def admin_combo_toggle(cid):
    con = db(); con.execute('UPDATE combos SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?', (cid,)); con.commit(); con.close(); return redirect(url_for('admin_combos'))


@app.route('/admin/rewards', methods=['GET', 'POST'])
@admin_required
def admin_rewards():
    con = db()
    if request.method == 'POST':
        con.execute('INSERT INTO rewards(name,description,points_cost,stock,active,created_at) VALUES(?,?,?,?,1,?)', (request.form['name'].strip(), request.form.get('description', '').strip(), int(request.form['points_cost']), int(request.form.get('stock', '-1')), now_iso())); con.commit(); con.close(); flash('Benefício criado.', 'success'); return redirect(url_for('admin_rewards'))
    rewards = con.execute('SELECT * FROM rewards ORDER BY points_cost,id').fetchall(); redemptions = con.execute('''SELECT rr.*,rw.name reward_name,c.name customer_name FROM reward_redemptions rr JOIN rewards rw ON rw.id=rr.reward_id JOIN customers c ON c.id=rr.customer_id ORDER BY rr.id DESC LIMIT 50''').fetchall(); con.close(); return render_template('admin_rewards.html', rewards=rewards, redemptions=redemptions)


@app.post('/admin/reward/<int:rid>/toggle')
@admin_required
def admin_reward_toggle(rid):
    con = db(); con.execute('UPDATE rewards SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?', (rid,)); con.commit(); con.close(); return redirect(url_for('admin_rewards'))


@app.post('/admin/redemption/<int:rid>/status')
@admin_required
def admin_redemption_status(rid):
    status = request.form.get('status', 'Concluído'); con = db(); row = con.execute('SELECT * FROM reward_redemptions WHERE id=?', (rid,)).fetchone()
    if row: con.execute('UPDATE reward_redemptions SET status=? WHERE id=?', (status, rid)); notify(con, row['customer_id'], f'Seu resgate #{rid} foi atualizado para: {status}.'); con.commit()
    con.close(); return redirect(url_for('admin_rewards'))


@app.route('/admin/choppers', methods=['GET', 'POST'])
@admin_required
def admin_choppers():
    con = db()
    if request.method == 'POST': con.execute('INSERT INTO choppers(name,active,created_at) VALUES(?,1,?)', (request.form['name'].strip(), now_iso())); con.commit(); con.close(); flash('Chopeira cadastrada.', 'success'); return redirect(url_for('admin_choppers'))
    choppers = con.execute('SELECT * FROM choppers ORDER BY id').fetchall(); reservations = con.execute('''SELECT r.*,ch.name chopper_name,c.name customer_name,o.id order_id FROM chopper_reservations r JOIN choppers ch ON ch.id=r.chopper_id JOIN customers c ON c.id=r.customer_id JOIN orders o ON o.id=r.order_id ORDER BY r.event_date DESC,r.id DESC LIMIT 100''').fetchall(); con.close(); return render_template('admin_choppers.html', choppers=choppers, reservations=reservations)


@app.post('/admin/chopper/<int:cid>/toggle')
@admin_required
def admin_chopper_toggle(cid):
    con = db(); con.execute('UPDATE choppers SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?', (cid,)); con.commit(); con.close(); return redirect(url_for('admin_choppers'))


@app.route('/admin/reviews')
@admin_required
def admin_reviews():
    con = db(); reviews = con.execute('''SELECT r.*,c.name customer_name FROM reviews r JOIN customers c ON c.id=r.customer_id ORDER BY r.id DESC''').fetchall(); con.close(); return render_template('admin_reviews.html', reviews=reviews)


@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    keys = ['installation_fee', 'delivery_fee', 'pix_key', 'payment_methods', 'whatsapp', 'points_reais_per_point', 'points_validity_days', 'low_stock_threshold', 'event_liters_per_person', 'referrer_bonus_points', 'referred_bonus_points', 'delivery_slots']
    if request.method == 'POST':
        con = db()
        for k in keys: con.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (k, request.form.get(k, '')))
        con.commit(); con.close(); flash('Configurações salvas.', 'success'); return redirect(url_for('admin_settings'))
    values = {k: setting(k) for k in keys}; return render_template('admin_settings.html', **values)


@app.route('/manifest.json')
def manifest():
    return jsonify({'name': 'Chopp Brahma Mogi Mirim', 'short_name': 'Chopp Brahma', 'start_url': '/', 'display': 'standalone', 'background_color': '#f4ead7', 'theme_color': '#d71920', 'icons': [{'src': '/static/capa_brahma.jpg', 'sizes': '512x512', 'type': 'image/jpeg'}]})


@app.route('/service-worker.js')
def sw():
    return app.send_static_file('service-worker.js')


if __name__ == '__main__':
    init_db(); app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=True)
else:
    init_db()
