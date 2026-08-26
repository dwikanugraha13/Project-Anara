"use client";

/**
 * Scene.tsx
 *
 * Cinematic Studio Rendering:
 * - 85mm portrait camera focal framing (FOV 32) for photorealistic human proportions.
 * - 5-Point Studio Portrait Lighting:
 *   1. Key Light (Soft Warm Daylight)
 *   2. Fill Light (Soft Sky Blue)
 *   3. Warm Rim Light (Golden Sunlight edge)
 *   4. Cool Hair Light (Cyan rim for hair separation)
 *   5. Under-chin Bounce (Soft peach/pink bounce for radiant facial tones)
 * - HDR City Environment map with balanced reflection intensity.
 * - Soft ground contact shadow.
 */

import React, { Suspense, Component } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, ContactShadows, Preload } from "@react-three/drei";
import * as THREE from "three";
import Avatar3D, { type Avatar3DHandle } from "./Avatar3D";


// ── Main Avatar Error Boundary ────────────────────────────────────────────────
class AvatarErrorBoundary extends Component<
  { children: React.ReactNode },
  { hasError: boolean; error: string }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: "" };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }
  componentDidCatch(error: Error) {
    console.error("[AvatarErrorBoundary] Avatar failed:", error.message);
    // Reset after 3s so avatar retries on next render
    setTimeout(() => this.setState({ hasError: false, error: "" }), 3000);
  }
  render() {
    if (this.state.hasError) {
      console.warn("[AvatarErrorBoundary] Retrying avatar in 3s...");
      return null;
    }
    return this.props.children;
  }
}

interface SceneProps {
  avatarUrl: string;
  isSpeaking: boolean;
  audioIntensity: number;
  avatarRef: React.RefObject<Avatar3DHandle | null>;
  onAvatarLoad?: () => void;
  onDanceStart?: () => void;
  onDanceEnd?: () => void;
}

// ── Stable constants (outside component to avoid re-render loops) ────────────
const CONTAINER_STYLE: React.CSSProperties = {
  position: "fixed",
  top: 0,
  left: 0,
  width: "100vw",
  height: "100vh",
  background: "radial-gradient(ellipse at 50% 35%, #0f172a 0%, #030712 70%, #020617 100%)",
};

const CAMERA_CONFIG = {
  position: [0, -0.06, 1.82] as [number, number, number],
  fov: 34,
  near: 0.1,
  far: 100,
};

const GL_CONFIG = {
  antialias: true,
  powerPreference: "high-performance" as const,
  toneMapping: THREE.ACESFilmicToneMapping,
  toneMappingExposure: 1.05,
  outputColorSpace: THREE.SRGBColorSpace,
  failIfMajorPerformanceCaveat: false,
};

const SHADOWS_CONFIG = { type: THREE.PCFSoftShadowMap } as const;

export default function Scene({
  avatarUrl,
  isSpeaking,
  audioIntensity,
  avatarRef,
  onAvatarLoad,
  onDanceStart,
  onDanceEnd,
}: SceneProps) {
  return (
    <div style={CONTAINER_STYLE}>
      <Canvas
        id="avatar-canvas"
        camera={CAMERA_CONFIG}
        shadows={SHADOWS_CONFIG}
        gl={GL_CONFIG}
        dpr={[1, 1.5]} // HD sharpness with optimal fill-rate performance for 60 FPS
        onCreated={({ gl }) => {
          // Disable redundant WebGL validateProgram check that triggers driver false-positive 1282 warnings
          gl.debug.checkShaderErrors = false;
        }}
      >
        {/* ── 6-Point Warm Studio Portrait Lighting Setup ── */}
        <ambientLight intensity={0.85} color="#fff8f0" />

        {/* 1. Key Light: Soft Warm Daylight Portrait Light */}
        <directionalLight
          position={[1.8, 2.2, 2.4]}
          intensity={1.35}
          color="#fff5ea"
        />

        {/* 2. Fill Light: Soft Warm Daylight */}
        <directionalLight
          position={[-1.8, 1.6, 2.2]}
          intensity={0.85}
          color="#fef3e8"
        />

        {/* 3. Front Beauty Glow: Soft Dewy Radiant Skin Light */}
        <pointLight position={[0, 0.45, 1.6]} intensity={0.65} color="#fff6ed" />

        {/* 4. Golden Rim Light (Right Back Shoulder/Hair Accent) */}
        <pointLight position={[2.4, 1.8, -1.6]} intensity={2.0} color="#fed7aa" />

        {/* 5. Soft Edge Light (Left Back Silhouette Definition) */}
        <pointLight position={[-2.4, 1.8, -1.6]} intensity={1.6} color="#e2e8f0" />

        {/* 6. Under-chin Bounce for Warm Radiant Skin Subsurface Glow */}
        <pointLight position={[0, -0.6, 1.1]} intensity={0.60} color="#fed7aa" />


        {/* Soft Contact Ground Shadow (resolution 512 + frames 1 for fast zero-overhead rendering) */}
        <ContactShadows
          position={[0, -1.48, 0]}
          opacity={0.65}
          scale={4.0}
          blur={2.2}
          far={2.5}
          resolution={512}
          frames={1}
        />

        {/* 3D Photorealistic Avatar — wrapped in ErrorBoundary for resilience */}
        <AvatarErrorBoundary>
          <Suspense fallback={null}>
            <Avatar3D
              ref={avatarRef}
              url={avatarUrl}
              isSpeaking={isSpeaking}
              audioIntensity={audioIntensity}
              onLoad={onAvatarLoad}
              onDanceStart={onDanceStart}
              onDanceEnd={onDanceEnd}
            />
            <Preload all />
          </Suspense>
        </AvatarErrorBoundary>

        {/* Smooth Cinematic Orbit Controls */}
        <OrbitControls
          target={[0, 0.05, 0]}
          minDistance={0.8}
          maxDistance={2.6}
          minPolarAngle={Math.PI * 0.32}
          maxPolarAngle={Math.PI * 0.58}
          minAzimuthAngle={-Math.PI * 0.3}
          maxAzimuthAngle={Math.PI * 0.3}
          enablePan={false}
          enableDamping
          dampingFactor={0.05}
        />
      </Canvas>
    </div>
  );
}
