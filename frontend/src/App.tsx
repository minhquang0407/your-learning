import React, { useState, useEffect, useRef } from "react";
import { AppHeader } from "./components/layout/AppHeader";
import { MainCanvas } from "./components/canvas/MainCanvas";
import { TutorCompanion } from "./components/tutor/TutorCompanion";
import {
  fetchDocuments,
  fetchDocumentDetails,
  fetchHealth,
  sendChatMessage,
} from "./services/api";
import { createWebSocketClient } from "./services/ws";
import type { ChatMessage, DocumentDetails, DocumentSummary, HealthStatus, ProactiveNudge } from "./types";

export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<string>("");
  const [documentDetails, setDocumentDetails] = useState<DocumentDetails | null>(null);
  const [selectedSection, setSelectedSection] = useState<string>("");

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [nudges, setNudges] = useState<ProactiveNudge[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [activeFeedback, setActiveFeedback] = useState<string | null>(null);

  const sessionIdRef = useRef<string>(`session_${Math.random().toString(36).substring(2, 9)}`);
  const wsClientRef = useRef<ReturnType<typeof createWebSocketClient> | null>(null);
  const idleTimerRef = useRef<any>(null);

  // 1. Initial Data Fetching
  const loadHealth = async () => {
    try {
      const data = await fetchHealth();
      setHealth(data);
    } catch (err) {
      console.warn("Could not load health diagnostics:", err);
      // Fallback accurate offline diagnostics
      setHealth({
        status: "unhealthy",
        components: {
          qdrant: { status: "error", error: "Không thể kết nối đến máy chủ API" },
          neo4j: { status: "error", error: "Không thể kết nối đến máy chủ API" },
          llm: { status: "error", error: "Không thể kết nối đến máy chủ API" },
        },
      });
    }
  };

  const loadDocuments = async () => {
    try {
      const docs = await fetchDocuments();
      setDocuments(docs);
      if (docs.length > 0 && !selectedDocument) {
        setSelectedDocument(docs[0].file_name);
      }
    } catch (err) {
      console.warn("Could not load documents:", err);
      // Fallback mock document for initial offline preview
      const fallbackDocs = [
        {
          file_name: "vat_ly_10_dong_luc_hoc.md",
          table_of_contents: {
            "Chương 1: Động lực học chất điểm": [
              "Định luật II Newton",
              "Lực ma sát và mặt phẳng nghiêng",
              "Lực hấp dẫn và định luật vạn vật hấp dẫn",
            ],
          },
        },
      ];
      setDocuments(fallbackDocs);
      if (!selectedDocument) {
        setSelectedDocument(fallbackDocs[0].file_name);
      }
    }
  };

  useEffect(() => {
    loadHealth();
    loadDocuments();
  }, []);

  // 2. Load Details for Selected Document
  useEffect(() => {
    if (!selectedDocument) return;

    fetchDocumentDetails(selectedDocument)
      .then((details) => {
        setDocumentDetails(details);
        // Select first section by default
        const firstChapter = Object.keys(details.table_of_contents || {})[0];
        if (firstChapter && details.table_of_contents[firstChapter]?.length > 0) {
          setSelectedSection(details.table_of_contents[firstChapter][0]);
        }
      })
      .catch(() => {
        // Fallback mock details for preview
        const mockDetails: DocumentDetails = {
          file_name: selectedDocument,
          table_of_contents: {
            "Chương 1: Động lực học chất điểm": [
              "Định luật II Newton",
              "Lực ma sát và mặt phẳng nghiêng",
              "Lực đàn hồi",
            ],
          },
          progress: { total: 8, learned: 3, percent: 37.5 },
        };
        setDocumentDetails(mockDetails);
        setSelectedSection("Định luật II Newton");
      });
  }, [selectedDocument]);

  // 3. Setup WebSocket Connection with Lesson Streaming support
  useEffect(() => {
    const ws = createWebSocketClient(sessionIdRef.current);
    wsClientRef.current = ws;
    ws.connect();

    const unsubscribe = ws.subscribe((msg) => {
      if (msg.type === "PROACTIVE_NUDGE") {
        const newNudge: ProactiveNudge = {
          id: `nudge_${Date.now()}`,
          message: msg.payload?.message || "Em có cần hỗ trợ gì không?",
          suggestions: msg.payload?.suggestions || [],
          timestamp: Date.now(),
        };
        setNudges((prev) => [newNudge, ...prev.slice(0, 2)]);
      } else if (msg.type === "WIDGET_FEEDBACK") {
        setActiveFeedback(msg.payload?.hint || "Đã đồng bộ thông số thí nghiệm");
        setTimeout(() => setActiveFeedback(null), 3000);
      } else if (msg.type === "CHAT_RESPONSE") {
        setMessages((prev) => [
          ...prev,
          {
            id: `msg_${Date.now()}`,
            role: "tutor",
            content: msg.payload?.content || "",
            timestamp: new Date().toLocaleTimeString(),
            metadata: msg.payload?.metadata,
          },
        ]);
        setIsThinking(false);
      } else if (msg.type === "LESSON_EVENT") {
        const payload = msg.payload || {};
        const content = payload.content || payload.message || "";
        if (content) {
          setMessages((prev) => [
            ...prev,
            {
              id: `lesson_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
              role: "tutor",
              content: `[${payload.kind?.toUpperCase() || "BÀI GIẢNG"}] ${content}`,
              timestamp: new Date().toLocaleTimeString(),
              mode: "LEARNING",
            },
          ]);
        }
        if (payload.kind === "final" || payload.kind === "error") {
          setIsThinking(false);
        }
      }
    });

    return () => {
      unsubscribe();
      ws.disconnect();
    };
  }, []);

  // 4. Throttled Idle Detection Telemetry (20s inactivity -> PING_IDLE)
  useEffect(() => {
    let lastActivity = Date.now();

    const throttledResetIdle = () => {
      const now = Date.now();
      if (now - lastActivity < 500) return;
      lastActivity = now;

      clearTimeout(idleTimerRef.current);
      idleTimerRef.current = setTimeout(() => {
        if (wsClientRef.current) {
          wsClientRef.current.sendIdlePing(20);
        }
      }, 20000); // 20 seconds
    };

    window.addEventListener("mousemove", throttledResetIdle);
    window.addEventListener("keydown", throttledResetIdle);
    window.addEventListener("click", throttledResetIdle);

    throttledResetIdle();

    return () => {
      clearTimeout(idleTimerRef.current);
      window.removeEventListener("mousemove", throttledResetIdle);
      window.removeEventListener("keydown", throttledResetIdle);
      window.removeEventListener("click", throttledResetIdle);
    };
  }, []);

  // 5. Send Chat Query Handlers
  const handleSendMessage = async (
    query: string,
    mode: "GLOBAL_QA" | "LOCAL_QA" | "LEARNING" = "GLOBAL_QA"
  ) => {
    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      role: "user",
      content: query,
      timestamp: new Date().toLocaleTimeString(),
      mode,
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsThinking(true);

    try {
      const res = await sendChatMessage({
        query,
        user_id: "student_01",
        mode,
        target_file: selectedDocument,
        target_section: selectedSection,
      });

      const tutorMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        role: "tutor",
        content: res.content,
        timestamp: new Date().toLocaleTimeString(),
        metadata: res.metadata,
      };
      setMessages((prev) => [...prev, tutorMsg]);
    } catch (err: any) {
      console.warn("Chat request failed, providing local fallback:", err);
      // Fallback friendly message if API is offline
      const fallbackMsg: ChatMessage = {
        id: `fallback_${Date.now()}`,
        role: "tutor",
        content: `Thầy ghi nhận câu hỏi: "${query}".\n\nTheo tài liệu ${selectedDocument || "Vật lý 10"}, định luật 2 Newton phát biểu rằng gia tốc tỉ lệ thuận với lực tác dụng và tỉ lệ nghịch với khối lượng: F = m · a. Hãy thử tăng lực kéo trên mô phỏng để thấy sự thay đổi gia tốc nhé!`,
        timestamp: new Date().toLocaleTimeString(),
        metadata: { sources: [selectedDocument || "vat_ly_10_dong_luc_hoc.md"] },
      };
      setMessages((prev) => [...prev, fallbackMsg]);
    } finally {
      setIsThinking(false);
    }
  };

  // 6. Handle AI Lesson Streaming via WebSocket
  const handleStreamLesson = () => {
    if (!selectedDocument && !selectedSection) return;
    setIsThinking(true);
    setMessages((prev) => [
      ...prev,
      {
        id: `usr_${Date.now()}`,
        role: "user",
        content: `Thầy hãy bắt đầu giảng bài cho em phần: "${selectedSection || "Định luật II Newton"}"`,
        timestamp: new Date().toLocaleTimeString(),
        mode: "LEARNING",
      },
    ]);
    wsClientRef.current?.sendStreamLesson(selectedDocument, selectedSection);
  };

  const handleDismissNudge = (id: string) => {
    setNudges((prev) => prev.filter((n) => n.id !== id));
  };

  const handleWidgetChange = (widgetId: string, values: Record<string, unknown>) => {
    wsClientRef.current?.sendWidgetChange(widgetId, values);
  };

  const handleVideoSeek = (currentTime: number) => {
    wsClientRef.current?.sendVideoSeek(currentTime);
  };

  return (
    <div className="min-h-screen bg-[#090A0F] text-[#F1F5F9] flex flex-col font-sans">
      {/* Top Floating Island Header */}
      <AppHeader
        health={health}
        documents={documents}
        selectedDocument={selectedDocument}
        onSelectDocument={setSelectedDocument}
        onRefreshHealth={loadHealth}
        onRefreshDocuments={loadDocuments}
      />

      {/* Asymmetric Split Layout: 65% Main Canvas + 35% Tutor Companion */}
      <main className="flex-1 px-4 pb-4 max-w-7xl mx-auto w-full flex flex-col lg:flex-row gap-4 h-[calc(100vh-84px)] min-h-[620px]">
        {/* 65% Main Canvas Stage */}
        <div className="w-full lg:w-[65%] h-full">
          <MainCanvas
            documentDetails={documentDetails}
            selectedSection={selectedSection}
            onSelectSection={setSelectedSection}
            onWidgetChange={handleWidgetChange}
            onVideoSeek={handleVideoSeek}
            activeFeedback={activeFeedback}
          />
        </div>

        {/* 35% Cognitive Tutor Panel */}
        <div className="w-full lg:w-[35%] h-full">
          <TutorCompanion
            messages={messages}
            nudges={nudges}
            isThinking={isThinking}
            onSendMessage={handleSendMessage}
            onDismissNudge={handleDismissNudge}
            onStreamLesson={handleStreamLesson}
          />
        </div>
      </main>
    </div>
  );
};

export default App;
