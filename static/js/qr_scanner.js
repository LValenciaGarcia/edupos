/**
 * Punto Asis — Escáner QR usando la cámara del dispositivo.
 *
 * Estrategia dual:
 *   1. BarcodeDetector API nativa (Chrome 83+, Safari iOS 17.4+, Edge 83+)
 *   2. Fallback a jsQR via canvas (requiere jsqr@1.4.0 cargado antes)
 *
 * Uso:
 *   const s = new QRScanner({
 *     videoEl, canvasEl,
 *     onDetect: (data) => { ... },
 *     onError:  (err)  => { ... },
 *     facingMode: 'environment'
 *   });
 *   await s.start();
 *   s.stop();
 */
(function (global) {
  'use strict';

  class QRScanner {
    constructor(opts) {
      this.videoEl    = opts.videoEl;
      this.canvasEl   = opts.canvasEl;
      this.onDetect   = opts.onDetect || (() => {});
      this.onError    = opts.onError  || (() => {});
      this.facingMode = opts.facingMode || 'environment';
      this.stream     = null;
      this.rafId      = null;
      this._stopped   = false;
      this._detector  = null;
      this._useNative = false;
    }

    async start() {
      // ── Elegir motor de detección ──────────────────────────────────────
      if ('BarcodeDetector' in window) {
        try {
          this._detector = new BarcodeDetector({ formats: ['qr_code'] });
          this._useNative = true;
        } catch (_) {
          this._useNative = false;
        }
      }

      // Si no hay BarcodeDetector, necesitamos jsQR
      if (!this._useNative && typeof jsQR === 'undefined') {
        throw new Error('jsQR no está cargado. Verifica el <script> de jsqr@1.4.0 en la página.');
      }

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Tu navegador no expone la cámara (getUserMedia).');
      }

      // ── Abrir cámara ───────────────────────────────────────────────────
      try {
        try {
          this.stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: this.facingMode }, width: { ideal: 1280 } },
            audio: false,
          });
        } catch (_) {
          this.stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        }
      } catch (e) {
        throw new Error('No se pudo acceder a la cámara: ' + (e.message || e));
      }

      this.videoEl.srcObject = this.stream;
      this.videoEl.setAttribute('playsinline', 'true');
      await this.videoEl.play().catch(() => {});

      this._stopped = false;
      this._scheduleLoop();
    }

    _scheduleLoop() {
      if (this._stopped) return;
      this.rafId = requestAnimationFrame(() => this._loop());
    }

    async _loop() {
      if (this._stopped) return;

      const v = this.videoEl;
      if (v.readyState >= 2 && v.videoWidth > 0) {
        try {
          let result = null;

          if (this._useNative) {
            // ── BarcodeDetector (lee el video directamente) ──
            const barcodes = await this._detector.detect(v);
            if (barcodes.length > 0) result = barcodes[0].rawValue;
          } else {
            // ── jsQR (requiere canvas) ───────────────────────
            const w = v.videoWidth;
            const h = v.videoHeight;
            const maxSide = 480;
            const scale   = Math.min(1, maxSide / Math.max(w, h));
            this.canvasEl.width  = Math.round(w * scale);
            this.canvasEl.height = Math.round(h * scale);
            const ctx = this.canvasEl.getContext('2d', { willReadFrequently: true });
            ctx.drawImage(v, 0, 0, this.canvasEl.width, this.canvasEl.height);
            const img  = ctx.getImageData(0, 0, this.canvasEl.width, this.canvasEl.height);
            const code = jsQR(img.data, img.width, img.height, { inversionAttempts: 'dontInvert' });
            if (code && code.data) result = code.data;
          }

          if (result) {
            try { this.onDetect(result); } catch (_) {}
          }
        } catch (_) {
          // Fotograma no legible — ignorar y continuar
        }
      }

      this._scheduleLoop();
    }

    stop() {
      this._stopped = true;
      if (this.rafId) {
        cancelAnimationFrame(this.rafId);
        this.rafId = null;
      }
      if (this.stream) {
        this.stream.getTracks().forEach(t => { try { t.stop(); } catch (_) {} });
        this.stream = null;
      }
      try { this.videoEl.pause(); } catch (_) {}
      this.videoEl.srcObject = null;
      this._detector = null;
    }
  }

  global.QRScanner = QRScanner;
})(window);