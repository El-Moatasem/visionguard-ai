import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VisionGuard AI | Video Workspace",
  description: "Evidence-first visual safety review with SAM tracks and deterministic rules",
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
