<script setup>
const props = defineProps({
  currentStep: { type: Number, default: 0 },
  canAnalyze: { type: Boolean, default: false },
  canExport: { type: Boolean, default: false },
});

const emit = defineEmits(["analyze", "export"]);

const steps = [
  { label: "Import", icon: "1" },
  { label: "Analyze & Sync", icon: "2" },
  { label: "Export", icon: "3" },
];
</script>

<template>
  <div class="workflow-bar">
    <div class="workflow-steps">
      <template v-for="(step, index) in steps" :key="index">
        <!-- Connector line -->
        <div
          v-if="index > 0"
          class="step-connector"
          :class="{ active: currentStep >= index }"
        ></div>

        <!-- Step -->
        <div
          class="step"
          :class="{
            active: currentStep === index,
            completed: currentStep > index,
            upcoming: currentStep < index,
            clickable: (index === 1 && canAnalyze) || (index === 2 && canExport),
          }"
          @click="index === 1 && canAnalyze ? emit('analyze') : index === 2 && canExport ? emit('export') : null"
        >
          <div class="step-circle">
            <span v-if="currentStep > index" class="step-check">&#10003;</span>
            <span v-else>{{ step.icon }}</span>
          </div>
          <span class="step-label">{{ step.label }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.workflow-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 14px 24px;
  background-color: var(--bg-panel);
  border-bottom: 1px solid var(--border-subtle);
}

.workflow-steps {
  display: flex;
  align-items: center;
  gap: 0;
}

.step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  border-radius: 12px;
  transition: all 0.3s ease;
}

.step.clickable {
  cursor: pointer;
}

.step.clickable:hover {
  background: rgba(56, 189, 248, 0.06);
}

.step-circle {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  transition: all 0.3s ease;
  border: 2px solid var(--border-light);
  color: var(--text-muted);
  background: var(--bg-input);
}

.step-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  transition: color 0.3s ease;
}

.step-connector {
  width: 40px;
  height: 2px;
  background: var(--border-subtle);
  transition: background 0.3s ease;
}

.step-connector.active {
  background: linear-gradient(90deg, var(--cyan), var(--purple));
}

/* Active step */
.step.active .step-circle {
  border-color: var(--cyan);
  background: var(--cyan);
  color: var(--navy-deep);
  box-shadow: 0 0 16px var(--glow-cyan);
}

.step.active .step-label {
  color: var(--text-bright);
}

/* Completed step */
.step.completed .step-circle {
  border-color: var(--purple);
  background: var(--purple);
  color: white;
}

.step.completed .step-label {
  color: var(--text-dim);
}

.step-check {
  font-size: 14px;
  line-height: 1;
}
</style>
