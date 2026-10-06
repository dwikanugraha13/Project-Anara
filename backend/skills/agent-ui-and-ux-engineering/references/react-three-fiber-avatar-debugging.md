# React Three Fiber (R3F) Avatar & 3D Scene Debugging

Reference for debugging 3D avatar rendering issues in R3F + Next.js + drei stacks.

## R3F DOM Structure

`<Canvas id="my-canvas">` creates a **`<div>`** wrapper with that id, not a `<canvas>` element.
The actual `<canvas>` is a child element inside that div.

```ts
// WRONG — getContext is not a function (div has no getContext)
const canvas = document.getElementById("avatar-canvas") as HTMLCanvasElement;
canvas.getContext("webgl2"); // TypeError!

// CORRECT
const wrapper = document.getElementById("avatar-canvas");
const canvas = wrapper?.querySelector("canvas") as HTMLCanvasElement | null;
const gl = canvas?.getContext("webgl2");
```

## WebGL Canvas Pixel Verification

Three.js default `preserveDrawingBuffer: false` means `readPixels` returns black even on a working scene. Do NOT use pixel sampling to verify rendering.

Reliable alternatives:
- Check `gl.isContextLost()` — true = GPU driver failure
- Check `canvas.width > 0 && canvas.height > 0` — zero = not mounted
- Trust the `onLoad` callback from `useGLTF` / Avatar3D — if model traversal completed, rendering works

## Suspense Inside `<Canvas>`

`<Suspense fallback={null}>` inside R3F `<Canvas>` causes invisible loading states.
If `useGLTF` hangs (network slow, parse error), the canvas renders lights/shadows but no model — looks like a blank dark screen.

Always use a visible 3D fallback:
```tsx
<Suspense fallback={<LoadingMesh />}>
  <Avatar3D ... />
</Suspense>

function LoadingMesh() {
  return (
    <mesh position={[0, 0, 0]}>
      <sphereGeometry args={[0.3, 16, 16]} />
      <meshStandardMaterial color="#22d3ee" wireframe transparent opacity={0.4} />
    </mesh>
  );
}
```

## Diagnostic Logging Checklist

When avatar fails to render, add logs at each pipeline stage before adding fallback UI:

1. `[Scene] Component mounted` — Scene.tsx useEffect
2. `[Scene] WebGL support check: {result}` — checkWebGLSupport()
3. `[Scene] Avatar3D Suspense: loading...` — Suspense fallback mount
4. `[Scene] Avatar3D Suspense: resolved` — Suspense fallback unmount
5. `[AvatarBones] Found: head, neck, spine...` — Avatar3D scene.traverse
6. `[CanvasErrorBoundary] WebGL error:` — error boundary catch
7. `[AvatarErrorBoundary] Mesh failed:` — GLTF parse error

If log 1 appears but not 3 → Scene renders but Suspense never triggers.
If log 3 appears but not 4 → useGLTF stuck loading (network or parse hang).
If log 4 appears but not 5 → Avatar3D renders but scene.traverse useEffect doesn't fire.

## Anti-Pattern: Overlay Fallbacks That Cover Working Content

Never add a z-indexed fallback overlay on top of the 3D scene without first confirming the scene truly fails to render. If the verification code itself crashes, the fallback shows permanently even when the avatar is rendering fine underneath.

Correct approach:
1. Add diagnostic logging first to identify exactly where the pipeline breaks
2. Fix the actual rendering issue
3. Only then add a fallback for confirmed-dead scenarios (WebGL disabled, context lost)

## Next.js HMR and 3D Components

- R3F components with `useGLTF` Suspense may not hot-reload cleanly
- When code changes don't take effect: kill dev server, `rm -rf .next/`, restart `npm run dev`
- Verify compiled bundle contains new code: `curl -s http://localhost:3000/_next/static/chunks/app/page.js | grep "unique_string"`
- Browser hard refresh (`Ctrl+Shift+R`) required after dev server restart

## drei useGLTF Behavior (v10+)

`useGLTF(path, useDraco, useMeshopt)` — second arg is Draco, third is Meshopt (defaults to `true`).
Passing `useGLTF(url, false)` disables Draco but keeps Meshopt enabled.
If Meshopt decoder fails silently, loading hangs forever in Suspense.

## GPU Power Preference

`powerPreference: "high-performance"` can be rejected by Windows laptops on integrated GPU or battery mode. Use `"default"` for broader compatibility.
