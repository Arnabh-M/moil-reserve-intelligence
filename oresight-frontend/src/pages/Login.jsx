import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mountain, Lock, Mail, ArrowRight, ShieldCheck } from 'lucide-react';
import { Button } from '../components';

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);

  function handleSubmit(e) {
    e.preventDefault();
    // Authentication is mocked for this build — no backend auth endpoint exists yet.
    navigate('/');
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-navy px-4">
      <svg
        className="pointer-events-none absolute inset-0 z-0 h-full w-full opacity-10"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <pattern id="contours" width="240" height="240" patternUnits="userSpaceOnUse">
            <path d="M -20 100 Q 40 60 100 100 T 260 100" fill="none" stroke="#ffffff" strokeWidth="1" />
            <path d="M -20 140 Q 40 100 100 140 T 260 140" fill="none" stroke="#ffffff" strokeWidth="1" />
            <path d="M -20 60 Q 40 20 100 60 T 260 60" fill="none" stroke="#ffffff" strokeWidth="1" />
            <path d="M -20 180 Q 40 140 100 180 T 260 180" fill="none" stroke="#ffffff" strokeWidth="1" />
            <path d="M -20 20 Q 40 -20 100 20 T 260 20" fill="none" stroke="#ffffff" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#contours)" />
      </svg>

      <div className="relative z-10 w-full max-w-[920px] grid grid-cols-1 md:grid-cols-[1.1fr_1fr] overflow-hidden rounded-md border border-white/10 shadow-sm">
        <div className="hidden md:flex flex-col justify-between bg-navy2/60 p-10 border-r border-white/10">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-sm bg-orange text-white">
                <Mountain size={20} strokeWidth={2.25} />
              </div>
              <div>
                <div className="font-heading text-lg font-semibold text-white leading-none">OreSight</div>
                <div className="text-[10px] uppercase tracking-wider text-white/50 mt-1">MOIL Reserve Intelligence</div>
              </div>
            </div>

            <h2 className="mt-12 font-heading text-2xl font-semibold leading-snug text-white">
              AI-driven mining intelligence for the manganese belt.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-white/60">
              Unified reserve confidence, causal risk analysis, and production simulation — built
              for the mine planning desk.
            </p>
          </div>

          <div className="flex items-center gap-3 text-xs text-white/50">
            <ShieldCheck size={15} className="text-teal" />
            Digital twin last synced 2 min ago
          </div>
        </div>

        <div className="bg-white p-8 sm:p-10 flex flex-col justify-center">
          <div className="md:hidden flex items-center gap-3 mb-8">
            <div className="flex h-9 w-9 items-center justify-center rounded-sm bg-orange text-white">
              <Mountain size={18} strokeWidth={2.25} />
            </div>
            <div className="font-heading text-base font-semibold text-navy">OreSight</div>
          </div>

          <h1 className="font-heading text-xl font-semibold text-navy">Sign in to your console</h1>
          <p className="mt-2 text-sm text-text-secondary">Access the mine production planning dashboard.</p>

          <form className="mt-7 space-y-4" onSubmit={handleSubmit}>
            <div>
              <label htmlFor="email" className="mb-2 block text-xs font-semibold text-navy">
                Work email
              </label>
              <div className="relative">
                <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@moil.co.in"
                  className="w-full rounded-sm border border-border bg-white py-3 pl-10 pr-3 text-sm text-navy placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-teal/40 focus:border-teal"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="mb-2 block text-xs font-semibold text-navy">
                Password
              </label>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-sm border border-border bg-white py-3 pl-10 pr-3 text-sm text-navy placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-teal/40 focus:border-teal"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <label className="flex items-center gap-2 text-xs font-medium text-text-secondary cursor-pointer">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  className="h-4 w-4 rounded-sm border-border text-orange focus:ring-orange/40"
                />
                Remember me
              </label>
              <a href="#" className="text-xs font-semibold text-teal hover:text-teal/80">
                Forgot password?
              </a>
            </div>

            <Button type="submit" variant="primary" className="w-full mt-2 py-3">
              Sign In
              <ArrowRight size={16} />
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
