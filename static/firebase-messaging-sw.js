importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-messaging-compat.js');


// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyADy57398AgmjhkaTUvTQpRQ1hdCijGgvs",
  authDomain: "vericampus-13104.firebaseapp.com",
  projectId: "vericampus-13104",
  storageBucket: "vericampus-13104.firebasestorage.app",
  messagingSenderId: "762945690586",
  appId: "1:762945690586:web:66e6a7fc5a524cb2c93ee3"
};
// ---------------------------------------

firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

// Handle background messages
messaging.onBackgroundMessage(function(payload) {
  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/static/logo.png'
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});