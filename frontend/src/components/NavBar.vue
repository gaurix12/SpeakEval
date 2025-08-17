<template>
  <nav class="navbar">
    <div class="logo">SpeakEval</div>
    <div class="links">
      <template v-if="!token">
        <router-link
          to="/login"
          class="nav-link"
          active-class="active-link"
        >
          Login
        </router-link>
        <router-link
          to="/register"
          class="nav-link"
          active-class="active-link"
        >
          Register
        </router-link>
      </template>
      <template v-else>
        <router-link
          to="/exams"
          class="nav-link"
          active-class="active-link"
        >
          Exams
        </router-link>
        <button
          @click.prevent="onLogout"
          class="nav-button"
        >
          Logout
        </button>
      </template>
    </div>
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
      this.$emit('logout');
    }
  }
};
</script>