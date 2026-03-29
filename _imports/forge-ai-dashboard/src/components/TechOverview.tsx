import React from 'react';
import { Layers, Code, Bug, Search, Calendar, Eye, Database, Cpu, Zap, Globe } from 'lucide-react';
import { cn } from '@/src/lib/utils';

const TechLogo = ({ icon: Icon, name }: { icon: any, name: string }) => (
  <div className="flex items-center gap-3 grayscale opacity-60 hover:grayscale-0 hover:opacity-100 transition-all cursor-pointer">
    <Icon size={24} className="text-slate-900" />
    <span className="text-xl font-bold text-slate-900 tracking-tight">{name}</span>
  </div>
);

const AgentNode = ({ icon: Icon, label, description, className }: { icon: any, label: string, description: string, className?: string }) => (
  <div className={cn(
    "bg-white p-4 md:p-6 rounded-3xl border border-slate-100 shadow-sm w-40 md:w-48 relative z-10",
    className
  )}>
    <div className="w-8 h-8 md:w-10 md:h-10 rounded-xl bg-slate-50 flex items-center justify-center text-slate-600 mb-4">
      <Icon size={16} />
    </div>
    <h4 className="font-bold text-slate-900 mb-1 text-sm md:text-base">{label}</h4>
    <p className="text-[9px] md:text-[10px] text-slate-400 leading-relaxed">{description}</p>
  </div>
);

export const TechOverview = () => {
  return (
    <div className="min-h-screen bg-white py-12 md:py-24 px-4 md:px-8 transition-colors duration-300">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16 md:mb-24">
          <h2 className="text-2xl md:text-3xl font-bold text-slate-900 mb-4">Autonomous Orchestration</h2>
          <p className="text-slate-400 max-w-md mx-auto text-sm leading-relaxed">
            The most AI deviling to esme conterrrate and contains the commomdes a plamining agents.
          </p>
        </div>

        {/* Orchestration Diagram - Responsive */}
        <div className="relative h-[500px] md:h-[600px] flex items-center justify-center mb-24 md:mb-32 scale-[0.85] sm:scale-100">
          {/* Central Node */}
          <div className="bg-white p-6 md:p-8 rounded-[40px] border border-slate-100 shadow-xl w-56 md:w-64 text-center relative z-20">
            <div className="w-12 h-12 rounded-2xl bg-indigo-50 flex items-center justify-center text-indigo-600 mx-auto mb-4">
              <Layers size={24} />
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-1">Orchestrator Agent</h3>
            <p className="text-xs text-slate-400 font-bold uppercase tracking-widest">(Groq)</p>
          </div>

          {/* Connection Lines (Simplified SVG) */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-30" style={{ zIndex: 5 }}>
            <line x1="50%" y1="50%" x2="20%" y2="20%" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" className="text-slate-300" />
            <line x1="50%" y1="50%" x2="20%" y2="50%" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" className="text-slate-300" />
            <line x1="50%" y1="50%" x2="20%" y2="80%" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" className="text-slate-300" />
            <line x1="50%" y1="50%" x2="80%" y2="25%" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" className="text-slate-300" />
            <line x1="50%" y1="50%" x2="80%" y2="75%" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" className="text-slate-300" />
            <line x1="50%" y1="50%" x2="50%" y2="85%" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" className="text-slate-300" />
            
            {/* Dots on lines */}
            <circle cx="35%" cy="35%" r="3" fill="#818cf8" />
            <circle cx="35%" cy="50%" r="3" fill="#818cf8" />
            <circle cx="35%" cy="65%" r="3" fill="#818cf8" />
            <circle cx="65%" cy="37%" r="3" fill="#818cf8" />
            <circle cx="65%" cy="63%" r="3" fill="#818cf8" />
            <circle cx="50%" cy="67%" r="3" fill="#818cf8" />
          </svg>

          {/* Surrounding Nodes */}
          <div className="absolute top-0 left-0">
            <AgentNode icon={Code} label="Code" description="Cermss tha ksst agent to evsiuate web softvers." />
          </div>
          <div className="absolute top-1/2 left-0 -translate-y-1/2">
            <AgentNode icon={Bug} label="Debug" description="Prevet the agent of ehug and nogenesestnnnuotem." />
          </div>
          <div className="absolute bottom-0 left-0">
            <AgentNode icon={Search} label="Research" description="Rexearch agent to data analyss aocoomnrasses." />
          </div>
          <div className="absolute top-10 right-0">
            <AgentNode icon={Calendar} label="Planner" description="Flaver's cods wotais and need breadsaciility." />
          </div>
          <div className="absolute bottom-10 right-0">
            <AgentNode icon={Eye} label="Reviewer" description="Reviewn ooso:08 coren and outfAAR4066R 506N32." />
          </div>
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2">
            <AgentNode icon={Calendar} label="Planner" description="Planoeo ageotnents and nonaretisban pnocesns." />
          </div>
        </div>

        {/* Tech Stack */}
        <div className="text-center">
          <h3 className="text-2xl font-bold text-slate-900 mb-4">Tech Stack</h3>
          <p className="text-slate-400 text-sm mb-12">FastAPI, supabases, ressanln.qieq, NVIDIA NIM and taympohws on tech stack.</p>
          
          <div className="flex flex-wrap items-center justify-center gap-8 md:gap-16 mb-12">
            <TechLogo icon={Zap} name="FastAPI" />
            <TechLogo icon={Database} name="supabase" />
            <TechLogo icon={Cpu} name="groq" />
            <TechLogo icon={Globe} name="NVIDIA NIM" />
          </div>

          <div className="inline-block px-6 py-2 bg-slate-50 rounded-full text-sm font-bold text-slate-900 border border-slate-100">
            Total Monthly Cost: $0
          </div>
        </div>
      </div>

      <footer className="max-w-5xl mx-auto mt-32 pt-8 border-t border-slate-100 flex flex-col md:flex-row items-center justify-between gap-6 text-[11px] font-bold uppercase tracking-widest text-slate-400 text-center md:text-left">
        <div className="flex gap-6">
          <a href="#" className="hover:text-slate-900 transition-colors">Forge</a>
          <a href="#" className="hover:text-slate-900 transition-colors">Links</a>
          <a href="#" className="hover:text-slate-900 transition-colors">Pricing</a>
          <a href="#" className="hover:text-slate-900 transition-colors">Community</a>
        </div>
        <p>© COPYRIGHT WMNSTTERRTLOK</p>
      </footer>
    </div>
  );
};
