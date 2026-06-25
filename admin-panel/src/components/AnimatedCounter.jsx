import { useState, useEffect, useRef } from 'react';

/**
 * Animated number counter that eases from 0 to target value.
 * Uses requestAnimationFrame for smooth 60fps animation.
 */
export default function AnimatedCounter({
  value = 0,
  duration = 800,
  suffix = '',
  prefix = '',
  className = '',
  formatter = (v) => Math.round(v).toLocaleString('en-US'),
}) {
  const [display, setDisplay] = useState(0);
  const prevValue = useRef(0);
  const frameRef = useRef(null);

  useEffect(() => {
    const start = prevValue.current;
    const end = Number(value) || 0;
    const startTime = performance.now();

    const animate = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = start + (end - start) * eased;

      setDisplay(current);

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      } else {
        prevValue.current = end;
      }
    };

    frameRef.current = requestAnimationFrame(animate);

    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [value, duration]);

  return (
    <span className={className}>
      {prefix}{formatter(display)}{suffix}
    </span>
  );
}

/**
 * Non-animated version for static display
 */
export function StaticCounter({ value, suffix = '', prefix = '', className = '' }) {
  const formatted = typeof value === 'number' ? value.toLocaleString('en-US') : value;
  return (
    <span className={className}>
      {prefix}{formatted}{suffix}
    </span>
  );
}
