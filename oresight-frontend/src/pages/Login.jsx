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
    navigate('/');
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[var(--charcoal)] px-4">
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

      <div className="relative z-10 w-full max-w-[920px] grid grid-cols-1 md:grid-cols-[1.1fr_1fr] overflow-hidden rounded-[3px] border border-[var(--border)] shadow-md">
        <div className="hidden md:flex flex-col justify-between bg-[var(--charcoal)]/90 p-10 border-r border-[var(--border)]/40 text-white">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-[3px] bg-[var(--accent-primary)] text-white shadow-xs">
                <Mountain size={20} strokeWidth={2} />
              </div>
              <div>
                <div className="font-heading text-lg font-bold text-white leading-none">OreSight</div>
                <div className="text-[10px] uppercase tracking-wider text-[var(--border)] mt-1 opacity-80">MOIL Reserve Intelligence</div>
              </div>
            </div>

            <h2 className="mt-12 font-heading text-2xl font-bold leading-snug text-white">
              Institutional intelligence for the manganese mining belt.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-[#D5CFBF] font-body">
              Unified reserve prospectivity modeling, causal risk mitigation, and production forecasting for the mine planning desk.
            </p>
          </div>

          <div className="flex items-center gap-3 text-xs text-[#A5A096] font-mono">
            <ShieldCheck size={15} className="text-[var(--accent-secondary)]" />
            Digital twin synced • Verified secure
          </div>
        </div>

        <div className="bg-[var(--bg-surface)] p-8 sm:p-10 flex flex-col justify-center text-[var(--text-primary)] transition-colors duration-180">
          <div className="md:hidden flex items-center gap-3 mb-8">
            <div className="flex h-9 w-9 items-center justify-center rounded-[3px] bg-[var(--accent-primary)] text-white">
              <Mountain size={18} strokeWidth={2} />
            </div>
            <div className="font-heading text-base font-bold text-[var(--text-primary)]">OreSight</div>
          </div>

          <h1 className="font-heading text-xl font-bold text-[var(--text-primary)]">Sign in to console</h1>
          <p className="mt-1.5 text-xs text-[var(--text-muted)] font-body">Access the mine production planning dashboard.</p>

          <form className="mt-7 space-y-4" onSubmit={handleSubmit}>
            <div>
              <label htmlFor="email" className="mb-1.5 block text-xs font-bold text-[var(--text-primary)]">
                Work email
              </label>
              <div className="relative">
                <Mail size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="engineer@moil.co.in"
                  className="w-full rounded-[3px] border border-[var(--border)] bg-[var(--bg-primary)] py-2.5 pl-10 pr-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)] focus:border-[var(--accent-primary)] font-body"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-xs font-bold text-[var(--text-primary)]">
                Password
              </label>
              <div className="relative">
                <Lock size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-[3px] border border-[var(--border)] bg-[var(--bg-primary)] py-2.5 pl-10 pr-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)] focus:border-[var(--accent-primary)] font-mono"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <label className="flex items-center gap-2 text-xs font-medium text-[var(--text-muted)] cursor-pointer">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  className="h-3.5 w-3.5 rounded-[2px] border-[var(--border)] text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                />
                Remember me
              </label>
              <a href="#" className="text-xs font-bold text-[var(--accent-primary)] hover:underline">
                Forgot password?
              </a>
            </div>

            <Button type="submit" variant="primary" className="w-full mt-3 py-2.5">
              Sign In
              <ArrowRight size={15} />
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
