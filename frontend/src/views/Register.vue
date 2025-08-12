<template>
  <div>
    <h2>Register</h2>
    <form @submit.prevent="register">
      <input v-model="name" type="text" placeholder="Full Name" required />
      <input v-model="email" type="email" placeholder="Email" required />
      <input v-model="password" type="password" placeholder="Password" required />
      <select v-model="role" required>
        <option disabled value="">Select Role</option>
        <option value="student">Student</option>
        <option value="educator">Educator</option>
      </select>
      <button type="submit">Register</button>
    </form>
    <p v-if="error" style="color: red">{{ error }}</p>
  </div>
</template>

<script>
export default {
  data() {
    return {
      name: '',
      email: '',
      password: '',
      role: '',
      error: ''
    }
  },
  methods: {
    async register() {
      this.error = ''
      try {
        const res = await fetch('http://127.0.0.1:5000/api/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: this.name,
            email: this.email,
            password: this.password,
            role: this.role
          })
        })
        const data = await res.json()

        if (!res.ok) {
          throw new Error(data.error || 'Registration failed')
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