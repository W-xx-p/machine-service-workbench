import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'
import AppShell from './components/AppShell.vue'
import LoginView from './views/LoginView.vue'
import DashboardView from './views/DashboardView.vue'
import AskView from './views/AskView.vue'
import ProductsView from './views/ProductsView.vue'
import ServiceDataView from './views/ServiceDataView.vue'
import DocumentsView from './views/DocumentsView.vue'
import KnowledgeView from './views/KnowledgeView.vue'
import CasesView from './views/CasesView.vue'
import AdminView from './views/AdminView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    {
      path: '/',
      component: AppShell,
      children: [
        { path: '', name: 'dashboard', component: DashboardView },
        { path: 'ask', name: 'ask', component: AskView },
        { path: 'products', name: 'products', component: ProductsView },
        { path: 'service-data', name: 'service-data', component: ServiceDataView },
        { path: 'documents', name: 'documents', component: DocumentsView },
        { path: 'knowledge', name: 'knowledge', component: KnowledgeView },
        { path: 'cases', name: 'cases', component: CasesView },
        { path: 'admin', name: 'admin', component: AdminView, meta: { roles: ['reviewer', 'admin'] } },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) return { name: 'login' }
  if (to.name === 'login' && auth.isLoggedIn) return { name: 'dashboard' }
  const roles = to.meta.roles as string[] | undefined
  if (roles && (!auth.user || !roles.includes(auth.user.role))) return { name: 'dashboard' }
})

export default router
