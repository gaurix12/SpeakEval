<template>
  <nav>
    <template v-if="!token">
      <router-link to="/login" active-class="active">Login</router-link> |
      <router-link to="/register" active-class="active">Register</router-link>
    </template>

    <template v-else>
      <router-link to="/exams" active-class="active">Exams</router-link> |
      <a href="#" @click.prevent="onLogout">Logout</a>
    </template>
  </nav>
</template>

<script>
export default {
  name: 'NavBar',
  props: {
    token: {
      type: String,
      default: null
    }
  },
  methods: {
    onLogout() {
      // Emit logout so App.vue can clear token and redirect
      this.$emit('logout')
    }
  }
}
</script>

<style>
nav {
  margin-bottom: 20px;
}
.active {
  font-weight: bold;
  color: blue;
}
</style>