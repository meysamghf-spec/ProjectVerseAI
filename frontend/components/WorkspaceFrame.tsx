import type { ReactNode } from "react";

export function WorkspaceFrame({
  viewport,
  side,
}: {
  viewport: ReactNode;
  side: ReactNode;
}) {
  return (
    <div data-testid="workspace-frame" className="flex flex-col gap-4 lg:flex-row">
      <div className="min-h-[50vh] min-w-0 flex-1 lg:min-h-[calc(100vh-8rem)]">{viewport}</div>
      <aside className="w-full shrink-0 lg:w-[22rem]">{side}</aside>
    </div>
  );
}
