<template>
  <div
    v-if="show"
    class="fixed inset-0 bg-black/70 flex items-center justify-center z-50"
    @click.self="onCancel"
  >
    <div class="bg-slate-900/95 backdrop-blur-xl rounded-2xl p-6 max-w-2xl w-full mx-4 border border-cyan-500/30 shadow-2xl shadow-cyan-500/20">
      <!-- Header -->
      <div class="flex items-center gap-3 mb-6">
        <div class="w-12 h-12 rounded-full bg-amber-500/20 flex items-center justify-center">
          <svg class="w-6 h-6 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
          </svg>
        </div>
        <div>
          <h2 class="text-xl font-semibold text-white">Missing Files</h2>
          <p class="text-slate-400 text-sm">
            {{ missingFiles.length }} file(s) could not be found
          </p>
        </div>
      </div>

      <!-- Missing files list -->
      <div class="max-h-80 overflow-y-auto mb-6 space-y-2">
        <div
          v-for="(file, index) in missingFiles"
          :key="index"
          class="bg-slate-800/50 rounded-lg p-3 border border-slate-700/50 flex items-start gap-3"
        >
          <div class="w-8 h-8 rounded bg-red-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
            <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-white font-medium truncate">{{ file.clip_name }}</p>
            <p class="text-slate-400 text-sm truncate">{{ file.original_path }}</p>
            <p class="text-slate-500 text-xs">{{ file.track_name }}</p>
          </div>
          <button
            v-if="!file.new_path"
            @click="locateFile(index)"
            class="px-3 py-1.5 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-400 rounded-lg text-sm transition-colors flex-shrink-0"
          >
            Locate
          </button>
          <div
            v-else
            class="px-3 py-1.5 bg-green-500/20 text-green-400 rounded-lg text-sm flex-shrink-0 flex items-center gap-1"
          >
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
            </svg>
            Found
          </div>
        </div>
      </div>

      <!-- Warnings -->
      <div
        v-if="warnings.length > 0"
        class="mb-6 bg-amber-500/10 border border-amber-500/30 rounded-lg p-4"
      >
        <h3 class="text-amber-400 font-medium mb-2 flex items-center gap-2">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          Warnings
        </h3>
        <ul class="text-slate-300 text-sm space-y-1">
          <li v-for="(warning, index) in warnings" :key="index" class="flex items-start gap-2">
            <span class="text-amber-400">•</span>
            <span>{{ warning.path }}: {{ warning.warning }}</span>
          </li>
        </ul>
      </div>

      <!-- Actions -->
      <div class="flex flex-wrap gap-3">
        <button
          @click="searchInFolder"
          class="flex-1 px-4 py-2.5 bg-slate-700/50 hover:bg-slate-700 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          Search in Folder
        </button>
        <button
          @click="skipMissing"
          class="px-4 py-2.5 bg-slate-700/50 hover:bg-slate-700 text-white rounded-lg transition-colors"
        >
          Skip Missing
        </button>
        <button
          @click="onCancel"
          class="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors"
        >
          Cancel
        </button>
      </div>

      <!-- Progress -->
      <div
        v-if="processing"
        class="mt-4 bg-slate-800/50 rounded-lg p-4 flex items-center gap-3"
      >
        <div class="w-5 h-5 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
        <span class="text-slate-300">{{ processingMessage }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { invoke } from '@tauri-apps/api/core';
import { open } from '@tauri-apps/plugin-dialog';

const props = defineProps({
  show: Boolean,
  missingFiles: {
    type: Array,
    default: () => []
  },
  warnings: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['cancel', 'relink', 'skip']);

const processing = ref(false);
const processingMessage = ref('');
const remapping = ref({});

// Locate a single file
async function locateFile(index) {
  try {
    const filePath = await open({
      multiple: false,
      filters: [
        {
          name: 'Media Files',
          extensions: ['wav', 'mp3', 'aiff', 'flac', 'mp4', 'mov', 'mkv', 'avi', 'mxf']
        }
      ]
    });

    if (filePath) {
      const file = props.missingFiles[index];
      remapping.value[file.original_path] = filePath;
      file.new_path = filePath;
    }
  } catch (error) {
    console.error('Failed to locate file:', error);
  }
}

// Search for all missing files in a folder
async function searchInFolder() {
  try {
    const folderPath = await open({
      directory: true,
      multiple: false,
      title: 'Select folder to search for missing files'
    });

    if (folderPath) {
      processing.value = true;
      processingMessage.value = 'Searching for files...';

      const result = await invoke('find_missing_files_in_directory', {
        missingFiles: props.missingFiles,
        searchDir: folderPath
      });

      // Update files with found paths
      let foundCount = 0;
      for (const [originalPath, newPath] of Object.entries(result)) {
        remapping.value[originalPath] = newPath;
        const file = props.missingFiles.find(f => f.original_path === originalPath);
        if (file) {
          file.new_path = newPath;
          foundCount++;
        }
      }

      if (foundCount > 0) {
        processingMessage.value = `Found ${foundCount} file(s). Click a button below to apply.`;
      } else {
        processingMessage.value = 'No matching files found in the selected folder.';
      }
    }
  } catch (error) {
    console.error('Failed to search folder:', error);
    processingMessage.value = 'Error searching folder: ' + error.message;
  }
}

// Apply the relinking
async function applyRelinking() {
  if (Object.keys(remapping.value).length === 0) {
    onCancel();
    return;
  }

  processing.value = true;
  processingMessage.value = 'Relinking files...';

  try {
    const result = await invoke('relink_files', {
      remapping: remapping.value
    });

    emit('relink', result);
  } catch (error) {
    console.error('Failed to relink files:', error);
    processingMessage.value = 'Error relinking files: ' + error;
  }
}

// Skip missing files (remove them from the project)
function skipMissing() {
  emit('skip', props.missingFiles);
}

// Cancel the dialog
function onCancel() {
  if (Object.keys(remapping.value).length > 0) {
    applyRelinking();
  } else {
    emit('cancel');
  }
}
</script>
