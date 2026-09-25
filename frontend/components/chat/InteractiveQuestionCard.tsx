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
  if (!raw) return "(no answer)";
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
  const { questionId, questions, isAnswered = false } = data;
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string | string[]>>({});

  const [customInputs, setCustomInputs] = useState<Record<number, string>>({});
  const [isCustomActive, setIsCustomActive] = useState<Record<number, boolean>>({});
  const [isAccordionOpen, setIsAccordionOpen] = useState(false);

  const currentQ = questions[currentStep];
  const totalSteps = questions.length;

  const defaultOptionForCurrentStep =
    currentQ?.options.find((o) => o.label.toLowerCase().includes("(recommended)"))?.label ||
    currentQ?.options[0]?.label ||
    "";
  const currentSelection =
    selectedAnswers[currentStep] ?? (isCustomActive[currentStep] ? customInputs[currentStep] : defaultOptionForCurrentStep);

  // If already answered or dismissed, show the sleek collapsible summary (OpenCode style)
  if (isAnswered) {
    const answeredCount = questions.filter((q, idx) => {
      const ans = (Array.isArray(data.answers) ? data.answers[idx] : data.answers?.[idx]) || selectedAnswers[idx];
      const ansText = resolveAnswerText(ans);
      return ansText && ansText !== "(no answer)" && ansText !== "(no answer)";
    }).length;

    const accordionTitle =
      answeredCount === 0 ? "Questions dismissed (no answers)" : `${answeredCount} question${answeredCount > 1 ? "s" : ""} answered`;

    return (
      <div className="w-full my-2 px-1">
        <div
          className="rounded-xl border border-white/12 backdrop-blur-xl overflow-hidden transition-all shadow-lg"
          style={{
            background: "linear-gradient(165deg, rgba(20, 26, 38, 0.92) 0%, rgba(13, 17, 26, 0.95) 100%)",
            boxShadow: "0 10px 30px rgba(0, 0, 0, 0.6), inset 0 1px 0 0 rgba(255, 255, 255, 0.15)",
          }}
        >
          <button
            type="button"
            onClick={() => setIsAccordionOpen((prev) => !prev)}
            className="w-full px-4 py-2.5 flex items-center justify-between text-left hover:bg-white/[0.03] transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${answeredCount > 0 ? "bg-white animate-pulse" : "bg-slate-500"}`} />
              <span className="text-xs font-mono font-semibold text-slate-200">
                {accordionTitle}
              </span>
            </div>
            <svg
              className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isAccordionOpen ? "rotate-180" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {isAccordionOpen && (
            <div className="px-4 pb-3.5 pt-1 space-y-3 border-t border-white/5 animate-fade-in text-[12.5px]">
              {questions.map((q, idx) => {
                const ans =
                  (Array.isArray(data.answers) ? data.answers[idx] : data.answers?.[idx]) || selectedAnswers[idx];
                const ansText = resolveAnswerText(ans);
                const isNoAnswer = !ansText || ansText === "(no answer)" || ansText === "(no answer)";
                return (
                  <div key={idx} className="space-y-0.5">
                    <p className="text-slate-400 font-medium">{q.question}</p>
                    {isNoAnswer ? (
                      <p className="text-slate-500 font-mono text-xs pl-2 border-l border-white/10 italic">
                        (no answer)
                      </p>
                    ) : (
                      <p className="text-white/90 font-semibold font-mono pl-2 border-l border-white/20">
                        {ansText}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  }

  const handleSelectOption = (label: string) => {
    setIsCustomActive((prev) => ({ ...prev, [currentStep]: false }));
    if (currentQ.multiple) {
      const existing = (selectedAnswers[currentStep] as string[]) || [];
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
    setSelectedAnswers((prev) => ({ ...prev, [currentStep]: text.trim() || "(no answer)" }));
  };

  const handleNext = () => {
    setSelectedAnswers((prev) => ({
      ...prev,
      [currentStep]: isCustomActive[currentStep]
        ? (customInputs[currentStep]?.trim() || "(no answer)")
        : (prev[currentStep] ?? currentSelection),
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
    // User explicitly closes/dismisses: all questions become "(no answer)" with dismissed flag
    const formatted = questions.map((q) => ({
      header: q.header,
      question: q.question,
      answer: "(no answer)",
    }));
    onSubmitAnswers(questionId, formatted, true);
  };

  const isSelected = (label: string) => {
    if (isCustomActive[currentStep]) return false;
    if (Array.isArray(currentSelection)) {
      return currentSelection.includes(label);
    }
    return currentSelection === label;
  };

  return (
    <div className="w-full animate-fade-in select-text pointer-events-auto">
      <div
        className="w-full rounded-2xl border border-white/15 p-4 sm:p-5 shadow-2xl shadow-black/90 space-y-3.5 backdrop-blur-2xl transition-all duration-300 relative overflow-hidden"
        style={{
          background: "linear-gradient(165deg, rgba(20, 26, 38, 0.90) 0%, rgba(13, 17, 26, 0.94) 50%, rgba(9, 13, 20, 0.97) 100%)",
          boxShadow: "0 20px 50px rgba(0, 0, 0, 0.8), inset 0 1px 0 0 rgba(255, 255, 255, 0.25)",
        }}
      >
        {/* Top Specular Sheen Highlight */}
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/35 to-transparent pointer-events-none" />
        {/* Step Indicator and Progress Bars */}
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono font-medium text-slate-300">
            Step {currentStep + 1} of {totalSteps}
          </span>
          <div className="flex items-center gap-1.5">
            {questions.map((_, idx) => (
              <div
                key={idx}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  idx === currentStep
                    ? "w-6 bg-white shadow-[0_0_8px_rgba(255,255,255,0.5)]"
                    : idx < currentStep
                    ? "w-4 bg-white/40"
                    : "w-4 bg-white/10"
                }`}
              />
            ))}
          </div>
        </div>

        {/* Question Header */}
        <div className="space-y-1">
          <h3 className="text-[15px] font-semibold text-white tracking-tight leading-snug">
            {currentQ.question}
          </h3>
          <p className="text-[11.5px] text-slate-400 font-sans">
            {currentQ.multiple ? "Select one or more options" : "Select an option"}
          </p>
        </div>

        {/* Choices List */}
        <div className="space-y-2 pt-1">
          {currentQ.options.map((opt, oIdx) => {
            const active = isSelected(opt.label);
            const isRec = opt.label.toLowerCase().includes("(recommended)");
            const cleanLabel = isRec ? opt.label.replace(/\s*\(recommended\)/i, "").trim() : opt.label;

            return (
              <button
                key={oIdx}
                type="button"
                onClick={() => handleSelectOption(opt.label)}
                className={`w-full text-left p-3.5 rounded-xl border transition-all flex items-start gap-3 cursor-pointer group select-none ${
                  active
                    ? "bg-white/[0.08] border-white/30 shadow-[0_0_15px_rgba(255,255,255,0.06)] ring-1 ring-white/20"
                    : "bg-white/[0.02] border-white/8 hover:bg-white/[0.05] hover:border-white/16"
                }`}
              >
                {/* Radio Indicator */}
                <div
                  className={`w-4 h-4 rounded-full mt-0.5 shrink-0 flex items-center justify-center border transition-all ${
                    active ? "border-white bg-white shadow-[0_0_6px_rgba(255,255,255,0.6)]" : "border-slate-500 bg-transparent group-hover:border-slate-400"
                  }`}
                >
                  {active && <div className="w-1.5 h-1.5 rounded-full bg-slate-950" />}
                </div>

                {/* Option Label & Description */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[13px] font-semibold text-slate-100">{cleanLabel}</span>
                    {isRec && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-white/10 text-slate-200 border border-white/20">
                        Recommended
                      </span>
                    )}
                  </div>
                  {opt.description && (
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed font-sans">{opt.description}</p>
                  )}
                </div>
              </button>
            );
          })}

          {/* Custom Answer Option */}
          <div
            onClick={() => {
              setIsCustomActive((prev) => ({ ...prev, [currentStep]: true }));
            }}
            className={`w-full text-left p-3.5 rounded-xl border transition-all flex items-start gap-3 cursor-pointer ${
              isCustomActive[currentStep]
                ? "bg-white/[0.08] border-white/30 ring-1 ring-white/20"
                : "bg-white/[0.02] border-white/8 hover:bg-white/[0.05] hover:border-white/16"
            }`}
          >
            <div
              className={`w-4 h-4 rounded-full mt-0.5 shrink-0 flex items-center justify-center border transition-all ${
                isCustomActive[currentStep] ? "border-white bg-white shadow-[0_0_6px_rgba(255,255,255,0.6)]" : "border-slate-500 bg-transparent"
              }`}
            >
              {isCustomActive[currentStep] && <div className="w-1.5 h-1.5 rounded-full bg-slate-950" />}
            </div>

            <div className="min-w-0 flex-1">
              <span className="text-[13px] font-semibold text-slate-100">Type your own answer</span>
              {isCustomActive[currentStep] ? (
                <input
                  type="text"
                  value={customInputs[currentStep] || ""}
                  onChange={(e) => handleCustomChange(e.target.value)}
                  placeholder="Type your answer here..."
                  className="mt-2 w-full px-3 py-2 rounded-lg bg-black/50 border border-white/20 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-white/40 focus:border-white/40 font-sans"
                  autoFocus
                />
              ) : (
                <p className="text-xs text-slate-400 mt-0.5">Type custom answer...</p>
              )}
            </div>
          </div>
        </div>

        {/* Wizard Footer Controls */}
        <div className="flex items-center justify-between pt-3 border-t border-white/8">
          <button
            type="button"
            onClick={handleDismiss}
            className="text-xs text-slate-400 hover:text-slate-200 transition-colors px-2 py-1.5 cursor-pointer"
          >
            Dismiss
          </button>

          <div className="flex items-center gap-2">
            {currentStep > 0 && (
              <button
                type="button"
                onClick={() => setCurrentStep((prev) => Math.max(0, prev - 1))}
                className="px-3.5 py-1.5 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 text-xs font-semibold text-slate-200 transition-all cursor-pointer active:scale-95"
              >
                Back
              </button>
            )}

            {currentStep < totalSteps - 1 ? (
              <button
                type="button"
                onClick={handleNext}
                className="px-4 py-1.5 rounded-lg bg-white hover:bg-slate-200 text-xs font-bold text-slate-950 transition-all shadow-md shadow-white/20 cursor-pointer active:scale-95"
              >
                Next
              </button>
            ) : (
              <button
                type="button"
                onClick={handleFinish}
                className="px-4 py-1.5 rounded-lg bg-emerald-400 hover:bg-emerald-300 text-xs font-bold text-slate-950 transition-all shadow-md shadow-emerald-400/30 cursor-pointer active:scale-95"
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
