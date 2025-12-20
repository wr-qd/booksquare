<script setup>
import { RouterView } from 'vue-router'
</script>

<template>
  <RouterView />
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2f2f39;
  position: relative;
  background-color: #f5f7fb;
  /* First layer can be overridden via --app-bg-image (or VITE_BG_IMAGE_URL).
     Default: use local forest photo in repo root (served by Vite as /background.jpg when placed under client/).
     Second layer: always keep a soft SVG fallback for consistency. */
  background-image: var(--app-bg-image, url('/background.jpg')),
    url('./assets/misty-landscape.svg');
  background-position: center;
  background-size: cover;
  background-repeat: no-repeat;
  background-attachment: fixed;
}

body::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(900px 520px at 18% 10%, rgba(255, 255, 255, 0.32), transparent 60%),
    radial-gradient(900px 520px at 92% 12%, rgba(255, 255, 255, 0.26), transparent 58%),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.26), rgba(255, 255, 255, 0.46));
}

#app {
  position: relative;
  z-index: 1;
}

/* 全局“磨砂玻璃”基调：让各页 scoped 里也能复用 */
:root {
  --glass-bg: rgba(255, 255, 255, 0.62);
  --glass-border: rgba(255, 255, 255, 0.60);
  --glass-shadow: 0 18px 50px rgba(0, 0, 0, 0.12);
  --ink: #2f2f39;
  --ink-soft: #5a5a6a;
}
</style>