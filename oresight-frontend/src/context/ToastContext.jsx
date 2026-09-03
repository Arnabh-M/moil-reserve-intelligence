import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from 'lucide-react';

const ToastContext = createContext(null);

const toastVariants = {
  success: {
    bg: 'bg-bg-surface border-success/30 text-text-primary',
    icon: CheckCircle2,
    iconColor: 'text-success',
    bar: 'bg-success',
  },
  error: {
    bg: 'bg-bg-surface border-danger/30 text-text-primary',
    icon: AlertCircle,
    iconColor: 'text-danger',
    bar: 'bg-danger',
  },
  warning: {
    bg: 'bg-bg-surface border-warning/30 text-text-primary',
    icon: AlertTriangle,
    iconColor: 'text-warning',
    bar: 'bg-warning',
  },
  info: {
    bg: 'bg-bg-surface border-teal/30 text-text-primary',
    icon: Info,
    iconColor: 'text-teal',
    bar: 'bg-teal',
  },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback(({ title, message, type = 'info', duration = 4000 }) => {
    const id = Date.now() + Math.random().toString(36).substring(2, 6);
    setToasts(prev => [...prev, { id, title, message, type, duration }]);

    if (duration > 0) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, duration);
    }
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      {/* Toast container overlay */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none">
        {toasts.map(toast => {
          const config = toastVariants[toast.type] || toastVariants.info;
          const Icon = config.icon;

          return (
            <div
              key={toast.id}
              className={`pointer-events-auto relative overflow-hidden rounded-xl border shadow-lg p-3.5 flex items-start gap-3 transition-all duration-300 animate-slide-in ${config.bg}`}
            >
              <div className={`shrink-0 mt-0.5 ${config.iconColor}`}>
                <Icon size={18} />
              </div>
              <div className="flex-1 min-w-0 pr-2">
                {toast.title && (
                  <h5 className="text-xs font-bold text-text-primary mb-0.5">{toast.title}</h5>
                )}
                <p className="text-xs text-text-secondary leading-relaxed">{toast.message}</p>
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-text-muted hover:text-text-primary transition-colors p-1"
                aria-label="Dismiss notification"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}
