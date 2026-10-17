/**
 * AeroGuard Cockpit Sound Effects Engine
 *
 * Synthesizes authentic avionics alerts using the browser Web Audio API:
 * - Master Warning (urgent two-tone pulsed klaxon for ESCALATED / Emergency)
 * - Master Caution (cockpit chime for SUSPECTED / AWAITING_ACK)
 * - ATC Radio Transmission (comm squelch and incoming radio chime)
 * - Acknowledgement Confirmation (positive resolving chime)
 * - Action Executed (stabilization sequence tone)
 *
 * SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
 */

class SoundEffectsEngine {
  private ctx: AudioContext | null = null;
  private isMuted: boolean = false;
  private activeKlaxonInterval: number | null = null;

  constructor() {
    // AudioContext will be initialized on first user gesture or sound trigger
  }

  private getContext(): AudioContext | null {
    if (typeof window === "undefined") return null;
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return null;

    if (!this.ctx) {
      this.ctx = new AudioCtx();
    }
    if (this.ctx.state === "suspended") {
      this.ctx.resume().catch(() => undefined);
    }
    return this.ctx;
  }

  private muteListeners: Set<(muted: boolean) => void> = new Set();

  public ensureAudioContext(): void {
    const ctx = this.getContext();
    if (ctx && ctx.state === "suspended") {
      ctx.resume().catch(() => undefined);
    }
  }

  public onMuteChange(listener: (muted: boolean) => void): () => void {
    this.muteListeners.add(listener);
    return () => {
      this.muteListeners.delete(listener);
    };
  }

  public setMuted(muted: boolean): void {
    this.isMuted = muted;
    if (muted) {
      this.stopContinuousAlerts();
    }
    this.muteListeners.forEach((l) => {
      try {
        l(this.isMuted);
      } catch {
        // Ignored
      }
    });
  }

  public getMuted(): boolean {
    return this.isMuted;
  }

  public toggleMute(): boolean {
    this.setMuted(!this.isMuted);
    return this.isMuted;
  }

  public stopContinuousAlerts(): void {
    if (this.activeKlaxonInterval !== null) {
      clearInterval(this.activeKlaxonInterval);
      this.activeKlaxonInterval = null;
    }
  }

  /**
   * Master Warning Klaxon
   * Two alternating tones (850Hz & 1050Hz) pulsed with envelope
   */
  public playMasterWarning(durationMs = 2400): void {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    this.stopContinuousAlerts();

    const now = ctx.currentTime;
    const pulseCount = Math.floor(durationMs / 400);

    for (let i = 0; i < pulseCount; i++) {
      const startTime = now + i * 0.4;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "sawtooth";
      // Alternating high and low emergency pitch
      osc.frequency.setValueAtTime(i % 2 === 0 ? 980 : 820, startTime);
      osc.frequency.exponentialRampToValueAtTime(i % 2 === 0 ? 840 : 700, startTime + 0.35);

      gain.gain.setValueAtTime(0, startTime);
      gain.gain.linearRampToValueAtTime(0.25, startTime + 0.05);
      gain.gain.exponentialRampToValueAtTime(0.01, startTime + 0.35);

      const filter = ctx.createBiquadFilter();
      filter.type = "lowpass";
      filter.frequency.setValueAtTime(1600, startTime);

      osc.connect(filter);
      filter.connect(gain);
      gain.connect(ctx.destination);

      osc.start(startTime);
      osc.stop(startTime + 0.38);
    }
  }

  /**
   * Master Caution (Cockpit Ding-Dong Chime)
   * Classic two-tone Boeing/Airbus caution chime (660Hz -> 550Hz)
   */
  public playMasterCaution(): void {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const now = ctx.currentTime;

    // Tone 1: 660 Hz
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = "sine";
    osc1.frequency.setValueAtTime(659.25, now);
    gain1.gain.setValueAtTime(0.3, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.6);

    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.6);

    // Tone 2: 554 Hz (starts slightly after Tone 1)
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = "sine";
    osc2.frequency.setValueAtTime(554.37, now + 0.18);
    gain2.gain.setValueAtTime(0, now);
    gain2.gain.setValueAtTime(0.3, now + 0.18);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.8);

    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.18);
    osc2.stop(now + 0.85);
  }

  /**
   * ATC Radio Transmission Chime & Squelch
   * High-pitch double pip and subtle radio noise burst
   */
  public playATCRadioChime(): void {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const now = ctx.currentTime;

    // Radio pip 1
    const pip1 = ctx.createOscillator();
    const pipGain1 = ctx.createGain();
    pip1.type = "sine";
    pip1.frequency.setValueAtTime(1200, now);
    pipGain1.gain.setValueAtTime(0.2, now);
    pipGain1.gain.exponentialRampToValueAtTime(0.001, now + 0.08);

    pip1.connect(pipGain1);
    pipGain1.connect(ctx.destination);
    pip1.start(now);
    pip1.stop(now + 0.09);

    // Radio pip 2
    const pip2 = ctx.createOscillator();
    const pipGain2 = ctx.createGain();
    pip2.type = "sine";
    pip2.frequency.setValueAtTime(1400, now + 0.1);
    pipGain2.gain.setValueAtTime(0.2, now + 0.1);
    pipGain2.gain.exponentialRampToValueAtTime(0.001, now + 0.22);

    pip2.connect(pipGain2);
    pipGain2.connect(ctx.destination);
    pip2.start(now + 0.1);
    pip2.stop(now + 0.23);
  }

  /**
   * Positive Pilot Acknowledged Confirmation Chime
   * Rising major chord (523Hz -> 659Hz -> 784Hz)
   */
  public playAckChime(): void {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    const notes = [523.25, 659.25, 783.99];

    notes.forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const start = now + idx * 0.09;

      osc.type = "triangle";
      osc.frequency.setValueAtTime(freq, start);

      gain.gain.setValueAtTime(0, start);
      gain.gain.linearRampToValueAtTime(0.22, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, start + 0.45);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(start);
      osc.stop(start + 0.5);
    });
  }

  /**
   * Action Executed / Stabilization Sequence Tone
   * Deep smooth resonance confirming stabilization lock
   */
  public playActionTone(): void {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(440, now);
    osc.frequency.exponentialRampToValueAtTime(880, now + 0.35);

    gain.gain.setValueAtTime(0.25, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.7);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.72);
  }

  /**
   * Sensor Degraded / Camera Obstructed Caution Tone
   * Double short alert blip (480 Hz)
   */
  public playSensorCaution(): void {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    [0, 0.14].forEach((offset) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(480, now + offset);
      gain.gain.setValueAtTime(0.2, now + offset);
      gain.gain.exponentialRampToValueAtTime(0.001, now + offset + 0.1);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now + offset);
      osc.stop(now + offset + 0.11);
    });
  }

  /**
   * Nominal Status Flight Ping
   * Soft affirmative single ping
   */
  public playNominalPing(): void {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, now);
    gain.gain.setValueAtTime(0.15, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.36);
  }

  /**
   * Dispatches realistic aviation audio cues tailored specifically to the scenario.
   */
  public playScenarioAlert(scenarioId: string): void {
    if (this.isMuted) return;
    switch (scenarioId) {
      case "normal_flight":
        this.playNominalPing();
        break;
      case "single_pilot_unresponsive":
        this.playMasterCaution();
        break;
      case "dual_pilot_atc_connected":
        this.playMasterWarning(1800);
        break;
      case "dual_pilot_atc_disconnected":
        this.playMasterWarning(2400);
        break;
      case "camera_obstructed":
        this.playSensorCaution();
        break;
      default:
        this.playMasterCaution();
        break;
    }
  }

  /**
   * Subtle avionics mechanical switch click
   */
  public playClick(): void {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(1600, now);
    gain.gain.setValueAtTime(0.05, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.03);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.04);
  }
}

export const soundEffects = new SoundEffectsEngine();
