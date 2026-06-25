"use client";

import { QueryProvider } from "@/lib/query-provider";
import type { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  return <QueryProvider>{children}</QueryProvider>;
}
