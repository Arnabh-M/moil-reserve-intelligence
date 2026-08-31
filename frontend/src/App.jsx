import { Routes, Route, Outlet } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import Login from './pages/Login'
import CommandCenter from './pages/CommandCenter'
import MapPage from './pages/MapPage'
import Simulator from './pages/Simulator'
import Timeline from './pages/Timeline'
import Recommendations from './pages/Recommendations'
import SiteDetail from './pages/SiteDetail'
import DataInput from './pages/DataInput'
import Reports from './pages/Reports'
import GraphTest from './pages/GraphTest'

function DashboardLayout() {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-bg">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<DashboardLayout />}>
        <Route path="/" element={<CommandCenter />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/simulator" element={<Simulator />} />
        <Route path="/timeline" element={<Timeline />} />
        <Route path="/recommendations" element={<Recommendations />} />
        <Route path="/site/:id" element={<SiteDetail />} />
        <Route path="/data-input" element={<DataInput />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/graph-test" element={<GraphTest />} />
      </Route>
    </Routes>
  )
}
