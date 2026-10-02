import React, { useState, useEffect, useRef } from "react";

export interface SelectOption {
  value: string;
  label: string;
  icon?: React.ReactNode;
}

export interface LiquidGlassSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  className?: string;
  disabled?: boolean;
  align?: "left" | "right";
}

export function LiquidGlassSelect({
  value,
  onChange,
  options,
  className = "",
  disabled = false,
  align = "left",
}: LiquidGlassSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const selectedOption = options.find((opt) => opt.value === value) || options[0];

  return (
    <div ref={dropdownRef} className={`relative z-50 inline-block font-sans ${className}`}>
      <button
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-disabled={disabled}
        disabled={disabled}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        className={`w-full flex items-center justify-between gap-2.5 px-3.5 py-1.5 rounded-xl border border-white/[0.08] bg-[#060913]/80 backdrop-blur-xl hover:border-cyan-400/40 hover:shadow-[0_4px_20px_rgba(34,211,238,0.12)] transition-all duration-200 ${
          disabled ? "opacity-50 cursor-not-allowed pointer-events-none" : "cursor-pointer"
        }`}
      >
        <span className="truncate text-xs text-slate-200 flex items-center gap-1.5">
          {selectedOption?.icon}
          <span>{selectedOption?.label || "Select..."}</span>
        </span>
        <svg
          className={`w-3.5 h-3.5 text-cyan-400 transition-transform duration-300 shrink-0 ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div
          role="listbox"
          className={`absolute ${align === "right" ? "right-0" : "left-0"} mt-1.5 w-full min-w-[170px] max-h-56 overflow-y-auto rounded-xl bg-[#060913]/95 border border-white/10 backdrop-blur-2xl shadow-[0_12px_40px_rgba(0,0,0,0.7)] py-1 z-50 animate-fade-in custom-scrollbar relative`}
        >
          <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-cyan-400/30 to-transparent pointer-events-none" />
          {options.map((opt) => {
            const isSelected = opt.value === value;
            return (
              <button
                key={opt.value}
                type="button"
                role="option"
                aria-selected={isSelected}
                onClick={() => {
                  onChange(opt.value);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center justify-between gap-2 px-3 py-1.5 text-left text-xs transition-colors duration-150 cursor-pointer ${
                  isSelected ? "bg-cyan-500/15 text-cyan-300 font-semibold border-l-2 border-cyan-400" : "text-slate-300 hover:bg-white/[0.06] hover:text-white"
                }`}
              >
                <span className="flex items-center gap-1.5 truncate">
                  {opt.icon}
                  <span className="truncate">{opt.label}</span>
                </span>
                {isSelected && (
                  <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
