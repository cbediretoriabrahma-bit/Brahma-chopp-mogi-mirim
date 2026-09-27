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
    CREATE TABLE IF NOT EXISTS promotions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        product_id INTEGER,
        promo_price REAL,
        starts_at TEXT NOT NULL,
        ends_at TEXT NOT NULL,
        qty_limit INTEGER DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );
    CREATE TABLE IF NOT EXISTS combos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        original_price REAL NOT NULL DEFAULT 0,
        price REAL NOT NULL DEFAULT 0,
        stock INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS rewards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        points_cost INTEGER NOT NULL,
        stock INTEGER NOT NULL DEFAULT -1,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS reward_redemptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        reward_id INTEGER NOT NULL,
        points_cost INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'Solicitado',
        created_at TEXT NOT NULL,
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        FOREIGN KEY(reward_id) REFERENCES rewards(id)
    );
    CREATE TABLE IF NOT EXISTS favorites (
        customer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY(customer_id, product_id),
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    );
    CREATE TABLE IF NOT EXISTS choppers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS chopper_reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chopper_id INTEGER NOT NULL,
        order_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        event_date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Reservada',
        created_at TEXT NOT NULL,
        FOREIGN KEY(chopper_id) REFERENCES choppers(id),
        FOREIGN KEY(order_id) REFERENCES orders(id),
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    );
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_customer_id INTEGER NOT NULL,
        referred_customer_id INTEGER NOT NULL UNIQUE,
        code TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pendente',
        created_at TEXT NOT NULL,
        FOREIGN KEY(referrer_customer_id) REFERENCES customers(id),
        FOREIGN KEY(referred_customer_id) REFERENCES customers(id)
    );
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL UNIQUE,
        customer_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        comment TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id),
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        read_at TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    );
    ''')

    # Migrações seguras: preservam o banco e os dados existentes.
    ensure_column(con, 'customers', 'referral_code', "TEXT DEFAULT ''")
    ensure_column(con, 'customers', 'referred_by_code', "TEXT DEFAULT ''")
    ensure_column(con, 'orders', 'fulfillment_type', "TEXT DEFAULT 'Entrega'")
    ensure_column(con, 'orders', 'delivery_date', "TEXT DEFAULT ''")
    ensure_column(con, 'orders', 'delivery_slot', "TEXT DEFAULT ''")
    ensure_column(con, 'orders', 'delivery_address', "TEXT DEFAULT ''")
    ensure_column(con, 'orders', 'event_date', "TEXT DEFAULT ''")
    ensure_column(con, 'orders', 'event_time', "TEXT DEFAULT ''")
    ensure_column(con, 'orders', 'needs_chopper', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(con, 'orders', 'chopper_status', "TEXT DEFAULT 'Não solicitado'")
    ensure_column(con, 'order_items', 'item_type', "TEXT DEFAULT 'product'")
    ensure_column(con, 'order_items', 'source_id', 'INTEGER')
    ensure_column(con, 'points_ledger', 'expires_at', "TEXT DEFAULT ''")
    ensure_column(con, 'points_ledger', 'remaining_points', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(con, 'points_ledger', 'expired', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(con, 'points_ledger', 'action_type', "TEXT DEFAULT 'credito'")

    defaults = {
        'installation_fee': '59.00',
        'delivery_fee': '0.00',
        'pix_key': '19 97401-9632',
        'payment_methods': 'Pix,Cartão de crédito,Cartão de débito,Dinheiro',
        'whatsapp': '5519974019632',
        'points_reais_per_point': '10.00',
        'points_validity_days': '365',
        'low_stock_threshold': '5',
        'event_liters_per_person': '1.00',
        'referrer_bonus_points': '0',
        'referred_bonus_points': '0',
        'delivery_slots': '09h às 12h|12h às 15h|15h às 18h',
    }
    for k, v in defaults.items():
        con.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)', (k, v))

    customers = con.execute("SELECT id FROM customers WHERE COALESCE(referral_code,'')='' ").fetchall()
    for c in customers:
        con.execute('UPDATE customers SET referral_code=? WHERE id=?', (f'BRAHMA{c["id"]:05d}', c['id']))

    migrated = con.execute("SELECT value FROM settings WHERE key='migration_points_remaining_v2'").fetchone()
    if not migrated:
        old_credits = con.execute("SELECT id,points,created_at,remaining_points,expires_at FROM points_ledger WHERE points>0").fetchall()
        validity = int(float(defaults['points_validity_days']))
        for row in old_credits:
            updates = []
            params = []
            if not row['remaining_points']:
                updates.append('remaining_points=?')
                params.append(row['points'])
            if not row['expires_at']:
                try:
                    created = datetime.fromisoformat(row['created_at'])
                except Exception:
                    created = datetime.now()
                updates.append('expires_at=?')
                params.append((created + timedelta(days=validity)).isoformat(timespec='seconds'))
            if updates:
                params.append(row['id'])
                con.execute(f"UPDATE points_ledger SET {', '.join(updates)} WHERE id=?", params)
        con.execute("INSERT INTO settings(key,value) VALUES('migration_points_remaining_v2','1')")

    count = con.execute('SELECT COUNT(*) c FROM products').fetchone()['c']
    if count == 0:
        now = now_iso()
        seed = [
            ('Barril Chopp Brahma 30L', 'Chopp Brahma gelado para seu evento.', 495.00, 20, ''),
            ('Barril Chopp Brahma 50L', 'Ideal para festas maiores e confraternizações.', 825.00, 15, ''),
            ('Copo 400 ml', 'Copo para servir seu chopp.', 3.50, 200, ''),
            ('Copo 700 ml', 'Copo grande para servir seu chopp.', 5.00, 150, ''),
        ]
        con.executemany(
            'INSERT INTO products(name,description,price,stock,image,created_at) VALUES(?,?,?,?,?,?)',
            [(a, b, c, d, e, now) for a, b, c, d, e in seed],
        )
    con.commit()
    con.close()

