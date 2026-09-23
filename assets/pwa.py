"""Inyecta manifest, service worker y metadatos PWA en la app Streamlit."""
import streamlit as st


def inyectar_pwa():
    st.markdown("""
    <link rel="manifest" href="/app/static/manifest.json">
    <meta name="theme-color" content="#7B68EE">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="OZOLABS">
    <script>
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/app/static/service-worker.js')
          .then(() => console.log('SW registrado'))
          .catch((e) => console.warn('SW error:', e));
      }
    </script>
    """, unsafe_allow_html=True)
