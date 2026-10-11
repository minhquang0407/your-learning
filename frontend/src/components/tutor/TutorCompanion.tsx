import React, { useState, useRef, useEffect } from "react";
import {
  Mic,
  MicOff,
  Send,
  Sparkles,
  Bot,
  User,
  Lightbulb,
  X,
  Compass,
  ArrowRight,
} from "lucide-react";
import type { ChatMessage, ProactiveNudge } from "../../types";

interface TutorCompanionProps {
  messages: ChatMessage[];
  nudges: ProactiveNudge[];
  isThinking: boolean;
  onSendMessage: (query: string, mode?: "GLOBAL_QA" | "LOCAL_QA" | "LEARNING") => void;
  onDismissNudge: (id: string) => void;
  onStreamLesson?: () => void;
}

export const TutorCompanion: React.FC<TutorCompanionProps> = ({
  messages,
  nudges,
  isThinking,
  onSendMessage,
  onDismissNudge,
  onStreamLesson,
}) => {
  const [inputQuery, setInputQuery] = useState("");
  const [qaMode, setQaMode] = useState<"GLOBAL_QA" | "LOCAL_QA" | "LEARNING">("GLOBAL_QA");
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);

  // Auto-scroll chat to latest message
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  // Handle Speech Recognition toggle
  const toggleVoice = () => {
    if (isVoiceActive) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsVoiceActive(false);
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Trình duyệt không hỗ trợ Web Speech API. Bạn có thể gõ câu hỏi bằng bàn phím.");
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = "vi-VN";
      recognition.interimResults = true;
      recognition.continuous = false;

      recognition.onstart = () => {
        setIsVoiceActive(true);
      };

      recognition.onresult = (event: any) => {
        const transcript = Array.from(event.results)
          .map((result: any) => result[0].transcript)
          .join("");
        setInputQuery(transcript);
      };

      recognition.onerror = (event: any) => {
        console.warn("Speech recognition error:", event.error);
        setIsVoiceActive(false);
      };

      recognition.onend = () => {
        setIsVoiceActive(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.warn("Could not start speech recognition:", err);
      setIsVoiceActive(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuery.trim() || isThinking) return;
    onSendMessage(inputQuery.trim(), qaMode);
    setInputQuery("");
  };

  const handleSuggestionClick = (suggestionText: string) => {
    onSendMessage(suggestionText, qaMode);
  };

  return (
    <div className="flex flex-col h-full rounded-2xl bg-[#0F111A] border border-white/10 shadow-bezel overflow-hidden">
      {/* 1. TUTOR AVATAR & AUDIO WAVEFORM HEADER */}
      <div className="p-4 border-b border-white/10 bg-[#121522]/60 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-emerald-500 to-cyan-500 p-0.5 shadow-glow-emerald">
              <div className="w-full h-full rounded-[14px] bg-[#0F111A] flex items-center justify-center text-emerald-400">
                <Bot className="w-5 h-5" />
              </div>
            </div>
            {/* Live Indicator */}
            <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 border-2 border-[#0F111A] animate-pulse" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-white">Gia sư Socratic AI</h3>
              <span className="px-1.5 py-0.5 text-[10px] rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                Omni-Tutor
              </span>
            </div>
            <p className="text-[11px] text-studio-muted">
              {isVoiceActive ? "Đang lắng nghe giọng nói..." : isThinking ? "Đang suy luận sư phạm..." : "Sẵn sàng đồng hành cùng em"}
            </p>
          </div>
        </div>

        {/* Audio Visualizer Waveform */}
        <div className="flex items-center gap-1 h-6 px-2 py-1 rounded-xl bg-[#161926] border border-white/5">
          <div className={`w-1 rounded-full bg-emerald-400 transition-all ${isVoiceActive || isThinking ? "animate-wave-bar h-5" : "h-2"}`} style={{ animationDelay: "0ms" }} />
          <div className={`w-1 rounded-full bg-cyan-400 transition-all ${isVoiceActive || isThinking ? "animate-wave-bar h-4" : "h-3"}`} style={{ animationDelay: "150ms" }} />
          <div className={`w-1 rounded-full bg-emerald-400 transition-all ${isVoiceActive || isThinking ? "animate-wave-bar h-6" : "h-1.5"}`} style={{ animationDelay: "300ms" }} />
          <div className={`w-1 rounded-full bg-purple-400 transition-all ${isVoiceActive || isThinking ? "animate-wave-bar h-3" : "h-2.5"}`} style={{ animationDelay: "450ms" }} />
          <div className={`w-1 rounded-full bg-cyan-400 transition-all ${isVoiceActive || isThinking ? "animate-wave-bar h-5" : "h-2"}`} style={{ animationDelay: "600ms" }} />
        </div>
      </div>

      {/* 2. PROACTIVE NUDGE CARDS (Pop up on Idle or Simulation Events) */}
      {nudges.length > 0 && (
        <div className="p-3 bg-amber-500/5 border-b border-amber-500/15 space-y-2">
          {nudges.map((nudge) => (
            <div
              key={nudge.id}
              className="p-3 rounded-xl bg-[#1A1D2C] border border-amber-500/20 text-xs text-amber-200/90 relative animate-fade-in"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-start gap-2">
                  <Lightbulb className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-amber-300 block mb-0.5">Gợi ý từ Thầy:</span>
                    <span>{nudge.message}</span>
                  </div>
                </div>
                <button
                  onClick={() => onDismissNudge(nudge.id)}
                  className="text-studio-muted hover:text-white p-0.5 rounded"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Suggestions quick chips */}
              {nudge.suggestions && nudge.suggestions.length > 0 && (
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {nudge.suggestions.map((s, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSuggestionClick(s)}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-[11px] text-amber-300 transition-colors"
                    >
                      <span>{s}</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 3. SOCRATIC CHAT STREAM */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-studio-muted">
            <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-studio-subtle mb-3">
              <Compass className="w-6 h-6" />
            </div>
            <h4 className="text-sm font-semibold text-white mb-1">Chưa có tương tác nào</h4>
            <p className="text-xs text-studio-subtle max-w-xs mb-4">
              Hãy hỏi một câu hỏi hoặc kéo thử các thông số thí nghiệm bên cạnh để bắt đầu học.
            </p>
            <div className="flex flex-col gap-2 w-full max-w-xs">
              {onStreamLesson && (
                <button
                  onClick={onStreamLesson}
                  className="text-left text-xs p-2.5 rounded-xl bg-gradient-to-r from-emerald-500/15 to-cyan-500/15 hover:from-emerald-500/25 hover:to-cyan-500/25 border border-emerald-500/30 text-emerald-300 transition-all font-medium flex items-center justify-between"
                >
                  <span>✨ Bắt đầu giảng giải bài học AI</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                onClick={() => handleSuggestionClick("Giải thích trực quan định luật 2 Newton")}
                className="text-left text-xs p-2.5 rounded-xl bg-[#161926] hover:bg-[#1D2132] border border-white/10 text-studio-text transition-colors"
              >
                💡 "Giải thích trực quan định luật 2 Newton"
              </button>
              <button
                onClick={() => handleSuggestionClick("Tại sao vật không chuyển động khi góc nghiêng quá nhỏ?")}
                className="text-left text-xs p-2.5 rounded-xl bg-[#161926] hover:bg-[#1D2132] border border-white/10 text-studio-text transition-colors"
              >
                ❓ "Tại sao vật không chuyển động khi góc nhỏ?"
              </button>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex items-start gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
            >
              <div
                className={`w-7 h-7 rounded-xl flex items-center justify-center shrink-0 ${
                  msg.role === "user"
                    ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                    : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                }`}
              >
                {msg.role === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div
                className={`max-w-[85%] rounded-2xl p-3.5 text-xs leading-relaxed ${
                  msg.role === "user"
                    ? "bg-cyan-950/40 border border-cyan-500/30 text-cyan-50 rounded-tr-none"
                    : "bg-[#161926] border border-white/10 text-studio-text rounded-tl-none shadow-md"
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>

                {/* Grounding Source Metadata */}
                {msg.metadata?.sources && (
                  <div className="mt-2 pt-2 border-t border-white/10 text-[10px] text-studio-subtle flex items-center gap-1 font-mono">
                    <span className="text-emerald-400">Nguồn:</span>
                    <span>{(msg.metadata.sources as string[]).join(", ")}</span>
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {/* Thinking Indicator */}
        {isThinking && (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-[#161926]/50 border border-white/10 text-xs text-studio-muted w-fit">
            <Sparkles className="w-4 h-4 text-emerald-400 animate-spin" />
            <span>Thầy đang đối chiếu tài liệu và phân tích câu trả lời...</span>
          </div>
        )}

        <div ref={chatBottomRef} />
      </div>

      {/* 4. CHAT INPUT & MICROPHONE CONTROLLER */}
      <div className="p-3 border-t border-white/10 bg-[#121522]/80 space-y-2">
        {/* QA Mode Switcher */}
        <div className="flex items-center justify-between text-[11px] text-studio-subtle px-1">
          <span>Chế độ:</span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setQaMode("GLOBAL_QA")}
              className={`px-2 py-0.5 rounded-md transition-colors ${
                qaMode === "GLOBAL_QA" ? "bg-white/10 text-white font-medium" : "hover:text-studio-text"
              }`}
            >
              Toàn bộ bài học
            </button>
            <span>•</span>
            <button
              onClick={() => setQaMode("LOCAL_QA")}
              className={`px-2 py-0.5 rounded-md transition-colors ${
                qaMode === "LOCAL_QA" ? "bg-white/10 text-white font-medium" : "hover:text-studio-text"
              }`}
            >
              Tiết học này
            </button>
          </div>
        </div>

        {/* Input Form with Microphone */}
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          {/* Mic Button */}
          <button
            type="button"
            onClick={toggleVoice}
            title={isVoiceActive ? "Dừng ghi âm" : "Nói chuyện bằng giọng nói với Thầy"}
            className={`p-2.5 rounded-xl border transition-all ${
              isVoiceActive
                ? "bg-rose-500/20 text-rose-400 border-rose-500/40 ring-2 ring-rose-500/30"
                : "bg-[#161926] text-studio-muted border-white/10 hover:text-white hover:bg-white/5"
            }`}
          >
            {isVoiceActive ? <Mic className="w-4 h-4 animate-pulse" /> : <MicOff className="w-4 h-4" />}
          </button>

          {/* Text Input */}
          <div className="relative flex-1">
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Hỏi Thầy về công thức, bài tập..."
              className="w-full bg-[#161926] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-studio-subtle focus:outline-none focus:border-emerald-500/50 transition-colors pr-9"
            />
            <button
              type="submit"
              disabled={!inputQuery.trim() || isThinking}
              className="absolute right-2 top-2 p-1 rounded-lg text-emerald-400 hover:text-emerald-300 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
