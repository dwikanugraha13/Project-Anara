"use client";

import React, { useEffect, useState } from "react";
import { ConnectionIcon } from "../ConnectionIcons";
import { BACKEND_URL } from "@/components/brain/types";

interface WhatsAppQrModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConnected?: () => void;
}

export function WhatsAppQrModal({ isOpen, onClose, onConnected }: WhatsAppQrModalProps) {
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [status, setStatus] = useState<"disconnected" | "connecting" | "connected">("disconnected");

  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;

    // Initial fetch
    fetch(`${BACKEND_URL}/api/integrations/whatsapp/qr`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!isMounted) return;
        setIsLoading(false);
        if (d?.qr_data_url) setQrUrl(d.qr_data_url);
        if (d?.status) setStatus(d.status);
      })
      .catch(() => {
        if (isMounted) setIsLoading(false);
      });

    // Polling interval
    const interval = setInterval(() => {
      fetch(`${BACKEND_URL}/api/integrations/whatsapp/qr`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (!isMounted) return;
          if (d?.qr_data_url) {
            setQrUrl(d.qr_data_url);
          }
          if (d?.status === "connected" && d?.user) {
            setStatus("connected");
            if (onConnected) onConnected();
            setTimeout(() => {
              if (isMounted) onClose();
            }, 1200);
          }
        })
        .catch(() => {});
    }, 2500);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [isOpen, onClose, onConnected]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fade-in select-none">
      <div className="relative w-full max-w-sm p-6 rounded-3xl bg-[#090d18] border border-emerald-400/40 shadow-[0_0_60px_rgba(52,211,153,0.2)] flex flex-col items-center text-center font-sans">
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white flex items-center justify-center transition-colors cursor-pointer"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* WhatsApp Icon */}
        <div className="w-12 h-12 rounded-2xl bg-emerald-500/20 border border-emerald-400/40 flex items-center justify-center text-emerald-400 mb-3 shadow-lg">
          <ConnectionIcon name="whatsapp" className="w-6 h-6" />
        </div>

        <h3 className="text-sm font-semibold text-white tracking-wide font-mono">
          Connect WhatsApp Web
        </h3>
        <p className="text-xs text-slate-300 mt-1 mb-4 leading-relaxed">
          Open <span className="text-emerald-300 font-semibold">WhatsApp on your phone</span> &gt; Linked Devices &gt; Link a Device, then scan the QR code:
        </p>

        {/* QR Code Container */}
        <div className="p-3.5 bg-white rounded-2xl shadow-2xl border-2 border-emerald-400/50 relative">
          {isLoading && !qrUrl ? (
            <div className="w-52 h-52 flex flex-col items-center justify-center text-slate-800 font-mono text-xs gap-3">
              <span className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
              <span>Connecting Bridge...</span>
            </div>
          ) : qrUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={qrUrl}
              alt="WhatsApp QR Code"
              className="w-52 h-52 object-contain rounded-lg"
            />
          ) : (
            <div className="w-52 h-52 flex flex-col items-center justify-center text-slate-800 font-mono text-xs gap-2 p-2">
              <span>{status === "connected" ? "Successfully Connected!" : "Waiting for QR Code..."}</span>
            </div>
          )}
        </div>

        <div className="mt-4 flex items-center gap-2 text-[11px] font-mono text-emerald-300">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>Modal will close automatically after successful pairing</span>
        </div>
      </div>
    </div>
  );
}
