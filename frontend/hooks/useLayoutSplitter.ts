import { useState, useCallback, useRef, useEffect } from "react";

export interface UseLayoutSplitterOptions {
  dimension: "width" | "height";
  direction?: "left" | "right" | "top" | "bottom";
  min: number;
  max: number;
  initialSize: number;
  storageKey?: string;
  targetRef?: React.RefObject<HTMLElement | null>;
  throttleReactUpdates?: boolean;
  onResizeStart?: () => void;
  onResize?: (size: number) => void;
  onResizeEnd?: (finalSize: number) => void;
}

export interface UseLayoutSplitterReturn {
  size: number;
  isResizing: boolean;
  startResizing: (e: React.MouseEvent | React.PointerEvent) => void;
  setSize: React.Dispatch<React.SetStateAction<number>>;
  resetSize: () => void;
  min: number;
  max: number;
}

const SELECTION_SHIELD_ID = "anara-splitter-selection-shield";

export function useLayoutSplitter({
  dimension,
  direction = "right",
  min,
  max,
  initialSize,
  storageKey,
  targetRef,
  throttleReactUpdates = false,
  onResizeStart,
  onResize,
  onResizeEnd,
}: UseLayoutSplitterOptions): UseLayoutSplitterReturn {
  // Normalize bounds to prevent min > max inverted ranges
  const effectiveMin = Math.min(min, max);
  const effectiveMax = Math.max(min, max);
  const clampedInitial = Math.max(effectiveMin, Math.min(effectiveMax, initialSize));

  const [size, setSize] = useState<number>(clampedInitial);
  const [isResizing, setIsResizing] = useState(false);

  const startCoordRef = useRef(0);
  const startSizeRef = useRef(size);
  const currentSizeRef = useRef(size);
  const pendingSizeRef = useRef<number | null>(null);
  const rafIdRef = useRef<number | null>(null);
  const pointerIdRef = useRef<number | null>(null);
  const targetElementRef = useRef<HTMLElement | null>(null);

  // Keep currentSizeRef in sync
  useEffect(() => {
    currentSizeRef.current = size;
  }, [size]);

  // Clamp current size if bounds change dynamically
  useEffect(() => {
    setSize((prev) => {
      const clamped = Math.max(effectiveMin, Math.min(effectiveMax, prev));
      if (clamped !== prev) {
        currentSizeRef.current = clamped;
        return clamped;
      }
      return prev;
    });
  }, [effectiveMin, effectiveMax]);

  // Restore saved size from localStorage safely on mount (client-only to prevent SSR hydration mismatch)
  useEffect(() => {
    if (!storageKey || typeof window === "undefined") return;
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed)) {
          const clamped = Math.max(effectiveMin, Math.min(effectiveMax, parsed));
          setSize(clamped);
          currentSizeRef.current = clamped;
        }
      }
    } catch {
      // Safe fallback if localStorage is disabled or throws QuotaExceededError
    }
  }, [storageKey, effectiveMin, effectiveMax]);

  // Selection shield management: prevents event eating by iframes/xterm/monaco during active drag
  const mountSelectionShield = useCallback((cursorStyle: string) => {
    if (typeof document === "undefined") return;
    let shield = document.getElementById(SELECTION_SHIELD_ID);
    if (!shield) {
      shield = document.createElement("div");
      shield.id = SELECTION_SHIELD_ID;
      document.body.appendChild(shield);
    }
    shield.style.cssText = `position: fixed; inset: 0; z-index: 99999; cursor: ${cursorStyle}; user-select: none; -webkit-user-select: none; pointer-events: auto; background: transparent;`;
  }, []);

  const unmountSelectionShield = useCallback(() => {
    if (typeof document === "undefined") return;
    const shield = document.getElementById(SELECTION_SHIELD_ID);
    if (shield && shield.parentNode) {
      shield.parentNode.removeChild(shield);
    }
  }, []);

  const resetSize = useCallback(() => {
    setSize(clampedInitial);
    currentSizeRef.current = clampedInitial;
    if (storageKey && typeof window !== "undefined") {
      try {
        localStorage.removeItem(storageKey);
      } catch {}
    }
  }, [clampedInitial, storageKey]);

  // Gesture start handler: supports both PointerEvent and MouseEvent with pointer capture
  const startResizing = useCallback(
    (e: React.MouseEvent | React.PointerEvent) => {
      e.preventDefault();
      e.stopPropagation();

      const coord = dimension === "width" ? e.clientX : e.clientY;
      startCoordRef.current = coord;
      startSizeRef.current = currentSizeRef.current;
      pendingSizeRef.current = currentSizeRef.current;

      // Extract pointerId if PointerEvent and attempt pointer capture
      if ("pointerId" in e && typeof e.pointerId === "number") {
        pointerIdRef.current = e.pointerId;
        const target = e.currentTarget as HTMLElement;
        if (target && typeof target.setPointerCapture === "function") {
          try {
            target.setPointerCapture(e.pointerId);
            targetElementRef.current = target;
          } catch {
            // Ignored if target cannot capture
          }
        }
      } else {
        pointerIdRef.current = null;
        targetElementRef.current = null;
      }

      setIsResizing(true);
      onResizeStart?.();
    },
    [dimension, onResizeStart]
  );

  useEffect(() => {
    if (!isResizing) return;

    const cursorStyle = dimension === "width" ? "col-resize" : "row-resize";
    const originalUserSelect = document.body.style.userSelect;
    const originalCursor = document.body.style.cursor;

    document.body.style.userSelect = "none";
    document.body.style.cursor = cursorStyle;
    mountSelectionShield(cursorStyle);

    // High-performance RAF-coalesced coordinate updater
    const updateSizeFromCoord = (clientX: number, clientY: number) => {
      const currentCoord = dimension === "width" ? clientX : clientY;
      const delta = currentCoord - startCoordRef.current;
      const multiplier = direction === "right" || direction === "bottom" ? 1 : -1;
      const calculated = startSizeRef.current + delta * multiplier;
      const clamped = Math.max(effectiveMin, Math.min(effectiveMax, calculated));

      pendingSizeRef.current = clamped;

      if (rafIdRef.current === null) {
        rafIdRef.current = requestAnimationFrame(() => {
          rafIdRef.current = null;
          if (pendingSizeRef.current !== null) {
            currentSizeRef.current = pendingSizeRef.current;
            // Direct zero-commit DOM mutation (Anara Desktop Standard)
            if (targetRef && targetRef.current) {
              if (dimension === "width") {
                targetRef.current.style.width = `${pendingSizeRef.current}px`;
              } else {
                targetRef.current.style.height = `${pendingSizeRef.current}px`;
              }
            }
            if (!throttleReactUpdates || !targetRef?.current) {
              setSize(pendingSizeRef.current);
            }
            onResize?.(pendingSizeRef.current);
          }
        });
      }
    };

    const handlePointerMove = (e: PointerEvent) => {
      updateSizeFromCoord(e.clientX, e.clientY);
    };

    const handleMouseMove = (e: MouseEvent) => {
      updateSizeFromCoord(e.clientX, e.clientY);
    };

    // Clean finish: flush any pending RAF, persist to storage, and notify caller
    const finishResize = (finalSize: number) => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }

      setIsResizing(false);
      setSize(finalSize);
      currentSizeRef.current = finalSize;
      pendingSizeRef.current = null;

      // Release pointer capture if held
      if (
        pointerIdRef.current !== null &&
        targetElementRef.current &&
        typeof targetElementRef.current.releasePointerCapture === "function"
      ) {
        try {
          if (targetElementRef.current.hasPointerCapture(pointerIdRef.current)) {
            targetElementRef.current.releasePointerCapture(pointerIdRef.current);
          }
        } catch {}
      }
      pointerIdRef.current = null;
      targetElementRef.current = null;

      document.body.style.userSelect = originalUserSelect;
      document.body.style.cursor = originalCursor;
      unmountSelectionShield();

      // Safe storage persistence
      if (storageKey && typeof window !== "undefined") {
        try {
          localStorage.setItem(storageKey, String(finalSize));
        } catch {}
      }

      onResizeEnd?.(finalSize);
    };

    const handlePointerUp = () => {
      const finalSize = pendingSizeRef.current ?? currentSizeRef.current;
      finishResize(finalSize);
    };

    const handleMouseUp = () => {
      const finalSize = pendingSizeRef.current ?? currentSizeRef.current;
      finishResize(finalSize);
    };

    // Window blur or visibility change: cancel gesture smoothly to avoid stuck states
    const handleCancel = () => {
      const current = currentSizeRef.current;
      finishResize(current);
    };

    // Keyboard Escape cancels and restores starting size (Anara Desktop / Anara CLI parity)
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        finishResize(startSizeRef.current);
      }
    };

    // Attach listeners across pointer, mouse, touch, blur, and escape
    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handleCancel);
    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    window.addEventListener("mouseup", handleMouseUp);
    window.addEventListener("blur", handleCancel);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
      document.body.style.userSelect = originalUserSelect;
      document.body.style.cursor = originalCursor;
      unmountSelectionShield();

      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handleCancel);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      window.removeEventListener("blur", handleCancel);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [
    isResizing,
    dimension,
    direction,
    effectiveMin,
    effectiveMax,
    storageKey,
    mountSelectionShield,
    unmountSelectionShield,
    onResize,
    onResizeEnd,
  ]);

  return {
    size,
    isResizing,
    startResizing,
    setSize,
    resetSize,
    min: effectiveMin,
    max: effectiveMax,
  };
}
