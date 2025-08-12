<template>
  <div>
    <NavBar :token="token" @logout="logout" />

    <main>
      <!-- Router-view forwards events from routed components -->
      <router-view @authenticated="handleAuth" @logout="logout" :token="token" />
    </main>
  </div>
</template>

<script>
import NavBar from './components/NavBar.vue' // file name matches component

export default {
  components: { NavBar },
  data() {
    return {
      token: localStorage.getItem('token') || null
    }
  },
  methods: {
    handleAuth(token) {
      this.token = token
      localStorage.setItem('token', token)
    },
    logout() {
      this.token = null
      localStorage.removeItem('token')
      this.$router.push('/login')
    }
  }
}
</script>

<style>
main {
  padding: 20px;
}
</style>