# Chopp Brahma Mogi Mirim

Aplicativo web/PWA de vendas com:
- catálogo e carrinho;
- cadastro/login de clientes;
- histórico de compras;
- pontos: 10 pontos a cada R$ 100,00 pagos;
- painel administrativo;
- cadastro/edição de produtos, preços, estoque e fotos;
- pedidos e status de pagamento/entrega;
- métodos de pagamento;
- taxa de instalação configurável;
- PWA instalável no celular.

## Rodar localmente
```bash
pip install -r requirements.txt
python app.py
```
Acesse http://localhost:5000
Painel: http://localhost:5000/admin
Senha inicial: 1234 (mude pela variável ADMIN_PASSWORD no Render).

## Publicar no Render
1. Envie todos os arquivos para um repositório GitHub.
2. No Render, crie um Web Service conectado ao repositório (ou use render.yaml).
3. Build: `pip install -r requirements.txt`
4. Start: `gunicorn app:app`
5. Defina `SECRET_KEY` e troque `ADMIN_PASSWORD`.

Observação: SQLite em hospedagens efêmeras pode perder dados em novos deploys. Para produção, recomenda-se disco persistente ou PostgreSQL.
