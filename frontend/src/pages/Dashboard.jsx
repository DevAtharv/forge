import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { 
  Terminal, Search, Bell, Settings, Layers, Zap, FolderOpen, 
  Send, Activity, Database, CheckCircle2, CircleDashed, User, ExternalLink
} from "lucide-react";
import { useAuth } from "../AuthContext";
import { fetchAuthedJson, fetchJson } from "../api";

const PROMPT_PRESETS = [
  {
    label: "SaaS Landing",
    value: "Build a conversion-focused SaaS landing page with hero, value props, pricing cards, FAQ, and CTA.",
  },
  {
    label: "Creator Portfolio",
    value: "Create a bold portfolio for a creator with case studies, testimonials, and contact section.",
  },
  {
    label: "Simple Tool",
    value: "Build a simple single-page tool UI with clear input, output card, and friendly onboarding copy.",
  },
];

const THEME_PRESETS = [
  {
    label: "Cyber Mint",
    value:
      "Use Space Grotesk + Manrope, mint and steel accents, frosted panels, and subtle staggered reveal animations.",
  },
  {
    label: "Editorial Sand",
    value:
      "Use instrument-serif inspired feel with warm sand palette, bold headings, generous whitespace, and card reveal motion.",
  },
  {
    label: "Studio Neon",
    value:
      "Use high-contrast neon highlights, layered gradients, dynamic section transitions, and a modern product feel.",
  },
];

const MISSION_STEPS = [
  { key: "planning", label: "Researching & planning" },
  { key: "building", label: "Building project" },
  { key: "previewing", label: "Preparing sandbox link" },
  { key: "deploying", label: "Finalizing deployment" },
  { key: "completed", label: "Done" },
];

function getStageState(status, stepKey) {
  const order = ["queued", "planning", "building", "previewing", "deploying", "completed"];
  const stepOrder = {
    planning: 1,
    building: 2,
    previewing: 3,
    deploying: 4,
    completed: 5,
  };
  const missionIndex = Math.max(order.indexOf(status), 0);
  const stepIndex = stepOrder[stepKey];
  if (missionIndex > stepIndex) return "done";
  if (missionIndex === stepIndex) return "active";
  if (status === "failed" && stepKey === "completed") return "failed";
  return "pending";
}

export default function Dashboard() {
  const { session, user, signOut } = useAuth();
  const navigate = useNavigate();

  const [prompt, setPrompt] = useState("");
  const [selectedPreset, setSelectedPreset] = useState(PROMPT_PRESETS[0].label);
  const [selectedTheme, setSelectedTheme] = useState(THEME_PRESETS[0].label);
  const [feedback, setFeedback] = useState("Ready for input.");
  const [isRunning, setIsRunning] = useState(false);
  const [terminalOutput, setTerminalOutput] = useState([]);
  const [activeTab, setActiveTab] = useState("overview");
  const [missionStatus, setMissionStatus] = useState("queued");
  const [livePreviewUrl, setLivePreviewUrl] = useState("");
  const [currentMissionId, setCurrentMissionId] = useState("");
  const [currentProjectId, setCurrentProjectId] = useState("");

  useEffect(() => {
    if (!session) {
      navigate("/auth");
    }
  }, [session, navigate]);

  const handleSignOut = () => {
    signOut();
    navigate("/");
  };

  const runMission = async () => {
    if (!prompt.trim()) {
      setFeedback("Add a mission prompt first.");
      return;
    }
    
    const selectedThemePrompt = THEME_PRESETS.find((item) => item.label === selectedTheme)?.value || "";
    const composedPrompt = `${prompt.trim()}\n\nVisual direction:\n${selectedThemePrompt}\n\nOutput format: keep scaffold-first Next.js + Tailwind and provide preview-ready build.`;

    setIsRunning(true);
    setLivePreviewUrl("");
    setMissionStatus("planning");
    setCurrentMissionId("");
    setCurrentProjectId("");
    setFeedback("Running protected mission and tracking live status...");
    setTerminalOutput(prev => [...prev, `[MISSION] Initiating: ${prompt}`, `[THEME] ${selectedTheme}`]);

    try {
      const payload = await fetchAuthedJson("/api/app/run", session, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: composedPrompt }),
      });
      
      setFeedback(payload.message || "Mission queued.");
      if (!payload.mission || !payload.mission.id) {
        const text = payload.direct_response || "Completed without background build mission.";
        setTerminalOutput(prev => [...prev, `[DIRECT] ${text}`]);
        setFeedback(payload.message || "Answered directly.");
        setMissionStatus("completed");
        setIsRunning(false);
        return;
      }

      setTerminalOutput(prev => [...prev, `[API] Mission ID received: ${payload.mission.id}`]);

      let missionId = payload.mission.id;
      setCurrentMissionId(missionId);
      let missionCompleted = false;
      let lastStatus = payload.mission.status;
      let lastProjectId = payload.mission.project_id || "";
      let lastPreviewUrl = payload.mission.preview_url || "";
      setMissionStatus(lastStatus || "queued");

      // Real-time API Polling
      while (!missionCompleted) {
        await new Promise(r => setTimeout(r, 700));
        try {
          const pollRes = await fetchAuthedJson(`/api/app/missions/${missionId}`, session);
          const currentStatus = pollRes.mission.status;
          const polledProjectId = pollRes.mission.project_id || "";
          const missionPreview = pollRes.mission.preview_url || "";
          
          if (currentStatus !== lastStatus) {
            setTerminalOutput(prev => [...prev, `[UPDATE] Status transitioned to: ${currentStatus.toUpperCase()} (done)`]);
            lastStatus = currentStatus;
            setMissionStatus(currentStatus);
          }

          if (polledProjectId && polledProjectId !== lastProjectId) {
            lastProjectId = polledProjectId;
            setCurrentProjectId(polledProjectId);
            setTerminalOutput(prev => [...prev, `[PROJECT] Attached project: ${polledProjectId}`]);
          }

          if (missionPreview && missionPreview !== lastPreviewUrl) {
            lastPreviewUrl = missionPreview;
            setLivePreviewUrl(missionPreview);
            setTerminalOutput(prev => [...prev, `[SANDBOX] Live preview ready: ${missionPreview}`]);
          }

          if (currentStatus === "previewing" && polledProjectId) {
            try {
              const previewRes = await fetchAuthedJson(`/api/app/projects/${polledProjectId}/preview`, session, {
                method: "POST",
              });
              const previewUrl = previewRes?.project?.preview_url || "";
              if (previewUrl && previewUrl !== lastPreviewUrl) {
                lastPreviewUrl = previewUrl;
                setLivePreviewUrl(previewUrl);
                setTerminalOutput(prev => [...prev, `[SANDBOX] Instant preview link issued: ${previewUrl}`]);
              }
            } catch (_err) {
              // Keep polling even if preview refresh endpoint is not ready yet.
            }
          }

          if (currentStatus === "completed" || currentStatus === "failed") {
            setFeedback(`Mission ${currentStatus}.`);
            setMissionStatus(currentStatus);
            setTerminalOutput(prev => [
              ...prev, 
              currentStatus === "failed" 
                ? `[FAILED] ${pollRes.mission.error || "Unknown error."}`
                : `[SUCCESS] Mission executed gracefully.`,
              `[SUMMARY] ${pollRes.mission.result_summary || "Done."}`
            ]);
            missionCompleted = true;
          } else {
             setFeedback(`Mission status: ${currentStatus}...`);
          }
        } catch (e) {
          console.error("Polling error:", e);
        }
      }
      setIsRunning(false);
      
    } catch (error) {
      setFeedback(error.message);
      setTerminalOutput(prev => [...prev, `[ERROR] ${error.message}`]);
      setIsRunning(false);
    }
  };

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-300 font-sans overflow-hidden selection:bg-teal-500/30">
      {/* Sidebar Navigation */}
      <nav className="w-64 border-r border-zinc-800/50 bg-zinc-900/30 flex flex-col pt-6 pb-4 shrink-0">
        <div className="px-6 mb-8 flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-white flex items-center justify-center">
            <Layers className="w-5 h-5 text-zinc-950" />
          </div>
          <span className="font-bold text-lg text-white tracking-tight">Forge</span>
        </div>

        <div className="flex-1 px-4 space-y-1">
          <div className="px-3 py-2 text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">Workspace</div>
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg bg-zinc-800/50 text-white font-medium">
            <Activity className="w-4 h-4" /> Overview
          </button>
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800/30 transition-colors">
            <Terminal className="w-4 h-4" /> Missions
          </button>
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800/30 transition-colors">
            <FolderOpen className="w-4 h-4" /> Artifacts
          </button>
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800/30 transition-colors">
            <Send className="w-4 h-4" /> Delivery
          </button>
        </div>

        <div className="px-4 pt-4 border-t border-zinc-800/50">
          <button onClick={handleSignOut} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800/30 transition-colors">
            <LogOutIcon className="w-4 h-4" /> Sign out
          </button>
        </div>
      </nav>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <header className="h-16 border-b border-zinc-800/50 bg-zinc-900/30 flex items-center justify-between px-6 shrink-0 z-10 backdrop-blur-md">
          <div className="flex-1 max-w-xl">
            <div className="relative group">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 group-focus-within:text-teal-500 transition-colors" />
              <input 
                type="text" 
                placeholder="Search missions, artifacts, and runs..."
                className="w-full bg-zinc-950 border border-zinc-800/50 rounded-lg pl-10 pr-4 py-2 text-sm focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/50 transition-all placeholder:text-zinc-600"
              />
            </div>
          </div>
          <div className="flex items-center gap-4 ml-4">
             <button className="relative w-8 h-8 flex items-center justify-center rounded-lg hover:bg-zinc-800/50 text-zinc-400 hover:text-white transition-colors">
               <Bell className="w-4 h-4" />
               <span className="absolute top-2 right-2 w-1.5 h-1.5 bg-teal-500 rounded-full"></span>
             </button>
             <button className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-zinc-800/50 text-zinc-400 hover:text-white transition-colors">
               <Settings className="w-4 h-4" />
             </button>
             <div className="h-4 w-px bg-zinc-800"></div>
             <button className="flex items-center gap-2 pl-2">
               <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-teal-500 to-emerald-400 flex items-center justify-center text-zinc-950 font-bold text-sm">
                 {user?.email?.[0].toUpperCase() || "U"}
               </div>
             </button>
          </div>
        </header>

        {/* Scrollable Dashboard View */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-6xl mx-auto space-y-8"
          >
            {/* Page Title & Tabs */}
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold text-white tracking-tight mb-1">Mainframe Dashboard</h1>
                <p className="text-zinc-500 text-sm">Monitor, command, and deploy AI automated tasks.</p>
              </div>
              <div className="flex bg-zinc-900/50 border border-zinc-800/50 rounded-lg p-1">
                {['overview', 'projects', 'deployments'].map((tab) => (
                  <button 
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-4 py-1.5 text-sm font-medium rounded-md capitalize transition-all ${
                      activeTab === tab 
                        ? "bg-zinc-800 text-white shadow-sm" 
                        : "text-zinc-400 hover:text-white hover:bg-zinc-800/30"
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>

            {/* Mockup Presentation Section (erikx 'Section with Mockup' aesthetic) */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* Central Mission Control */}
              <div className="lg:col-span-2 space-y-6">
                
                {/* Mission Input Panel */}
                <div className="rounded-2xl border border-zinc-800/50 bg-zinc-900/20 backdrop-blur-sm overflow-hidden flex flex-col relative group">
                  <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-teal-500/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
                  
                  <div className="px-5 py-4 border-b border-zinc-800/50 flex items-center justify-between bg-zinc-900/40">
                    <div className="flex items-center gap-2">
                      <Zap className="w-4 h-4 text-teal-400" />
                      <span className="font-semibold text-white text-sm">Mission Control Panel</span>
                    </div>
                    <span className="text-xs font-medium px-2 py-1 rounded bg-teal-500/10 text-teal-400 border border-teal-500/20">
                      Ready for Deployment
                    </span>
                  </div>
                  
                  <div className="p-5 flex flex-col gap-4">
                    <textarea 
                      placeholder="Describe the mission or automated task you want to execute..."
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      className="w-full h-32 bg-zinc-950/50 border border-zinc-800/80 rounded-xl p-4 text-sm text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/50 resize-none transition-all"
                    />
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <label className="text-xs text-zinc-500 flex flex-col gap-1">
                        Prompt template
                        <select
                          value={selectedPreset}
                          onChange={(event) => {
                            const next = event.target.value;
                            setSelectedPreset(next);
                            const preset = PROMPT_PRESETS.find((item) => item.label === next);
                            if (preset) setPrompt(preset.value);
                          }}
                          className="bg-zinc-950/60 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-300"
                        >
                          {PROMPT_PRESETS.map((item) => (
                            <option key={item.label} value={item.label}>
                              {item.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="text-xs text-zinc-500 flex flex-col gap-1">
                        Theme style
                        <select
                          value={selectedTheme}
                          onChange={(event) => setSelectedTheme(event.target.value)}
                          className="bg-zinc-950/60 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-300"
                        >
                          {THEME_PRESETS.map((item) => (
                            <option key={item.label} value={item.label}>
                              {item.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="text-xs text-zinc-500 font-mono flex items-center gap-2">
                        {isRunning ? <CircleDashed className="w-3.5 h-3.5 animate-spin text-teal-500" /> : <div className="w-2 h-2 rounded-full bg-zinc-700"></div>}
                        {feedback}
                      </div>

                      <div className="flex items-center gap-3">
                        <button 
                          onClick={() => setPrompt("Should I use Redis or Supabase for storing sessions?")}
                          className="text-xs font-medium text-zinc-400 hover:text-white transition-colors"
                        >
                          Load Template
                        </button>
                        <button 
                          onClick={runMission}
                          disabled={isRunning}
                          className="px-5 py-2 rounded-full bg-white text-zinc-950 text-sm font-semibold hover:bg-zinc-200 transition-colors disabled:opacity-50 flex items-center gap-2"
                        >
                          {isRunning ? "Executing..." : "Execute"} <Send className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Mission Stage Tracker */}
                <div className="rounded-2xl border border-zinc-800/50 bg-zinc-900/30 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-white text-sm">Build Status</h3>
                    <span className="text-xs text-zinc-400 uppercase tracking-wider">{missionStatus}</span>
                  </div>
                  <div className="space-y-3">
                    {MISSION_STEPS.map((step) => {
                      const stageState = getStageState(missionStatus, step.key);
                      const icon =
                        stageState === "done" ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        ) : stageState === "active" ? (
                          <CircleDashed className="w-4 h-4 text-teal-400 animate-spin" />
                        ) : stageState === "failed" ? (
                          <span className="w-4 h-4 rounded-full bg-rose-500/70" />
                        ) : (
                          <span className="w-4 h-4 rounded-full bg-zinc-700" />
                        );

                      const suffix =
                        stageState === "done" ? "done" : stageState === "active" ? "in progress" : "pending";

                      return (
                        <div key={step.key} className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2 text-zinc-300">
                            {icon}
                            <span>{step.label}</span>
                          </div>
                          <span className="text-zinc-500">{suffix}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Secure Terminal Output */}
                <div className="rounded-2xl border border-zinc-800/50 bg-black overflow-hidden flex flex-col font-mono text-xs">
                  <div className="px-4 py-2 border-b border-zinc-900 bg-zinc-950 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-1.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-rose-500/20 border border-rose-500/50"></div>
                      <div className="w-2.5 h-2.5 rounded-full bg-amber-500/20 border border-amber-500/50"></div>
                      <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/20 border border-emerald-500/50"></div>
                      <span className="ml-2 text-zinc-600">secure-execution-context</span>
                    </div>
                    <span className="text-zinc-700">{terminalOutput.length} output logs</span>
                  </div>
                  <div className="p-4 h-[250px] overflow-y-auto w-full text-zinc-400 space-y-1.5 selection:bg-teal-500/30">
                    <div className="text-teal-600">admin@forge-mainframe ~ % _</div>
                    {terminalOutput.length === 0 ? (
                      <div className="text-zinc-600 italic">Run a mission to view execution outputs...</div>
                    ) : (
                      terminalOutput.map((log, i) => (
                        <div key={i} className="animate-in fade-in slide-in-from-bottom-1">{log}</div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* Right Sidebar Elements */}
              <div className="space-y-6">

                {/* Telegram Link Widget */}
                <div className="rounded-2xl border border-zinc-800/50 bg-zinc-900/20 p-5 relative overflow-hidden group">
                  <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#0088cc]/50 to-transparent"></div>
                  <h3 className="font-semibold text-white mb-2 text-sm flex items-center justify-between">
                    Telegram Integration
                    <svg className="w-4 h-4 text-[#0088cc]" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.14-.26.26-.532.26l.215-3.05 5.56-5.023c.242-.215-.054-.334-.373-.122l-6.87 4.326-2.96-.924c-.64-.202-.656-.64.136-.95l11.58-4.46c.535-.196 1.002.128.832.941z"/>
                    </svg>
                  </h3>
                  <p className="text-xs text-zinc-400 mb-4 leading-relaxed">
                    Link your Telegram to get real-time mission execution logs and approval requests globally.
                  </p>
                  
                  <button 
                    onClick={async () => {
                      try {
                        const payload = await fetchAuthedJson("/api/app/link/telegram", session, {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ refresh: true }),
                        });
                        alert(`Message @${payload.bot_username} on Telegram with code:\n/link ${payload.code}`);
                      } catch (err) {
                        alert(`Failed to link: ${err.message}`);
                      }
                    }}
                    className="w-full px-4 py-2 bg-[#0088cc]/10 hover:bg-[#0088cc]/20 text-[#0088cc] border border-[#0088cc]/20 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-2"
                  >
                    Generate Link Code
                  </button>
                </div>

                {/* Sandbox Link */}
                <div className="rounded-2xl border border-zinc-800/50 bg-zinc-900/20 p-5">
                  <h3 className="font-semibold text-white mb-2 text-sm">Sandbox Preview</h3>
                  {livePreviewUrl ? (
                    <>
                      <p className="text-xs text-zinc-400 mb-4">Live link is ready while the build finalizes.</p>
                      <a
                        href={livePreviewUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="w-full px-4 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/20 rounded-lg text-xs font-semibold transition-colors inline-flex items-center justify-center gap-2"
                      >
                        Open Live Sandbox <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </>
                  ) : (
                    <p className="text-xs text-zinc-500">
                      Preview link will appear here instantly when the mission reaches sandbox stage.
                    </p>
                  )}
                  {currentMissionId && <p className="text-[10px] text-zinc-600 mt-3">Mission: {currentMissionId}</p>}
                </div>

                <div className="rounded-2xl border border-zinc-800/50 bg-zinc-900/20 p-5">
                  <h3 className="font-semibold text-white mb-4 text-sm flex items-center justify-between">
                    Active Pipeline <Activity className="w-4 h-4 text-teal-500" />
                  </h3>
                  <div className="space-y-3">
                    {['Repository Access', 'Container Build', 'Telegram Dispatch'].map((step, i) => (
                      <div key={i} className="flex flex-col gap-1">
                        <div className="flex justify-between text-xs text-zinc-400">
                          <span>{step}</span>
                          <span className="text-white">Active</span>
                        </div>
                        <div className="h-1 w-full bg-zinc-800 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-teal-500 to-emerald-400 w-full rounded-full animate-pulse"></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl border border-zinc-800/50 bg-zinc-900/20 p-5">
                  <h3 className="font-semibold text-white mb-4 text-sm flex items-center justify-between">
                    Resources <Database className="w-4 h-4 text-teal-500" />
                  </h3>
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-full border-4 border-zinc-800 border-t-teal-500 flex items-center justify-center shrink-0">
                      <span className="text-xs font-bold text-white">42%</span>
                    </div>
                    <div className="space-y-1 w-full">
                       <div className="flex justify-between text-xs"><span className="text-zinc-500">Compute Cache</span><span className="text-white">Low</span></div>
                       <div className="flex justify-between text-xs"><span className="text-zinc-500">API Throttling</span><span className="text-white">Stable</span></div>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </motion.div>
        </main>
      </div>
    </div>
  );
}

// Simple LogOut icon component for the sidebar
function LogOutIcon(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" x2="9" y1="12" y2="12" />
    </svg>
  )
}
