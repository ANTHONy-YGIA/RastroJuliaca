import { Dialog as D, Tabs as T } from "radix-ui";
import type { ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/format";

export function Dialog({ open, onOpenChange, title, description, children, trigger, wide }: {
  open?: boolean; onOpenChange?: (v: boolean) => void; title: string; description?: string; children: ReactNode; trigger?: ReactNode; wide?: boolean;
}) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      {trigger && <D.Trigger asChild>{trigger}</D.Trigger>}
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-50 bg-navy-950/50 backdrop-blur-[2px] data-[state=open]:animate-fade-in" />
        <D.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl bg-white p-6 shadow-xl data-[state=open]:animate-fade-in",
            wide ? "max-w-2xl" : "max-w-lg",
          )}
        >
          <D.Title className="pr-8 text-lg font-semibold text-navy-900">{title}</D.Title>
          {description ? <D.Description className="mt-1 text-sm text-slate-500">{description}</D.Description> : <D.Description className="sr-only">{title}</D.Description>}
          <div className="mt-4">{children}</div>
          <D.Close className="absolute right-4 top-4 rounded-md p-1 text-slate-500 hover:bg-slate-100" aria-label="Cerrar">
            <X className="size-4" />
          </D.Close>
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

export function Tabs({ value, onValueChange, tabs, children }: {
  value: string; onValueChange: (v: string) => void; tabs: { value: string; label: string; count?: number }[]; children: ReactNode;
}) {
  return (
    <T.Root value={value} onValueChange={onValueChange}>
      <T.List className="mb-5 flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1 shadow-sm" aria-label="Secciones">
        {tabs.map((t) => (
          <T.Trigger
            key={t.value}
            value={t.value}
            className="flex shrink-0 items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50 data-[state=active]:bg-navy-900 data-[state=active]:text-white"
          >
            {t.label}
            {t.count !== undefined && <span className="rounded-full bg-black/10 px-1.5 text-xs tabular-nums">{t.count}</span>}
          </T.Trigger>
        ))}
      </T.List>
      {children}
    </T.Root>
  );
}

export const TabPanel = T.Content;
