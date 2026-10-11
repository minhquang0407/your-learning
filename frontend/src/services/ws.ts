export interface WebSocketMessage {
  type: string;
  session_id?: string;
  payload?: any;
}

type MessageHandler = (message: WebSocketMessage) => void;

class WebSocketClient {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private url: string;
  private handlers: Set<MessageHandler> = new Set();
  private reconnectTimer: any = null;
  private isExplicitlyClosed = false;
  private isConnecting = false;
  private pendingQueue: Array<{ type: string; payload: Record<string, unknown> }> = [];

  constructor(sessionId: string) {
    this.sessionId = sessionId;
    const rawBase = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");
    const wsBase = rawBase
      .replace(/^http:/, "ws:")
      .replace(/^https:/, "wss:");
    this.url = `${wsBase}/api/ws/session/${sessionId}`;
  }

  public connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isExplicitlyClosed = false;
    this.isConnecting = true;

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.isConnecting = false;
        console.log(`[WS] Connected to tutor session: ${this.sessionId}`);
        // Flush any queued telemetry or questions
        while (this.pendingQueue.length > 0) {
          const item = this.pendingQueue.shift();
          if (item && this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(item));
          }
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          this.handlers.forEach((h) => h(parsed));
        } catch (err) {
          console.warn("[WS] Non-JSON message received:", event.data);
        }
      };

      this.ws.onclose = () => {
        this.isConnecting = false;
        if (!this.isExplicitlyClosed) {
          console.log("[WS] Disconnected. Reconnecting in 3 seconds...");
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = setTimeout(() => this.connect(), 3000);
        }
      };

      this.ws.onerror = (err) => {
        console.warn("[WS] WebSocket error:", err);
      };
    } catch (err) {
      this.isConnecting = false;
      console.error("[WS] Failed to create WebSocket connection:", err);
    }
  }

  public subscribe(handler: MessageHandler): () => void {
    this.handlers.add(handler);
    return () => {
      this.handlers.delete(handler);
    };
  }

  public send(type: string, payload: Record<string, unknown> = {}): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload }));
    } else {
      // Queue message until socket is opened
      this.pendingQueue.push({ type, payload });
      if (!this.ws || this.ws.readyState === WebSocket.CLOSED) {
        this.connect();
      }
    }
  }

  public sendIdlePing(idleSeconds: number = 20): void {
    this.send("PING_IDLE", { idleSeconds });
  }

  public sendWidgetChange(widgetId: string, values: Record<string, unknown>): void {
    this.send("WIDGET_CHANGE", { widget_id: widgetId, values });
  }

  public sendVideoSeek(currentTime: number): void {
    this.send("VIDEO_SEEK", { currentTime });
  }

  public sendQuestion(query: string, options: Record<string, unknown> = {}): void {
    this.send("USER_QUESTION", { query, ...options });
  }

  public sendStreamLesson(
    targetFile: string,
    targetSection: string,
    stepData?: Record<string, unknown>
  ): void {
    this.send("STREAM_LESSON", {
      target_file: targetFile,
      target_section: targetSection,
      step_data: stepData || { step_title: targetSection },
    });
  }

  public disconnect(): void {
    this.isExplicitlyClosed = true;
    clearTimeout(this.reconnectTimer);
    this.pendingQueue = [];
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  public get isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  public get isConnectingState(): boolean {
    return this.isConnecting;
  }
}

export const createWebSocketClient = (sessionId: string) => new WebSocketClient(sessionId);
