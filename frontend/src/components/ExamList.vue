<template>
  <div class="exam-list-container">
    <h2>Exams</h2>
    <button @click="fetchExams">Refresh Exams</button>

    <ul>
      <li v-for="exam in exams" :key="exam.id">
        <strong>{{ exam.title }}</strong> - Duration: {{ exam.duration_minutes }} min
        <button @click="startExam(exam.id)">Start</button>
      </li>
    </ul>
  </div>
</template>

<script>
export default {
  name: 'ExamList',
  props: ['token'],
  data() {
    return {
      exams: [],
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
          this.$emit('logout')
          return
        }
        if (!res.ok) throw new Error('Failed to fetch exams')
        this.exams = await res.json()
      } catch (e) {
        console.error('Error fetching exams:', e)
        alert('Failed to load exams')
      }
    },

    // Navigate to a separate page. Let ExamStart create the attempt.
    startExam(examId) {
      this.$router.push({ name: 'ExamStart', params: { examId } })
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
