<template>
  <div class="exam-results-container">
    <h2>Exam Results</h2>
    
    <div v-if="loading" class="text-center">
      <p>Loading results...</p>
    </div>

    <div v-else-if="error" class="text-center">
      <p style="color: red">{{ error }}</p>
      <button @click="$router.push('/exams')">Back to Exams</button>
    </div>

    <div v-else-if="resultData">
      <!-- Score Summary -->
      <div class="score-summary">
        <h3>{{ resultData.exam_title }}</h3>
        <div class="score-display">{{ resultData.total_score }}</div>
        <p>Total Score</p>
      </div>

      <!-- Question Breakdown -->
      <div class="breakdown-section">
        <h4>Question Breakdown</h4>
        <div 
          v-for="(item, index) in resultData.breakdown" 
          :key="item.question_id || index"
          class="question-breakdown"
        >
          <strong>Q{{ index + 1 }}: {{ item.question_text }}</strong>
          <p><strong>Your Answer:</strong> {{ item.spoken_text || 'No answer provided' }}</p>
          <p><strong>Points:</strong> {{ item.points_awarded || 0 }}</p>
        </div>
      </div>

      <div class="text-center mt-4">
        <button @click="$router.push('/exams')">Back to Exams</button>
      </div>
    </div>

    <div v-else class="text-center">
      <p>No results found.</p>
      <button @click="$router.push('/exams')">Back to Exams</button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ExamResults',
  props: ['token'],
  data() {
    return {
      resultData: null,
      loading: true,
      error: ''
    }
  },
  computed: {
    attemptId() {
      return this.$route.params.attemptId
    }
  },
  methods: {
    async fetchResults() {
      if (!this.attemptId) {
        this.error = 'No attempt ID provided'
        this.loading = false
        return
      }

      try {
        // First try to get from sessionStorage
        const storedData = sessionStorage.getItem(`exam_result_${this.attemptId}`)
        if (storedData) {
          this.resultData = JSON.parse(storedData)
          this.loading = false
          return
        }

        // If not in sessionStorage, fetch from API
        const res = await fetch(`http://127.0.0.1:5000/api/exam-results/${this.attemptId}`, {
          headers: {
            Authorization: `Bearer ${this.token}`
          }
        })

        if (!res.ok) {
          throw new Error(`Failed to fetch results (${res.status})`)
        }

        this.resultData = await res.json()
      } catch (err) {
        console.error('fetchResults error', err)
        this.error = err.message || 'Failed to load results'
      } finally {
        this.loading = false
      }
    }
  },
  mounted() {
    if (this.token) {
      this.fetchResults()
    } else {
      this.error = 'Please login to view results'
      this.loading = false
    }
  }
}
</script>