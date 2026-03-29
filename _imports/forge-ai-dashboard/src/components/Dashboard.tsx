import React, { useState } from 'react';
import { 
  LayoutGrid, 
  Users, 
  Terminal, 
  Settings, 
  FileText, 
  LifeBuoy, 
  Bell, 
  Search,
  ExternalLink,
  Code,
  Bug,
  Search as SearchIcon,
  Calendar,
  Eye,
  Plus,
  CreditCard,
  Wallet
} from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  ResponsiveContainer, 
  Cell 
} from 'recharts';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';

const pipelineData = [
  { value: 40 }, { value: 60 }, { value: 75 }, { value: 90 }, 
  { value: 100 }, { value: 85 }, { value: 65 }, { value: 50 }, 
  { value: 45 }, { value: 70 }, { value: 80 }, { value: 60 }
];

const SidebarItem = ({ icon: Icon, label, active = false, onClick }: { icon: any, label: string, active?: boolean, onClick?: () => void }) => (
  <button 
    onClick={onClick}
    className={cn(
      "flex items-center gap-3 px-4 py-2.5 w-full rounded-xl transition-all duration-200 group",
      active 
        ? "bg-white shadow-sm text-slate-900 font-medium" 
        : "text-slate-500 hover:text-slate-900 hover:bg-slate-100/50"
    )}
  >
    <Icon size={18} className={cn(active ? "text-forge-purple" : "text-slate-400 group-hover:text-slate-600")} />
    <span className="text-[14px]">{label}</span>
  </button>
);

const StatCard = ({ label, value }: { label: string, value: string }) => (
  <div className="flex flex-col gap-1">
    <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">{label}</span>
    <span className="text-xl md:text-2xl font-bold text-slate-900 tracking-tight">{value}</span>
  </div>
);

const ActivityItem = ({ title, id, time, icon: Icon = CircleIcon }: { title: string, id: string, time: string, icon?: any }) => (
  <div className="flex items-center justify-between py-4 border-b border-slate-50 last:border-0 group cursor-pointer">
    <div className="flex items-start gap-3">
      <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-slate-300 group-hover:bg-forge-purple transition-colors" />
      <div>
        <h4 className="text-[14px] font-medium text-slate-800">{title}</h4>
        <p className="text-[11px] text-slate-400 uppercase tracking-wide mt-0.5">{id} • {time}</p>
      </div>
    </div>
    <ExternalLink size={16} className="text-slate-300 group-hover:text-slate-500 transition-colors" />
  </div>
);

const CircleIcon = () => <div className="w-1.5 h-1.5 rounded-full bg-slate-300" />;

const AgentStatus = ({ icon: Icon, name, status }: { icon: any, name: string, status: 'ACTIVE' | 'IDLE' }) => (
  <div className="flex items-center justify-between p-3 rounded-xl border border-slate-100 bg-white/50 hover:bg-white hover:shadow-sm transition-all">
    <div className="flex items-center gap-3">
      <div className="p-2 rounded-lg bg-slate-50 text-slate-600">
        <Icon size={16} />
      </div>
      <span className="text-[14px] font-medium text-slate-700">{name}</span>
    </div>
    <div className={cn(
      "flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider uppercase",
      status === 'ACTIVE' ? "bg-green-50 text-green-600" : "bg-blue-50 text-blue-600"
    )}>
      {status}
      <div className={cn("w-1 h-1 rounded-full", status === 'ACTIVE' ? "bg-green-500" : "bg-blue-500")} />
    </div>
  </div>
);

export const Dashboard = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-[#F8F9FA] transition-colors duration-300">
      {/* Sidebar - Mobile Responsive */}
      <aside className={cn(
        "fixed inset-y-0 left-0 z-50 w-64 border-r border-slate-200/60 p-6 flex flex-col gap-8 bg-white/80 backdrop-blur-md transition-transform duration-300 lg:relative lg:translate-x-0",
        isSidebarOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="flex items-center justify-between lg:justify-start gap-3 px-2">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-200">
              <LayoutGrid size={22} fill="currentColor" />
            </div>
            <div>
              <h1 className="font-bold text-lg leading-tight">Forge</h1>
              <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400 font-bold">Developer AI</p>
            </div>
          </div>
          <button onClick={() => setIsSidebarOpen(false)} className="lg:hidden p-2 text-slate-400">
            <Plus size={20} className="rotate-45" />
          </button>
        </div>

        <nav className="flex flex-col gap-1">
          <SidebarItem icon={LayoutGrid} label="Pipelines" active />
          <SidebarItem icon={Users} label="Agents" />
          <SidebarItem icon={Terminal} label="Console" />
          <SidebarItem icon={Settings} label="Settings" />
        </nav>

        <div className="mt-auto flex flex-col gap-1">
          <SidebarItem icon={FileText} label="Docs" />
          <SidebarItem icon={LifeBuoy} label="Support" />
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-4 md:p-10 max-w-6xl mx-auto w-full">
        {/* Header */}
        <header className="flex flex-col md:flex-row md:items-center justify-between mb-10 gap-6">
          <div className="flex items-center justify-between w-full md:w-auto">
            <button onClick={() => setIsSidebarOpen(true)} className="lg:hidden p-2 -ml-2 text-slate-600">
              <LayoutGrid size={24} />
            </button>
            <div className="text-right md:text-left">
              <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400 font-bold mb-1">System Overview</p>
              <h2 className="text-2xl md:text-3xl font-bold text-slate-900">Main Dashboard</h2>
            </div>
          </div>
          <div className="flex items-center justify-between md:justify-end gap-6 w-full md:w-auto">
            <div className="text-left md:text-right">
              <p className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">Network Latency</p>
              <p className="text-sm font-mono font-bold text-slate-800">14ms</p>
            </div>
            <div className="flex items-center gap-4">
              <button className="p-2.5 rounded-full bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors relative">
                <Bell size={20} />
                <div className="absolute top-2.5 right-2.5 w-2 h-2 bg-indigo-500 rounded-full border-2 border-slate-100" />
              </button>
              <div className="w-10 h-10 rounded-full bg-slate-200 overflow-hidden border-2 border-white shadow-sm">
                <img src="https://picsum.photos/seed/user/100/100" alt="Profile" referrerPolicy="no-referrer" />
              </div>
            </div>
          </div>
        </header>

        <div className="grid grid-cols-12 gap-6">
          {/* Active Pipeline Chart */}
          <section className="col-span-12 lg:col-span-8 bg-white rounded-[32px] p-6 md:p-8 shadow-sm border border-slate-100/50">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Active Pipeline</h3>
                <p className="text-sm text-slate-400">Real-time agent task distribution</p>
              </div>
              <div className="px-3 py-1 bg-indigo-50 text-indigo-600 text-[10px] font-bold tracking-widest uppercase rounded-full">
                Live
              </div>
            </div>

            <div className="h-40 w-full mb-8">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={pipelineData}>
                  <Bar dataKey="value" radius={[6, 6, 6, 6]}>
                    {pipelineData.map((entry, index) => (
                      <Cell 
                        key={`cell-${index}`} 
                        fill={index % 3 === 0 ? '#818cf8' : '#cbd5e1'} 
                        fillOpacity={index % 3 === 0 ? 0.8 : 0.4}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="grid grid-cols-3 pt-8 border-t border-slate-50">
              <StatCard label="Success Rate" value="99.8%" />
              <StatCard label="Tokens/sec" value="1.4k" />
              <StatCard label="Queue Depth" value="12" />
            </div>
          </section>

          {/* Create New Pipeline Card */}
          <section className="col-span-12 lg:col-span-4 bg-indigo-400 rounded-[32px] p-8 text-white relative overflow-hidden group cursor-pointer shadow-lg shadow-indigo-100 min-h-[200px] flex flex-col justify-between">
            <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -mr-16 -mt-16 blur-2xl group-hover:scale-110 transition-transform duration-500" />
            <div className="w-12 h-12 rounded-2xl bg-white/20 flex items-center justify-center mb-8 backdrop-blur-sm">
              <Plus size={24} />
            </div>
            <div>
              <h3 className="text-2xl font-bold mb-2">Create New Pipeline</h3>
              <p className="text-indigo-50 text-sm leading-relaxed opacity-80">
                Initialize a new multi-agent orchestrator with custom logic.
              </p>
            </div>
          </section>

          {/* Recent Activity */}
          <section className="col-span-12 lg:col-span-7 bg-white rounded-[32px] p-6 md:p-8 shadow-sm border border-slate-100/50">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-slate-900">Recent Activity</h3>
              <button className="text-[10px] font-bold uppercase tracking-widest text-slate-400 hover:text-indigo-600 transition-colors">
                View Logs
              </button>
            </div>
            <div className="flex flex-col">
              <ActivityItem title="Planner agent generated execution graph" id="PIPELINE-772" time="2M AGO" />
              <ActivityItem title="Reviewer agent approved PR #892" id="AUTH-F13" time="13M AGO" />
              <ActivityItem title="Code agent refactored database.ts" id="REFACTOR-92" time="32M AGO" />
              <ActivityItem title="Debug agent identified race condition" id="PIPELINE-772" time="1H AGO" />
            </div>
          </section>

          {/* Agent Health */}
          <section className="col-span-12 lg:col-span-5 bg-white rounded-[32px] p-6 md:p-8 shadow-sm border border-slate-100/50">
            <h3 className="text-lg font-bold text-slate-900 mb-6">Agent Health</h3>
            <div className="flex flex-col gap-3">
              <AgentStatus icon={Code} name="Code" status="ACTIVE" />
              <AgentStatus icon={Bug} name="Debug" status="IDLE" />
              <AgentStatus icon={SearchIcon} name="Research" status="ACTIVE" />
              <AgentStatus icon={Calendar} name="Planner" status="ACTIVE" />
              <AgentStatus icon={Eye} name="Reviewer" status="ACTIVE" />
            </div>
          </section>
        </div>

        <footer className="mt-16 pt-8 border-t border-slate-200/60 flex flex-col md:flex-row items-center justify-between gap-6 text-[11px] font-bold uppercase tracking-widest text-slate-400 text-center md:text-left">
          <p>© 2024 FORGE AI. BUILT FOR THE NEXT GENERATION OF DEVELOPERS.</p>
          <div className="flex gap-6 md:gap-8">
            <a href="#" className="hover:text-slate-900 transition-colors">Privacy</a>
            <a href="#" className="hover:text-slate-900 transition-colors">Terms</a>
            <a href="#" className="hover:text-slate-900 transition-colors">API</a>
            <a href="#" className="hover:text-slate-900 transition-colors">Changelog</a>
            <a href="#" className="hover:text-slate-900 transition-colors">Github</a>
          </div>
        </footer>
      </main>
    </div>
  );
};
