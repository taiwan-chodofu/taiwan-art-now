const CACHE_NAME = 'taiwan-art-v1';
const OFFLINE_URL = '/';

// キャッシュするリソース
const PRECACHE_URLS = [
  '/',
  '/taishin',
  '/artists',
  '/search',
];

// インストール時にプリキャッシュ
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_URLS);
    })
  );
  self.skipWaiting();
});

// アクティベーション（古いキャッシュ削除）
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Web Push: 通知を表示
self.addEventListener('push', (event) => {
  let payload = { title: 'Taiwan Art Now', body: '', url: '/' };
  try {
    if (event.data) payload = Object.assign(payload, event.data.json());
  } catch (e) {}
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: '/static/icon-192.png',
      badge: '/static/icon-192.png',
      data: { url: payload.url },
    })
  );
});

// 通知タップ: 該当URLでアプリを開く（既に開いていればフォーカス）
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(url) && 'focus' in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});

// フェッチ: ネットワーク優先、失敗時キャッシュ
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // 成功したらキャッシュに保存
        if (response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
        }
        return response;
      })
      .catch(() => {
        // オフライン時はキャッシュから返す
        return caches.match(event.request).then((cached) => {
          return cached || caches.match(OFFLINE_URL);
        });
      })
  );
});
