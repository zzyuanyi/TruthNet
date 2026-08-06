import { Outlet } from 'react-router-dom';
import { PageTransition } from '@/components/page-transition';
import { AppHeader } from './app-header';

export default function Layout() {
  return (
    <div className="min-h-screen bg-background">
      <AppHeader />
      <main className="min-h-0">
        <PageTransition><Outlet /></PageTransition>
      </main>
    </div>
  );
}
