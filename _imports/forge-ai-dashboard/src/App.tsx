import React, { useState } from 'react';
import { Dashboard } from './components/Dashboard';
import { LandingPage } from './components/LandingPage';
import { TechOverview } from './components/TechOverview';
import { LayoutGrid, Home, Cpu } from 'lucide-react';

export default function App() {
  const [view, setView] = useState<'dashboard' | 'landing' | 'tech'>('dashboard');

  return (
    <div className="relative min-h-screen">
      {/* View Switcher */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-white/80 backdrop-blur-md border border-slate-200 p-2 rounded-2xl shadow-2xl z-[100] flex items-center gap-2 max-w-[95vw] overflow-x-auto no-scrollbar">
        <div className="flex gap-1">
          <button 
            onClick={() => setView('dashboard')}
            className={`flex items-center gap-2 px-3 md:px-4 py-2 rounded-xl text-xs md:text-sm font-bold transition-all whitespace-nowrap ${view === 'dashboard' ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
          >
            <LayoutGrid size={16} />
            <span className="hidden sm:inline">Dashboard</span>
          </button>
          <button 
            onClick={() => setView('landing')}
            className={`flex items-center gap-2 px-3 md:px-4 py-2 rounded-xl text-xs md:text-sm font-bold transition-all whitespace-nowrap ${view === 'landing' ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
          >
            <Home size={16} />
            <span className="hidden sm:inline">Landing</span>
          </button>
          <button 
            onClick={() => setView('tech')}
            className={`flex items-center gap-2 px-3 md:px-4 py-2 rounded-xl text-xs md:text-sm font-bold transition-all whitespace-nowrap ${view === 'tech' ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
          >
            <Cpu size={16} />
            <span className="hidden sm:inline">Tech</span>
          </button>
        </div>
      </div>

      {view === 'dashboard' && <Dashboard />}
      {view === 'landing' && <LandingPage />}
      {view === 'tech' && <TechOverview />}
    </div>
  );
}
