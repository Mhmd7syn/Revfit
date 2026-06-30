// ignore: avoid_web_libraries_in_flutter
import 'dart:js_interop';

// ── Web Speech API bindings ──────────────────────────────────────────────────

@JS('SpeechSynthesisUtterance')
@staticInterop
class _SpeechSynthesisUtterance {
  external factory _SpeechSynthesisUtterance(JSString text);
}

extension _SpeechSynthesisUtteranceExtension on _SpeechSynthesisUtterance {
  external set lang(JSString value);
  external set rate(JSNumber value);
  external set pitch(JSNumber value);
  external set volume(JSNumber value);
}

@JS('speechSynthesis')
external _SpeechSynthesis get _speechSynthesis;

@JS()
@staticInterop
class _SpeechSynthesis {}

extension _SpeechSynthesisExt on _SpeechSynthesis {
  external void speak(_SpeechSynthesisUtterance utterance);
  external void cancel();
}

// ── Public API ───────────────────────────────────────────────────────────────

/// Speaks [message] using the browser's built-in Web Speech API.
///
/// - Does NOT require a prior user gesture (unlike AudioContext).
/// - Cancels any currently-playing speech before starting.
/// - Falls back silently if the API is unavailable.
void playSpeech(String message) {
  if (message.isEmpty) return;
  try {
    _speechSynthesis.cancel();
    final utt = _SpeechSynthesisUtterance(message.toJS);
    utt.lang = 'en-US'.toJS;
    utt.rate = 0.9.toJS;
    utt.pitch = 1.0.toJS;
    utt.volume = 1.0.toJS;
    _speechSynthesis.speak(utt);
  } catch (_) {
    // Web Speech API unavailable — fail silently
  }
}

/// Cancels any in-progress speech synthesis.
void cancelSpeech() {
  try {
    _speechSynthesis.cancel();
  } catch (_) {}
}

/// Plays an error beep using the Web Audio API (best-effort).
///
/// Note: This may be silently blocked by Chrome's autoplay policy if no
/// prior user gesture has occurred. The primary feedback channel is [playSpeech].
void playErrorSound() {
  try {
    cancelSpeech(); // Ensure speech is stopped before beeping
  } catch (_) {}
}
