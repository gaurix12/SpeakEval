import { createRouter, createWebHistory } from 'vue-router'
import ExamList from '../components/ExamList.vue'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import ExamResults from '../components/ExamResults.vue'
import ExamStart from '../components/ExamStart.vue'

const routes = [
  {
    path: '/',
    redirect: { name: 'Exams' }
  },
  {
    path: '/exams',
    name: 'Exams',
    component: ExamList
  },
  {
    path: '/exams/:examId',
    name: 'ExamStart',
    component: ExamStart,
    props: true
  },
  {
    path: '/exam-result/:attemptId',
    name: 'ExamResults',
    component: ExamResults,
    props: true
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
  // Optional: 404 fallback
  {
    path: '/:pathMatch(.*)*',
    redirect: { name: 'Exams' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
