import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, ArrowRight, ArrowLeft } from "lucide-react";
import { useAuth } from "../AuthContext";

export default function Auth() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { signIn, signUp, authEnabled } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!authEnabled) {
      setError("Authentication is not configured.");
      return;
    }
    
    setLoading(true);
    setError("");
    try {
      if (isLogin) {
        await signIn(email, password);
        navigate("/dashboard");
      } else {
        const res = await signUp(email, password);
        if (res.session) navigate("/dashboard");
        else setError("Check your inbox for confirmation.");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white dark:bg-zinc-950 flex overflow-hidden">
      {/* Left side Form */}
      <div className="w-full lg:w-1/2 flex flex-col p-8 md:p-12 xl:p-24 relative z-10">
        <Link to="/" className="inline-flex items-center gap-2 text-sm font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white mb-12 w-fit transition-colors">
          <ArrowLeft className="w-4 h-4" />
          Back to home
        </Link>
        
        <div className="flex-1 flex flex-col justify-center max-w-sm w-full mx-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={isLogin ? "login" : "signup"}
              initial={{ opacity: 0, x: -10, filter: "blur(4px)" }}
              animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
              exit={{ opacity: 0, x: 10, filter: "blur(4px)" }}
              transition={{ duration: 0.3, ease: "easeOut" }}
            >
              <div className="flex items-center gap-2 mb-8">
                <div className="w-8 h-8 rounded bg-zinc-900 dark:bg-white flex items-center justify-center shadow-md">
                  <Sparkles className="w-5 h-5 text-white dark:text-zinc-900" />
                </div>
                <span className="font-bold tracking-tight text-zinc-900 dark:text-white">Forge</span>
              </div>

              <h1 className="text-3xl font-extrabold tracking-tight text-zinc-900 dark:text-white mb-2">
                {isLogin ? "Welcome back" : "Create an account"}
              </h1>
              <p className="text-zinc-600 dark:text-zinc-400 mb-8 font-medium">
                {isLogin ? "Enter your details to access your workspace." : "Enter your details to get started with Forge."}
              </p>

              <form onSubmit={handleSubmit} className="space-y-5">
                {error && (
                  <motion.div 
                    initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }}
                    className="p-3 text-sm font-medium text-rose-500 bg-rose-500/10 rounded-lg border border-rose-500/20"
                  >
                    {error}
                  </motion.div>
                )}
                
                <div className="space-y-2 group">
                  <label className="text-sm font-semibold text-zinc-900 dark:text-zinc-200 transition-colors group-focus-within:text-teal-500">Email</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-white focus:ring-2 focus:ring-teal-500/50 focus:border-teal-500 outline-none transition-all shadow-sm"
                    placeholder="you@example.com"
                  />
                </div>

                <div className="space-y-2 group">
                  <label className="text-sm font-semibold text-zinc-900 dark:text-zinc-200 transition-colors group-focus-within:text-teal-500">Password</label>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-white focus:ring-2 focus:ring-teal-500/50 focus:border-teal-500 outline-none transition-all shadow-sm"
                    placeholder="••••••••"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full px-4 py-3 text-sm font-bold bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 rounded-xl hover:bg-zinc-800 dark:hover:bg-zinc-100 transition-all flex items-center justify-center gap-2 mt-4 disabled:opacity-50 hover:scale-[1.02] active:scale-[0.98] shadow-lg shadow-zinc-900/10 dark:shadow-white/10"
                >
                  {loading ? "Please wait..." : isLogin ? "Log in" : "Sign up"}
                  {!loading && <ArrowRight className="w-4 h-4" />}
                </button>
              </form>

              <div className="mt-8 text-center text-sm text-zinc-600 dark:text-zinc-400 font-medium">
                {isLogin ? "Don't have an account? " : "Already have an account? "}
                <button
                  onClick={() => {
                    setIsLogin(!isLogin);
                    setError("");
                  }}
                  className="font-semibold text-zinc-900 dark:text-white hover:text-teal-500 transition-colors"
                >
                  {isLogin ? "Sign up" : "Log in"}
                </button>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      {/* Right side Illustration (AuthFuse concept) */}
      <div className="hidden lg:flex w-1/2 bg-zinc-100 dark:bg-zinc-900 pb-0 flex-col justify-center items-center relative overflow-hidden p-12 shadow-inner">
         {/* Grid background */}
         <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:32px_32px]"></div>
         <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-gradient-to-tr from-teal-500/30 to-emerald-400/20 blur-[120px] rounded-full pointer-events-none mix-blend-screen dark:mix-blend-lighten"></div>

         <motion.div 
           initial={{ opacity: 0, scale: 0.95, y: 20 }}
           animate={{ opacity: 1, scale: 1, y: 0 }}
           transition={{ duration: 0.8, delay: 0.1, ease: "easeOut" }}
           className="relative z-10 max-w-lg text-center"
         >
            <div className="glass-panel p-10 rounded-3xl border border-white/40 dark:border-zinc-800/60 bg-white/60 dark:bg-zinc-950/60 backdrop-blur-2xl shadow-2xl dark:shadow-[0_0_50px_rgba(20,184,166,0.1)]">
              <Sparkles className="w-12 h-12 text-teal-500 mx-auto mb-6" />
              <h2 className="text-2xl font-extrabold tracking-tight text-zinc-900 dark:text-white mb-4 drop-shadow-sm">
                The AI workspace for modern engineering
              </h2>
              <p className="text-zinc-600 dark:text-zinc-400 leading-relaxed font-medium">
                Connect your sign-in flows, run background missions, deliver to Telegram, and control execution offload with zero boilerplate.
              </p>
            </div>
         </motion.div>
      </div>
    </div>
  );
}
