<script setup lang="ts">
import AccessGate from './components/AccessGate.vue'
import Dashboard from './views/Dashboard.vue'
</script>

<template>
  <AccessGate>
    <Dashboard />
  </AccessGate>
</template>
