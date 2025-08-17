<template>
  <div class="register">
    <h2>Register</h2>

    <form @submit.prevent="register" novalidate>
      <div>
        <label for="name">Full name</label>
        <input id="name" v-model="name" type="text" placeholder="Full Name" required />
      </div>

      <div>
        <label for="email">Email</label>
        <input id="email" v-model="email" type="email" placeholder="Email" required />
      </div>

      <div>
        <label for="role">Role</label>
        <select id="role" v-model="role" required>
          <option disabled value="">Select Role</option>
          <option value="student">Student</option>
          <option value="educator">Educator</option>
        </select>
      </div>

      <div>
        <label for="password">Password</label>
        <input id="password" v-model="password" type="password" placeholder="Password" required />
        <small v-if="password && password.length < minPasswordLength">
          Password should be at least {{ minPasswordLength }} characters.
        </small>
      </div>

      <div>
        <label for="confirm">Confirm password</label>
        <input id="confirm" v-model="confirmPassword" type="password" placeholder="Confirm password" />
        <small v-if="confirmPassword && confirmPassword !== password">
          Passwords do not match.
        </small>
      </div>

      <div>
        <button type="submit" :disabled="loading || !canSubmit">
          <span v-if="loading">Registering…</span>
          <span v-else>Register</span>
        </button>
      </div>
    </form>

    <p v-if="message" style="color:green">{{ message }}</p>
    <p v-if="error" style="color: red">{{ error }}</p>
  </div>
</template>

<script>
export default {
  name: 'Register',
  data() {
    return {
      name: '',
      email: '',
      password: '',
      confirmPassword: '',
      role: '',
      loading: false,
      error: '',
      message: '',
      minPasswordLength: 8,
    }
  },
  computed: {
    // Small client-side checks to avoid wasted network calls
    canSubmit() {
      if (!this.name.trim()) return false
      if (!this.email.trim() || !this.role) return false
      if (!this.password || this.password.length < this.minPasswordLength) return false
      if (this.confirmPassword && this.confirmPassword !== this.password) return false
      return true
    },
    apiBase() {
      // Prefer environment var (Vite): import.meta.env.VITE_API_BASE
      // Fallback to local backend for dev
      return (import.meta && import.meta.env && import.meta.env.VITE_API_BASE) ? import.meta.env.VITE_API_BASE : 'http://127.0.0.1:5000'
    }
  },
  methods: {
    async register() {
      this.error = ''
      this.message = ''
      if (!this.canSubmit) {
        this.error = 'Please fill all required fields correctly.'
        return
      }

      this.loading = true
      try {
        const payload = {
          name: this.name.trim(),
          email: this.email.trim().toLowerCase(),
          password: this.password,
          role: this.role
        }

        const res = await fetch(`${this.apiBase}/api/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })

        // Prefer checking res.ok before parsing JSON to handle non-json error responses safely.
        if (!res.ok) {
          // try parsing JSON error body, otherwise fall back to text
          let errMsg = `Registration failed (${res.status})`
          try {
            const errJson = await res.json()
            errMsg = errJson.error || JSON.stringify(errJson)
          } catch (e) {
            const text = await res.text().catch(() => '')
            if (text) errMsg = text
          }
          throw new Error(errMsg)
        }

        const data = await res.json()
        if (!data || !data.token) {
          throw new Error('Invalid response from server')
        }

        // Emit token (parent App.vue should store token and user)
        this.$emit('authenticated', data.token, data.user || null)
        this.message = 'Registration successful! Redirecting…'

        // clear password fields for safety
        this.password = ''
        this.confirmPassword = ''

        // Navigate to exams using route name (ensure router has name 'Exams')
        this.$router.push({ name: 'Exams' }).catch(() => {})
      } catch (err) {
        console.error('register error', err)
        this.error = err.message || 'Registration failed'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>