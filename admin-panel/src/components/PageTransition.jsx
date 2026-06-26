import { useEffect, useRef, useState } from 'react';

/**
 * Wraps children with a fade-in animation on mount.
 * Re-triggers when `triggerKey` changes (e.g., on route change).
 *
 * Usage:
 *   <PageTransition triggerKey={location.pathname}>
 *     <Outlet />
 *   </PageTransition>
 */
export default function PageTransition({ children, triggerKey, className = '' }) {

  const prevKey = useRef(triggerKey);

  useEffect(() => {
    if (triggerKey !== prevKey.current) {
      setVisible(false);
      prevKey.current = triggerKey;
    }

    // Trigger animation on next frame
    const raf = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(raf);
  }, [triggerKey]);

  return (
    <div
      className={`transition-all duration-300 ${
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
      } ${className}`}
    >
      {children}
    </div>
  );
}

