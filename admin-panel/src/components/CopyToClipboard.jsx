import { useState, useCallback } from 'react';
import { Copy, Check } from 'lucide-react';
import { useToast } from './Toast';

/**
 * Click-to-copy component with visual feedback.
 *
 * Usage:
 *   <CopyToClipboard text={user.user_id} />
 *   <CopyToClipboard text="hello" label="Copy code" />
 */
export default function CopyToClipboard({
  text,
  label,
  className = '',
  iconOnly = false,
  toastMessage = 'تم النسخ!',
}) {
  const [copied, setCopied] = useState(false);
  const { toast } = useToast();

  const handleCopy = useCallback(async () => {
    if (!text && text !== 0) return;

    try {
      await navigator.clipboard.writeText(String(text));
      setCopied(true);
      if (toastMessage) toast.success(toastMessage);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = String(text);
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      try {
        document.execCommand('copy');
        setCopied(true);
        if (toastMessage) toast.success(toastMessage);
        setTimeout(() => setCopied(false), 2000);
      } catch {
        toast.error('فشل النسخ');
      }
      document.body.removeChild(textarea);
    }
  }, [text, toastMessage, toast]);

  if (iconOnly) {
    return (
      <button
        onClick={handleCopy}
        className={`p-1.5 rounded-lg transition-all ${
          copied
            ? 'bg-emerald-500/10 text-emerald-400'
            : 'hover:bg-slate-700 text-slate-500 hover:text-slate-300'
        } ${className}`}
        title="نسخ"
      >
        {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
      </button>
    );
  }

  return (
    <button
      onClick={handleCopy}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs transition-all ${
        copied
          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
          : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700 border border-slate-700'
      } ${className}`}
    >
      {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
      {label || text}
    </button>
  );
}
