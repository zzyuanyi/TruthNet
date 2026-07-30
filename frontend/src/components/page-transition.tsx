
import { useEffect, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';

export function PageTransition({ children }: { children: ReactNode }) {
  const location = useLocation();
  const pathname = location.pathname;
  const [displayChildren, setDisplayChildren] = useState(children);
  const [transitioning, setTransitioning] = useState(false);

  useEffect(() => {
    setTransitioning(true);
    const timer = setTimeout(() => {
      setDisplayChildren(children);
      setTransitioning(false);
    }, 150);
    return () => clearTimeout(timer);
  }, [pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      className={`transition-all duration-150 ease-in-out ${
        transitioning ? 'opacity-0 translate-y-1' : 'opacity-100 translate-y-0'
      }`}
    >
      {displayChildren}
    </div>
  );
}
