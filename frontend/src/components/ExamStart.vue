<template>
  <div class="exam-start-container">
    <!-- Voice Command Instructions Panel -->
    <div class="voice-instructions">
      <h4>You can say:</h4>
      <ul>
        <li><code>"end exam"</code> – finish the exam</li>
        <li><code>"skip the question"</code> – skip current question (0 points)</li>
        <li><code>"move to the next question"</code> – grade current and go next</li>
      </ul>
    </div>

    <h3 v-if="exam && exam.title">Exam: {{ exam.title }}</h3>
    <p v-if="exam && exam.duration_minutes !== undefined">Duration: {{ exam.duration_minutes }} min</p>
    <p v-if="timeLeft > 0">Time Left: {{ formattedTimeLeft }}</p>
    <p v-else-if="attemptId">Time is up!</p>

    <div v-if="faceCheckWarning" style="color: red; font-weight: bold; margin-bottom: 15px;">
      {{ faceCheckWarning }}
    </div>

    <div v-if="!currentQuestion && !loading && questions.length === 0">
      No questions found for this exam.
    </div>
    <div v-else-if="!currentQuestion">
      Loading question...
    </div>

    <div v-else class="question-container">
      <strong>Q{{ currentQuestion.order }}: {{ currentQuestion.question_text }}</strong>
      <p v-if="liveTranscript[currentQuestion.id]"><em>Heard: {{ liveTranscript[currentQuestion.id] }}</em></p>

      <div v-if="answers[currentQuestion.id]">
        <p><strong>Final Answer:</strong> {{ answers[currentQuestion.id].spoken_text }}</p>
        <p>
          Score:
          {{ intScore(answers[currentQuestion.id].points_awarded) }}
          /
          {{ currentQuestion.points }}
        </p>
      </div>
    </div>

    <div class="exam-controls">
      <button @click="completeExam" :disabled="loading || timeLeft <= 0 || !attemptId">Complete Exam</button>
      <button @click="onCancel" :disabled="timeLeft <= 0">Cancel</button>
    </div>

    <p v-if="error" style="color:red">{{ error }}</p>

    <div class="webcam-container">
      <video
        ref="video"
        autoplay
        muted
        playsinline
        width="320"
        height="240"
      ></video>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ExamStart',
  props: {
    token: { type: String, required: true },
    // Optional if using as a routed page: will fallback to $route.params.examId
    examId: { type: [String, Number], default: null }
  },
  data() {
    return {
      exam: {},
      questions: [],
      currentIdx: 0,
      answers: {},            // saved answers & scores
      liveTranscript: {},     // interim/final transcripts per question id
      recognition: null,
      loading: false,
      error: '',
      attemptId: null,
      timeLeft: 0,
      timerInterval: null,
      proctorInterval: null,
      faceCheckWarning: '',
      lastProcessedText: {},  // prevent duplicate processing per question
      _proctorLocked: false,
      _destroyed: false,
      // Add base URL configuration
      baseURL: process.env.NODE_ENV === 'production' ? '/api' : 'http://localhost:5000/api'
    }
  },
  computed: {
    effectiveExamId() {
      // Allow route-driven usage: /exams/:examId/start
      return this.examId || this.$route?.params?.examId
    },
    formattedTimeLeft() {
      const min = Math.floor(this.timeLeft / 60)
      const sec = this.timeLeft % 60
      return `${min}:${sec.toString().padStart(2, '0')}`
    },
    currentQuestion() {
      return this.questions[this.currentIdx] || null
    }
  },
  methods: {
    intScore(val) {
      // Ensure integer display in UI
      const n = Number(val || 0)
      return Number.isFinite(n) ? Math.round(n) : 0
    },

    // Enhanced fetch wrapper with better error handling
    async apiRequest(endpoint, options = {}) {
      const url = `${this.baseURL}${endpoint}`
      const defaultOptions = {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.token}`,
          ...options.headers
        }
      }
      
      try {
        console.log(`Making request to: ${url}`)
        const response = await fetch(url, { ...defaultOptions, ...options })
        
        if (!response.ok) {
          let errorMessage = `HTTP ${response.status}: ${response.statusText}`
          try {
            const errorData = await response.json()
            errorMessage = errorData.error || errorMessage
          } catch (e) {
            // If JSON parsing fails, use the status text
            try {
              const textError = await response.text()
              errorMessage = textError || errorMessage
            } catch (e2) {
              // Keep the default error message
            }
          }
          throw new Error(errorMessage)
        }
        
        return await response.json()
      } catch (error) {
        console.error(`API request failed for ${url}:`, error)
        
        // Handle network errors specifically
        if (error instanceof TypeError && error.message.includes('fetch')) {
          throw new Error('Network error: Unable to connect to server. Please check if the backend is running.')
        }
        
        throw error
      }
    },

    async fetchQuestions() {
      if (!this.effectiveExamId) {
        this.error = 'Missing examId.'
        return
      }
      try {
        this.loading = true
        this.error = '' // Clear previous errors
        
        const data = await this.apiRequest(`/exams/${this.effectiveExamId}/start`, {
          method: 'POST'
        })
        
        this.exam = data.exam || {}
        this.questions = data.questions || []
        this.attemptId = data.attempt_id
        this.currentIdx = 0

        // Timer
        this.timeLeft = (this.exam.duration_minutes || 0) * 60
        this.startTimer()

        // Devices & services
        await this.startWebcam()
        this.startProctoring()
        this.startRecognition()

        // If there are no questions, immediately finalize (edge case)
        if (this.questions.length === 0) {
          await this.finalizeExamAndNotify()
        }
      } catch (err) {
        console.error('fetchQuestions error', err)
        this.error = err.message || String(err)
      } finally {
        this.loading = false
      }
    },

    startTimer() {
      if (this.timerInterval) clearInterval(this.timerInterval)
      this.timerInterval = setInterval(() => {
        if (this._destroyed) return clearInterval(this.timerInterval)
        if (this.timeLeft > 0) this.timeLeft--
        else {
          clearInterval(this.timerInterval)
          this.finalizeExamAndNotify()
        }
      }, 1000)
    },

    async startWebcam() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        if (this.$refs.video) this.$refs.video.srcObject = stream
      } catch (err) {
        console.error('startWebcam error', err)
        this.error = 'Webcam access denied or error: ' + (err.message || err)
      }
    },

    startProctoring() {
      if (this.proctorInterval) clearInterval(this.proctorInterval)
      this._proctorLocked = false
      // Fire once quickly, then repeat
      this.sendProctorFrame()
      this.proctorInterval = setInterval(this.sendProctorFrame, 5000)
    },

    async sendProctorFrame() {
      if (this._destroyed) return
      const video = this.$refs.video
      if (!video || !video.videoWidth || this._proctorLocked) return

      const canvas = document.createElement('canvas')
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext('2d')
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

      const base64Image = canvas.toDataURL('image/jpeg')
      try {
        this._proctorLocked = true
        const data = await this.apiRequest('/proctoring/face-check', {
          method: 'POST',
          body: JSON.stringify({ frame: base64Image })
        })

        if (!data.face_detected) this.faceCheckWarning = 'No face detected! Please keep your face visible.'
        else if (data.multiple_faces) this.faceCheckWarning = 'Multiple faces detected! Exam may be flagged.'
        else if (data.eye_movement_detected) this.faceCheckWarning = 'Excessive eye movement detected! Stay focused.'
        else this.faceCheckWarning = ''
      } catch (err) {
        console.warn('sendProctorFrame', err)
        this.faceCheckWarning = 'Proctoring error: ' + (err.message || err)
      } finally {
        this._proctorLocked = false
      }
    },

    startRecognition() {
      if (!('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)) {
        this.error = 'Speech Recognition not supported in this browser.'
        return
      }
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
      this.recognition = new SpeechRecognition()
      this.recognition.lang = 'en-US'
      this.recognition.continuous = true
      this.recognition.interimResults = true
      this.recognition.maxAlternatives = 1

      this.recognition.onresult = (event) => {
        if (!this.currentQuestion) return
        const qid = this.currentQuestion.id
        let interim = ''
        let final = ''

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const r = event.results[i]
          const part = (r[0] && r[0].transcript) ? r[0].transcript : ''
          if (r.isFinal) final += (final ? ' ' : '') + part
          else interim += (interim ? ' ' : '') + part
        }

        if (final) {
          const normalized = final.trim()
          this.liveTranscript[qid] = normalized
          if (this.lastProcessedText[qid] === normalized) return
          this.lastProcessedText[qid] = normalized
          this.handleFinalTranscript(qid, normalized.toLowerCase())
        } else {
          this.liveTranscript[qid] = interim.trim()
        }
      }

      this.recognition.onerror = (e) => {
        console.warn('Speech recognition error:', e)
        // Ignore "no-speech" but surface other errors
        if (e.error && e.error !== 'no-speech') {
          this.error = 'Speech recognition error: ' + e.error
        }
      }

      this.recognition.onend = () => {
        // Keep it running while the exam is active
        if (this._destroyed) return
        if (this.timeLeft > 0) {
          try { this.recognition.start() } catch (e) { /* sometimes throws if already starting */ }
        }
      }

      try { this.recognition.start() } catch (e) { console.warn('recognition start error', e) }
    },

    // handle final transcript - robust command detection using includes & regex
    async handleFinalTranscript(questionId, text) {
      if (!text) return

      // normalize punctuation & whitespace
      const normalized = text.replace(/[^\w\s]/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase()

      const containsSkip = /(^|\s)(skip|skip the question|skip this question)(\s|$)/.test(normalized)
      const containsMoveNext = /(^|\s)(move to the next question|move next|next question|move to next question)(\s|$)/.test(normalized)
      const containsEnd = /(^|\s)(end examination|end exam|finish exam|finish examination|end the exam)(\s|$)/.test(normalized)

      // split answer text from trailing command (e.g., "answer ... move to next question")
      let answerPart = normalized
      answerPart = answerPart.replace(/(move to the next question|move next|next question|skip the question|skip this question|end examination|end exam|finish exam|finish examination|end the exam)$/i, '').trim()

      try {
        if (containsSkip) {
          await this.callSkipEndpoint(questionId)
        } else if (containsMoveNext) {
          const data = await this.callMoveNextEndpoint(questionId, answerPart)
          if (!data.next_question) {
            await this.finalizeExamAndNotify()
          }
        } else if (containsEnd) {
          await this.finalizeExamAndNotify()
        } else {
          // normal answer (no navigation)
          await this.sendAnswer(questionId, text)
        }
      } catch (err) {
        console.error('handleFinalTranscript error', err)
        this.error = err.message || String(err)
      }
    },

    // call existing backend skip endpoint
    async callSkipEndpoint(questionId) {
      if (!this.attemptId || !questionId) throw new Error('Missing attempt or question id')
      
      const data = await this.apiRequest('/skip-question', {
        method: 'POST',
        body: JSON.stringify({ attempt_id: this.attemptId, question_id: questionId })
      })
      
      // update local answers
      this.answers[questionId] = { spoken_text: '', points_awarded: 0 }
      // move to next question if exists
      const nextIdx = this.questions.findIndex(q => q.id === questionId) + 1
      if (nextIdx < this.questions.length) this.currentIdx = nextIdx
      else await this.finalizeExamAndNotify()
      return data
    },

    // call existing backend move-next endpoint (grades current and returns next question)
    async callMoveNextEndpoint(questionId, spokenText = '') {
      if (!this.attemptId || !questionId) throw new Error('Missing attempt or question id')
      
      const data = await this.apiRequest('/move-next', {
        method: 'POST',
        body: JSON.stringify({ attempt_id: this.attemptId, question_id: questionId, spoken_text: spokenText })
      })

      // update local answer if returned
      if (data.points_awarded !== undefined) {
        this.answers[questionId] = {
          spoken_text: data.spoken_text || spokenText || '',
          points_awarded: data.points_awarded || 0
        }
      }

      // if next_question returned, switch to it
      if (data.next_question) {
        const idx = this.questions.findIndex(q => q.id === data.next_question.id)
        if (idx !== -1) this.currentIdx = idx
        else {
          this.questions = this.questions.concat([data.next_question])
          this.currentIdx = this.questions.length - 1
        }
      }

      return data
    },

    async sendAnswer(questionId, spokenText) {
      if (!spokenText) return
      if (this.lastProcessedText[questionId] === spokenText.trim()) return
      this.lastProcessedText[questionId] = spokenText.trim()

      try {
        this.loading = true
        this.error = '' // Clear previous errors
        
        const data = await this.apiRequest('/evaluate-answer', {
          method: 'POST',
          body: JSON.stringify({ 
            attempt_id: this.attemptId, 
            question_id: questionId, 
            spoken_text: spokenText 
          })
        })
        
        this.answers[questionId] = {
          spoken_text: data.spoken_text || spokenText,
          points_awarded: data.points_awarded || 0
        }
      } catch (err) {
        console.error('sendAnswer error', err)
        this.error = err.message || String(err)
      } finally {
        this.loading = false
      }
    },

    // finalize exam; store breakdown and navigate to results
    async finalizeExamAndNotify() {
      if (!this.attemptId) return
      try {
        this.loading = true
        this.error = '' // Clear previous errors
        
        const data = await this.apiRequest('/complete-exam', {
          method: 'POST',
          body: JSON.stringify({ attempt_id: this.attemptId })
        })

        // Build breakdown from answers + questions if backend didn't return it
        let breakdown = data.breakdown || []
        if (!Array.isArray(breakdown) || breakdown.length === 0) {
          breakdown = this.questions.map(q => {
            const a = this.answers[q.id] || {}
            return {
              question_id: q.id,
              question_text: q.question_text,
              spoken_text: a.spoken_text || '',
              points_awarded: this.intScore(a.points_awarded || 0)
            }
          })
        } else {
          // ensure integer points for any existing breakdown
          breakdown = breakdown.map(b => ({
            ...b,
            points_awarded: this.intScore(b.points_awarded)
          }))
        }

        const resultData = {
          attempt_id: this.attemptId,
          exam_id: this.exam?.id,
          exam_title: this.exam?.title || '',
          total_score: this.intScore(data.total_score ?? 0),
          breakdown
        }

        // Save to sessionStorage then navigate to results route
        try {
          sessionStorage.setItem(`exam_result_${this.attemptId}`, JSON.stringify(resultData))
        } catch(e) { /* ignore quota errors */ }

        // Navigate to exam results page (expects route to be registered)
        this.$router.push({ name: 'ExamResults', params: { attemptId: String(this.attemptId) } })
      } catch (err) {
        console.error('finalizeExam error', err)
        this.error = err.message || String(err)
      } finally {
        this.loading = false
        this.cleanup()
      }
    },

    async completeExam() {
      await this.finalizeExamAndNotify()
    },

    onCancel() {
      // If used as a child component in a parent view:
      this.$emit('cancel')
      // If used as a dedicated route page:
      if (this.$router) this.$router.back()
    },

    cleanup() {
      clearInterval(this.timerInterval)
      clearInterval(this.proctorInterval)
      if (this.recognition) {
        try { this.recognition.onend = null } catch(e) {}
        try { this.recognition.stop() } catch(e) {}
      }
      if (this.$refs.video && this.$refs.video.srcObject) {
        try {
          this.$refs.video.srcObject.getTracks().forEach(t => t.stop())
        } catch(e) { /* ignore */ }
      }
    }
  },

  async mounted() {
    await this.fetchQuestions()
  },

  watch: {
    // If routed to a new exam id while component is alive
    '$route.params.examId': {
      immediate: false,
      async handler(newVal, oldVal) {
        if (String(newVal || '') !== String(oldVal || '')) {
          this.cleanup()
          this.exam = {}
          this.questions = []
          this.answers = {}
          this.liveTranscript = {}
          this.lastProcessedText = {}
          this.error = ''
          this.attemptId = null
          await this.fetchQuestions()
        }
      }
    }
  },

  beforeUnmount() {
    this._destroyed = true
    this.cleanup()
  }
}
</script>

<style scoped>
.exam-start-container {
  max-width: 720px;
  margin: 0 auto;
  padding: 16px;
}

.voice-instructions {
  background: #f7f7ff;
  border: 1px solid #e2e2ff;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

.question-container {
  margin: 16px 0;
  padding: 12px 16px;
  border: 1px solid #eee;
  border-radius: 8px;
}

.exam-controls {
  display: flex;
  gap: 12px;
  margin: 16px 0;
}

.webcam-container {
  margin-top: 16px;
}
</style>