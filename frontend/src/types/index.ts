export interface DocumentSummary {
  file_name: string;
  table_of_contents: Record<string, string[]>;
}

export interface DocumentDetails {
  file_name: string;
  table_of_contents: Record<string, string[]>;
  progress: {
    total: number;
    learned: number;
    percent: number;
  };
}

export interface HealthComponentStatus {
  status: "connected" | "error";
  details?: string;
  response?: string;
  error?: string;
}

export interface HealthStatus {
  status: "healthy" | "degraded" | "unhealthy";
  components: {
    qdrant: HealthComponentStatus;
    neo4j: HealthComponentStatus;
    llm: HealthComponentStatus;
  };
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "tutor";
  content: string;
  timestamp: string;
  mode?: "GLOBAL_QA" | "LOCAL_QA" | "LEARNING";
  metadata?: {
    sources?: string[];
    [key: string]: unknown;
  };
}

export interface ProactiveNudge {
  id: string;
  message: string;
  suggestions?: string[];
  timestamp: number;
}
