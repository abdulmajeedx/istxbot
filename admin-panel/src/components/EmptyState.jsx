import { Link } from 'react-router-dom';
import { Inbox, Plus } from 'lucide-react';

/**
 * Empty state placeholder for when lists/tables have no data.
 *
 * Usage:
 *   <EmptyState icon={Users} title="لا يوجد مستخدمين" />
 *   <EmptyState icon={ScrollText} title="لا توجد سجلات" action={{ label: 'تحديث', onClick: load }} />
 */
export default function EmptyState({
  icon: Icon = Inbox,
  title = 'لا توجد بيانات',
  description,
  action,
  className = '',
}) {
  return (
    <div className={`flex flex-col items-center justify-center py-16 px-4 text-center ${className}`}>
      <div className="w-16 h-16 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center mb-4">
        <Icon className="w-8 h-8 text-slate-600" />
      </div>
      <h3 className="text-lg font-semibold text-white mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-slate-500 max-w-sm mb-4">{description}</p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="btn btn-primary inline-flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          {action.label}
        </button>
      )}
    </div>
  );
}

/**
 * Empty state with link (for navigation actions)
 */
export function EmptyStateLink({
  icon: Icon = Inbox,
  title = 'لا توجد بيانات',
  description,
  to,
  linkLabel = 'إضافة',
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-16 h-16 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center mb-4">
        <Icon className="w-8 h-8 text-slate-600" />
      </div>
      <h3 className="text-lg font-semibold text-white mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-slate-500 max-w-sm mb-4">{description}</p>
      )}
      <Link to={to} className="btn btn-primary inline-flex items-center gap-2">
        <Plus className="w-4 h-4" />
        {linkLabel}
      </Link>
    </div>
  );
}
