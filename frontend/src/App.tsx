import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import { ErrorBoundary } from '@/components/error-boundary';
import { ScrollToTop } from '@/components/scroll-to-top';
import Layout from '@/components/layout';

// ── Lazy-loaded pages ──
const ChatPage = lazy(() => import('@/pages/ChatPage'));
const CompanyProfilePage = lazy(() => import('@/pages/CompanyProfilePage'));
const ComparePage = lazy(() => import('@/pages/ComparePage'));
const SettingsPage = lazy(() => import('@/pages/SettingsPage'));
const ReportPage = lazy(() => import('@/pages/ReportPage'));
const RulesPage = lazy(() => import('@/pages/RulesPage'));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'));

// ── Suspense fallback ──
function PageLoader() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="space-y-4 text-center">
        <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-primary/30 border-t-primary" />
        <p className="text-sm text-muted-foreground">加载中...</p>
      </div>
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ScrollToTop />
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<ChatPage />} />
              <Route path="company/:companyCode" element={<CompanyProfilePage />} />
              <Route path="compare" element={<ComparePage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="reports/:reportId" element={<ReportPage />} />
              <Route path="rules" element={<RulesPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </Suspense>
        <Toaster richColors position="top-center" />
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;