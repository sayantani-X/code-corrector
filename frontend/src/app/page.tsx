"use client";

import { useState, useRef, useEffect } from "react";

export default function Home() {
  const [task, setTask] = useState("");
  const [bypassPlanner, setBypassPlanner] = useState(false);
  const [useHeavyModel, setUseHeavyModel] = useState(false);
  const [autoApprovePlanner, setAutoApprovePlanner] = useState(false);
  const [autoApproveExecutor, setAutoApproveExecutor] = useState(false);
  
  const [threadId, setThreadId] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [plan, setPlan] = useState<string[]>([]);
  const [files, setFiles] = useState<Record<string, string>>({});
  const [isPaused, setIsPaused] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [activeTab, setActiveTab] = useState<"Logs" | "Plan" | "Files">("Logs");
  
  const logsEndRef = useRef<HTMLDivElement>(null);
  const startTimeRef = useRef<number | null>(null);
  const [copiedFile, setCopiedFile] = useState<string | null>(null);

  useEffect(() => {
    if (activeTab === "Logs") {
      logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, activeTab]);

  const startTask = async () => {
    setLogs(["Initializing task..."]);
    setPlan([]);
    setFiles({});
    setIsPaused(false);
    setIsRunning(true);
    setActiveTab("Logs");
    startTimeRef.current = Date.now();
    
    try {
      const res = await fetch("http://localhost:8000/api/v1/agent/task", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": "default-dev-key-change-in-prod"
        },
        body: JSON.stringify({
          task,
          bypass_planner: bypassPlanner,
          use_heavy_model: useHeavyModel,
          auto_approve_planner: autoApprovePlanner,
          auto_approve_executor: autoApproveExecutor
        })
      });
      
      const data = await res.json();
      setThreadId(data.thread_id);
      connectStream(data.thread_id);
    } catch (e) {
      setLogs(prev => [...prev, `[ERROR] Failed to start task: ${e}`]);
    }
  };

  const connectStream = (id: string) => {
    const eventSource = new EventSource(`http://localhost:8000/api/v1/agent/stream/${id}?api_key=default-dev-key-change-in-prod`);
    
    eventSource.addEventListener("node_update", (e) => {
      const data = JSON.parse(e.data);
      const node = data.node;
      const update = data.update;

      // Update State Tracking
      if (update.plan) setPlan(update.plan);
      if (update.files) setFiles(update.files);

      // Create human-readable log messages
      if (node === "planner") {
        setLogs(prev => [...prev, `[PLANNER] Generated ${update.plan?.length || 0} step plan. Entry point: ${update.entry_point}`]);
      } else if (node === "coder") {
        setLogs(prev => [...prev, `[CODER] Updated files. Working on step ${update.current_step_index + 1}`]);
      } else if (node === "reviewer") {
        if (update.review_comments) {
          setLogs(prev => [...prev, `[REVIEWER] ❌ Lint/Security issues found:\n${update.review_comments}`]);
        } else {
          setLogs(prev => [...prev, `[REVIEWER] ✅ Code passed quality checks.`]);
        }
      } else if (node === "executor") {
        if (update.exit_code !== 0) {
          setLogs(prev => [...prev, `[EXECUTOR] ❌ Execution failed (Exit code: ${update.exit_code}):\n${update.stderr}`]);
        } else {
          setLogs(prev => [...prev, `[EXECUTOR] ✅ Execution succeeded!\n${update.stdout}`]);
        }
      } else if (node === "summarizer") {
        setLogs(prev => [...prev, `[SUMMARIZER] Condensing massive error logs for the Coder...`]);
      } else if (node === "system") {
        const elapsed = startTimeRef.current ? ((Date.now() - startTimeRef.current) / 1000).toFixed(1) : "?";
        setLogs(prev => [...prev, `[SYSTEM] 🟢 ${update.status || update} (Completed in ${elapsed}s)`]);
        setIsRunning(false);
      } else {
        setLogs(prev => [...prev, `[${node}] updated state...`]);
      }
    });

    eventSource.addEventListener("interrupt", (e) => {
      const data = JSON.parse(e.data);
      setLogs(prev => [...prev, `[PAUSED] ⏸️ ${data.interrupt}`]);
      setIsPaused(true);
      eventSource.close();
    });

    eventSource.addEventListener("agent_error", (e) => {
      const data = JSON.parse(e.data);
      setLogs(prev => [...prev, `[ERROR] 🛑 ${data.detail}`]);
      setIsRunning(false);
      eventSource.close();
    });

    eventSource.addEventListener("error", (e) => {
      eventSource.close();
    });
  };

  const resumeTask = async (action: string) => {
    if (!threadId) return;
    setIsPaused(false);
    setLogs(prev => [...prev, `[RESUMING] Action: ${action}...`]);
    
    try {
      await fetch(`http://localhost:8000/api/v1/agent/resume/${threadId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": "default-dev-key-change-in-prod"
        },
        body: JSON.stringify({ action })
      });
      
      connectStream(threadId);
    } catch (e) {
      setLogs(prev => [...prev, `[ERROR] Failed to resume: ${e}`]);
    }
  };

  const copyToClipboard = async (filename: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedFile(filename);
      setTimeout(() => setCopiedFile(null), 2000);
    } catch (err) {
      console.error("Failed to copy text: ", err);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-gray-200 p-8 font-sans">
      <div className="max-w-[1400px] mx-auto flex flex-col md:flex-row gap-8 h-[calc(100vh-4rem)]">
        
        {/* Left Pane: Controls */}
        <div className="w-full md:w-1/3 flex flex-col gap-6 bg-[#111] p-6 rounded-2xl border border-gray-800 shadow-2xl">
          <h1 className="text-3xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
            Code Corrector
          </h1>
          
          <div className="flex flex-col gap-3">
            <label className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Settings</label>
            
            <label className="flex items-center gap-3 cursor-pointer group">
              <input 
                type="checkbox" 
                checked={bypassPlanner} 
                onChange={(e) => setBypassPlanner(e.target.checked)}
                className="w-5 h-5 rounded border-gray-600 text-blue-500 focus:ring-blue-500 bg-gray-800"
              />
              <span className="text-gray-300 group-hover:text-white transition-colors">Skip Planner (Use for easy tasks)</span>
            </label>
            
            <label className="flex items-center gap-3 cursor-pointer group">
              <input 
                type="checkbox" 
                checked={useHeavyModel} 
                onChange={(e) => setUseHeavyModel(e.target.checked)}
                className="w-5 h-5 rounded border-gray-600 text-purple-500 focus:ring-purple-500 bg-gray-800"
              />
              <span className="text-gray-300 group-hover:text-white transition-colors">Use Heavy Model (Gemini Pro)</span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer group">
              <input 
                type="checkbox" 
                checked={autoApprovePlanner} 
                onChange={(e) => setAutoApprovePlanner(e.target.checked)}
                className="w-5 h-5 rounded border-gray-600 text-green-500 focus:ring-green-500 bg-gray-800"
              />
              <span className="text-gray-300 group-hover:text-white transition-colors">Auto-Approve Planner</span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer group">
              <input 
                type="checkbox" 
                checked={autoApproveExecutor} 
                onChange={(e) => setAutoApproveExecutor(e.target.checked)}
                className="w-5 h-5 rounded border-gray-600 text-green-500 focus:ring-green-500 bg-gray-800"
              />
              <span className="text-gray-300 group-hover:text-white transition-colors">Auto-Approve Executor</span>
            </label>
          </div>

          <div className="flex flex-col gap-2 flex-grow">
            <label className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Task Description</label>
            <textarea 
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="E.g. Create a Python script that scrapes HackerNews..."
              className="w-full flex-grow p-4 bg-gray-900 border border-gray-700 rounded-xl focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none text-gray-200"
            />
          </div>

          <button 
            onClick={startTask}
            disabled={!task.trim() || isRunning}
            className="w-full py-4 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:opacity-50 text-white font-bold rounded-xl shadow-lg transition-all transform active:scale-95 text-lg"
          >
            {isRunning ? "Agent Running..." : "Start Agent Run"}
          </button>
        </div>

        {/* Right Pane: Output & Terminal */}
        <div className="w-full md:w-2/3 flex flex-col bg-[#111] rounded-2xl border border-gray-800 shadow-2xl overflow-hidden relative">
          
          <div className="bg-[#1A1A1A] px-6 py-4 border-b border-gray-800 flex justify-between items-center">
            <div className="flex gap-4">
              <button 
                onClick={() => setActiveTab("Logs")} 
                className={`font-semibold transition-colors ${activeTab === "Logs" ? "text-blue-400" : "text-gray-500 hover:text-gray-300"}`}
              >
                Terminal Logs
              </button>
              <button 
                onClick={() => setActiveTab("Plan")} 
                className={`font-semibold transition-colors ${activeTab === "Plan" ? "text-blue-400" : "text-gray-500 hover:text-gray-300"}`}
              >
                Plan ({plan.length})
              </button>
              <button 
                onClick={() => setActiveTab("Files")} 
                className={`font-semibold transition-colors ${activeTab === "Files" ? "text-blue-400" : "text-gray-500 hover:text-gray-300"}`}
              >
                Files ({Object.keys(files).length})
              </button>
            </div>
            {isPaused && (
              <span className="px-3 py-1 bg-yellow-500/20 text-yellow-400 text-xs font-bold rounded-full animate-pulse">
                ACTION REQUIRED
              </span>
            )}
          </div>

          <div className="p-6 overflow-y-auto flex-grow font-mono text-sm bg-gray-950">
            {activeTab === "Logs" && (
              <div className="flex flex-col gap-3">
                {logs.length === 0 ? (
                  <div className="text-gray-600 italic text-center mt-20">No output yet. Enter a task to begin.</div>
                ) : (
                  logs.map((log, idx) => (
                    <div key={idx} className={`whitespace-pre-wrap ${log.includes("[ERROR]") || log.includes("❌") ? "text-red-400" : log.includes("[PAUSED]") ? "text-yellow-400" : log.includes("✅") || log.includes("🟢") ? "text-green-400" : "text-blue-300"}`}>
                      {log}
                    </div>
                  ))
                )}
                <div ref={logsEndRef} />
              </div>
            )}

            {activeTab === "Plan" && (
              <div className="flex flex-col gap-4 text-gray-300">
                {plan.length === 0 ? (
                  <div className="text-gray-600 italic text-center mt-20">No plan generated yet.</div>
                ) : (
                  <ul className="list-decimal list-inside space-y-2">
                    {plan.map((step, idx) => (
                      <li key={idx} className="p-3 bg-gray-900 rounded-lg border border-gray-800">{step}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {activeTab === "Files" && (
              <div className="flex flex-col gap-6">
                {Object.keys(files).length === 0 ? (
                  <div className="text-gray-600 italic text-center mt-20">No files modified yet.</div>
                ) : (
                  Object.entries(files).map(([filename, content]) => (
                    <div key={filename} className="flex flex-col rounded-lg overflow-hidden border border-gray-800">
                      <div className="bg-gray-800 px-4 py-2 text-gray-300 font-bold border-b border-gray-700 flex justify-between items-center">
                        <span>{filename}</span>
                        <button 
                          onClick={() => copyToClipboard(filename, content)}
                          className="text-xs px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-gray-200 transition-colors"
                        >
                          {copiedFile === filename ? "Copied!" : "Copy Code"}
                        </button>
                      </div>
                      <pre className="p-4 bg-gray-900 text-blue-300 overflow-x-auto whitespace-pre-wrap">
                        {content}
                      </pre>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* HITL Action Bar (Glassmorphism overlay) */}
          {isPaused && (
            <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 flex gap-4 p-4 bg-gray-900/80 backdrop-blur-md rounded-2xl border border-gray-700 shadow-2xl">
              <button 
                onClick={() => resumeTask("approve")}
                className="px-6 py-2 bg-green-600 hover:bg-green-500 text-white font-bold rounded-lg transition-colors shadow-lg"
              >
                Approve & Continue
              </button>
              <button 
                onClick={() => resumeTask("reject")}
                className="px-6 py-2 bg-red-600 hover:bg-red-500 text-white font-bold rounded-lg transition-colors shadow-lg"
              >
                Reject / Stop
              </button>
            </div>
          )}
          
        </div>
      </div>
    </div>
  );
}
