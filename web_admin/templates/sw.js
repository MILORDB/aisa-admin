// web_admin/templates/sw.js
// Service Worker para notificaciones push y PWA

const CACHE_NAME = 'aisa-v2';
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
    '/static/css/style.css',
    '/static/js/app.js',
    '/static/img/favicon.svg',
    '/static/img/favicon.ico',
    '/static/img/favicon-16x16.png',
    '/static/img/favicon-32x32.png',
    '/static/img/favicon-48x48.png',
    '/static/img/favicon-64x64.png',
    '/static/img/favicon-96x96.png',
    '/static/img/favicon-128x128.png',
    '/static/img/icon-72.png',
    '/static/img/icon-96.png',
    '/static/img/icon-128.png',
    '/static/img/icon-144.png',
    '/static/img/icon-152.png',
    '/static/img/icon-192.png',
    '/static/img/icon-384.png',
    '/static/img/icon-512.png',
    '/static/img/apple-touch-icon.png'
];

// ============================================
// INSTALACIÓN DEL SERVICE WORKER
// ============================================

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

// ============================================
// ACTIVACIÓN DEL SERVICE WORKER
// ============================================

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

// ============================================
// INTERCEPTAR PETICIONES (CACHE FIRST)
// ============================================

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
                    // Si está en caché, devolverlo
                    return response;
                }
                // Si no está en caché, hacer fetch y guardar en caché
                return fetch(event.request).then(response => {
                    // Clonar la respuesta para guardarla en caché
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, responseClone);
                    });
                    return response;
                });
            })
            .catch(() => {
                // Si no hay conexión, mostrar la página offline
                return caches.match('/offline');
            })
    );
});

// ============================================
// RECIBIR MENSAJES
// ============================================

self.addEventListener('message', event => {
    console.log('[Service Worker] Mensaje recibido:', event.data);
    
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data && event.data.type === 'CLEAR_CACHE') {
        caches.delete(CACHE_NAME);
        console.log('[Service Worker] Cache eliminado');
    }
});

// ============================================
// RECIBIR NOTIFICACIONES PUSH
// ============================================

self.addEventListener('push', event => {
    console.log('[Service Worker] Push recibido:', event);
    
    let data = {
        title: '🔔 Notificación AIsa',
        body: 'Tienes una nueva notificación',
        icon: '/static/img/icon-192.png',
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
            // Si no es JSON, usar el texto como body
            data.body = event.data.text() || data.body;
        }
    }
    
    const options = {
        body: data.body,
        icon: data.icon || '/static/img/icon-192.png',
        badge: data.badge || '/static/img/favicon-48x48.png',
        vibrate: data.vibrate || [200, 100, 200],
        data: data.data || { dateOfArrival: Date.now() },
        actions: data.actions || [
            { action: 'ver', title: 'Ver' },
            { action: 'cerrar', title: 'Cerrar' }
        ],
        tag: data.tag || 'notification',
        requireInteraction: data.requireInteraction || false,
        renotify: data.renotify || false,
        silent: data.silent || false,
        timestamp: Date.now()
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// ============================================
// CLICK EN NOTIFICACIÓN
// ============================================

self.addEventListener('notificationclick', event => {
    console.log('[Service Worker] Click en notificación:', event);
    
    event.notification.close();
    
    const action = event.action;
    const notificationData = event.notification.data || {};
    
    // Si la acción es "cerrar", no hacer nada
    if (action === 'cerrar') {
        return;
    }
    
    // Si la acción es "ver" o no hay acción, abrir la app
    event.waitUntil(
        clients.matchAll({ 
            type: 'window', 
            includeUncontrolled: true 
        })
        .then(windowClients => {
            // Buscar una ventana abierta de la app
            for (let client of windowClients) {
                if (client.url.includes('/dashboard') && 'focus' in client) {
                    client.focus();
                    // Enviar mensaje a la ventana
                    client.postMessage({
                        type: 'NOTIFICATION_CLICK',
                        data: notificationData
                    });
                    return;
                }
            }
            // Si no hay ventana abierta, abrir una nueva
            if (clients.openWindow) {
                const url = notificationData.url || '/dashboard';
                return clients.openWindow(url);
            }
        })
        .catch(err => {
            console.error('[Service Worker] Error al manejar click:', err);
        })
    );
});

// ============================================
// SINCRONIZACIÓN EN SEGUNDO PLANO (Background Sync)
// ============================================

self.addEventListener('sync', event => {
    console.log('[Service Worker] Sincronización en segundo plano:', event.tag);
    
    if (event.tag === 'sync-notifications') {
        event.waitUntil(
            fetch('/api/notificaciones/sync', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                console.log('[Service Worker] Sincronización completada:', data);
            })
            .catch(error => {
                console.error('[Service Worker] Error en sincronización:', error);
            })
        );
    }
});

// ============================================
// ACTUALIZACIÓN EN SEGUNDO PLANO (Background Fetch)
// ============================================

self.addEventListener('backgroundfetchsuccess', event => {
    console.log('[Service Worker] Background Fetch exitoso:', event);
    
    event.waitUntil(
        event.updateUI({ title: '📥 Descarga completada' })
    );
});

self.addEventListener('backgroundfetchfail', event => {
    console.log('[Service Worker] Background Fetch fallido:', event);
    
    event.waitUntil(
        event.updateUI({ title: '❌ Error en la descarga' })
    );
});

// ============================================
// FALLBACK PARA CUANDO NO HAY CONEXIÓN
// ============================================

self.addEventListener('fetch', event => {
    event.respondWith(
        fetch(event.request)
            .catch(() => {
                // Si la petición es para una página HTML, mostrar offline
                if (event.request.headers.get('accept').includes('text/html')) {
                    return caches.match('/offline');
                }
                // Si es para una imagen, mostrar imagen por defecto
                if (event.request.url.match(/\.(jpg|jpeg|png|gif|webp|svg)$/i)) {
                    return caches.match('/static/img/favicon-192.png');
                }
                // Para otros recursos, devolver error
                return new Response('Sin conexión', {
                    status: 503,
                    statusText: 'Service Unavailable'
                });
            })
    );
});

// ============================================
// PERIODIC SYNC (ACTUALIZACIÓN PERIÓDICA)
// ============================================

if ('periodicSync' in self.registration) {
    self.addEventListener('periodicsync', event => {
        console.log('[Service Worker] Sincronización periódica:', event.tag);
        
        if (event.tag === 'update-notifications') {
            event.waitUntil(
                fetch('/api/notificaciones/check')
                    .then(response => response.json())
                    .then(data => {
                        console.log('[Service Worker] Notificaciones actualizadas:', data);
                    })
                    .catch(error => {
                        console.error('[Service Worker] Error en sincronización periódica:', error);
                    })
            );
        }
    });
}

console.log('[Service Worker] Service Worker cargado correctamente');
