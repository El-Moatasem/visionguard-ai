import { redirect } from "next/navigation";
import VisionGuardStudio from "@/components/VisionGuardStudio";
import "../visionguard-gallery.css";
import "../studio-layout-polish.css";

export const metadata = {
  title: "Analysis Studio | VisionGuard AI",
  description: "Inspect uploaded footage, tracking observations, monitored zones and evidence.",
};

type StudioParams = { video?: string; capture?: string };

export default async function StudioPage({ searchParams }: { searchParams: Promise<StudioParams> }) {
  // A replay-only public deployment must not offer a nonfunctional upload studio.
  if (process.env.NEXT_PUBLIC_REPLAY_ONLY === "1") redirect("/replay");
  const { video, capture } = await searchParams;
  return <VisionGuardStudio requestedVideoId={video} openCamera={capture === "1"} />;
}
