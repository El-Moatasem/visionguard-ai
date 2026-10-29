"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Props = { onCaptured: (file: File) => void };

function recorderType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  for (const type of ["video/mp4", "video/webm;codecs=vp8", "video/webm"]) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return undefined;
}

export default function CameraCapture({ onCaptured }: Props) {
  const previewRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [active, setActive] = useState(false);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState("");

  const release = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (previewRef.current) previewRef.current.srcObject = null;
    setActive(false);
  }, []);

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  async function openCamera() {
    setError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera preview requires HTTPS or localhost. Use Capture with phone instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } }, audio: false,
      });
      streamRef.current = stream;
      if (previewRef.current) {
        previewRef.current.srcObject = stream;
        await previewRef.current.play();
      }
      setActive(true);
    } catch {
      setError("Camera access was denied or is not supported. Use file capture instead.");
    }
  }

  function startRecording() {
    if (!streamRef.current || typeof MediaRecorder === "undefined") {
      setError("This browser cannot record from the live preview. Use Capture with phone.");
      return;
    }
    setError("");
    const mimeType = recorderType();
    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(streamRef.current, mimeType ? { mimeType } : undefined);
    } catch {
      setError("Video recording unavailable in this browser. Use Capture with phone.");
      return;
    }
    recorderRef.current = recorder;
    const chunks: BlobPart[] = [];
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    recorder.onerror = () => setError("Recording failed. Try camera capture instead.");
    recorder.onstop = () => {
      const type = recorder.mimeType || mimeType || "video/webm";
      const extension = type.includes("mp4") ? "mp4" : "webm";
      const blob = new Blob(chunks, { type });
      if (blob.size) {
        onCaptured(new File([blob], `visionguard-camera-${Date.now()}.${extension}`, { type }));
      } else {
        setError("No video frames recorded.");
      }
      setRecording(false);
      release();
    };
    recorder.start(1000);
    setRecording(true);
    // Short bounded clips for local development and affordable hosted inference.
    timerRef.current = setTimeout(() => {
      if (recorder.state === "recording") recorder.stop();
    }, 15000);
  }

  function stopRecording() {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  return <section className="panel camera-panel" aria-label="Phone camera">
    <div className="section-heading"><div><span className="eyebrow">CAMERA INPUT</span><h2>Record a short clip</h2></div><span className="pill">15s max</span></div>
    <video className="camera-preview" ref={previewRef} autoPlay playsInline muted aria-label="Camera preview" />
    <div className="button-row">
      {!active ? <button type="button" className="button button-secondary" onClick={openCamera}>Open camera preview</button> :
        !recording ? <button type="button" className="button button-primary" onClick={startRecording}>Start 15s recording</button> :
        <button type="button" className="button button-alert" onClick={stopRecording}>Stop recording</button>}
      {active && !recording && <button type="button" className="button button-quiet" onClick={release}>Close camera</button>}
    </div>
    <p className="helper">Camera preview requires HTTPS or localhost. Phone capture input below works on more browsers.</p>
    {error && <p className="error" role="alert">{error}</p>}
  </section>;
}
