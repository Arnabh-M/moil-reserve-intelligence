import React from 'react';
import { BrowserRouter, Routes, Route, Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Toaster } from 'react-hot-toast';
import { Navigation } from './components';
import { ToastProvider } from './context/ToastContext';
import { ThemeProvider } from './context/ThemeContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Production from './pages/Production';
import Reserves from './pages/Reserves';
import Equipment from './pages/Equipment';
import Risks from './pages/Risks';
import Simulator from './pages/Simulator';
import Recommendations from './pages/Recommendations';
import EventTimeline from './pages/EventTimeline';
import SiteDetail from './pages/SiteDetail';
import DataInput from './pages/DataInput';
import Reports from './pages/Reports';
import ComingSoon from './pages/ComingSoon';
import MapPage from './pages/MapPage';

function Layout() {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] flex flex-col transition-colors duration-180">
      {/* 6-Item Top Navigation Bar with Hover Dropdowns & Theme Toggle */}
      <Navigation />
      
      {/* Main Page Area */}
      <main className="flex-1">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16, ease: 'easeInOut' }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: 'var(--charcoal)',
              color: 'var(--text-primary)',
              fontSize: '13px',
              borderRadius: '3px',
              border: '1px solid var(--border)',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
              fontFamily: 'var(--font-body)',
              padding: '12px 16px',
            },
            success: {
              iconTheme: {
                primary: 'var(--success)',
                secondary: '#ffffff',
              },
              style: {
                borderLeft: '4px solid var(--success)',
              },
            },
            error: {
              iconTheme: {
                primary: 'var(--warning)',
                secondary: '#ffffff',
              },
              style: {
                borderLeft: '4px solid var(--warning)',
              },
            },
          }}
        />
        <BrowserRouter>
          <Routes>
            {/* Pre-auth: no topbar chrome */}
            <Route path="/login" element={<Login />} />

            <Route element={<Layout />}>
              {/* Core Routes */}
              <Route path="/" element={<Dashboard />} />
              <Route path="/production" element={<Production />} />
              <Route path="/reserves" element={<Reserves />} />
              <Route path="/equipment" element={<Equipment />} />
              <Route path="/risks" element={<Risks />} />
              <Route path="/simulator" element={<Simulator />} />
              <Route path="/recommendations" element={<Recommendations />} />
              <Route path="/timeline" element={<EventTimeline />} />
              <Route path="/site/:id" element={<SiteDetail />} />
              <Route path="/data-input" element={<DataInput />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/map" element={<MapPage />} />
              <Route path="/blasting" element={<ComingSoon />} />
              <Route path="/geology" element={<Reserves />} />
              <Route path="/settings" element={<ComingSoon />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </ThemeProvider>
  );
}
