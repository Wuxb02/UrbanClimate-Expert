/**
 * Vue Router 配置
 */
import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
    {
        path: '/',
        redirect: '/chat',
    },
    {
        path: '/chat',
        name: 'Chat',
        component: () => import('@/views/Chat.vue'),
        meta: { title: '智能问答' },
    },
    {
        path: '/graph',
        name: 'Graph',
        component: () => import('@/views/Graph.vue'),
        meta: { title: '知识图谱' },
    },
];

const router = createRouter({
    history: createWebHistory(),
    routes,
});

router.beforeEach((to, _from, next) => {
    const title = to.meta.title as string;
    document.title = title
        ? `${title} - UrbanClimate-Expert`
        : 'UrbanClimate-Expert';
    next();
});

export default router;
