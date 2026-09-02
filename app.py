from flask import Flask, request, jsonify, session, redirect, render_template_string
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "mude-em-producao")

db_url = os.environ.get("DATABASE_URL", "sqlite:///cervejeiros.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    description = db.Column(db.String(300), default="")
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.Text, default="")
    emoji = db.Column(db.String(20), default="🍺")
    active = db.Column(db.Boolean, default=True)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    phone = db.Column(db.String(50), nullable=False, index=True)
    email = db.Column(db.String(140), default="")

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False)
    customer = db.relationship("Customer")
    delivery_type = db.Column(db.String(20), default="pickup")
    address = db.Column(db.String(350), default="")
    desired_date = db.Column(db.String(30), default="")
    notes = db.Column(db.String(700), default="")
    subtotal = db.Column(db.Float, default=0)
    delivery_fee = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    status = db.Column(db.String(60), default="Aguardando pagamento")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship("OrderItem", cascade="all, delete-orphan")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, nullable=False)
    product_name = db.Column(db.String(140), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)

class Setting(db.Model):
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, default="")

def gs(key, default=""):
    row = db.session.get(Setting, key)
    return row.value if row else default

def ss(key, value):
    row = db.session.get(Setting, key)
    if row:
        row.value = str(value)
    else:
        db.session.add(Setting(key=key, value=str(value)))

def seed():
    if Product.query.count() == 0:
        db.session.add_all([
            Product(name="Barril Brahma 30 L", description="Barril de chopp Brahma 30 litros", price=567, stock=20, emoji="🛢️"),
            Product(name="Barril Brahma 50 L", description="Barril de chopp Brahma 50 litros", price=895, stock=20, emoji="🛢️"),
            Product(name="Chopeira elétrica", description="Para festas e eventos", price=1490, stock=6, emoji="🍺"),
            Product(name="Chopeira a gelo", description="Chopeira prática", price=890, stock=8, emoji="🧊"),
            Product(name="Copos 400 ml • 50 un.", description="Pacote com 50 copos", price=39.90, stock=60, emoji="🥤"),
            Product(name="Copos 700 ml • 50 un.", description="Pacote com 50 copos", price=59.90, stock=60, emoji="🥤"),
            Product(name="Growler 1 L", description="Growler para levar seu chopp", price=39.90, stock=30, emoji="🍶"),
        ])
    if not db.session.get(Setting, "delivery_fee"): ss("delivery_fee", "59")
    if not db.session.get(Setting, "pix_key"): ss("pix_key", "")
    if not db.session.get(Setting, "whatsapp"): ss("whatsapp", "5519974019632")
    if not db.session.get(Setting, "admin_hash"): ss("admin_hash", generate_password_hash("1234"))
    db.session.commit()

STYLE = """
<style>
:root{--r:#b41018;--bg:#f4f4f2;--dark:#171717;--line:#e5e5e1;--muted:#6d7278;--green:#198754}
*{box-sizing:border-box}body{margin:0;background:var(--bg);font-family:Arial,sans-serif;color:#171717;padding-bottom:35px}
header{background:linear-gradient(135deg,#a50e16,#d71920);color:#fff;padding:14px 16px;position:sticky;top:0;z-index:20}
.wrap{max-width:820px;margin:auto}.brand{display:flex;justify-content:space-between;align-items:center;gap:10px}.brand h1{font-size:19px;margin:0}
.hero{background:#191919;color:#fff;padding:25px 16px}.hero h2{margin:0 0 8px;font-size:29px}.hero p{margin:0;color:#ddd}
main{padding:16px}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:13px;margin-bottom:12px}
.pic{height:112px;border-radius:13px;background:#f2efea;display:grid;place-items:center;overflow:hidden}.pic img{width:100%;height:100%;object-fit:cover}.emoji{font-size:48px}
h2{margin-top:24px}.card h3{font-size:15px;margin:10px 0 4px}.desc{font-size:12px;color:var(--muted);min-height:28px}.price{font-size:20px;font-weight:900;color:var(--r);margin:8px 0}.stock{font-size:12px;font-weight:800;color:var(--green)}
button{border:0;border-radius:11px;padding:10px 12px;font-weight:800;cursor:pointer}.primary{background:var(--r);color:#fff}.dark{background:#171717;color:#fff}.light{background:#eee;color:#222}.full{width:100%}
label{font-size:13px;font-weight:800;display:block}input,textarea,select{width:100%;padding:10px;border:1px solid #d7d7d3;border-radius:10px;margin:6px 0 11px;background:#fff}
.line{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px dashed #ddd}.total{font-size:22px;color:var(--r);font-weight:900}.qty button{padding:4px 9px;background:#eee;color:#111}.qty{display:flex;gap:8px;align-items:center;margin-top:5px}
.notice{background:#fff5ce;border:1px solid #ecd26a;border-radius:12px;padding:11px;font-size:13px}.success{background:#e9f7ee;border:1px solid #b9dfc6;border-radius:12px;padding:12px}
.tabs{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:13px}.tabs button{border-radius:999px}.hidden{display:none}.scroll{overflow:auto}
table{width:100%;border-collapse:collapse;font-size:12px}th,td{padding:8px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}
.status{font-weight:800}.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:520px){.grid,.two{grid-template-columns:1fr 1fr}.hero h2{font-size:26px}}
</style>
"""

STORE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cervejeiros</title>""" + STYLE + """</head><body>
<header><div class="wrap brand"><div><h1>🍺 Brahma Chopp Mogi Mirim</h1><small>Chopp Brahma</small></div><button class="light" onclick="document.getElementById('checkout').scrollIntoView()">🛒 <span id="count">0</span></button></div></header>
<section class="hero"><div class="wrap"><h2>Brahma Chopp Mogi Mirim</h2><p>Barris, chopeiras, copos e growlers. Retirada ou entrega.</p></div></section>
<main class="wrap">
<div class="card" style="margin-top:14px">
<b>WhatsApp:</b> <a href="https://wa.me/5519974019632" target="_blank">(19) 97401-9632</a><br>
<b>Telefone:</b> <a href="tel:+551938062786">(19) 3806-2786</a><br>
<b>Endereço:</b> Av. 22 de Outubro, 826 • Mogi Mirim
</div>
<h2>Produtos</h2><div id="products" class="grid"></div>
<h2 id="checkout">Carrinho</h2><div class="card"><div id="cart"></div><div class="line"><span>Subtotal</span><b id="sub">R$ 0,00</b></div><div class="line"><span>Entrega</span><b id="fee">R$ 0,00</b></div><div class="line total"><span>Total</span><span id="tot">R$ 0,00</span></div></div>
<h2>Dados do cliente</h2><div class="card">
<label>Nome<input id="name"></label><label>WhatsApp<input id="phone"></label><label>E-mail<input id="email" type="email"></label>
<label>Recebimento<select id="delivery"><option value="pickup">Retirada</option><option value="delivery">Entrega</option></select></label>
<div id="abox" class="hidden"><label>Endereço completo<input id="address"></label></div>
<label>Data desejada<input id="date" type="date"></label><label>Observações<textarea id="notes" rows="3"></textarea></label>
<button class="dark full" onclick="finish()">Finalizar pedido</button><div id="result" style="margin-top:12px"></div></div>
<p style="text-align:center"><a href="/admin">Painel administrativo</a></p>
</main>
<script>
let P=[],C={},SET={delivery_fee:59}; const M=v=>Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
async function load(){P=await fetch('/api/products').then(r=>r.json());SET=await fetch('/api/public-settings').then(r=>r.json());rp();rc()}
function pic(p){return p.image?`<img src="${p.image}">`:`<div class="emoji">${p.emoji||'🍺'}</div>`}
function rp(){products.innerHTML=P.map(p=>`<div class="card"><div class="pic">${pic(p)}</div><h3>${p.name}</h3><div class="desc">${p.description||''}</div><div class="stock">Estoque: ${p.stock}</div><div class="price">${M(p.price)}</div><button class="primary full" ${p.stock<=0?'disabled':''} onclick="add(${p.id})">Adicionar</button></div>`).join('')}
function add(id){let p=P.find(x=>x.id===id);C[id]=(C[id]||0)+1;if(C[id]>p.stock)C[id]=p.stock;rc()}
function q(id,d){C[id]=(C[id]||0)+d;if(C[id]<=0)delete C[id];rc()}
function calc(){let s=0,c=0;Object.entries(C).forEach(([id,q])=>{let p=P.find(x=>x.id==id);s+=p.price*q;c+=q});let f=delivery.value==='delivery'?Number(SET.delivery_fee):0;return{s,f,t:s+f,c}}
function rc(){let h='';Object.entries(C).forEach(([id,qv])=>{let p=P.find(x=>x.id==id);h+=`<div class="line"><div><b>${p.name}</b><div class="qty"><button onclick="q(${id},-1)">−</button>${qv}<button onclick="q(${id},1)">+</button></div></div><b>${M(p.price*qv)}</b></div>`});cart.innerHTML=h||'<p>Carrinho vazio.</p>';let x=calc();count.textContent=x.c;sub.textContent=M(x.s);fee.textContent=M(x.f);tot.textContent=M(x.t)}
delivery.onchange=()=>{abox.classList.toggle('hidden',delivery.value!=='delivery');rc()}
async function finish(){let items=Object.entries(C).map(([id,qty])=>({product_id:Number(id),qty}));let body={name:name.value,phone:phone.value,email:email.value,delivery_type:delivery.value,address:address.value,desired_date:date.value,notes:notes.value,items};let r=await fetch('/api/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let d=await r.json();if(!r.ok){result.innerHTML=`<div class="notice">${d.error}</div>`;return}C={};await load();result.innerHTML=`<div class="success"><b>Pedido ${d.code} registrado ✅</b><p>Total: <b>${M(d.total)}</b></p>${d.pix_key?`<div class="notice">Pix: <b>${d.pix_key}</b></div>`:'<div class="notice">A loja ainda não configurou o Pix.</div>'}</div>`}
load();
</script></body></html>"""

LOGIN = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin</title>""" + STYLE + """</head><body>
<header><div class="wrap brand"><h1>⚙️ Brahma Chopp Mogi Mirim • Admin</h1><a href="/"><button class="light">Loja</button></a></div></header>
<main class="wrap" style="max-width:520px"><div class="card"><h2>Acesso</h2><div class="notice">Senha inicial: <b>1234</b>. Troque depois.</div><label style="margin-top:12px">Senha<input id="pwd" type="password"></label><button class="dark full" onclick="login()">Entrar</button><div id="msg"></div></div></main>
<script>async function login(){let r=await fetch('/api/admin/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pwd.value})});if(r.ok)location='/admin';else msg.innerHTML='<div class="notice">Senha incorreta.</div>'}</script></body></html>"""

ADMIN = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Painel Brahma Chopp Mogi Mirim</title>""" + STYLE + """</head><body>
<header><div class="wrap brand"><h1>⚙️ Painel Brahma Chopp Mogi Mirim</h1><div><a href="/"><button class="light">Loja</button></a> <button class="light" onclick="logout()">Sair</button></div></div></header>
<main class="wrap"><div class="tabs"><button class="dark" onclick="show('orders')">Pedidos</button><button onclick="show('products')">Produtos</button><button onclick="show('report')">Relatório</button><button onclick="show('settings')">Configurações</button></div>
<section id="orders"></section><section id="products" class="hidden"></section><section id="report" class="hidden"></section><section id="settings" class="hidden"></section></main>
<script>
const M=v=>Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
function show(id){['orders','products','report','settings'].forEach(x=>document.getElementById(x).classList.toggle('hidden',x!==id));if(id==='orders')lo();if(id==='products')lp();if(id==='report')lr();if(id==='settings')ls()}
async function logout(){await fetch('/api/admin/logout',{method:'POST'});location='/admin'}
async function lo(){let d=await fetch('/api/admin/orders').then(r=>r.json());orders.innerHTML='<h2>Pedidos</h2>'+(d.length?d.map(o=>`<div class="card"><b>${o.code}</b> • <span class="status">${o.status}</span><br><small>${new Date(o.created_at).toLocaleString('pt-BR')}</small><hr><b>${o.customer.name}</b> • ${o.customer.phone}<p>${o.items.map(i=>i.qty+'x '+i.name).join('<br>')}</p><p><b>${M(o.total)}</b> • ${o.delivery_type==='delivery'?'Entrega':'Retirada'}${o.address?'<br>'+o.address:''}</p><label>Status<select onchange="st(${o.id},this.value)">${['Aguardando pagamento','Pago','Em separação','Saiu para entrega','Entregue','Cancelado'].map(s=>`<option ${s===o.status?'selected':''}>${s}</option>`).join('')}</select></label></div>`).join(''):'<div class="card">Nenhum pedido.</div>')}
async function st(id,status){await fetch('/api/admin/orders/'+id+'/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});lo()}
function pic(p){return p.image?`<img src="${p.image}">`:`<div class="emoji">${p.emoji||'🍺'}</div>`}
async function lp(){let d=await fetch('/api/admin/products').then(r=>r.json());products.innerHTML='<h2>Produtos</h2><div class="notice">Você pode trocar foto, preço, nome e estoque pelo celular.</div><br>'+d.map(p=>`<div class="card"><div class="two"><div><div class="pic">${pic(p)}</div><label>Trocar foto<input type="file" accept="image/*" onchange="photo(${p.id},this)"></label></div><div><label>Nome<input value="${p.name.replace(/"/g,'&quot;')}" onchange="up(${p.id},'name',this.value)"></label><label>Preço<input type="number" step="0.01" value="${p.price}" onchange="up(${p.id},'price',this.value)"></label><label>Estoque<input type="number" value="${p.stock}" onchange="up(${p.id},'stock',this.value)"></label><label><input style="width:auto" type="checkbox" ${p.active?'checked':''} onchange="up(${p.id},'active',this.checked)"> Ativo</label></div></div></div>`).join('')+`<div class="card"><h3>Novo produto</h3><label>Nome<input id="nn"></label><label>Preço<input id="np" type="number"></label><label>Estoque<input id="ns" type="number"></label><button class="primary full" onclick="addp()">Adicionar</button></div>`}
async function up(id,k,v){if(k==='price'||k==='stock')v=Number(v);await fetch('/api/admin/products/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({[k]:v})})}
function photo(id,input){let f=input.files[0];if(!f)return;if(f.size>1200000){alert('Use uma foto de até 1,2 MB.');return}let r=new FileReader();r.onload=async e=>{await up(id,'image',e.target.result);lp()};r.readAsDataURL(f)}
async function addp(){await fetch('/api/admin/products',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:nn.value,price:np.value,stock:ns.value})});lp()}
async function lr(){let d=await fetch('/api/admin/report').then(r=>r.json());report.innerHTML=`<h2>Relatório</h2><div class="grid"><div class="card"><b>Pedidos</b><div class="price">${d.orders}</div></div><div class="card"><b>Entregues</b><div class="price">${d.delivered}</div></div><div class="card"><b>Em aberto</b><div class="price">${d.open}</div></div><div class="card"><b>Cancelados</b><div class="price">${d.cancelled}</div></div></div><div class="card"><div class="line"><span>Valor entregue</span><b>${M(d.delivered_value)}</b></div><div class="line"><span>Total não cancelado</span><b>${M(d.valid_value)}</b></div></div>`}
async function ls(){let d=await fetch('/api/admin/settings').then(r=>r.json());settings.innerHTML=`<h2>Configurações</h2><div class="card"><label>Taxa entrega<input id="sf" value="${d.delivery_fee}"></label><label>Chave Pix<input id="sp" value="${d.pix_key}"></label><label>WhatsApp loja<input id="sw" value="${d.whatsapp}"></label><label>Nova senha<input id="sx" type="password"></label><button class="primary full" onclick="saves()">Salvar</button></div>`}
async function saves(){await fetch('/api/admin/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({delivery_fee:sf.value,pix_key:sp.value,whatsapp:sw.value,new_password:sx.value})});alert('Salvo')}
lo();
</script></body></html>"""

@app.route("/")
def home():
    return render_template_string(STORE)

@app.route("/admin")
def admin():
    if not session.get("admin"):
        return render_template_string(LOGIN)
    return render_template_string(ADMIN)

@app.route("/api/products")
def api_products():
    rows = Product.query.filter_by(active=True).order_by(Product.id).all()
    return jsonify([{"id":p.id,"name":p.name,"description":p.description,"price":p.price,"stock":p.stock,"image":p.image,"emoji":p.emoji} for p in rows])

@app.route("/api/public-settings")
def public_settings():
    return jsonify({"delivery_fee":float(gs("delivery_fee","59"))})

@app.route("/api/orders", methods=["POST"])
def new_order():
    d = request.get_json(force=True)
    items = d.get("items") or []
    name = (d.get("name") or "").strip()
    phone = (d.get("phone") or "").strip()
    if not items: return jsonify(error="Carrinho vazio."), 400
    if not name or not phone: return jsonify(error="Informe nome e WhatsApp."), 400
    delivery = d.get("delivery_type","pickup")
    address = (d.get("address") or "").strip()
    if delivery == "delivery" and not address:
        return jsonify(error="Informe o endereço de entrega."), 400

    customer = Customer.query.filter_by(phone=phone).first()
    if not customer:
        customer = Customer(name=name, phone=phone, email=(d.get("email") or "").strip())
        db.session.add(customer); db.session.flush()
    else:
        customer.name = name
        customer.email = (d.get("email") or customer.email or "").strip()

    subtotal = 0
    resolved = []
    for i in items:
        p = db.session.get(Product, int(i["product_id"]))
        q = int(i["qty"])
        if not p or not p.active or q < 1: return jsonify(error="Produto inválido."),400
        if q > p.stock: return jsonify(error=f"Estoque insuficiente: {p.name}"),400
        subtotal += p.price*q
        resolved.append((p,q))
    fee = float(gs("delivery_fee","59")) if delivery=="delivery" else 0
    code = "CV"+datetime.utcnow().strftime("%y%m%d%H%M%S%f")[-12:]
    o = Order(code=code,customer_id=customer.id,delivery_type=delivery,address=address,
              desired_date=d.get("desired_date",""),notes=(d.get("notes") or "").strip(),
              subtotal=subtotal,delivery_fee=fee,total=subtotal+fee)
    db.session.add(o); db.session.flush()
    for p,q in resolved:
        db.session.add(OrderItem(order_id=o.id,product_id=p.id,product_name=p.name,qty=q,unit_price=p.price))
        p.stock -= q
    db.session.commit()
    return jsonify(ok=True,code=o.code,total=o.total,pix_key=gs("pix_key",""))

@app.route("/api/admin/login", methods=["POST"])
def login():
    d=request.get_json(force=True)
    if check_password_hash(gs("admin_hash",""), d.get("password","")):
        session["admin"]=True
        return jsonify(ok=True)
    return jsonify(error="Senha incorreta"),401

@app.route("/api/admin/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify(ok=True)

def auth():
    return bool(session.get("admin"))

@app.route("/api/admin/orders")
def adm_orders():
    if not auth(): return jsonify(error="Não autorizado"),401
    rows=Order.query.order_by(Order.created_at.desc()).all()
    return jsonify([{"id":o.id,"code":o.code,"created_at":o.created_at.isoformat(),"status":o.status,
                     "customer":{"name":o.customer.name,"phone":o.customer.phone},
                     "delivery_type":o.delivery_type,"address":o.address,"total":o.total,
                     "items":[{"name":i.product_name,"qty":i.qty} for i in o.items]} for o in rows])

@app.route("/api/admin/orders/<int:oid>/status", methods=["POST"])
def adm_status(oid):
    if not auth(): return jsonify(error="Não autorizado"),401
    o=db.session.get(Order,oid)
    if not o: return jsonify(error="Pedido não encontrado"),404
    o.status=request.get_json(force=True).get("status",o.status)
    db.session.commit()
    return jsonify(ok=True)

@app.route("/api/admin/products", methods=["GET","POST"])
def adm_products():
    if not auth(): return jsonify(error="Não autorizado"),401
    if request.method=="POST":
        d=request.get_json(force=True)
        p=Product(name=(d.get("name") or "Novo produto").strip(),price=float(d.get("price") or 0),
                  stock=int(d.get("stock") or 0),description=d.get("description",""),emoji="🍺")
        db.session.add(p);db.session.commit()
        return jsonify(ok=True,id=p.id)
    rows=Product.query.order_by(Product.id).all()
    return jsonify([{"id":p.id,"name":p.name,"price":p.price,"stock":p.stock,"active":p.active,
                     "image":p.image,"emoji":p.emoji} for p in rows])

@app.route("/api/admin/products/<int:pid>", methods=["PUT"])
def adm_update_product(pid):
    if not auth(): return jsonify(error="Não autorizado"),401
    p=db.session.get(Product,pid)
    if not p: return jsonify(error="Produto não encontrado"),404
    d=request.get_json(force=True)
    if "name" in d: p.name=str(d["name"])[:140]
    if "price" in d: p.price=float(d["price"])
    if "stock" in d: p.stock=int(d["stock"])
    if "active" in d: p.active=bool(d["active"])
    if "image" in d: p.image=d["image"]
    db.session.commit()
    return jsonify(ok=True)

@app.route("/api/admin/report")
def adm_report():
    if not auth(): return jsonify(error="Não autorizado"),401
    rows=Order.query.all()
    delivered=[o for o in rows if o.status=="Entregue"]
    cancelled=[o for o in rows if o.status=="Cancelado"]
    open_=[o for o in rows if o.status not in ("Entregue","Cancelado")]
    valid=[o for o in rows if o.status!="Cancelado"]
    return jsonify(orders=len(rows),delivered=len(delivered),cancelled=len(cancelled),open=len(open_),
                   delivered_value=sum(o.total for o in delivered),valid_value=sum(o.total for o in valid))

@app.route("/api/admin/settings", methods=["GET","POST"])
def adm_settings():
    if not auth(): return jsonify(error="Não autorizado"),401
    if request.method=="POST":
        d=request.get_json(force=True)
        if "delivery_fee" in d: ss("delivery_fee",d["delivery_fee"])
        if "pix_key" in d: ss("pix_key",d["pix_key"])
        if "whatsapp" in d: ss("whatsapp",d["whatsapp"])
        if d.get("new_password"): ss("admin_hash",generate_password_hash(d["new_password"]))
        db.session.commit()
        return jsonify(ok=True)
    return jsonify(delivery_fee=gs("delivery_fee","59"),pix_key=gs("pix_key",""),whatsapp=gs("whatsapp",""))

with app.app_context():
    db.create_all()
    seed()

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
