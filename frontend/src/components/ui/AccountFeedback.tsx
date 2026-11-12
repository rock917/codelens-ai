import * as Dialog from '@radix-ui/react-dialog'
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { CheckCircle2, AlertCircle, Info, LoaderCircle, X } from 'lucide-react'
import './account-feedback.css'

type Notice = { id: number; message: string; kind: 'success' | 'error' | 'info' }
type Notify = (message: string, kind?: Notice['kind']) => void
const ToastContext = createContext<Notify>(() => {})
export const useToast = () => useContext(ToastContext)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [notices, setNotices] = useState<Notice[]>([])
  const counter = useRef(0)
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])
  const notify = useCallback<Notify>((message, kind = 'info') => {
    const id = ++counter.current
    setNotices(items => [...items.slice(-2), { id, message, kind }])
    const timer = setTimeout(() => {
      setNotices(items => items.filter(item => item.id !== id))
      timers.current = timers.current.filter(item => item !== timer)
    }, 7000)
    timers.current.push(timer)
  }, [])
  useEffect(() => () => timers.current.forEach(clearTimeout), [])
  return <ToastContext.Provider value={notify}>{children}<div className="account-toasts" aria-label="Notifications">
    {notices.map(notice => <div key={notice.id} className={`account-toast ${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}>
      {notice.kind === 'success' ? <CheckCircle2 size={18} /> : notice.kind === 'error' ? <AlertCircle size={18} /> : <Info size={18} />}
      <span>{notice.message}</span><button aria-label="Dismiss notification" onClick={() => setNotices(items => items.filter(item => item.id !== notice.id))}><X size={16} /></button>
    </div>)}
  </div></ToastContext.Provider>
}

export function BusyLabel({ children }: { children: ReactNode }) {
  return <><LoaderCircle className="account-spinner" size={17} aria-hidden="true" />{children}</>
}

export function AccountDialog({ open, onOpenChange, title, description, busy = false, destructive = false, children, returnFocus }: {
  open: boolean; onOpenChange: (open: boolean) => void; title: string; description: string;
  busy?: boolean; destructive?: boolean; children: ReactNode; returnFocus?: () => void;
}) {
  const cancel = useRef<HTMLButtonElement>(null)
  return <Dialog.Root open={open} onOpenChange={value => { if (!busy) onOpenChange(value) }}>
    <Dialog.Portal><Dialog.Overlay className="account-modal-overlay" />
      <Dialog.Content className={`account-modal ${destructive ? 'destructive' : ''}`} aria-busy={busy}
        onOpenAutoFocus={event => { event.preventDefault(); cancel.current?.focus() }}
        onCloseAutoFocus={event => { if (returnFocus) { event.preventDefault(); returnFocus() } }}
        onEscapeKeyDown={event => { if (busy) event.preventDefault() }}
        onInteractOutside={event => { if (busy) event.preventDefault() }}>
        <div className="account-modal-eyebrow">{destructive ? 'PERMANENT ACTION' : 'YOUR WORKSPACE'}</div>
        <Dialog.Title>{title}</Dialog.Title>
        <Dialog.Description>{description}</Dialog.Description>
        {children}
        <Dialog.Close asChild><button ref={cancel} type="button" className="account-button account-modal-cancel" disabled={busy}>Cancel</button></Dialog.Close>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
}
