<template>
    <el-container class="app-container">
        <el-header class="app-header">
            <div class="logo">
                <el-icon :size="24"><Sunrise /></el-icon>
                <span>UrbanClimate-Expert</span>
            </div>
            <el-menu
                mode="horizontal"
                :router="true"
                :default-active="route.path"
                class="nav-menu"
            >
                <el-menu-item index="/chat">
                    <el-icon><ChatDotRound /></el-icon>
                    <span>智能问答</span>
                </el-menu-item>
                <el-menu-item index="/graph">
                    <el-icon><Share /></el-icon>
                    <span>知识图谱</span>
                </el-menu-item>
                <el-menu-item index="/documents">
                    <el-icon><Document /></el-icon>
                    <span>文档管理</span>
                </el-menu-item>
            </el-menu>
        </el-header>
        <el-main class="app-main">
            <router-view />
        </el-main>
    </el-container>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { Sunrise, ChatDotRound, Share, Document } from '@element-plus/icons-vue';

const route = useRoute();
</script>

<style scoped>
.app-container {
    height: 100vh;
}

.app-header {
    display: flex;
    align-items: center;
    background: #fff;
    border-bottom: 1px solid #e5e7eb;
    padding: 0 20px;
    height: 60px;
}

.logo {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 18px;
    font-weight: 600;
    color: #409eff;
    margin-right: 40px;
    white-space: nowrap;
}

.nav-menu {
    border-bottom: none;
    flex: 1;
}

.app-main {
    background: #f5f7fa;
    padding: 20px;
    overflow: auto;
}
</style>
