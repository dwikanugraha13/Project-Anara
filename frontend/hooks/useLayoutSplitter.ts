import { useState, useCallback, useRef, useEffect } from "react";

export interface UseLayoutSplitterOptions {
  dimension: "width" | "height";
  direction?: "left" | "right" | "top" | "bottom";
  min: number;
  max: number;
  initialSize: number;
  storageKey?: string;
}

export function useLayoutSplitter({
  dimension,
  direction = "right",
  min,
  max,
  initialSize,
  storageKey,
}: UseLayoutSplitterOptions) {
  const [size, setSize] = useState(initialSize);
  const [isResizing, setIsResizing] = useState(false);
  const startCoordRef = useRef(0);
  const startSizeRef = useRef(size);

  const startResizing = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      startCoordRef.current = dimension === "width" ? e.clientX : e.clientY;
      startSizeRef.current = size;
      setIsResizing(true);
    },
    [dimension, size]
  );

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const currentCoord = dimension === "width" ? e.clientX : e.clientY;
      const delta = currentCoord - startCoordRef.current;
      const multiplier = direction === "right" || direction === "bottom" ? 1 : -1;
      const newSize = Math.max(min, Math.min(max, startSizeRef.current + delta * multiplier));
      setSize(newSize);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      if (storageKey && typeof window !== "undefined") {
        try {
          localStorage.setItem(storageKey, String(size));
        } catch {}
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing, dimension, direction, min, max, size, storageKey]);

  return {
    size,
    isResizing,
    startResizing,
    setSize,
  };
}
