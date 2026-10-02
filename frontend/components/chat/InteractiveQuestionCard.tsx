"use client";

import React, { useState } from "react";

export interface InteractiveQuestionOption {
  label: string;
  description: string;
}

export interface InteractiveQuestionItem {
  header: string;
  question: string;
  multiple?: boolean;
  options: InteractiveQuestionOption[];
}

export interface InteractiveQuestionData {
  questionId: string;
  questions: InteractiveQuestionItem[];
  answers?: Record<number, string | string[]>;
  isAnswered?: boolean;
}

export interface InteractiveQuestionCardProps {
  data: InteractiveQuestionData;
  onSubmitAnswers: (
    questionId: string,
    answers: Array<{ header: string; question: string; answer: string | string[] }>,
    dismissed?: boolean
  ) => void;
}

function resolveAnswerText(raw: any): string {
  if (raw === undefined || raw === null || raw === "") return "(no answer)";
  if (typeof raw === "object" && !Array.isArray(raw)) {
    if ("answer" in raw) {
      return resolveAnswerText(raw.answer);
    }
    return JSON.stringify(raw);
  }
  if (Array.isArray(raw)) {
    return raw
      .map((item) => {
        if (typeof item === "object" && item !== null && "answer" in item) {
          return resolveAnswerText(item.answer);
        }
        return String(item);
      })
      .join(", ");
  }
  return String(raw);
}

export default function InteractiveQuestionCard({ data, onSubmitAnswers }: InteractiveQuestionCardProps) {
  const { questionId, questions = [], isAnswered = false } = data || {};
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string | string[]>>({});

  const [customInputs, setCustomInputs] = useState<Record<number, string>>({});
  const [isCustomActive, setIsCustomActive] = useState<Record<number, boolean>>({});
  const [isAccordionOpen, setIsAccordionOpen] = useState(false);

  if (!questions || questions.length === 0) {
    return null;
  }

  const currentQ = questions[currentStep] || questions[0];
  const totalSteps = questions.length;
  const isMultiple = Boolean(currentQ?.multiple);

  // The active selection for this question (null if user hasn't selected anything yet)
  const currentSelection = isCustomActive[currentStep]
    ? customInputs[currentStep] || ""
    : selectedAnswers[currentStep] ?? null;

  const handleSelectOption = (label: string) => {
    setIsCustomActive((prev) => ({ ...prev, [currentStep]: false }));
    if (isMultiple) {
      const existing = (selectedAnswers[currentStep] as string[]) || (Array.isArray(currentSelection) ? currentSelection : (currentSelection ? [currentSelection as string] : []));
      const updated = existing.includes(label)
        ? existing.filter((item) => item !== label)
        : [...existing, label];
      setSelectedAnswers((prev) => ({ ...prev, [currentStep]: updated }));
    } else {
      setSelectedAnswers((prev) => ({ ...prev, [currentStep]: label }));
    }
  };

  const handleCustomChange = (text: string) => {
    setCustomInputs((prev) => ({ ...prev, [currentStep]: text }));
    setIsCustomActive((prev) => ({ ...prev, [currentStep]: true }));
    setSelectedAnswers((prev) => ({ ...prev, [currentStep]: text.trim() || "(no answer)" }));
  };

  const handleNext = () => {
    setSelectedAnswers((prev) => ({
      ...prev,
      [currentStep]: isCustomActive[currentStep]
        ? (customInputs[currentStep]?.trim() || "(no answer)")
        : (prev[currentStep] ?? currentSelection ?? "(no answer)"),
    }));
    setCurrentStep((prev) => Math.min(totalSteps - 1, prev + 1));
  };

  const handleFinish = () => {
    const finalAnswers = {
      ...selectedAnswers,
      [currentStep]: isCustomActive[currentStep]
        ? (customInputs[currentStep]?.trim() || "(no answer)")
        : (selectedAnswers[currentStep] ?? currentSelection),
    };
    const formatted = questions.map((q, idx) => ({
      header: q.header,
      question: q.question,
      answer:
        finalAnswers[idx] ||
        q.options.find((o) => o.label.toLowerCase().includes("(recommended)"))?.label ||
        q.options[0]?.label ||
        "(no answer)",
    }));
    onSubmitAnswers(questionId, formatted);
  };

  const handleDismiss = () => {
    const formatted = questions.map((q) => ({
      header: q.header,
      question: q.question,
      answer: "(dismissed)",
    }));
    onSubmitAnswers(questionId, formatted, true);
  };

  // Keyboard navigation engine (1-9 hotkeys, Enter, Escape)
  React.useEffect(() => {
    if (isAnswered) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        (e.target as HTMLElement)?.isContentEditable
      ) {
        return;
      }

      const options = currentQ?.options || [];

      // Numbers 1-9 select option
      if (e.key >= "1" && e.key <= "9") {
        const index = parseInt(e.key, 10) - 1;
        if (index < options.length) {
          e.preventDefault();
          handleSelectOption(options[index].label);
        }
        return;
      }

      // Enter key confirms / advances
      if (e.key === "Enter") {
        e.preventDefault();
        if (currentStep < totalSteps - 1) {
          handleNext();
        } else {
          handleFinish();
        }
        return;
      }

      // Escape key dismisses
      if (e.key === "Escape") {
        e.preventDefault();
        handleDismiss();
        return;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentStep, totalSteps, currentQ, isAnswered, currentSelection, selectedAnswers, customInputs, isCustomActive]);

  // If already answered or dismissed, show flat Liquid Glass scaffold (Hermes Desktop Parity)
  if (isAnswered) {
    const answeredCount = questions.filter((q, idx) => {
      const ans = (Array.isArray(data.answers) ? data.answers[idx] : data.answers?.[idx]) || selectedAnswers[idx];
      const ansText = resolveAnswerText(ans);
      return ansText && ansText !== "(no answer)" && ansText !== "(dismissed)";
    }).length;

    return (
      <div className="w-full my-2 font-mono text-xs select-none">
        <button
          type="button"
          onClick={() => setIsAccordionOpen((prev) => !prev)}
          className="flex items-center gap-2 text-left text-slate-300 hover:text-white transition-colors cursor-pointer py-1 group"
        >
          <span className="relative flex h-2 w-2 shrink-0">
            <span className={`inline-flex rounded-full h-1.5 w-1.5 ${answeredCount > 0 ? "bg-emerald-400" : "bg-slate-500"}`} />
          </span>
          <span className="font-semibold text-slate-200 tracking-tight text-[11.5px]">
            {answeredCount === 0 ? "Questions dismissed" : "Questions answered"}
          </span>
          <span className="text-slate-400 text-[11px]">({answeredCount} of {questions.length})</span>
          <svg
            className={`w-3 h-3 text-slate-500 group-hover:text-slate-300 transition-transform duration-150 shrink-0 ${
              isAccordionOpen ? "rotate-90" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>

        {isAccordionOpen && (
          <div className="pl-4 py-1.5 space-y-2 border-l border-white/[0.08] my-1 font-mono text-[11px] animate-fade-in">
            {questions.map((q, idx) => {
              const ans = (Array.isArray(data.answers) ? data.answers[idx] : data.answers?.[idx]) || selectedAnswers[idx];
              const ansText = resolveAnswerText(ans);
              const isNoAnswer = !ansText || ansText === "(no answer)" || ansText === "(dismissed)";
              return (
                <div key={idx} className="space-y-0.5">
                  <p className="text-slate-400 font-sans">{q.question}</p>
                  <p className={`font-mono text-[11px] ${isNoAnswer ? "text-slate-500 italic" : "text-cyan-300 font-semibold"}`}>
                    {ansText || "(no answer)"}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  const isSelected = (label: string) => {
    if (isCustomActive[currentStep]) return false;
    if (Array.isArray(currentSelection)) {
      return currentSelection.includes(label);
    }
    return currentSelection === label;
  };

  return (
    <div className="w-full my-2 animate-fade-in select-text pointer-events-auto">
      <div className="w-full rounded-xl border border-white/10 bg-[#070b14]/90 p-4 sm:p-5 shadow-[0_8px_32px_rgba(0,0,0,0.5)] space-y-3.5 backdrop-blur-xl transition-all duration-200 relative overflow-hidden">
        {/* Specular Hairline */}
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-cyan-400/25 to-transparent pointer-events-none" />

        {/* Step Indicator (Only if multi-step) */}
        {totalSteps > 1 && (
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-medium text-slate-400">
              Step {currentStep + 1} of {totalSteps}
            </span>
            <div className="flex items-center gap-1.5">
              {questions.map((_, idx) => (
                <div
                  key={idx}
                  className={`h-1.5 rounded-full transition-all duration-300 ${
                    idx === currentStep
                      ? "w-6 bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.5)]"
                      : idx < currentStep
                      ? "w-4 bg-white/40"
                      : "w-4 bg-white/10"
                  }`}
                />
              ))}
            </div>
          </div>
        )}

        {/* Question Header */}
        <div className="space-y-1">
          <h3 className="text-[14px] font-semibold text-white tracking-tight leading-snug">
            {currentQ.question}
          </h3>
          <p className="text-[11.5px] text-slate-400 font-sans">
            {isMultiple ? "Select one or more options (keys 1-9 to pick)" : "Select an option (keys 1-9 to pick, Enter to submit)"}
          </p>
        </div>

        {/* Choices List */}
        <div className="space-y-2 pt-1">
          {currentQ.options.map((opt, oIdx) => {
            const active = isSelected(opt.label);
            const isRec = opt.label.toLowerCase().includes("(recommended)");
            const cleanLabel = isRec ? opt.label.replace(/\s*\(recommended\)/i, "").trim() : opt.label;
            const hotkey = oIdx < 9 ? oIdx + 1 : null;

            return (
              <button
                key={oIdx}
                type="button"
                onClick={() => handleSelectOption(opt.label)}
                className={`w-full text-left p-3 rounded-lg border transition-all flex items-start gap-3 cursor-pointer group select-none ${
                  active
                    ? "bg-cyan-500/[0.08] border-cyan-400/40 shadow-[0_0_12px_rgba(34,211,238,0.1)] ring-1 ring-cyan-400/20"
                    : "bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04] hover:border-white/[0.12]"
                }`}
              >
                {/* Hotkey Badge / Radio */}
                <div className="flex items-center gap-2 shrink-0 mt-0.5">
                  {hotkey && (
                    <span className="w-4 h-4 rounded text-[10px] font-mono flex items-center justify-center bg-white/[0.06] text-slate-400 group-hover:text-slate-200">
                      {hotkey}
                    </span>
                  )}
                  <div
                    className={`w-3.5 h-3.5 rounded-full shrink-0 flex items-center justify-center border transition-all ${
                      active ? "border-cyan-400 bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.6)]" : "border-slate-600 bg-transparent group-hover:border-slate-400"
                    }`}
                  >
                    {active && <div className="w-1 h-1 rounded-full bg-slate-950" />}
                  </div>
                </div>

                {/* Option Label & Description */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-[12.5px] font-medium ${active ? "text-cyan-200" : "text-slate-200"}`}>{cleanLabel}</span>
                    {isRec && (
                      <span className="px-1.5 py-0.5 rounded text-[9.5px] font-mono font-semibold bg-cyan-500/10 text-cyan-300 border border-cyan-400/20">
                        Recommended
                      </span>
                    )}
                  </div>
                  {opt.description && (
                    <p className="text-[11.5px] text-slate-400 mt-0.5 leading-relaxed font-sans">{opt.description}</p>
                  )}
                </div>
              </button>
            );
          })}

          {/* Custom Answer Option */}
          <div
            onClick={() => setIsCustomActive((prev) => ({ ...prev, [currentStep]: true }))}
            className={`w-full p-3 rounded-lg border transition-all space-y-2 cursor-pointer ${
              isCustomActive[currentStep]
                ? "bg-cyan-500/[0.08] border-cyan-400/40 shadow-[0_0_12px_rgba(34,211,238,0.1)] ring-1 ring-cyan-400/20"
                : "bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04] hover:border-white/[0.12]"
            }`}
          >
            <div className="flex items-center gap-3">
              <div
                className={`w-3.5 h-3.5 rounded-full shrink-0 flex items-center justify-center border transition-all ${
                  isCustomActive[currentStep]
                    ? "border-cyan-400 bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.6)]"
                    : "border-slate-600 bg-transparent"
                }`}
              >
                {isCustomActive[currentStep] && <div className="w-1 h-1 rounded-full bg-slate-950" />}
              </div>
              <span className="text-[12.5px] font-medium text-slate-300">Other (type custom answer)</span>
            </div>

            {isCustomActive[currentStep] && (
              <div className="pl-6.5 pt-1 animate-fade-in" onClick={(e) => e.stopPropagation()}>
                <input
                  type="text"
                  autoFocus
                  value={customInputs[currentStep] || ""}
                  onChange={(e) => handleCustomChange(e.target.value)}
                  placeholder="Specify custom instructions or reasoning..."
                  className="w-full px-3 py-1.5 rounded-md bg-black/40 border border-white/10 text-white placeholder-slate-500 text-xs font-sans focus:outline-none focus:border-cyan-400 transition-colors"
                />
              </div>
            )}
          </div>
        </div>

        {/* Wizard Footer Controls */}
        <div className="flex items-center justify-between pt-2 border-t border-white/[0.06]">
          <button
            type="button"
            onClick={handleDismiss}
            className="px-3 py-1.5 rounded-md text-xs font-mono text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
          >
            Dismiss
          </button>

          <div className="flex items-center gap-2">
            {currentStep > 0 && (
              <button
                type="button"
                onClick={() => setCurrentStep((prev) => Math.max(0, prev - 1))}
                className="px-3 py-1.5 rounded-md text-xs font-mono text-slate-400 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] transition-colors cursor-pointer"
              >
                Back
              </button>
            )}

            {currentStep < totalSteps - 1 ? (
              <button
                type="button"
                onClick={handleNext}
                disabled={!currentSelection}
                className="px-4 py-1.5 rounded-md text-xs font-mono font-medium text-white bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/40 transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next
              </button>
            ) : (
              <button
                type="button"
                onClick={handleFinish}
                disabled={!currentSelection}
                className="px-4 py-1.5 rounded-md text-xs font-mono font-semibold text-slate-950 bg-cyan-400 hover:bg-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.5)] transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Submit
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
