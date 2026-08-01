// 织网鉴真 TruthNet - 应用入口
// 路由配置

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout';
import ChatPage from './pages/ChatPage';
import CompanyProfilePage from './pages/CompanyProfilePage';
import ComparePage from './pages/ComparePage';

// FinForge 原有页面（保留，注释掉以便后续参考）
// import Dashboard from './pages/dashboard';
// import Login from './pages/login';
// import Copilot from './pages/copilot';
// import Repository from './pages/repository/index';
// import Tasks from './pages/tasks';
// import Service from './pages/service';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* TruthNet 路由 */}
        <Route element={<Layout />}>
          <Route path="/" element={<ChatPage />} />
          <Route path="/company/:code" element={<CompanyProfilePage />} />
          <Route path="/compare" element={<ComparePage />} />
        </Route>

        {/* FinForge 原有路由（保留供参考） */}
        {/*
        <Route path="/login" element={<Login />} />
        <Route element={<AuthGuard><Layout /></AuthGuard>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/copilot" element={<Copilot />} />
          <Route path="/repository" element={<Repository />} />
          <Route path="/repository/:id" element={<RepositoryDetail />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/service" element={<Service />} />
        </Route>
        */}

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
