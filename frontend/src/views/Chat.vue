<template>
    <div class="chat-page">
        <ChatWindow />
    </div>
</template>

<script setup lang="ts">
import ChatWindow from '@/components/ChatWindow.vue';
</script>

<style scoped>
.chat-page {
    height: calc(100vh - 100px);
    max-width: 900px;
    margin: 0 auto;
}
</style>
