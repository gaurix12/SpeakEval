<template>
  <div id="app">
    <NavBar :token="token" @logout="logout" />

    <!-- Use router-view slot to forward props/listeners to the routed component -->
    <router-view v-slot="{ Component, route }">
      <component
        :is="Component"
        :token="token"
        :key="route.fullPath"
        @authenticated="handleAuthenticated"
        @logout="logout"
      />
    </router-view>
  </div>
</template>

<script>
import NavBar from './components/NavBar.vue'

export default {
  name: 'App',
  components: { NavBar },
  data() {
    return {
      token: null,
      user: null
    }
  },
  methods: {
    handleAuthenticated(token, user = null) {
      this.token = token
      this.user = user

      localStorage.setItem('auth_token', token)
      if (user) localStorage.setItem('user_data', JSON.stringify(user))
    },

    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user_data')
      if (this.$route.name !== 'Login' && this.$route.name !== 'Register') {
        this.$router.push({ name: 'Login' }).catch(()=>{})
      }
    },

    async validateToken(token) {
      try {
        const res = await fetch('http://127.0.0.1:5000/api/validate-token', {
          method: 'GET',
          headers: { Authorization: `Bearer ${token}` }
        })
        // treat 200 as valid, any other as invalid
        return res.ok
      } catch (e) {
        console.warn('Token validation failed:', e)
        return false
      }
    }
  },

  async mounted() {
    const storedToken = localStorage.getItem('auth_token')
    const storedUser = localStorage.getItem('user_data')

    if (storedToken) {
      const isValid = await this.validateToken(storedToken)
      if (isValid) {
        this.token = storedToken
        if (storedUser) {
          try { this.user = JSON.parse(storedUser) } catch(_) { this.user = null }
        }
        // route to exams by name to avoid path mismatch
        if (this.$route.name === 'Login' || this.$route.name === 'Register' || this.$route.name === 'Home') {
          this.$router.push({ name: 'Exams' }).catch(()=>{})
        }
      } else {
        this.logout()
      }
    } else {
      // if public pages exist, skip redirect; otherwise send to login
      if (this.$route.name !== 'Login' && this.$route.name !== 'Register') {
        this.$router.push({ name: 'Login' }).catch(()=>{})
      }
    }
  }
}
</script>
