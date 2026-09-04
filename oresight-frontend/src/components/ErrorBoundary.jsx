import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import Button from './Button';

// A render-time crash in one page used to take down the whole router — React
// unmounts the entire tree when nothing catches the error, so a bad field
// access on /reports white-screened the app including the nav. Error
// boundaries have to be class components; there is no hook equivalent.
//
// Used at two levels in App.jsx:
//   - around the routed page, keyed by pathname, so the nav chrome survives
//     and navigating elsewhere clears the error by remounting the boundary;
//   - around the whole app, to catch anything that escapes that (the nav
//     itself, the providers, a routing error).
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Keep the component stack in the console — the boundary swallows the
    // error for the user, it must not swallow it for whoever is debugging.
    console.error('[ErrorBoundary] Render error:', error, info?.componentStack);
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    const { title = 'This page failed to render', fullPage = false } = this.props;

    return (
      <div
        role="alert"
        className={`flex flex-col items-center justify-center text-center px-6 ${
          fullPage ? 'min-h-screen bg-[var(--bg-primary)]' : 'py-16'
        }`}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-danger/10 text-danger mb-3">
          <AlertTriangle size={22} strokeWidth={2} />
        </div>
        <div className="font-semibold text-sm text-text-primary">{title}</div>
        <p className="mt-1 max-w-md text-xs text-text-muted">
          The rest of the app is still usable — pick another page from the navigation, or
          try rendering this one again.
        </p>
        <p className="mt-3 max-w-md break-words font-mono text-[11px] text-danger/80">
          {error.message || String(error)}
        </p>
        <Button variant="ghost" size="sm" className="mt-4" onClick={this.handleReset}>
          <RefreshCw size={14} />
          Try again
        </Button>
      </div>
    );
  }
}
