import { Loader2 } from 'lucide-react';

const sizes = {
  sm: 'w-4 h-4',
  md: 'w-8 h-8',
  lg: 'w-12 h-12',
};

export default function LoadingSpinner({ size = 'md', label, className = '' }) {
  const spinnerSize = sizes[size] || sizes.md;

  return (
    <div className={`flex flex-col items-center justify-center gap-3 ${className}`}>
      <Loader2 className={`${spinnerSize} animate-spin text-indigo-400`} />
      {label && <p className="text-sm text-slate-500">{label}</p>}
    </div>
  );
}

// Full-page loading variant
export function PageLoading() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <LoadingSpinner size="lg" label="جار التحميل..." />
    </div>
  );
}
