import React, { useState } from "react";
import {
  Sparkles,
  Database,
  Layers,
  Cpu,
  BookOpen,
  Upload,
  RefreshCw,
  X,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import type { DocumentSummary, HealthStatus } from "../../types";
import { uploadDocument } from "../../services/api";

interface AppHeaderProps {
  health: HealthStatus | null;
  documents: DocumentSummary[];
  selectedDocument: string;
  onSelectDocument: (docName: string) => void;
  onRefreshHealth: () => void;
  onRefreshDocuments: () => void;
}

export const AppHeader: React.FC<AppHeaderProps> = ({
  health,
  documents,
  selectedDocument,
  onSelectDocument,
  onRefreshHealth,
  onRefreshDocuments,
}) => {
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const res = await uploadDocument(file);
      setUploadSuccess(`Đã nạp thành công ${res.file_name}!`);
      onRefreshDocuments();
      onSelectDocument(res.file_name);
      setTimeout(() => {
        setIsUploadOpen(false);
        setUploadSuccess(null);
      }, 1500);
    } catch (err: any) {
      setUploadError(err.message || "Tải tài liệu thất bại.");
    } finally {
      setUploading(false);
    }
  };

  const getStatusColor = (status?: string) => {
    if (status === "connected") return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    if (status === "error") return "bg-rose-500/10 text-rose-400 border-rose-500/20";
    return "bg-amber-500/10 text-amber-400 border-amber-500/20";
  };

  return (
    <>
      <header className="sticky top-3 z-40 px-4 mb-4">
        <div className="mx-auto max-w-7xl flex items-center justify-between px-5 py-3 rounded-2xl bg-[#0F111A]/90 backdrop-blur-xl border border-white/10 shadow-bezel">
          {/* Logo & Product Title */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-500/20 to-cyan-500/20 border border-white/15 flex items-center justify-center text-emerald-400 shadow-glow-emerald">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-sm tracking-tight text-white">Your Learning</span>
                <span className="px-1.5 py-0.5 text-[10px] font-medium tracking-wide uppercase rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Cognitive Studio
                </span>
              </div>
              <p className="text-[11px] text-studio-subtle leading-none">Phòng học đa phương thức thế hệ mới</p>
            </div>
          </div>

          {/* Document Selector */}
          <div className="flex items-center gap-2 bg-[#161926] px-3 py-1.5 rounded-xl border border-white/10">
            <BookOpen className="w-4 h-4 text-studio-muted" />
            <select
              value={selectedDocument}
              onChange={(e) => onSelectDocument(e.target.value)}
              className="bg-transparent text-xs font-medium text-studio-text focus:outline-none cursor-pointer pr-2"
            >
              {documents.length === 0 ? (
                <option value="" className="bg-[#161926]">Không có tài liệu nào</option>
              ) : (
                documents.map((doc) => (
                  <option key={doc.file_name} value={doc.file_name} className="bg-[#161926] text-white">
                    {doc.file_name}
                  </option>
                ))
              )}
            </select>
            <button
              onClick={() => setIsUploadOpen(true)}
              title="Tải tài liệu mới (.md)"
              className="p-1 rounded-lg text-studio-muted hover:text-white hover:bg-white/5 transition-colors"
            >
              <Upload className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* System Health Status Pills */}
          <div className="flex items-center gap-2">
            {/* Neo4j Pill */}
            <div
              title={`Neo4j: ${health?.components.neo4j.status || "checking..."}`}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium ${getStatusColor(health?.components.neo4j.status)}`}
            >
              <Database className="w-3.5 h-3.5" />
              <span className="text-[11px] hidden sm:inline">Neo4j</span>
              <span className={`w-1.5 h-1.5 rounded-full ${health?.components.neo4j.status === "connected" ? "bg-emerald-400 animate-pulse" : "bg-rose-400"}`} />
            </div>

            {/* Qdrant Pill */}
            <div
              title={`Qdrant: ${health?.components.qdrant.status || "checking..."}`}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium ${getStatusColor(health?.components.qdrant.status)}`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span className="text-[11px] hidden sm:inline">Qdrant</span>
              <span className={`w-1.5 h-1.5 rounded-full ${health?.components.qdrant.status === "connected" ? "bg-cyan-400 animate-pulse" : "bg-rose-400"}`} />
            </div>

            {/* LLM Pill */}
            <div
              title={`LLM Engine: ${health?.components.llm.status || "checking..."}`}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium ${getStatusColor(health?.components.llm.status)}`}
            >
              <Cpu className="w-3.5 h-3.5" />
              <span className="text-[11px] hidden sm:inline">LLM</span>
              <span className={`w-1.5 h-1.5 rounded-full ${health?.components.llm.status === "connected" ? "bg-purple-400 animate-pulse" : "bg-rose-400"}`} />
            </div>

            {/* Refresh Button */}
            <button
              onClick={() => {
                onRefreshHealth();
                onRefreshDocuments();
              }}
              title="Làm mới trạng thái kết nối"
              className="p-1.5 rounded-xl border border-white/10 text-studio-muted hover:text-white hover:bg-white/5 transition-all"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* Upload Modal */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl bg-[#0F111A] border border-white/15 p-6 shadow-2xl relative">
            <button
              onClick={() => setIsUploadOpen(false)}
              className="absolute top-4 right-4 text-studio-muted hover:text-white p-1 rounded-lg hover:bg-white/5"
            >
              <X className="w-4 h-4" />
            </button>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                <Upload className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white">Nạp tài liệu học tập</h3>
                <p className="text-xs text-studio-muted">Hỗ trợ định dạng Markdown (.md)</p>
              </div>
            </div>

            <div className="border-2 border-dashed border-white/15 rounded-xl p-8 text-center hover:border-cyan-500/50 transition-colors bg-[#161926]/40 cursor-pointer relative">
              <input
                type="file"
                accept=".md"
                onChange={handleFileUpload}
                disabled={uploading}
                className="absolute inset-0 opacity-0 cursor-pointer"
              />
              <Upload className="w-8 h-8 text-studio-muted mx-auto mb-2 animate-bounce" />
              <p className="text-sm font-medium text-white mb-1">
                {uploading ? "Đang xử lý tài liệu và phân tích DAG..." : "Nhấp hoặc kéo thả file .md vào đây"}
              </p>
              <p className="text-xs text-studio-subtle">Hệ thống sẽ tự động tách Section và tạo Knowledge Graph</p>
            </div>

            {uploadSuccess && (
              <div className="mt-3 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>{uploadSuccess}</span>
              </div>
            )}

            {uploadError && (
              <div className="mt-3 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};
