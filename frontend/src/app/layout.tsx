import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VisionGuard AI | Video Workspace",
  description: "Video ingestion MVP for explainable visual safety intelligence",
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
