<template>
  <div>
    <h3>Exam: {{ exam.title }}</h3>
    <p>Duration: {{ exam.duration_minutes }} min</p>
    <p v-if="timeLeft > 0">Time Left: {{ formattedTimeLeft }}</p>
    <p v-else>Time is up!</p>

    <div v-if="faceCheckWarning" style="color: red; font-weight: bold; margin-bottom: 15px;">
      {{ faceCheckWarning }}
    </div>

    <div v-if="!currentQuestion">Loading question...</div>

    <div v-else style="margin-bottom: 30px;">
      <strong>Q{{ currentQuestion.order }}: {{ currentQuestion.question_text }}</strong>

      <p v-if="liveTranscript[currentQuestion.id]"><em>Heard: {{ liveTranscript[currentQuestion.id] }}</em></p>

      <div v-if="answers[currentQuestion.id]">
        <p><strong>Final Answer:</strong> {{ answers[currentQuestion.id].spoken_text }}</p>
        <p>Score: {{ (answers[currentQuestion.id].points_awarded || 0).toFixed(2) }} / {{ currentQuestion.points }}</p>
      </div>
    </div>

    <button @click="completeExam" :disabled="loading || timeLeft <= 0">Complete Exam</button>
    <button @click="$emit('cancel')" :disabled="timeLeft <= 0">Cancel</button>
    <p v-if="error" style="color:red">{{ error }}</p>

    <!-- Webcam video for proctoring -->
    <video ref="video" autoplay muted playsinline width="320" height="240"
           style="border:1px solid black; margin-top: 20px;"></video>
  </div>
</template>

<script>
export default {
  props: ['token', 'examId'],
  data() {
    return {
      exam: {},
      questions: [],
      currentIdx: 0,
      answers: {},             // saved answers & scores
      liveTranscript: {},      // interim/final transcripts per question id
      recognition: null,
      loading: false,
      error: '',
      attemptId: null,
      timeLeft: 0,
      timerInterval: null,
      proctorInterval: null,
      faceCheckWarning: '',
      lastProcessedText: {},   // prevent duplicate processing per question
    }
  },
  computed: {
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
    async fetchQuestions() {
      try {
        const res = await fetch(`http://127.0.0.1:5000/api/exams/${this.examId}/start`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${this.token}` }
        })
        if (!res.ok) throw new Error('Failed to start exam')
        const data = await res.json()
        this.exam = data.exam
        this.questions = data.questions || []
        this.attemptId = data.attempt_id

        // show first question immediately
        this.currentIdx = 0

        this.timeLeft = this.exam.duration_minutes * 60
        this.startTimer()
        await this.startWebcam()
        this.startProctoring()

        // start continuous recognition AFTER webcam/proctoring started
        this.startRecognition()
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
          this.finalizeExamAndNotify()
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
      this.sendProctorFrame()
      this.proctorInterval = setInterval(this.sendProctorFrame, 5000)
    },

    async sendProctorFrame() {
      const video = this.$refs.video
      if (!video || !video.videoWidth) return

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
            Authorization: `Bearer ${this.token}`
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

    startRecognition() {
      // feature-detect
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

      // onresult: process final results only (interim shown but not processed)
      this.recognition.onresult = (event) => {
        if (!this.currentQuestion) return
        const qid = this.currentQuestion.id
        let interim = ''
        let final = ''

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const r = event.results[i]
          if (r.isFinal) final += r[0].transcript
          else interim += r[0].transcript
        }

        // show interim or final
        if (final) {
          const normalized = final.trim()
          // store transcript display
          this.liveTranscript[qid] = normalized
          // avoid processing same final twice
          if (this.lastProcessedText[qid] === normalized) {
            return
          }
          this.lastProcessedText[qid] = normalized
          // process final transcript (may contain answer + command)
          this.handleFinalTranscript(qid, normalized.toLowerCase())
        } else {
          // show interim only
          this.liveTranscript[qid] = interim.trim()
        }
      }

      this.recognition.onerror = (e) => {
        console.error('Speech recognition error:', e)
        // show only non-spammy errors
        if (e.error && e.error !== 'no-speech') {
          this.error = 'Speech recognition error: ' + e.error
        }
      }

      // restart on end to keep listening (common workaround for continuous)
      this.recognition.onend = () => {
        if (this.timeLeft > 0) {
          try {
            this.recognition.start()
          } catch (e) {
            // sometimes start throws if already running — ignore
            console.warn('recognition restart ignored', e)
          }
        }
      }

      try {
        this.recognition.start()
      } catch (e) {
        console.warn('recognition start failed:', e)
      }
    },

    // Detect & dispatch commands or normal answer.
    async handleFinalTranscript(questionId, text) {
      if (!text) return
      // strip punctuation, trim
      const normalized = text.replace(/[.,?!]/g, '').trim()

      // check for commands (allow a few variants)
      const isSkip = ['skip the question', 'skip this question', 'skip'].some(p => normalized.endsWith(p))
      const isMoveNext = ['move to the next question', 'move next', 'next question', 'move to next question'].some(p => normalized.endsWith(p))
      const isEnd = ['end examination', 'end exam', 'finish exam', 'finish examination', 'end the exam'].some(p => normalized === p || normalized.endsWith(p))

      // If transcript contains an answer and then command at end, separate
      let answerPart = normalized
      if (isSkip) {
        answerPart = normalized.replace(/(skip the question|skip this question|skip)$/i, '').trim()
      } else if (isMoveNext) {
        answerPart = normalized.replace(/(move to the next question|move next|next question|move to next question)$/i, '').trim()
      } else if (isEnd) {
        answerPart = normalized.replace(/(end examination|end exam|finish exam|finish examination|end the exam)$/i, '').trim()
      }

      try {
        if (isSkip) {
          // call voice-command skip (backend will return next_question)
          await this.callVoiceCommand('skip the question', '', questionId)
        } else if (isMoveNext) {
          // prefer answerPart if present; backend move-next will grade it
          await this.callVoiceCommand('move to next question', answerPart, questionId)
        } else if (isEnd) {
          // finalize
          await this.callVoiceCommand('end examination', answerPart, questionId)
        } else {
          // not a command → treat as regular answer (evaluate and save)
          await this.sendAnswer(questionId, text)
        }
      } catch (err) {
        console.error('handleFinalTranscript error', err)
        this.error = err.message || String(err)
      }
    },

    // Unified voice-command caller
    async callVoiceCommand(commandText, spokenText = '', questionId = null) {
      // When calling voice-command, pass attempt_id, question_id, command, spoken_text
      // If the backend returns next_question, move to it; if returns end, finalize.
      try {
        const res = await fetch('http://127.0.0.1:5000/api/voice-command', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${this.token}`
          },
          body: JSON.stringify({
            attempt_id: this.attemptId,
            question_id: questionId,
            command: commandText,
            spoken_text: spokenText
          })
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.error || 'Voice command failed')

        // If backend returned points_awarded / spoken_text — update answers for current question
        if (data.points_awarded !== undefined) {
          this.answers[questionId] = {
            spoken_text: data.spoken_text || spokenText || '',
            points_awarded: data.points_awarded || 0
          }
        }

        // If backend returned next_question => move to it (update currentIdx accordingly)
        if (data.next_question) {
          // find index of next_question in questions list and set currentIdx
          const idx = this.questions.findIndex(q => q.id === data.next_question.id)
          if (idx !== -1) {
            this.currentIdx = idx
          } else {
            // fallback: push next question to list and move
            this.questions = this.questions.concat([data.next_question])
            this.currentIdx = this.questions.length - 1
          }
          // reset live transcript for that question
          this.liveTranscript[data.next_question.id] = ''
        } else {
          // no next question -> finish
          await this.finalizeExamAndNotify()
        }

        return data
      } catch (err) {
        console.error('callVoiceCommand error', err)
        throw err
      }
    },

    async sendAnswer(questionId, spokenText) {
      // simple debounce/duplicate guard (do nothing if same final processed)
      if (!spokenText) return
      if (this.lastProcessedText[questionId] === spokenText.trim()) {
        // already processed by handleFinalTranscript
        return
      }
      // still set last processed for guard
      this.lastProcessedText[questionId] = spokenText.trim()

      try {
        this.loading = true
        const res = await fetch('http://127.0.0.1:5000/api/evaluate-answer', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${this.token}`
          },
          body: JSON.stringify({ attempt_id: this.attemptId, question_id: questionId, spoken_text: spokenText })
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.error || 'Failed to submit answer')
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

    async finalizeExamAndNotify() {
      // call end-exam route to finalize and get totals/breakdown
      try {
        const res = await fetch('http://127.0.0.1:5000/api/end-exam', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${this.token}`
          },
          body: JSON.stringify({ attempt_id: this.attemptId })
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.error || 'Failed to finalize exam')
        alert(`Exam completed! Total score: ${data.total_score.toFixed(2)}`)
        // optionally expose breakdown in UI: data.breakdown
        this.$emit('completed')
      } catch (err) {
        console.error('finalizeExam error', err)
        this.error = err.message || String(err)
      } finally {
        // teardown resources
        clearInterval(this.timerInterval)
        clearInterval(this.proctorInterval)
        if (this.recognition) {
          try { this.recognition.onend = null } catch(e) {}
          try { this.recognition.stop() } catch(e) {}
        }
        if (this.$refs.video && this.$refs.video.srcObject) {
          this.$refs.video.srcObject.getTracks().forEach(t => t.stop())
        }
      }
    },

    async completeExam() {
      // manual complete button – reuse same finalize helper
      await this.finalizeExamAndNotify()
    }
  },

  mounted() {
    this.fetchQuestions()
  },

  beforeUnmount() {
    clearInterval(this.timerInterval)
    clearInterval(this.proctorInterval)
    if (this.recognition) {
      try { this.recognition.onend = null } catch(e) {}
      try { this.recognition.stop() } catch(e) {}
    }
    if (this.$refs.video && this.$refs.video.srcObject) {
      this.$refs.video.srcObject.getTracks().forEach(t => t.stop())
    }
  }
}
</script>
