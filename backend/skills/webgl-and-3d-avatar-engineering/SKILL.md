---
category: autonomous-ai-agents
name: webgl-and-3d-avatar-engineering
description: Use when debugging 3D WebGL avatars and Three.js scenes.
---

# WebGL and 3D Avatar Engineering

Use this skill when building, rendering, optimizing, or debugging 3D humanoid avatars, Three.js / React Three Fiber (R3F) scenes, and GLTF/GLB models in web workspaces and desktop agent interfaces.

## Core Architectural Invariants

### 1. Robust GLTF Texture Loading: TextureLoader vs ImageBitmapLoader
- In Chromium-based browsers (especially Brave, or environments with GPU power saving or aggressive fingerprinting shields), `GLTFLoader`'s default `ImageBitmapLoader` fails when decoding models with multiple embedded textures (e.g. 20+ textures inside a single `.glb` file).
- The mechanism: `GLTFLoader` converts binary buffer views into `Blob` objects and calls `URL.createObjectURL(blob)`. Concurrent asynchronous `createImageBitmap` invocations on multiple newly created blob URLs trigger Chromium's blob concurrency race conditions and Brave Shields' canvas/fingerprint protections, throwing `THREE.GLTFLoader: Couldn't load texture blob:...`.
- When textures fail to load, subsequent material shader links fail (`WebGL: INVALID_OPERATION: useProgram: program not valid`), which rapidly cascades into browser GPU process termination (`WebGL: CONTEXT_LOST_WEBGL: loseContext`).
- **Fix:** Register a loader parser plugin via `extendLoader` in `useGLTF` to force standard `HTMLImageElement` `TextureLoader`:
  ```typescript
  const configureRobustGLTFLoader = (loader: any) => {
    if (!loader) return;
    loader.register((parser: any) => {
      if (typeof window !== "undefined") {
        parser.textureLoader = new THREE.TextureLoader(parser.options.manager);
      }
      return { name: "robust_native_texture_loader" };
    });
  };

  useGLTF(url, false, false, configureRobustGLTFLoader);
  useGLTF.preload(url, false, false, configureRobustGLTFLoader);
  ```
- **Rule:** Always use standard `HTMLImageElement` decoding for multi-texture embedded GLB humanoid avatars; native `<img>` decoding is handled by the browser's battle-tested cache and is immune to blob concurrency and fingerprinting shield traps.

### 2. Zero Synthetic Fallback Hijacking & Clean Context Restoration
- Never attach global window event listeners (such as `window.addEventListener("unhandledrejection")`) looking for loose string matches (`"context"`, `"webgl"`, `"three"`) to permanently replace the 3D Canvas with synthetic wireframe or holographic fallbacks.
- Hardware switching (e.g. dual-GPU laptops transitioning between integrated and discrete GPUs) and sleep/wake cycles routinely fire transient `webglcontextlost` events followed by `webglcontextrestored`.
- An aggressive error boundary permanently locks the UI into an unwanted fallback state that users perceive as an agent hallucination or broken asset.
- Handle context loss natively on the Canvas DOM element:
  ```typescript
  onCreated={({ gl }) => {
    gl.debug.checkShaderErrors = false;
    const domEl = gl.domElement;
    if (domEl) {
      domEl.addEventListener("webglcontextlost", (e) => {
        e.preventDefault(); // Informs the browser that the application intends to restore context
      });
      domEl.addEventListener("webglcontextrestored", () => {
        // Automatic resource re-allocation
      });
    }
  }}
  ```

### 3. Immediate Disposal of WebGL Capability Probe Contexts
- When testing client browser WebGL capabilities via programmatic canvas creation (`checkWebGLSupport()`), never leave probe WebGL contexts allocated.
- Browsers enforce hard limits on the total number of simultaneous WebGL contexts per page (typically 8 to 16). Leaving probe contexts active exhausts the quota, causing the subsequent primary 3D scene canvas to fail to acquire a context.
- **Rule:** Always release the probe context immediately using the `WEBGL_lose_context` extension:
  ```typescript
  const loseContext = gl.getExtension("WEBGL_lose_context");
  if (loseContext) {
    loseContext.loseContext();
  }
  ```

### 4. Build Cache Pruning vs Asset Deletion Diagnostics
- When users observe an unexpected drop in repository or folder size (e.g. from 1.2 GB to ~900 MB) and suspect that 3D model assets (`avatar.glb`, `animations.glb`) or source code were accidentally deleted, perform empirical inspection before hypothesizing:
  1. Inspect `git log --diff-filter=D --summary` to confirm zero tracked source or asset files were deleted.
  2. Inspect untracked build directories (`.next/cache`, `node_modules/.cache`, `dist/`). Next.js dev server compiler traces and Turbopack/Webpack caches regularly accumulate 250 MB – 350 MB during extended sessions and are cleared upon restart or fresh builds.
  3. Validate physical presence and byte length of all binary 3D assets in `public/`.
  4. Run an automated headless image extraction script (e.g. Pillow in Python) to verify that all embedded JPEG/PNG textures inside the `.glb` container remain uncorrupted.

### 5. React-Three-Fiber Automatic Render Loop & `useFrame` Priority Trap
- In React-Three-Fiber (R3F), `useFrame(callback, renderPriority = 0)` uses `renderPriority` to control render delegation.
- When `renderPriority > 0` (e.g. `useFrame((state, delta) => { ... }, 1)`), R3F sets `state.internal.priority = 1` and **disables the automatic render call** (`if (!state.internal.priority && state.gl.render) state.gl.render(state.scene, state.camera)`).
- R3F assumes that any subscriber with positive priority takes complete manual control of the render pass. If the callback performs animation updates (visemes, kinematics, morph targets) but does not explicitly invoke `state.gl.render(state.scene, state.camera)`, the canvas remains 100% transparent.
- The symptoms: No runtime exceptions are thrown, GLTF models load successfully, bone rigs are mapped, Suspense resolves, yet the screen remains completely blank (`gl.readPixels` returns `0` non-zero pixels).
- **Rule:** Never pass a non-zero `renderPriority` to `useFrame` unless the callback explicitly executes manual multi-pass rendering or post-processing passes. Leave priority at default `0` for animation and kinematic loops so R3F maintains the active 60 FPS render loop.

### 6. Headless Chrome CDP Pixel Probing (`gl.readPixels`) vs Visual Inspection
- When diagnosing reported blank 3D canvas issues where the DOM reports the canvas is mounted and sized (`canvasFound: true`, `canvasW > 0`), do not guess whether the model is invisible due to camera clipping, shader compilation, or CSS overlay obstruction.
- Query the WebGL drawing buffer directly via CDP evaluation:
  ```javascript
  const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
  const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
  const pixels = new Uint8Array(w * h * 4);
  gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  let nonZero = 0;
  for (let i = 0; i < pixels.length; i += 4) {
    if (pixels[i] > 10 || pixels[i+1] > 10 || pixels[i+2] > 10) nonZero++;
  }
  return { width: w, height: h, nonZeroPixels: nonZero };
  ```
- If `nonZeroPixels === 0`, the WebGL pipeline is not drawing anything (render loop disabled, camera facing away, or frustum culling).
- If `nonZeroPixels > 0` but the user sees a blank screen, the issue is purely CSS/DOM layer occlusion (e.g. `document.elementFromPoint(x, y)` hit testing finding an opaque overlay div or solid background like `bg-[#060913]` masking the canvas).

## Diagnostic Audit Checklist

1. **Texture Loader Strategy:** Are multi-texture embedded GLB models using HTMLImageElement TextureLoader instead of ImageBitmapLoader?
2. **Context Loss Handling:** Does the Canvas DOM element listen for `webglcontextlost` with `preventDefault()` rather than tearing down the canvas via global rejection boundaries?
3. **Probe Disposal:** Are temporary WebGL capability probe contexts immediately destroyed via `WEBGL_lose_context`?
4. **Cache Accounting:** Did size reductions trace to compiler caches (`.next/cache`) rather than deleted 3D assets?
5. **R3F Render Loop Priority:** Do all `useFrame` animation hooks use default priority 0 so R3F's automatic render loop is not suppressed?
6. **CDP Pixel Buffer Verification:** Has `gl.readPixels` been checked to verify non-zero drawing buffer output independently of CSS layer visibility?
