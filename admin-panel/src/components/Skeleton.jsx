import { Loader2 } from 'lucide-react';

// Base skeleton pulse element
export function SkeletonPulse({ className = '' }) {
  return <div className={`skeleton rounded-lg ${className}`} />;
}

// Card skeleton (mimics StatCard layout)
export function CardSkeleton() {
  return (
    <div className="card flex items-start gap-4">
      <SkeletonPulse className="w-12 h-12 rounded-xl" />
      <div className="flex-1 space-y-2">
        <SkeletonPulse className="h-7 w-20" />
        <SkeletonPulse className="h-4 w-32" />
      </div>
    </div>
  );
}

// Stats grid skeleton (row of 4 cards)
export function StatsGridSkeleton() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}

// Table skeleton
export function TableSkeleton({ rows = 8, cols = 6 }) {
  return (
    <div className="card overflow-hidden p-0">
      {/* Header */}
      <div className="flex items-center gap-4 p-4 bg-slate-800/30 border-b border-slate-700/50">
        {Array.from({ length: cols }).map((_, i) => (
          <SkeletonPulse key={i} className="h-4 flex-1" />
        ))}
      </div>
      {/* Rows */}
      <div className="divide-y divide-slate-800/50">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 p-4">
            <SkeletonPulse className="w-9 h-9 rounded-full shrink-0" />
            {Array.from({ length: cols - 1 }).map((_, j) => (
              <SkeletonPulse key={j} className="h-4 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// Chart skeleton
export function ChartSkeleton() {
  return (
    <div className="card space-y-4">
      <SkeletonPulse className="h-6 w-48" />
      <div className="h-64 flex items-end gap-2 px-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <SkeletonPulse
            key={i}
            className="flex-1 rounded-b-none"
            style={{ height: `${30 + Math.random() * 60}%` }}
          />
        ))}
      </div>
    </div>
  );
}

// Full page loading (dashboard skeleton)
export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <SkeletonPulse className="h-8 w-48" />
          <SkeletonPulse className="h-4 w-32" />
        </div>
        <div className="flex items-center gap-2">
          <SkeletonPulse className="w-2.5 h-2.5 rounded-full" />
          <SkeletonPulse className="h-5 w-16" />
        </div>
      </div>
      <div className="card">
        <div className="flex items-center gap-4">
          <SkeletonPulse className="h-5 w-16" />
          <SkeletonPulse className="h-9 w-20" />
          <SkeletonPulse className="h-9 w-20" />
          <SkeletonPulse className="h-9 w-28" />
        </div>
      </div>
      <StatsGridSkeleton />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartSkeleton />
        <div className="card space-y-4">
          <SkeletonPulse className="h-6 w-48" />
          <SkeletonPulse className="h-4 w-full" />
          <SkeletonPulse className="h-4 w-full" />
          <SkeletonPulse className="h-4 w-3/4" />
        </div>
      </div>
    </div>
  );
}

// Generic page skeleton
export function PageSkeleton({ withTable = false }) {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <SkeletonPulse className="h-8 w-48" />
        <SkeletonPulse className="h-4 w-32" />
      </div>
      <div className="card space-y-3">
        <SkeletonPulse className="h-10 w-full" />
      </div>
      {withTable ? <TableSkeleton /> : <StatsGridSkeleton />}
    </div>
  );
}

// Simple spinner (kept for small inline loads)
export function Spinner({ size = 'md', label }) {
  const sizes = { sm: 'w-4 h-4', md: 'w-8 h-8', lg: 'w-12 h-12' };
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <Loader2 className={`${sizes[size]} animate-spin text-indigo-400`} />
      {label && <p className="text-sm text-slate-500">{label}</p>}
    </div>
  );
}
