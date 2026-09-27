def install(original):
    app = original.app

    # A tela administrativa de cliente já existe no app original somente com GET.
    # As melhorias usam a mesma função também para ajustes manuais de pontos,
    # então registramos uma rota POST separada sem remover a rota existente.
    customer_view = app.view_functions.get('admin_customer')
    if customer_view:
        app.add_url_rule(
            '/admin/customer/<int:cid>',
            endpoint='admin_customer_post_v2',
            view_func=customer_view,
            methods=['POST'],
        )

    # Garante que a versão nova continue registrando o service worker no navegador.
    # O service worker atualizado invalida caches antigos para reduzir casos de tela
    # desatualizada/preta depois de um deploy.
    try:
        loader = app.jinja_loader.loaders[0]
        mapping = getattr(loader, 'mapping', {})
        base = mapping.get('base.html', '')
        if base and 'serviceWorker.register' not in base:
            mapping['base.html'] = base.replace(
                '</body>',
                "<script>if('serviceWorker' in navigator){navigator.serviceWorker.register('/service-worker.js')}</script></body>",
            )
    except Exception:
        pass
