import os

from flask import abort, request

import app as original

# O disco persistente do Render será montado exatamente nesta pasta.
# Assim, as fotos enviadas pelo painel e o banco SQLite sobrevivem a
# deploys, reinicializações e trocas de instância.
PERSISTENT_DIR = os.path.join(original.BASE_DIR, 'static', 'uploads')
os.makedirs(PERSISTENT_DIR, exist_ok=True)

original.UPLOAD_DIR = PERSISTENT_DIR
original.DB_PATH = os.path.join(PERSISTENT_DIR, '.loja_data.sqlite3')
original.app.config['UPLOAD_FOLDER'] = PERSISTENT_DIR

# Garante que o banco persistente exista e tenha todas as tabelas.
original.init_db()

# Instala as novas funções comerciais sobre a versão atual sem apagar
# clientes, pedidos, produtos, fotos ou histórico existentes.
import enhancements
enhancements.install(original)

# Pequenos ajustes de compatibilidade da nova versão.
import enhancements_patch
enhancements_patch.install(original)

app = original.app


@app.before_request
def protect_persistent_database():
    # O banco fica no mesmo volume das imagens, mas nunca deve ser
    # disponibilizado pela rota pública de arquivos estáticos.
    if request.path.startswith('/static/uploads/.loja_data.sqlite3'):
        abort(404)
