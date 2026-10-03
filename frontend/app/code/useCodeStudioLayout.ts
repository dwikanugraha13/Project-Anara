import { useState, useRef, useEffect, useCallback } from "react";

const MIN_LEFT_WIDTH = 180;
const MAX_LEFT_WIDTH = 500;
const DEFAULT_LEFT_WIDTH = 260;

const MIN_RIGHT_WIDTH = 340;
const MAX_RIGHT_WIDTH = 700;
const DEFAULT_RIGHT_WIDTH = 450;

const MIN_TERMINAL_HEIGHT = 100;
const MAX_TERMINAL_HEIGHT = 500;
const DEFAULT_TERMINAL_HEIGHT = 210;

export interface UseCodeStudioLayoutOptions {
  initialSidebarWidth?: number;
  initialRightWidth?: number;
  initialTerminalHeight?: number;
  initialTerminalOpen?: boolean;
}

export interface UseCodeStudioLayoutReturn {
  leftWidth: number;
  setLeftWidth: React.Dispatch<React.SetStateAction<number>>;
  rightWidth: number;
  setRightWidth: React.Dispatch<React.SetStateAction<number>>;
  terminalHeight: number;
  setTerminalHeight: React.Dispatch<React.SetStateAction<number>>;
  isLeftOpen: boolean;
  setIsLeftOpen: React.Dispatch<React.SetStateAction<boolean>>;
  isRightOpen: boolean;
  setIsRightOpen: React.Dispatch<React.SetStateAction<boolean>>;
  isTerminalOpen: boolean;
  setIsTerminalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  isResizingLeft: boolean;
  isResizingRight: boolean;
  isResizingTerminal: boolean;
  startResizingLeft: (e: React.MouseEvent) => void;
  startResizingRight: (e: React.MouseEvent) => void;
  startResizingTerminal: (e: React.MouseEvent) => void;
  handleResetLayout: () => void;
}

/**
 * useCodeStudioLayout — Layout state, pane widths/heights, and mouse drag resizing
 * for Anara Code Studio with persistent storage and SSR cookie synchronization.
 */
export function useCodeStudioLayout(
  options: UseCodeStudioLayoutOptions = {}
): UseCodeStudioLayoutReturn {
  const {
    initialSidebarWidth = DEFAULT_LEFT_WIDTH,
    initialRightWidth = DEFAULT_RIGHT_WIDTH,
    initialTerminalHeight = DEFAULT_TERMINAL_HEIGHT,
    initialTerminalOpen = true,
  } = options;

  const [leftWidth, setLeftWidth] = useState<number>(initialSidebarWidth);
  const [rightWidth, setRightWidth] = useState<number>(initialRightWidth);
  const [terminalHeight, setTerminalHeight] = useState<number>(initialTerminalHeight);

  const [isLeftOpen, setIsLeftOpen] = useState(true);
  const [isRightOpen, setIsRightOpen] = useState(true);
  const [isTerminalOpen, setIsTerminalOpen] = useState(initialTerminalOpen);

  const [isResizingLeft, setIsResizingLeft] = useState(false);
  const [isResizingRight, setIsResizingRight] = useState(false);
  const [isResizingTerminal, setIsResizingTerminal] = useState(false);

  const latestLeftWidthRef = useRef(initialSidebarWidth);
  latestLeftWidthRef.current = leftWidth;
  const latestRightWidthRef = useRef(initialRightWidth);
  latestRightWidthRef.current = rightWidth;
  const latestTerminalHeightRef = useRef(initialTerminalHeight);
  latestTerminalHeightRef.current = terminalHeight;

  // Load saved preferences from localStorage on mount
  useEffect(() => {
    try {
      const savedLeft = localStorage.getItem("anara_studio_left_width");
      if (savedLeft) {
        const val = parseInt(savedLeft, 10);
        if (!isNaN(val) && val >= MIN_LEFT_WIDTH && val <= MAX_LEFT_WIDTH) {
          setLeftWidth(val);
          document.documentElement.style.setProperty("--studio-left-width", `${val}px`);
        }
      }

      const savedRight = localStorage.getItem("anara_studio_right_width");
      if (savedRight) {
        const val = parseInt(savedRight, 10);
        if (!isNaN(val) && val >= MIN_RIGHT_WIDTH && val <= MAX_RIGHT_WIDTH) {
          setRightWidth(val);
          document.documentElement.style.setProperty("--studio-right-width", `${val}px`);
        }
      }

      const savedTermH = localStorage.getItem("anara_studio_term_height");
      if (savedTermH) {
        const val = parseInt(savedTermH, 10);
        if (!isNaN(val) && val >= MIN_TERMINAL_HEIGHT && val <= MAX_TERMINAL_HEIGHT) {
          setTerminalHeight(val);
        }
      }

      const savedTermOpen = localStorage.getItem("anara_studio_term_open");
      if (savedTermOpen !== null) {
        setIsTerminalOpen(savedTermOpen === "true");
      }
    } catch {}
  }, []);

  const startResizingLeft = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingLeft(true);
  }, []);

  const startResizingRight = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingRight(true);
  }, []);

  const startResizingTerminal = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingTerminal(true);
  }, []);

  const handleResetLayout = useCallback(() => {
    setLeftWidth(DEFAULT_LEFT_WIDTH);
    setRightWidth(DEFAULT_RIGHT_WIDTH);
    setTerminalHeight(DEFAULT_TERMINAL_HEIGHT);
    setIsLeftOpen(true);
    setIsRightOpen(true);
    try {
      localStorage.setItem("anara_studio_left_width", DEFAULT_LEFT_WIDTH.toString());
      localStorage.setItem("anara_studio_right_width", DEFAULT_RIGHT_WIDTH.toString());
      localStorage.setItem("anara_studio_term_height", DEFAULT_TERMINAL_HEIGHT.toString());
      document.cookie = `anara_studio_left_width=${DEFAULT_LEFT_WIDTH}; path=/; max-age=31536000; SameSite=Lax`;
      document.cookie = `anara_studio_right_width=${DEFAULT_RIGHT_WIDTH}; path=/; max-age=31536000; SameSite=Lax`;
      document.cookie = `anara_studio_term_height=${DEFAULT_TERMINAL_HEIGHT}; path=/; max-age=31536000; SameSite=Lax`;
      document.documentElement.style.setProperty("--studio-left-width", `${DEFAULT_LEFT_WIDTH}px`);
      document.documentElement.style.setProperty("--studio-right-width", `${DEFAULT_RIGHT_WIDTH}px`);
    } catch {}
  }, []);

  // Global mousemove and mouseup listeners for resizing
  useEffect(() => {
    if (!isResizingLeft && !isResizingRight && !isResizingTerminal) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (isResizingLeft) {
        const newW = Math.max(MIN_LEFT_WIDTH, Math.min(MAX_LEFT_WIDTH, e.clientX));
        latestLeftWidthRef.current = newW;
        document.documentElement.style.setProperty("--studio-left-width", `${newW}px`);
      }
      if (isResizingRight) {
        const newW = Math.max(MIN_RIGHT_WIDTH, Math.min(MAX_RIGHT_WIDTH, window.innerWidth - e.clientX));
        latestRightWidthRef.current = newW;
        document.documentElement.style.setProperty("--studio-right-width", `${newW}px`);
      }
      if (isResizingTerminal) {
        const newH = Math.max(MIN_TERMINAL_HEIGHT, Math.min(MAX_TERMINAL_HEIGHT, window.innerHeight - e.clientY));
        latestTerminalHeightRef.current = newH;
      }
    };

    const handleMouseUp = () => {
      if (isResizingLeft) {
        const w = latestLeftWidthRef.current;
        setLeftWidth(w);
        try {
          localStorage.setItem("anara_studio_left_width", w.toString());
          document.cookie = `anara_studio_left_width=${w}; path=/; max-age=31536000; SameSite=Lax`;
          document.documentElement.style.setProperty("--studio-left-width", `${w}px`);
        } catch {}
      }
      if (isResizingRight) {
        const w = latestRightWidthRef.current;
        setRightWidth(w);
        try {
          localStorage.setItem("anara_studio_right_width", w.toString());
          document.cookie = `anara_studio_right_width=${w}; path=/; max-age=31536000; SameSite=Lax`;
          document.documentElement.style.setProperty("--studio-right-width", `${w}px`);
        } catch {}
      }
      if (isResizingTerminal) {
        const h = latestTerminalHeightRef.current;
        setTerminalHeight(h);
        try {
          localStorage.setItem("anara_studio_term_height", h.toString());
          document.cookie = `anara_studio_term_height=${h}; path=/; max-age=31536000; SameSite=Lax`;
        } catch {}
      }
      setIsResizingLeft(false);
      setIsResizingRight(false);
      setIsResizingTerminal(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizingLeft, isResizingRight, isResizingTerminal]);

  return {
    leftWidth,
    setLeftWidth,
    rightWidth,
    setRightWidth,
    terminalHeight,
    setTerminalHeight,
    isLeftOpen,
    setIsLeftOpen,
    isRightOpen,
    setIsRightOpen,
    isTerminalOpen,
    setIsTerminalOpen,
    isResizingLeft,
    isResizingRight,
    isResizingTerminal,
    startResizingLeft,
    startResizingRight,
    startResizingTerminal,
    handleResetLayout,
  };
}
