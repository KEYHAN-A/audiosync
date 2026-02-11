<script setup>
import { useAuth } from "../composables/useAuth.js";

const props = defineProps({
  visible: { type: Boolean, default: false },
});

const emit = defineEmits(["close"]);

const { state: authState, isLoggedIn, startDeviceLogin, cancelDeviceLogin, logout } = useAuth();

async function handleLogin() {
  await startDeviceLogin();
}

async function handleLogout() {
  await logout();
}

function handleClose() {
  if (authState.deviceFlowActive) {
    cancelDeviceLogin();
  }
  emit("close");
}
</script>

<template>
  <Transition name="fade">
    <div v-if="visible" class="dialog-overlay" @click.self="handleClose">
      <div class="dialog glass-card">
        <div class="dialog-header">
          <h3 class="dialog-title">Account</h3>
          <button class="close-btn" @click="handleClose">&times;</button>
        </div>

        <!-- Logged in state -->
        <div v-if="isLoggedIn" class="logged-in">
          <div class="user-card">
            <img
              v-if="authState.user?.picture"
              :src="authState.user.picture"
              class="user-avatar"
              referrerpolicy="no-referrer"
            />
            <div v-else class="user-avatar-placeholder">
              {{ (authState.user?.name || authState.user?.email || "?")[0].toUpperCase() }}
            </div>
            <div class="user-info">
              <span class="user-name">{{ authState.user?.name || "User" }}</span>
              <span class="user-email">{{ authState.user?.email }}</span>
            </div>
          </div>

          <div class="feature-list">
            <div class="feature-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Save projects to the cloud
            </div>
            <div class="feature-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Share timelines via link
            </div>
            <div class="feature-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Access from any device
            </div>
          </div>

          <button class="btn btn-ghost btn-block" @click="handleLogout">
            Sign Out
          </button>
        </div>

        <!-- Device flow in progress -->
        <div v-else-if="authState.deviceFlowActive" class="device-flow">
          <div class="flow-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.193-9.193a4.5 4.5 0 00-6.364 0l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
            </svg>
          </div>

          <p class="flow-instruction">
            A browser window has opened. Sign in with Google, then enter this code:
          </p>

          <div class="user-code">{{ authState.userCode }}</div>

          <div class="flow-status">
            <div class="spinner"></div>
            <span>Waiting for authorization...</span>
          </div>

          <button class="btn btn-ghost btn-sm" @click="cancelDeviceLogin">
            Cancel
          </button>
        </div>

        <!-- Login prompt -->
        <div v-else class="login-prompt">
          <div class="prompt-icon">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
            </svg>
          </div>

          <h4 class="prompt-title">Sign in to unlock cloud features</h4>
          <p class="prompt-desc">
            Save your projects to the cloud, share timelines with collaborators, and access your work from anywhere.
          </p>

          <div class="feature-list">
            <div class="feature-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.338-2.32 3.75 3.75 0 013.572 5.345A4.5 4.5 0 0118 19.5H6.75z" />
              </svg>
              Cloud project storage
            </div>
            <div class="feature-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z" />
              </svg>
              Share timelines via link
            </div>
            <div class="feature-item dim">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Free — no account required to use the app
            </div>
          </div>

          <button class="btn btn-google" @click="handleLogin">
            <svg class="google-icon" viewBox="0 0 24 24" width="18" height="18">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            Sign in with Google
          </button>

          <p v-if="authState.deviceFlowError" class="flow-error">
            {{ authState.deviceFlowError }}
          </p>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(6, 12, 28, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog {
  width: 420px;
  max-width: 90vw;
  padding: 28px;
  border-radius: 20px;
  background: rgba(21, 28, 46, 0.95);
  border: 1px solid rgba(56, 189, 248, 0.15);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.dialog-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-bright);
}

.close-btn {
  width: 28px;
  height: 28px;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.close-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: #ef4444;
  color: #ef4444;
}

/* Logged in */
.user-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  background: rgba(56, 189, 248, 0.06);
  border: 1px solid rgba(56, 189, 248, 0.12);
  border-radius: 14px;
  margin-bottom: 20px;
}

.user-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid rgba(56, 189, 248, 0.3);
}

.user-avatar-placeholder {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: linear-gradient(135deg, #06b6d4, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 18px;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-bright);
}

.user-email {
  font-size: 11px;
  color: var(--text-muted);
}

/* Feature list */
.feature-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--text-dim);
}

.feature-item svg {
  color: #34d399;
  flex-shrink: 0;
}

.feature-item.dim {
  color: var(--text-muted);
}

.feature-item.dim svg {
  color: var(--text-muted);
}

/* Login prompt */
.login-prompt {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.prompt-icon {
  color: var(--cyan, #38bdf8);
  margin-bottom: 16px;
  opacity: 0.7;
}

.prompt-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-bright);
  margin-bottom: 8px;
}

.prompt-desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.6;
  max-width: 320px;
  margin-bottom: 20px;
}

.btn-google {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  padding: 12px 20px;
  border-radius: 12px;
  border: 1px solid var(--border-light, rgba(56, 189, 248, 0.2));
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-bright, #e2e8f0);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-google:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(56, 189, 248, 0.4);
  box-shadow: 0 0 20px rgba(56, 189, 248, 0.1);
}

.google-icon {
  flex-shrink: 0;
}

.flow-error {
  margin-top: 12px;
  font-size: 12px;
  color: #ef4444;
}

/* Device flow */
.device-flow {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.flow-icon {
  color: var(--cyan, #38bdf8);
  margin-bottom: 16px;
  opacity: 0.7;
}

.flow-instruction {
  font-size: 12px;
  color: var(--text-dim);
  line-height: 1.6;
  margin-bottom: 20px;
  max-width: 300px;
}

.user-code {
  font-family: "JetBrains Mono", "SF Mono", monospace;
  font-size: 32px;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: var(--cyan, #38bdf8);
  padding: 14px 28px;
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.25);
  border-radius: 14px;
  margin-bottom: 24px;
  user-select: all;
}

.flow-status {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(56, 189, 248, 0.2);
  border-top-color: var(--cyan, #38bdf8);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.btn-block {
  width: 100%;
}
</style>
