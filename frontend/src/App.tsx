import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import { ErrorBoundary } from '@/components/error-boundary';
import { ScrollToTop } from '@/components/scroll-to-top';
import CommandPalette from '@/components/command-palette';
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
    <div className="fixed inset-0 z-[999] flex items-center justify-center bg-white">
      <div className="flex flex-col items-center gap-5">
        {/* 织网纹路：经纬网格交织动画 */}
        <div className="relative h-24 w-24">
          <svg viewBox="0 0 100 100" className="h-full w-full text-neutral-900" aria-hidden="true">
            <g fill="none" stroke="currentColor" strokeWidth="1.4" opacity="0.85">
              {/* 经线 */}
              <path d="M50 2 C 50 30, 50 70, 50 98" className="tn-boot-line" style={{ animationDelay: '0ms' }} />
              <path d="M20 6 C 26 34, 26 66, 20 94" className="tn-boot-line" style={{ animationDelay: '120ms' }} />
              <path d="M80 6 C 74 34, 74 66, 80 94" className="tn-boot-line" style={{ animationDelay: '240ms' }} />
              {/* 纬线 */}
              <path d="M2 50 C 30 50, 70 50, 98 50" className="tn-boot-line" style={{ animationDelay: '360ms' }} />
              <path d="M6 20 C 34 26, 66 26, 94 20" className="tn-boot-line" style={{ animationDelay: '480ms' }} />
              <path d="M6 80 C 34 74, 66 74, 94 80" className="tn-boot-line" style={{ animationDelay: '600ms' }} />
            </g>
            <circle cx="50" cy="50" r="4.5" fill="currentColor" className="tn-boot-core" />
          </svg>
        </div>
        <div className="flex flex-col items-center gap-2">
          <p className="text-base font-medium tracking-[0.3em] text-neutral-900">织网鉴真</p>
          <div className="h-px w-28 overflow-hidden bg-neutral-200">
            <div className="tn-boot-bar h-full w-1/3 bg-neutral-900" />
          </div>
        </div>
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
        <CommandPalette />
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;