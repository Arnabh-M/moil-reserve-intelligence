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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[var(--bg-primary)] px-4">
      <div className="relative z-10 w-full max-w-[880px] grid grid-cols-1 md:grid-cols-2 overflow-hidden rounded-2xl border border-[var(--divider)] bg-[var(--bg-elevated)] shadow-xl">
        {/* Left Brand Panel */}
        <div className="hidden md:flex flex-col justify-between bg-[var(--accent-soft)]/50 p-10 border-r border-[var(--divider)]">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent-primary)] text-white shadow-xs">
                <Mountain size={18} strokeWidth={2} />
              </div>
              <div>
                <div className="text-base font-semibold text-[var(--text-primary)] leading-none">OreSight</div>
                <div className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] mt-1 font-medium">MOIL Reserve Intelligence</div>
              </div>
            </div>

            <h2 className="mt-12 text-2xl font-semibold leading-snug text-[var(--text-primary)] tracking-tight">
              Institutional intelligence for manganese reserve modeling.
            </h2>
            <p className="mt-3 text-xs leading-relaxed text-[var(--text-muted)]">
              Unified deposit prospectivity, causal risk telemetry, and automated production forecasting for modern mining operations.
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <ShieldCheck size={14} className="text-[var(--accent-primary)]" />
            <span>Digital Twin Synced • MOIL Certified</span>
          </div>
        </div>

        {/* Right Form Panel */}
        <div className="p-8 sm:p-10 flex flex-col justify-center text-[var(--text-primary)]">
          <div className="md:hidden flex items-center gap-3 mb-6">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent-primary)] text-white">
              <Mountain size={16} strokeWidth={2} />
            </div>
            <div className="text-base font-semibold text-[var(--text-primary)]">OreSight</div>
          </div>

          <h1 className="text-xl font-semibold text-[var(--text-primary)] tracking-tight">Sign in to console</h1>
          <p className="mt-1 text-xs text-[var(--text-muted)]">Access real-time telemetry and reserve intelligence.</p>

          <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
            <div>
              <label htmlFor="email" className="mb-1.5 block text-xs font-medium text-[var(--text-primary)]">
                Work Email
              </label>
              <div className="relative">
                <Mail size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="engineer@moil.co.in"
                  className="w-full rounded-lg border border-[var(--divider)] bg-[var(--bg-primary)] py-2 pl-9 pr-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--accent-primary)]"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-xs font-medium text-[var(--text-primary)]">
                Password
              </label>
              <div className="relative">
                <Lock size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-lg border border-[var(--divider)] bg-[var(--bg-primary)] py-2 pl-9 pr-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--accent-primary)]"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <label className="flex items-center gap-2 text-xs text-[var(--text-muted)] cursor-pointer">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  className="h-3.5 w-3.5 rounded border-[var(--divider)] text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                />
                Remember me
              </label>
              <a href="#" className="text-xs font-medium text-[var(--accent-primary)] hover:underline">
                Forgot password?
              </a>
            </div>

            <Button type="submit" variant="primary" className="w-full mt-3 py-2.5">
              <span>Sign In</span>
              <ArrowRight size={14} />
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}


