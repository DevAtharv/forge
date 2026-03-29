import React from 'react';
import { Send, BookOpen, Code, Bug, Search, Calendar, Eye, Layers } from 'lucide-react';
import { motion } from 'motion/react';

const NavLink = ({ children }: { children: React.ReactNode }) => (
  <a href="#" className="text-sm font-medium text-slate-600 hover:text-indigo-600 transition-colors">
    {children}
  </a>
);

const TeamCard = ({ icon: Icon, title, description }: { icon: any, title: string, description: string }) => (
  <div className="bg-white p-6 md:p-8 rounded-[32px] border border-slate-100 shadow-sm hover:shadow-md transition-all group">
    <div className="w-12 h-12 rounded-2xl bg-slate-50 flex items-center justify-center text-slate-600 mb-6 group-hover:bg-indigo-50 group-hover:text-indigo-600 transition-colors">
      <Icon size={20} />
    </div>
    <h3 className="text-xl font-bold text-slate-900 mb-3">{title}</h3>
    <p className="text-slate-500 text-sm leading-relaxed">{description}</p>
  </div>
);

export const LandingPage = () => {
  return (
    <div className="min-h-screen bg-white transition-colors duration-300">
      {/* Navbar */}
      <nav className="max-w-7xl mx-auto px-4 md:px-8 py-6 md:py-8 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white">
            <Layers size={18} fill="currentColor" />
          </div>
          <span className="text-xl font-bold tracking-tight">FORGE <span className="text-indigo-600">AI</span></span>
        </div>
        
        <div className="hidden lg:flex items-center gap-8">
          <NavLink>Docs</NavLink>
          <NavLink>Pricing</NavLink>
          <NavLink>Community</NavLink>
          <button className="px-6 py-2.5 rounded-xl bg-indigo-600 text-white font-bold text-sm hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-100">
            Open in Telegram
          </button>
          <button className="px-6 py-2.5 rounded-xl border border-slate-200 text-slate-700 font-bold text-sm hover:bg-slate-50 transition-all">
            Read the Docs
          </button>
        </div>

        <button className="lg:hidden p-2 text-slate-600">
          <Layers size={24} />
        </button>
      </nav>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 md:px-8 py-12 md:py-20 grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center">
        <div className="text-center lg:text-left">
          <h1 className="text-4xl md:text-6xl font-bold text-slate-900 leading-[1.1] mb-6 md:mb-8">
            Forge: Your AI Dev Team on Telegram.
          </h1>
          <p className="text-lg md:text-xl text-slate-500 leading-relaxed mb-8 md:mb-10 max-w-lg mx-auto lg:mx-0">
            Forge your AI minimal landing page for Telegram with Inter/SF Pro.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
            <button className="px-8 py-4 rounded-2xl bg-indigo-600 text-white font-bold text-lg hover:bg-indigo-700 transition-all shadow-xl shadow-indigo-100 flex items-center justify-center gap-2">
              Open in Telegram
            </button>
            <button className="px-8 py-4 rounded-2xl border border-slate-200 text-slate-700 font-bold text-lg hover:bg-slate-50 transition-all">
              Read the Docs
            </button>
          </div>
        </div>

        <div className="relative">
          <div className="bg-white rounded-[40px] shadow-2xl border border-slate-100 overflow-hidden">
            <div className="bg-slate-50 px-6 py-4 border-b border-slate-100 flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-400 flex items-center justify-center text-white">
                <Send size={14} fill="currentColor" />
              </div>
              <span className="font-bold text-slate-800">Forge</span>
            </div>
            <div className="p-6 md:p-8 flex flex-col gap-6">
              <div className="self-end bg-blue-500 text-white px-4 py-2 rounded-2xl rounded-tr-none text-sm max-w-[85%]">
                Al nitnati duennwas anores
              </div>
              <div className="self-end bg-blue-500 text-white px-4 py-2 rounded-2xl rounded-tr-none text-sm max-w-[85%]">
                What mess onea agent?
              </div>
              <div className="bg-slate-100 text-slate-800 px-4 py-3 rounded-2xl rounded-tl-none text-sm max-w-[85%]">
                Hello time you AI our configuration list moment
              </div>
              <div className="bg-slate-900 text-white p-4 rounded-2xl font-mono text-[10px] md:text-xs leading-relaxed overflow-x-auto">
                <pre>
{`0005
  return {
    ceost test = rolt {
      test = "longy"
    }
    return test.Resoucncoer('alx', test)
  }`}
                </pre>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/50 flex items-center gap-4">
              <div className="flex-1 bg-white border border-slate-200 rounded-full px-4 py-2 text-slate-400 text-sm">
                Message...
              </div>
              <div className="flex gap-3 text-slate-400">
                <Send size={18} />
              </div>
            </div>
          </div>
          <p className="text-center mt-6 text-[11px] uppercase tracking-widest text-slate-400 font-bold">
            Message window in JetBrains Mono
          </p>
        </div>
      </section>

      {/* Team Section */}
      <section className="max-w-7xl mx-auto px-4 md:px-8 py-20 md:py-32 text-center">
        <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">Meet the Team</h2>
        <p className="text-slate-500 mb-12 md:mb-16">Generous padding and criss, refined typography</p>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
          <TeamCard 
            icon={Code} 
            title="Code" 
            description="Code systems works and sceeaed fac to with owtenstating languaaes." 
          />
          <TeamCard 
            icon={Bug} 
            title="Debug" 
            description="Debug customise agent coreasive tools, eohting and snrroking and modutes." 
          />
          <TeamCard 
            icon={Search} 
            title="Research" 
            description="Research orarches, solutions and research med servicoo research typography." 
          />
          <TeamCard 
            icon={Calendar} 
            title="Planner" 
            description="Planner and managements pnocessing and automiating, and analytics." 
          />
          <TeamCard 
            icon={Eye} 
            title="Reviewer" 
            description="Reviewer as iternation. analysis and maxnwit analytics, rsiearms and development." 
          />
        </div>
      </section>
    </div>
  );
};
