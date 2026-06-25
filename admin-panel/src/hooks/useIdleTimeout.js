import { useState, useEffect, useRef, useCallback } from 'react';

const EVENTS = [
  'mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'click',
];

/**
 * Tracks user inactivity and fires callbacks.
 *
 * @param {object} options
 * @param {number} options.warnAfter - ms before warning (default 15 min)
 * @param {number} options.logoutAfter - ms before auto-logout (default 30 min)
 * @param {function} options.onWarning - called when warnAfter reached
 * @param {function} options.onLogout - called when logoutAfter reached
 * @param {boolean} options.enabled - enable/disable tracking
 *
 * @returns {{ resetTimer: function, timeUntilWarning: number, timeUntilLogout: number }}
 */
export default function useIdleTimeout({
  warnAfter = 15 * 60 * 1000,   // 15 minutes
  logoutAfter = 30 * 60 * 1000,  // 30 minutes
  onWarning,
  onLogout,
  enabled = true,
} = {}) {
  const [timeUntilWarning, setTimeUntilWarning] = useState(warnAfter);
  const [timeUntilLogout, setTimeUntilLogout] = useState(logoutAfter);
  const lastActivityRef = useRef(Date.now());
  const warnedRef = useRef(false);
  const intervalRef = useRef(null);

  const resetTimer = useCallback(() => {
    lastActivityRef.current = Date.now();
    warnedRef.current = false;
  }, []);

  // Track user activity
  useEffect(() => {
    if (!enabled) return;

    const handleActivity = () => {
      lastActivityRef.current = Date.now();
      warnedRef.current = false;
    };

    EVENTS.forEach((event) => {
      window.addEventListener(event, handleActivity, { passive: true });
    });

    return () => {
      EVENTS.forEach((event) => {
        window.removeEventListener(event, handleActivity);
      });
    };
  }, [enabled]);

  // Check timer every second
  useEffect(() => {
    if (!enabled || !onLogout) return;

    intervalRef.current = setInterval(() => {
      const now = Date.now();
      const elapsed = now - lastActivityRef.current;

      const remainingWarn = Math.max(0, warnAfter - elapsed);
      const remainingLogout = Math.max(0, logoutAfter - elapsed);

      setTimeUntilWarning(remainingWarn);
      setTimeUntilLogout(remainingLogout);

      // Warning
      if (elapsed >= warnAfter && !warnedRef.current && onWarning) {
        warnedRef.current = true;
        onWarning();
      }

      // Auto logout
      if (elapsed >= logoutAfter && onLogout) {
        onLogout();
      }
    }, 1000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [enabled, warnAfter, logoutAfter, onWarning, onLogout]);

  return { resetTimer, timeUntilWarning, timeUntilLogout };
}

/**
 * Format milliseconds to human readable time remaining
 */
export function formatTimeRemaining(ms) {
  if (ms <= 0) return '0 ثانية';
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  if (minutes > 0) return `${minutes} دقيقة و ${seconds} ثانية`;
  return `${seconds} ثانية`;
}
