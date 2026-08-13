// 织网鉴真 TruthNet - 应用入口
// 路由配置

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout';
import ChatPage from './pages/ChatPage';
import CompanyProfilePage from './pages/CompanyProfilePage';
import ComparePage from './pages/ComparePage';

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

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
