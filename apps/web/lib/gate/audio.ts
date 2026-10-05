import type { Classification } from "./validate";

/** Placeholder clips are silent — drop real Nepali voice recordings in at
 * these same paths and nothing else needs to change. (Any browser-
 * supported audio format works; update the extensions here if you don't
 * keep them as .wav.)
 */
const AUDIO_FILES: Record<Classification, string> = {
  green: "/audio/green.wav",
  amber: "/audio/amber.wav",
  red: "/audio/red.wav",
};

const cache = new Map<string, HTMLAudioElement>();

export function playCue(classification: Classification): void {
  if (typeof window === "undefined") return;
  const src = AUDIO_FILES[classification];
  let audio = cache.get(src);
  if (!audio) {
    audio = new Audio(src);
    cache.set(src, audio);
  }
  audio.currentTime = 0;
  audio.play().catch(() => {
    // Autoplay can be blocked until the kiosk gets its first user
    // interaction — not fatal, the visual result banner still shows.
  });
}
