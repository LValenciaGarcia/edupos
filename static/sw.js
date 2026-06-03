const CACHE_VERSION = 'puntoasis-v3';  // Cambia la versión para forzar actualización
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const DYNAMIC_CACHE = `${CACHE_VERSION}-dynamic`;

// Recursos estáticos iniciales (se cachean en la instalación)
const STATIC_ASSETS = [
  '/static/css/base.css',
  '/static/css/admin.css',
  '/static/css/docente.css',
  '/static/css/estudiante.css',
  '/static/img/icon.svg',
];

// Instalación: cachear recursos estáticos
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activación: limpiar caches antiguas
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(key => !key.startsWith(CACHE_VERSION)).map(key => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Estrategia: stale-while-revalidate para archivos estáticos
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Solo interesar peticiones GET
  if (request.method !== 'GET') return;

  // Para archivos estáticos (CSS, JS, imágenes, etc.)
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.open(STATIC_CACHE).then(cache => {
        return cache.match(request).then(cachedResponse => {
          // Clonar la petición para hacer fetch en segundo plano
          const fetchPromise = fetch(request.clone()).then(networkResponse => {
            // Actualizar caché con la nueva respuesta si es válida
            if (networkResponse && networkResponse.status === 200) {
              cache.put(request, networkResponse.clone());
            }
            return networkResponse;
          }).catch(() => {
            // Si falla la red y no hay caché, devolver error controlado
            return cachedResponse;
          });

          // Devolver la respuesta cacheada inmediatamente si existe,
          // sino esperar la red (comportamiento normal)
          return cachedResponse || fetchPromise;
        });
      })
    );
    return;
  }

  // Para el resto (HTML, API, etc.) no intervenir o usar network-first
  // (opcional, pero para evitar problemas con las vistas de Django)
  if (url.pathname.startsWith('/admin/') || url.pathname.startsWith('/accounts/')) {
    // No cachear páginas de administración o login
    event.respondWith(fetch(request));
    return;
  }

  // Opcional: para otros recursos, también usar stale-while-revalidate
  // pero limitado para no cachear cosas sensibles.
});