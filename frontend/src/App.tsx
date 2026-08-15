// 织网鉴真 TruthNet - 应用入口
// 路由配置

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout';
import ChatPage from './pages/ChatPage';
import CompanyProfilePage from './pages/CompanyProfilePage';
import ComparePage from './pages/ComparePage';
import ReportPage from './pages/ReportPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* TruthNet 路由 */}
        <Route element={<Layout />}>
          <Route path="/" element={<ChatPage />} />
          <Route path="/company/:code" element={<CompanyProfilePage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>

        {/* 报告页独立布局（无 Header） */}
        <Route path="/reports/:reportId" element={<ReportPage />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
