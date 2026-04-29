# audiosync-wasm

WebAssembly bindings for AudioSync core engine. Runs FFT cross-correlation audio synchronization entirely in the browser.

## Build

```bash
wasm-pack build --target web --out-dir pkg
```

## Usage

```javascript
import init, { WasmSyncEngine } from "./audiosync_wasm.js";

await init();
const engine = new WasmSyncEngine();

// Load WAV files from File API
const file = input.files[0];
const data = new Uint8Array(await file.arrayBuffer());
const info = engine.load_clip_from_bytes(file.name, data);

// Run analysis
const result = engine.analyze();
console.log(JSON.parse(result));

// Get tracks
const tracks = engine.get_tracks();
```

## Supported Formats

- 16-bit, 24-bit, and 32-bit float WAV files
- Audio is resampled to 8 kHz mono for analysis
- Video files are not supported (use the desktop app for video)

## WASM Binary Size

~330 KB (optimized with wasm-opt)
