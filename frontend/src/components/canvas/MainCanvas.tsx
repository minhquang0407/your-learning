import React, { useState, useEffect, useRef } from "react";
import {
  Presentation,
  Play,
  Pause,
  Sliders,
  ChevronLeft,
  ChevronRight,
  PenTool,
  Maximize2,
  Film,
  Zap,
  Eraser,
} from "lucide-react";
import type { DocumentDetails } from "../../types";

interface MainCanvasProps {
  documentDetails: DocumentDetails | null;
  selectedSection: string;
  onSelectSection: (section: string) => void;
  onWidgetChange: (widgetId: string, values: Record<string, unknown>) => void;
  onVideoSeek: (currentTime: number) => void;
  activeFeedback?: string | null;
}

export const MainCanvas: React.FC<MainCanvasProps> = ({
  documentDetails,
  selectedSection,
  onSelectSection,
  onWidgetChange,
  onVideoSeek,
  activeFeedback,
}) => {
  const [activeTab, setActiveTab] = useState<"slides" | "simulation" | "video">("simulation");
  const [slidePage, setSlidePage] = useState(1);
  const totalSlides = 5;

  // Simulation State: Newton's 2nd Law
  const [mass, setMass] = useState(5); // kg
  const [force, setForce] = useState(35); // N
  const [angle, setAngle] = useState(25); // degrees
  const [friction, setFriction] = useState(0.1); // coefficient

  // Drawing overlay state
  const [canvasDrawingMode, setCanvasDrawingMode] = useState(false);
  const [penColor, setPenColor] = useState("#F59E0B");
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const isDrawingRef = useRef(false);

  // Video State
  const [isPlaying, setIsPlaying] = useState(false);
  const [videoTime, setVideoTime] = useState(142.5); // seconds
  const totalVideoDuration = 600; // 10 minutes

  // Physics calculation
  const g = 9.81;
  const rad = (angle * Math.PI) / 180;
  const fGravityParallel = mass * g * Math.sin(rad);
  const fNormal = mass * g * Math.cos(rad);
  const fFrictionMax = friction * fNormal;

  let netForce = 0;
  let acceleration = 0;
  let motionState = "Cân bằng tĩnh (vật đứng yên)";

  if (force > fGravityParallel + fFrictionMax) {
    netForce = force - fGravityParallel - fFrictionMax;
    acceleration = netForce / mass;
    motionState = "Vật chuyển động gia tốc LÊN DỐC";
  } else if (force < fGravityParallel - fFrictionMax) {
    netForce = fGravityParallel - force - fFrictionMax;
    acceleration = netForce / mass;
    motionState = "Vật chuyển động gia tốc XUỐNG DỐC";
  } else {
    netForce = 0;
    acceleration = 0;
    motionState = "Cân bằng tĩnh (lực kéo và ma sát giữ vật)";
  }

  // Trigger telemetry on simulation change
  useEffect(() => {
    onWidgetChange("newton_second_law", {
      mass,
      force,
      angle,
      friction,
      acceleration: parseFloat(acceleration.toFixed(2)),
      netForce: parseFloat(netForce.toFixed(2)),
      motionState,
    });
  }, [mass, force, angle, friction, acceleration, netForce, motionState]);

  // Video scrubber handler
  const handleVideoSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = parseFloat(e.target.value);
    setVideoTime(newTime);
    onVideoSeek(newTime);
  };

  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${mins.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  // Drawing canvas handlers
  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    isDrawingRef.current = true;
    const rect = canvas.getBoundingClientRect();
    const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
    const clientY = "touches" in e ? e.touches[0].clientY : e.clientY;

    ctx.beginPath();
    ctx.moveTo(clientX - rect.left, clientY - rect.top);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (!isDrawingRef.current) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
    const clientY = "touches" in e ? e.touches[0].clientY : e.clientY;

    ctx.strokeStyle = penColor;
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineTo(clientX - rect.left, clientY - rect.top);
    ctx.stroke();
  };

  const stopDrawing = () => {
    isDrawingRef.current = false;
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  };

  // Geometry calculation for the SVG ramp
  const x0 = 70;
  const y0 = 170;
  const rampLength = 175;
  const xtop = x0 + rampLength * Math.cos(rad);
  const ytop = y0 - rampLength * Math.sin(rad);

  const blockS = rampLength * 0.52;
  const xBlock = x0 + blockS * Math.cos(rad);
  const yBlock = y0 - blockS * Math.sin(rad);

  return (
    <div className="flex flex-col h-full rounded-2xl bg-[#0F111A] border border-white/10 shadow-bezel overflow-hidden">
      {/* Canvas Top Bar: Navigation & Modes */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/10 bg-[#121522]/50">
        {/* Stage Mode Switcher */}
        <div className="flex items-center gap-1 p-1 bg-[#161926] rounded-xl border border-white/10">
          <button
            onClick={() => setActiveTab("simulation")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === "simulation"
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 shadow-sm"
                : "text-studio-muted hover:text-white"
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Mô phỏng tương tác</span>
          </button>
          <button
            onClick={() => setActiveTab("slides")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === "slides"
                ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-sm"
                : "text-studio-muted hover:text-white"
            }`}
          >
            <Presentation className="w-3.5 h-3.5" />
            <span>Slide bài giảng</span>
          </button>
          <button
            onClick={() => setActiveTab("video")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === "video"
                ? "bg-purple-500/15 text-purple-300 border border-purple-500/30 shadow-sm"
                : "text-studio-muted hover:text-white"
            }`}
          >
            <Film className="w-3.5 h-3.5" />
            <span>Video đồng bộ</span>
          </button>
        </div>

        {/* Section Picker Pills */}
        <div className="hidden lg:flex items-center gap-2">
          {documentDetails?.table_of_contents &&
            Object.entries(documentDetails.table_of_contents).flatMap(([_, secs]) =>
              secs.slice(0, 3).map((sec) => (
                <button
                  key={sec}
                  onClick={() => onSelectSection(sec)}
                  className={`px-2.5 py-1 rounded-lg text-xs transition-all border ${
                    selectedSection === sec
                      ? "bg-white/10 text-white border-white/20 font-medium"
                      : "text-studio-subtle hover:text-studio-muted border-transparent"
                  }`}
                >
                  {sec}
                </button>
              ))
            )}
        </div>

        {/* Tools Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCanvasDrawingMode(!canvasDrawingMode)}
            title="Bật/Tắt vẽ ghi chú trên bài giảng"
            className={`p-2 rounded-xl border transition-all ${
              canvasDrawingMode
                ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                : "border-white/10 text-studio-muted hover:text-white hover:bg-white/5"
            }`}
          >
            <PenTool className="w-4 h-4" />
          </button>
          <button
            title="Toàn màn hình"
            className="p-2 rounded-xl border border-white/10 text-studio-muted hover:text-white hover:bg-white/5"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Canvas Body */}
      <div className="relative flex-1 p-6 overflow-y-auto bg-gradient-to-b from-[#0F111A] to-[#0A0C13]">
        {/* Drawing Overlay Notice & Controls */}
        {canvasDrawingMode && (
          <div className="absolute top-4 right-4 z-30 px-3.5 py-2 rounded-xl bg-[#161926]/90 backdrop-blur-md border border-amber-500/30 text-amber-300 text-xs flex items-center gap-3 shadow-xl">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
              <span>Phấn điện tử</span>
            </div>
            {/* Color Swatches */}
            <div className="flex items-center gap-1 border-l border-white/10 pl-2">
              <button
                onClick={() => setPenColor("#F59E0B")}
                className={`w-4 h-4 rounded-full bg-amber-400 transition-transform ${penColor === "#F59E0B" ? "scale-125 ring-2 ring-white" : ""}`}
                title="Màu vàng"
              />
              <button
                onClick={() => setPenColor("#10B981")}
                className={`w-4 h-4 rounded-full bg-emerald-400 transition-transform ${penColor === "#10B981" ? "scale-125 ring-2 ring-white" : ""}`}
                title="Màu xanh lá"
              />
              <button
                onClick={() => setPenColor("#06B6D4")}
                className={`w-4 h-4 rounded-full bg-cyan-400 transition-transform ${penColor === "#06B6D4" ? "scale-125 ring-2 ring-white" : ""}`}
                title="Màu xanh dương"
              />
            </div>
            {/* Clear Button */}
            <button
              onClick={clearCanvas}
              title="Xóa toàn bộ nét vẽ"
              className="p-1 rounded-lg hover:bg-white/10 text-studio-muted hover:text-white flex items-center gap-1 text-[11px]"
            >
              <Eraser className="w-3.5 h-3.5" />
              <span>Xóa</span>
            </button>
          </div>
        )}

        {/* Live Feedback Toast from WebSocket */}
        {activeFeedback && (
          <div className="absolute top-4 left-4 z-20 px-3.5 py-1.5 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2 shadow-lg backdrop-blur-md">
            <Zap className="w-3.5 h-3.5 text-emerald-400" />
            <span>{activeFeedback}</span>
          </div>
        )}

        {/* 1. INTERACTIVE SIMULATION MODE */}
        {activeTab === "simulation" && (
          <div className="flex flex-col gap-6 max-w-4xl mx-auto h-full justify-between">
            {/* Visual Physics Simulation Canvas (SVG) */}
            <div className="relative h-64 sm:h-80 w-full rounded-2xl bg-[#090B12] border border-white/10 p-4 flex flex-col justify-between overflow-hidden shadow-inner">
              <div className="flex items-center justify-between text-xs text-studio-muted">
                <span className="font-mono text-emerald-400">Thí nghiệm: Vật trượt trên mặt phẳng nghiêng</span>
                <span className="font-mono text-cyan-400 font-semibold">
                  Gia tốc a = {acceleration.toFixed(2)} m/s² ({motionState})
                </span>
              </div>

              {/* Graphic Stage */}
              <div className="relative w-full h-44 flex items-center justify-center">
                <svg viewBox="0 0 500 200" className="w-full h-full">
                  <defs>
                    <marker id="arrow-cyan" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                      <path d="M 0 1 L 10 5 L 0 9 z" fill="#06B6D4" />
                    </marker>
                    <marker id="arrow-emerald" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                      <path d="M 0 1 L 10 5 L 0 9 z" fill="#10B981" />
                    </marker>
                    <marker id="arrow-amber" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                      <path d="M 0 1 L 10 5 L 0 9 z" fill="#F59E0B" />
                    </marker>
                    <marker id="arrow-purple" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                      <path d="M 0 1 L 10 5 L 0 9 z" fill="#A855F7" />
                    </marker>
                  </defs>

                  {/* Ground base */}
                  <line x1="40" y1="170" x2="460" y2="170" stroke="#2D334A" strokeWidth="2" strokeDasharray="4 4" />

                  {/* Inclined Plane Wedge */}
                  <polygon
                    points={`${x0},${y0} ${xtop},${ytop} ${xtop},${y0}`}
                    fill="#161926"
                    stroke="#3B4261"
                    strokeWidth="2"
                  />

                  {/* Angle Arc */}
                  <path
                    d={`M ${x0 + 40},${y0} A 40 40 0 0 0 ${x0 + 40 * Math.cos(rad)} ${y0 - 40 * Math.sin(rad)}`}
                    fill="none"
                    stroke="#F59E0B"
                    strokeWidth="1.5"
                  />
                  <text x={x0 + 46} y={y0 - 6} fill="#F59E0B" fontSize="11" fontFamily="JetBrains Mono">
                    α = {angle}°
                  </text>

                  {/* Mass Block positioned exactly on ramp surface */}
                  <g transform={`translate(${xBlock}, ${yBlock}) rotate(${-angle})`}>
                    <rect
                      x="-24"
                      y="-30"
                      width="48"
                      height="30"
                      rx="4"
                      fill="#10B981"
                      fillOpacity="0.85"
                      stroke="#34D399"
                      strokeWidth="2"
                    />
                    <text x="-12" y="-11" fill="#090A0F" fontSize="11" fontWeight="bold">
                      {mass}kg
                    </text>

                    {/* Applied Force Vector Arrow (Up the ramp) */}
                    <line
                      x1="24"
                      y1="-15"
                      x2={24 + Math.min(80, force * 1.2)}
                      y2="-15"
                      stroke="#06B6D4"
                      strokeWidth="2.5"
                      markerEnd="url(#arrow-cyan)"
                    />
                    <text x={28 + Math.min(80, force * 1.2)} y="-18" fill="#06B6D4" fontSize="10" fontFamily="JetBrains Mono">
                      F = {force}N
                    </text>

                    {/* Normal Force N (Perpendicular up) */}
                    <line
                      x1="0"
                      y1="-30"
                      x2="0"
                      y2={-30 - Math.min(45, fNormal * 0.35)}
                      stroke="#10B981"
                      strokeWidth="2"
                      markerEnd="url(#arrow-emerald)"
                    />
                    <text x="4" y={-32 - Math.min(45, fNormal * 0.35)} fill="#10B981" fontSize="9" fontFamily="JetBrains Mono">
                      N
                    </text>

                    {/* Friction Force F_ms (Opposing motion) */}
                    <line
                      x1="-24"
                      y1="-5"
                      x2={-24 - Math.min(50, fFrictionMax * 1.5)}
                      y2="-5"
                      stroke="#A855F7"
                      strokeWidth="2"
                      markerEnd="url(#arrow-purple)"
                    />
                    <text x={-28 - Math.min(50, fFrictionMax * 1.5)} y="-8" fill="#A855F7" fontSize="9" fontFamily="JetBrains Mono">
                      F_ms
                    </text>
                  </g>

                  {/* Gravity Force Vector P = mg (Straight down in world coordinates) */}
                  <line
                    x1={xBlock}
                    y1={yBlock - 15}
                    x2={xBlock}
                    y2={yBlock - 15 + Math.min(55, mass * g * 0.35)}
                    stroke="#F59E0B"
                    strokeWidth="2"
                    markerEnd="url(#arrow-amber)"
                  />
                  <text x={xBlock + 6} y={yBlock + 25} fill="#F59E0B" fontSize="10" fontFamily="JetBrains Mono">
                    P = {(mass * g).toFixed(1)}N
                  </text>
                </svg>
              </div>

              {/* Formula & Live Calculation readout */}
              <div className="flex flex-wrap items-center justify-between text-xs font-mono p-3 rounded-xl bg-[#121522] border border-white/5 gap-2">
                <div className="flex items-center gap-4 text-studio-muted">
                  <span>Trọng lực P = {(mass * g).toFixed(1)} N</span>
                  <span>F_ms_max = {fFrictionMax.toFixed(1)} N</span>
                  <span>Hợp lực F_net = {netForce.toFixed(1)} N</span>
                </div>
                <div className="text-emerald-400 font-semibold">
                  F_net = m · a ➔ a = {acceleration.toFixed(2)} m/s²
                </div>
              </div>
            </div>

            {/* Interactive Control Dials */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Slider 1: Force */}
              <div className="p-4 rounded-xl bg-[#161926] border border-white/10 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="text-studio-muted">Lực kéo (F)</span>
                  <span className="font-mono text-cyan-400 font-semibold">{force} N</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={force}
                  onChange={(e) => setForce(Number(e.target.value))}
                  className="w-full accent-cyan-400 cursor-pointer"
                />
              </div>

              {/* Slider 2: Mass */}
              <div className="p-4 rounded-xl bg-[#161926] border border-white/10 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="text-studio-muted">Khối lượng (m)</span>
                  <span className="font-mono text-emerald-400 font-semibold">{mass} kg</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="20"
                  value={mass}
                  onChange={(e) => setMass(Number(e.target.value))}
                  className="w-full accent-emerald-400 cursor-pointer"
                />
              </div>

              {/* Slider 3: Angle */}
              <div className="p-4 rounded-xl bg-[#161926] border border-white/10 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="text-studio-muted">Góc nghiêng (α)</span>
                  <span className="font-mono text-amber-400 font-semibold">{angle}°</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="55"
                  value={angle}
                  onChange={(e) => setAngle(Number(e.target.value))}
                  className="w-full accent-amber-400 cursor-pointer"
                />
              </div>

              {/* Slider 4: Friction */}
              <div className="p-4 rounded-xl bg-[#161926] border border-white/10 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="text-studio-muted">Hệ số ma sát (μ)</span>
                  <span className="font-mono text-purple-400 font-semibold">{friction}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="0.5"
                  step="0.05"
                  value={friction}
                  onChange={(e) => setFriction(Number(e.target.value))}
                  className="w-full accent-purple-400 cursor-pointer"
                />
              </div>
            </div>
          </div>
        )}

        {/* 2. SLIDE PRESENTER MODE WITH REAL DRAWING OVERLAY */}
        {activeTab === "slides" && (
          <div className="max-w-3xl mx-auto h-full flex flex-col justify-between">
            <div className="relative p-8 rounded-2xl bg-[#161926]/90 border border-white/10 shadow-bezel min-h-[400px] flex flex-col justify-between overflow-hidden">
              {/* Interactive Blackboard Canvas */}
              {canvasDrawingMode && (
                <canvas
                  ref={canvasRef}
                  width={750}
                  height={400}
                  onMouseDown={startDrawing}
                  onMouseMove={draw}
                  onMouseUp={stopDrawing}
                  onMouseLeave={stopDrawing}
                  onTouchStart={startDrawing}
                  onTouchMove={draw}
                  onTouchEnd={stopDrawing}
                  className="absolute inset-0 z-20 w-full h-full cursor-crosshair"
                />
              )}

              <div>
                <div className="flex items-center justify-between mb-4">
                  <span className="text-[11px] font-mono tracking-widest text-emerald-400 uppercase">
                    Chương 1: Động lực học chất điểm
                  </span>
                  <span className="text-xs text-studio-subtle font-mono">
                    Slide {slidePage} / {totalSlides}
                  </span>
                </div>
                <h2 className="text-2xl font-bold text-white mb-4">
                  {selectedSection || "Định luật II Newton & Phương trình cơ bản"}
                </h2>
                <div className="space-y-4 text-studio-text leading-relaxed text-sm">
                  <div className="p-4 rounded-xl bg-[#0F111A] border border-white/5 font-mono text-center text-lg text-emerald-300">
                    \vec&#123;F&#125; = m \cdot \vec&#123;a&#125;
                  </div>
                  <p>
                    Gia tốc của một vật cùng hướng với lực tác dụng lên vật. Độ lớn của gia tốc tỉ lệ thuận
                    với độ lớn của lực tác dụng và tỉ lệ nghịch với khối lượng của vật.
                  </p>
                  <ul className="list-disc pl-5 space-y-2 text-studio-muted">
                    <li>Nếu một vật chịu nhiều lực đồng thời: hợp lực <code className="text-cyan-300">\vec&#123;F_net&#125; = \sum \vec&#123;F_i&#125;</code>.</li>
                    <li>Khối lượng <code className="text-emerald-300">m</code> là đại lượng đặc trưng cho mức quán tính của vật.</li>
                  </ul>
                </div>
              </div>

              {/* Slide Navigation footer */}
              <div className="flex items-center justify-between pt-6 border-t border-white/10 mt-6 relative z-10">
                <button
                  disabled={slidePage <= 1}
                  onClick={() => setSlidePage((p) => Math.max(1, p - 1))}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-white/10 text-xs font-medium text-studio-muted hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="w-4 h-4" />
                  <span>Trang trước</span>
                </button>
                <span className="text-xs text-studio-subtle font-mono">{slidePage} / {totalSlides}</span>
                <button
                  disabled={slidePage >= totalSlides}
                  onClick={() => setSlidePage((p) => Math.min(totalSlides, p + 1))}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-white/10 text-xs font-medium text-studio-muted hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <span>Trang sau</span>
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 3. VIDEO SYNC MODE */}
        {activeTab === "video" && (
          <div className="max-w-3xl mx-auto h-full flex flex-col justify-between">
            <div className="relative aspect-video rounded-2xl bg-[#090B12] border border-white/10 flex flex-col items-center justify-center overflow-hidden shadow-2xl">
              <div
                className="w-16 h-16 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center text-white cursor-pointer hover:scale-105 transition-transform"
                onClick={() => setIsPlaying(!isPlaying)}
              >
                {isPlaying ? <Pause className="w-7 h-7" /> : <Play className="w-7 h-7 ml-1" />}
              </div>
              <p className="mt-4 text-xs font-mono text-studio-subtle">
                Video giảng viên đồng bộ thời gian thực: {formatTime(videoTime)}
              </p>
            </div>

            {/* Video Controls Bar */}
            <div className="mt-4 p-4 rounded-xl bg-[#161926] border border-white/10 flex items-center gap-4">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              </button>
              <span className="text-xs font-mono text-studio-muted min-w-[45px]">{formatTime(videoTime)}</span>
              <input
                type="range"
                min="0"
                max={totalVideoDuration}
                value={videoTime}
                onChange={handleVideoSeek}
                className="flex-1 accent-emerald-400 cursor-pointer"
              />
              <span className="text-xs font-mono text-studio-subtle min-w-[45px]">{formatTime(totalVideoDuration)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
