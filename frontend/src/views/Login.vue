<template>
  <div>
    <h2>Login</h2>
    <form @submit.prevent="login">
      <input v-model="email" type="email" placeholder="Email" required />
      <input v-model="password" type="password" placeholder="Password" required />
      <button type="submit">Login</button>
    </form>
    <p v-if="error" style="color: red">{{ error }}</p>
  </div>
</template>

<script>
export default {
  data() {
    return {
      email: '',
      password: '',
      error: ''
    }
  },
  methods: {
    async login() {
      this.error = ''
      try {
        const res = await fetch('http://127.0.0.1:5000/api/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: this.email,
            password: this.password
          })
        })
        const data = await res.json()

        if (!res.ok) {
          throw new Error(data.error || 'Login failed')
        }

        // Emit standardized event so App.vue can handle token storage
        this.$emit('authenticated', data.token)

        // navigate to exams
        this.$router.push('/exams')

      } catch (err) {
        this.error = err.message
      }
    }
  }
}
</script>