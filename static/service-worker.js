const CACHE='brahma-mogi-v3';
const ASSETS=['/static/style.css','/static/capa_brahma.jpg'];
self.addEventListener('install',event=>{self.skipWaiting();event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)).catch(()=>null));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{if(event.request.method!=='GET') return;event.respondWith(fetch(event.request).then(response=>{const copy=response.clone();if(event.request.url.includes('/static/')) caches.open(CACHE).then(c=>c.put(event.request,copy));return response;}).catch(()=>caches.match(event.request)));});