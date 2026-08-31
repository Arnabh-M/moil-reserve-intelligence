import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Outlet } from 'react-router-dom';
import { Sidebar, TopBar } from './components';
import Dashboard from './pages/Dashboard';
import Production from './pages/Production';
import Reserves from './pages/Reserves';
import Equipment from './pages/Equipment';
import Risks from './pages/Risks';
import Simulator from './pages/Simulator';
import Recommendations from './pages/Recommendations';
import Timeline from './pages/Timeline';
import SiteDetail from './pages/SiteDetail';
import DataInput from './pages/DataInput';
import ComingSoon from './pages/ComingSoon';

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
    <BrowserRouter>
      <Routes>
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
          <Route path="/timeline" element={<Timeline />} />
          <Route path="/site/:id" element={<SiteDetail />} />
          <Route path="/data-input" element={<DataInput />} />
          {/* Placeholder routes */}
          <Route path="/blasting" element={<ComingSoon />} />
          <Route path="/geology" element={<ComingSoon />} />
          <Route path="/reports" element={<ComingSoon />} />
          <Route path="/settings" element={<ComingSoon />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
