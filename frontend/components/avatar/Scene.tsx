"use client";

/**
 * Scene.tsx
 *
 * Cinematic Studio Rendering for Anara 3D Avatar:
 * - 85mm portrait camera focal framing (FOV 34) for photorealistic human proportions.
 * - 6-Point Warm Studio Portrait Lighting Setup.
 * - Dual-layer Error Boundaries:
 *   1. CanvasErrorBoundary: Catches WebGL/GPU driver disablement cleanly (Zero Red Screen).
 *   2. AvatarErrorBoundary: Catches GLTF animation or mesh loading errors.
 */

import React, { Suspense, Component } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, ContactShadows, Preload } from "@react-three/drei";
import * as THREE from "three";
import Avatar3D, { type Avatar3DHandle } from "./Avatar3D";

// ── Outer Canvas Error Boundary (Catches WebGL Disabled / Driver Loss) ──────
class CanvasErrorBoundary extends Component<
  { children: React.ReactNode; onWebGLFailure?: () => void },
  { hasError: boolean; errorMessage: string }
> {
  constructor(props: { children: React.ReactNode; onWebGLFailure?: () => void }) {
    super(props);
    this.state = { hasError: false, errorMessage: "" };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, errorMessage: error.message || "WebGL context creation failed" };
  }

  componentDidCatch(error: Error) {
    console.warn("[CanvasErrorBoundary] WebGL GPU context unavailable:", error.message);
    this.props.onWebGLFailure?.();
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="absolute inset-0 flex items-center justify-center p-6 select-none pointer-events-auto z-20">
          <div className="max-w-md w-full p-6 rounded-3xl bg-slate-950/90 border border-amber-500/30 text-center shadow-2xl backdrop-blur-xl">
            <div className="w-12 h-12 mx-auto mb-3 rounded-2xl bg-amber-500/15 border border-amber-400/30 flex items-center justify-center text-amber-400 text-xl font-bold">
              ⚡
            </div>
            <h3 className="text-sm font-bold text-white mb-1.5 font-mono">
              Akselerasi 3D GPU Dinonaktifkan di Browser
            </h3>
            <p className="text-xs text-slate-300 mb-4 leading-relaxed font-sans">
              Chrome menonaktifkan WebGL sementara waktu (<code className="text-amber-300 font-mono text-[11px]">GL_VENDOR = Disabled</code>). Anda tetap bisa berinteraksi penuh via suara atau teks, atau restart Chrome untuk menyalakan kembali avatar 3D.
            </p>
            <div className="flex items-center justify-center gap-2 font-mono">
              <a
                href="/code"
                className="px-3.5 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-semibold transition-colors"
              >
                Buka Code Studio (/code)
              </a>
              <button
                type="button"
                onClick={() => this.setState({ hasError: false, errorMessage: "" })}
                className="px-3.5 py-1.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-black text-xs font-semibold transition-colors cursor-pointer"
              >
                Coba Lagi
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Inner Avatar Error Boundary (Catches Mesh / Rigging Runtime Errors) ──────
class AvatarErrorBoundary extends Component<
  { children: React.ReactNode; onError?: () => void },
  { hasError: boolean; error: string }
> {
  constructor(props: { children: React.ReactNode; onError?: () => void }) {
    super(props);
    this.state = { hasError: false, error: "" };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }
  componentDidCatch(error: Error) {
    console.error("[AvatarErrorBoundary] Avatar mesh failed:", error.message);
    this.props.onError?.();
    setTimeout(() => this.setState({ hasError: false, error: "" }), 5000);
  }
  render() {
    if (this.state.hasError) {
      return null;
    }
    return this.props.children;
  }
}

export interface SceneProps {
  avatarUrl: string;
  isSpeaking: boolean;
  audioIntensity: number;
  avatarRef: React.RefObject<Avatar3DHandle | null>;
  onAvatarLoad?: () => void;
  onDanceStart?: () => void;
  onDanceEnd?: () => void;
  isVoiceMode?: boolean;
}

// ── Stable constants (outside component to avoid re-render loops) ────────────
const CONTAINER_STYLE: React.CSSProperties = {
  position: "absolute",
  top: 0,
  left: 0,
  width: "100%",
  height: "100%",
  background: "transparent",
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
  isVoiceMode = true,
}: SceneProps) {
  return (
    <div style={CONTAINER_STYLE}>
      <CanvasErrorBoundary onWebGLFailure={onAvatarLoad}>
        <Canvas
          id="avatar-canvas"
          camera={CAMERA_CONFIG}
          shadows={SHADOWS_CONFIG}
          gl={GL_CONFIG}
          dpr={[1, 1.5]}
          onCreated={({ gl }) => {
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

          {/* Soft Contact Ground Shadow */}
          <ContactShadows
            position={[0, -1.48, 0]}
            opacity={0.65}
            scale={4.0}
            blur={2.2}
            far={2.5}
            resolution={512}
            frames={1}
          />

          {/* 3D Photorealistic Avatar */}
          <AvatarErrorBoundary onError={onAvatarLoad}>
            <Suspense fallback={null}>
              <Avatar3D
                ref={avatarRef}
                url={avatarUrl}
                isSpeaking={isSpeaking}
                audioIntensity={audioIntensity}
                onLoad={onAvatarLoad}
                onDanceStart={onDanceStart}
                onDanceEnd={onDanceEnd}
                isVoiceMode={isVoiceMode}
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
      </CanvasErrorBoundary>
    </div>
  );
}
