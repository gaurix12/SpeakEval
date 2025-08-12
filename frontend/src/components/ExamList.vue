<template>
  <div>
    <h2>Exams</h2>
    <button @click="fetchExams">Refresh Exams</button>
    <ul>
      <li v-for="exam in exams" :key="exam.id">
        <strong>{{ exam.title }}</strong> - Duration: {{ exam.duration_minutes }} min
        <button @click="startExam(exam.id)">Start</button>
      </li>
    </ul>

    <ExamStart
      v-if="selectedExamId"
      :token="token"
      :examId="selectedExamId"
      @completed="onExamCompleted"
      @cancel="selectedExamId = null"
      @logout="$emit('logout')"
    />
  </div>
</template>

<script>
import ExamStart from './ExamStart.vue'

export default {
  props: ['token'],
  components: { ExamStart },
  data() {
    return {
      exams: [],
      selectedExamId: null
    }
  },
  methods: {
    async fetchExams() {
      try {
        const res = await fetch('http://127.0.0.1:5000/api/exams', {
          headers: {
            Authorization: `Bearer ${this.token}`
          }
        })
        if (res.status === 401) {
          alert('Unauthorized. Please login again.')
          // Notify App to logout
          this.$emit('logout')
          return
        }
        if (!res.ok) {
          throw new Error('Failed to fetch exams')
        }
        this.exams = await res.json()
      } catch (e) {
        console.error('Error fetching exams:', e)
        alert('Failed to load exams')
      }
    },
    startExam(id) {
      this.selectedExamId = id
    },
    onExamCompleted() {
      this.selectedExamId = null
      this.fetchExams()
    }
  },
  mounted() {
    if (this.token) {
      this.fetchExams()
    } else {
      alert('You need to login first')
      this.$emit('logout')
    }
  }
}
</script>