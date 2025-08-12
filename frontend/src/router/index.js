import { createRouter, createWebHistory } from 'vue-router'
import ExamList from '../components/ExamList.vue'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'

const routes = [
  {
    path: '/',
    redirect: '/login'  // or redirect to /exams if already logged in
  },
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/register',
    name: 'Register',
    component: Register
  },
  {
    path: '/exams',
    name: 'Exams',
    component: ExamList
  },
  // Add other routes here as needed
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
