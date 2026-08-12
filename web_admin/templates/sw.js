// web_admin/templates/sw.js
// Service Worker para notificaciones push y PWA

const CACHE_NAME = 'aisa-v1';
const urlsToCache = [
    '/',
    '/offline',
    '/dashboard',
    '/login',
    '/register',
    '/perfil',
    '/manifest.json',
    '/favicon.ico',
    '/favicon.svg',
    '/static/img/favicon.ico',
    '/static/img/favicon.svg',
    '/static/img/favicon-16x16.png',
    '/static/img/favicon-32x32.png',
    '/static/img/favicon-48x48.png',
    '/static/img/favicon-64x64.png',
    '/static/css/style.css',
    '/static/js/app.js'
];

// Instalación del Service Worker
self.addEventListener('install', event => {
    console.log('[Service Worker] Instalando...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[Service Worker] Cache abierto');
                return cache.addAll(urlsToCache);
            })
            .then(() => {
                console.log('[Service Worker] Instalado correctamente');
                return self.skipWaiting();
            })
            .catch(error => {
                console.error('[Service Worker] Error al cachear archivos:', error);
            })
    );
});

// Activación del Service Worker
self.addEventListener('activate', event => {
    console.log('[Service Worker] Activando...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[Service Worker] Eliminando cache antiguo:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
        .then(() => {
            console.log('[Service Worker] Activado correctamente');
            return self.clients.claim();
        })
    );
});

// Interceptar peticiones
self.addEventListener('fetch', event => {
    // Ignorar peticiones a la API
    if (event.request.url.includes('/api/')) {
        event.respondWith(fetch(event.request));
        return;
    }

    // Ignorar peticiones a archivos estáticos de terceros
    if (event.request.url.includes('googleapis') || 
        event.request.url.includes('gstatic') ||
        event.request.url.includes('cloudflare')) {
        event.respondWith(fetch(event.request));
        return;
    }

    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
                    return response;
                }
                return fetch(event.request).then(response => {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, responseClone);
                    });
                    return response;
                });
            })
            .catch(() => {
                if (event.request.headers.get('accept').includes('text/html')) {
                    return caches.match('/offline');
                }
                if (event.request.url.match(/\.(png|jpg|jpeg|gif|ico|svg)$/i)) {
                    return caches.match('/static/img/favicon-64x64.png');
                }
                return new Response('Sin conexión', {
                    status: 503,
                    statusText: 'Service Unavailable'
                });
            })
    );
});

// Recibir mensajes
self.addEventListener('message', event => {
    console.log('[Service Worker] Mensaje recibido:', event.data);
    
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

// RECIBIR NOTIFICACIONES PUSH
self.addEventListener('push', event => {
    console.log('[Service Worker] Push recibido');
    
    let data = {
        title: '🔔 Notificación AIsa',
        body: 'Tienes una nueva notificación',
        icon: '/static/img/favicon-64x64.png',
        badge: '/static/img/favicon-48x48.png',
        vibrate: [200, 100, 200],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: 1
        },
        actions: [
            { action: 'ver', title: 'Ver' },
            { action: 'cerrar', title: 'Cerrar' }
        ],
        tag: 'notification',
        requireInteraction: false,
        renotify: false
    };
    
    if (event.data) {
        try {
            const pushData = event.data.json();
            data = { ...data, ...pushData };
        } catch (e) {
            data.body = event.data.text() || data.body;
        }
    }
    
    const options = {
        body: data.body,
        icon: data.icon || '/static/img/favicon-64x64.png',
        badge: data.badge || '/static/img/favicon-48x48.png',
        vibrate: data.vibrate || [200, 100, 200],
        data: data.data || { dateOfArrival: Date.now() },
        actions: data.actions || [
            { action: 'ver', title: 'Ver' },
            { action: 'cerrar', title: 'Cerrar' }
        ],
        tag: data.tag || 'notification',
        requireInteraction: data.requireInteraction || false,
        renotify: data.renotify || false
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// Click en notificación
self.addEventListener('notificationclick', event => {
    console.log('[Service Worker] Click en notificación');
    event.notification.close();
    
    const action = event.action;
    const notificationData = event.notification.data || {};
    
    if (action === 'cerrar') {
        return;
    }
    
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then(windowClients => {
                for (let client of windowClients) {
                    if (client.url.includes('/dashboard') && 'focus' in client) {
                        client.focus();
                        client.postMessage({
                            type: 'NOTIFICATION_CLICK',
                            data: notificationData
                        });
                        return;
                    }
                }
                if (clients.openWindow) {
                    return clients.openWindow('/dashboard');
                }
            })
            .catch(err => {
                console.error('[Service Worker] Error al manejar click:', err);
            })
    );
});

// Fallback para cuando no hay conexión
self.addEventListener('fetch', event => {
    event.respondWith(
        fetch(event.request)
            .catch(() => {
                return caches.match('/offline');
            })
    );
});

console.log('[Service Worker] Service Worker cargado correctamente');
