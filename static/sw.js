self.addEventListener('install', event => {
  self.skipWaiting();
});
self.addEventListener('activate', event => {
  console.log('sw active');
});
// Simple fetch handler to allow offline shell
self.addEventListener('fetch', event => {
  // For demo, we won't implement full cache strategy. Leave network-first for API calls.
});