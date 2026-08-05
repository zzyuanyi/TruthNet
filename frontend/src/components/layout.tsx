import { Outlet } from 'react-router-dom';
import { PageTransition } from '@/components/page-transition';
import { AppHeader } from './app-header';

export default function Layout() {
  return (
    <div className="min-h-screen bg-background">
      <AppHeader />
      <main className="pt-16">
        <PageTransition><Outlet /></PageTransition>
      </main>
    </div>
  );
}
