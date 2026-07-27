import { Outlet } from 'react-router-dom';
import { AppHeader } from './app-header';

export default function Layout() {
  return (
    <div className="min-h-screen bg-background">
      <AppHeader />
      <main className="pt-16">
        <Outlet />
      </main>
    </div>
  );
}
