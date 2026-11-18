import type { ReactNode } from 'react'

/** Modal confirm box: title, one line of text, then the buttons (children). */
export default function Confirm({ title, text, children }: { title: string; text: ReactNode; children: ReactNode }) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"><div className="panel max-w-md p-6" role="dialog" aria-modal="true" aria-label={title}>
    <h2 className="text-xl">{title}</h2><p className="my-4 text-sm text-neutral-300">{text}</p>
    <div className="flex flex-wrap gap-2">{children}</div>
  </div></div>
}
