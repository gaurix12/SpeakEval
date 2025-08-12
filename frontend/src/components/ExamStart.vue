<template>
  <div>
    <h3>Exam: {{ exam.title }}</h3>
    <p>Duration: {{ exam.duration_minutes }} min</p>

    <p v-if="timeLeft > 0">Time Left: {{ formattedTimeLeft }}</p>
    <p v-else>Time is up!</p>

    <div v-if="faceCheckWarning" style="color: red; font-weight: bold; margin-bottom: 15px;">
      {{ faceCheckWarning }}
    </div>

    <div v-if="questions.length === 0">Loading questions...</div>

    <div v-for="q in questions" :key="q.id" style="margin-bottom: 30px;">
      <strong>Q{{ q.order }}: {{ q.question_text }}</strong>

      <div>
        <button 
          @click="startListening(q.id)" 
          :disabled="listeningQuestionId === q.id || timeLeft <= 0"
        >
          {{ listeningQuestionId === q.id ? 'Listening...' : 'Start Speaking' }}
        </button>
        <button 
          @click="stopListening()" 
          :disabled="listeningQuestionId !== q.id || timeLeft <= 0"
        >
          Stop
        </button>
      </div>

      <p v-if="liveTranscript[q.id]"><em>Heard: {{ liveTranscript[q.id] }}</em></p>

      <div v-if="answers[q.id]">
        <p><strong>Final Answer:</strong> {{ answers[q.id].spoken_text }}</p>
        <p>Score: {{ answers[q.id].points_awarded.toFixed(2) }} / {{ q.points }}</p>
      </div>
    </div>

    <button @click="completeExam" :disabled="loading || timeLeft <= 0">Complete Exam</button>
    <button @click="$emit('cancel')" :disabled="timeLeft <= 0">Cancel</button>

    <p v-if="error" style="color:red">{{ error }}</p>

    <!-- Webcam video for proctoring -->
    <video ref="video" autoplay muted playsinline width="320" height="240" style="border:1px solid black; margin-top: 20px;"></video>
  </div>
</template>

<script>
export default {
  props: ['token', 'examId'],
  data() {
    return {
      exam: {},
      questions: [],
      answers: {},
      liveTranscript: {},
      listeningQuestionId: null,
      recognition: null,
      loading: false,
      error: '',
      attemptId: null,
      timeLeft: 0,    // time left in seconds
      timerInterval: null,
      proctorInterval: null,
      faceCheckWarning: '',
    }
  },
  computed: {
    formattedTimeLeft() {
      const min = Math.floor(this.timeLeft / 60)
      const sec = this.timeLeft % 60
      return `${min}:${sec.toString().padStart(2, '0')}`
    }
  },
  methods: {
    async fetchQuestions() {
      try {
        const res = await fetch(`http://127.0.0.1:5000/api/exams/${this.examId}/start`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${this.token}`
          }
        })
        if (!res.ok) throw new Error('Failed to start exam')
        const data = await res.json()
        this.exam = data.exam
        this.questions = data.questions
        this.attemptId = data.attempt_id

        // Start timer and webcam proctoring
        this.timeLeft = this.exam.duration_minutes * 60
        this.startTimer()
        await this.startWebcam()
        this.startProctoring()  // start regular frame sending here

      } catch (err) {
        this.error = err.message
      }
    },
    startTimer() {
      if (this.timerInterval) clearInterval(this.timerInterval)
      this.timerInterval = setInterval(() => {
        if (this.timeLeft > 0) {
          this.timeLeft--
        } else {
          clearInterval(this.timerInterval)
          this.completeExam()
        }
      }, 1000)
    },
    async startWebcam() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        this.$refs.video.srcObject = stream
      } catch (err) {
        this.error = 'Webcam access denied or error: ' + err.message
      }
    },
    startProctoring() {
      if (this.proctorInterval) clearInterval(this.proctorInterval)
      this.proctorInterval = setInterval(this.sendProctorFrame, 5000)
      this.sendProctorFrame()  // also send immediately on start
    },
    async sendProctorFrame() {
      const video = this.$refs.video
      if (!video || !video.videoWidth || !video.videoHeight) return

      const canvas = document.createElement('canvas')
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext('2d')
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

      const base64Image = canvas.toDataURL('image/jpeg')

      try {
        const res = await fetch('http://127.0.0.1:5000/api/proctoring/face-check', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.token}`
          },
          body: JSON.stringify({ frame: base64Image })
        })
        const data = await res.json()

        if (!res.ok) throw new Error(data.error || 'Proctoring check failed')

        if (!data.face_detected) {
          this.faceCheckWarning = 'No face detected! Please keep your face visible.'
        } else if (data.multiple_faces) {
          this.faceCheckWarning = 'Multiple faces detected! Exam may be flagged.'
        } else if (data.eye_movement_detected) {
          this.faceCheckWarning = 'Excessive eye movement detected! Stay focused.'
        } else {
          this.faceCheckWarning = ''
        }
      } catch (err) {
        this.faceCheckWarning = 'Proctoring error: ' + err.message
      }
    },
    startListening(questionId) {
      this.error = ''
      if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
        this.error = 'Speech Recognition not supported in this browser.'
        return
      }

      if (this.recognition) {
        this.recognition.stop()
        this.recognition = null
      }

      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
      this.recognition = new SpeechRecognition()

      this.recognition.lang = 'en-US'
      this.recognition.interimResults = true
      this.recognition.maxAlternatives = 1

      this.listeningQuestionId = questionId
      this.liveTranscript[questionId] = ''

      this.recognition.onresult = (event) => {
        let interimTranscript = ''
        let finalTranscript = ''

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript
          } else {
            interimTranscript += event.results[i][0].transcript
          }
        }

        this.liveTranscript[questionId] = finalTranscript || interimTranscript
      }

      this.recognition.onerror = (event) => {
        this.error = 'Speech recognition error: ' + event.error
        this.stopListening()
      }

      this.recognition.onend = () => {
        if (this.liveTranscript[questionId]) {
          this.sendAnswer(questionId, this.liveTranscript[questionId])
        }
        this.listeningQuestionId = null
      }

      this.recognition.start()
    },
    stopListening() {
      if (this.recognition) {
        this.recognition.stop()
      }
      this.listeningQuestionId = null
    },
    async sendAnswer(questionId, spokenText) {
      this.error = ''
      try {
        this.loading = true
        const res = await fetch('http://127.0.0.1:5000/api/evaluate-answer', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.token}`
          },
          body: JSON.stringify({
            attempt_id: this.attemptId,
            question_id: questionId,
            spoken_text: spokenText
          })
        })

        const data = await res.json()
        if (!res.ok) throw new Error(data.error || 'Failed to submit answer')

        this.answers[questionId] = data
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    async completeExam() {
      try {
        this.loading = true
        const res = await fetch('http://127.0.0.1:5000/api/complete-exam', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.token}`
          },
          body: JSON.stringify({ attempt_id: this.attemptId })
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.error || 'Failed to complete exam')
        alert(`Exam completed! Total score: ${data.total_score.toFixed(2)}`)
        this.$emit('completed')
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
        clearInterval(this.timerInterval)
        clearInterval(this.proctorInterval)

        // Stop webcam stream
        if (this.$refs.video && this.$refs.video.srcObject) {
          this.$refs.video.srcObject.getTracks().forEach(track => track.stop())
        }
      }
    }
  },
  mounted() {
    this.fetchQuestions()
  },
  beforeUnmount() {
    if (this.timerInterval) clearInterval(this.timerInterval)
    if (this.proctorInterval) clearInterval(this.proctorInterval)

    if (this.$refs.video && this.$refs.video.srcObject) {
      this.$refs.video.srcObject.getTracks().forEach(track => track.stop())
    }
  }
}
</script>
