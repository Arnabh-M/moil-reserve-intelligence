import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Outlet } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { Sidebar, TopBar } from './components';
import { ToastProvider } from './context/ToastContext';
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="min-h-screen bg-bg">
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(c => !c)} />
      <div
        className="transition-all duration-300"
        style={{ marginLeft: sidebarCollapsed ? 68 : 240 }}
      >
        <TopBar />
        <main>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#101a2b',
            color: '#ffffff',
            fontSize: '13px',
            borderRadius: '10px',
            border: '1px solid #16233a',
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.25)',
            fontFamily: 'Inter, system-ui, sans-serif',
            padding: '12px 16px',
          },
          success: {
            iconTheme: {
              primary: '#2a7f8c', // teal accent
              secondary: '#ffffff',
            },
            style: {
              borderLeft: '4px solid #2a7f8c',
            },
          },
          error: {
            iconTheme: {
              primary: '#ef4444', // muted red
              secondary: '#ffffff',
            },
            style: {
              borderLeft: '4px solid #ef4444',
            },
          },
        }}
      />
      <BrowserRouter>
        <Routes>
          {/* Pre-auth: no sidebar/topbar chrome */}
          <Route path="/login" element={<Login />} />

          <Route element={<Layout />}>
            {/* Original 5 pages */}
            <Route path="/" element={<Dashboard />} />
            <Route path="/production" element={<Production />} />
            <Route path="/reserves" element={<Reserves />} />
            <Route path="/equipment" element={<Equipment />} />
            <Route path="/risks" element={<Risks />} />
            {/* New 5 pages (Day 1 assignment) */}
            <Route path="/simulator" element={<Simulator />} />
            <Route path="/recommendations" element={<Recommendations />} />
            <Route path="/timeline" element={<EventTimeline />} />
            <Route path="/site/:id" element={<SiteDetail />} />
            <Route path="/data-input" element={<DataInput />} />
            {/* Real */}
            <Route path="/reports" element={<Reports />} />
            {/* Placeholder routes */}
            <Route path="/map" element={<MapPage />} />
            <Route path="/blasting" element={<ComingSoon />} />
            <Route path="/geology" element={<ComingSoon />} />
            <Route path="/settings" element={<ComingSoon />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
