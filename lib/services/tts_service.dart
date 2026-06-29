// lib/services/tts_service.dart
import 'package:flutter_tts/flutter_tts.dart';

/// Lightweight wrapper around [FlutterTts] for speaking form-correction
/// alerts during streaming pose analysis.
///
/// Features:
/// - Per-message cooldown to avoid spamming the same correction
/// - Configurable speech rate, pitch, and language
/// - Non-blocking: if the engine is already speaking, new messages queue
class TtsService {
  TtsService._();
  static final TtsService instance = TtsService._();

  final FlutterTts _tts = FlutterTts();
  bool _initialised = false;

  /// Per-message cooldown tracking: message → last spoken timestamp (ms).
  final Map<String, int> _cooldowns = {};

  /// Minimum time (ms) before the same message can be spoken again.
  static const int cooldownMs = 3000;

  // ── Initialisation ──────────────────────────────────────────────────

  Future<void> init() async {
    if (_initialised) return;
    await _tts.setLanguage('en-US');
    await _tts.setSpeechRate(0.5); // Slightly slower for clarity
    await _tts.setPitch(1.0);
    await _tts.setVolume(1.0);
    _initialised = true;
  }

  // ── Public API ──────────────────────────────────────────────────────

  /// Speak [message] aloud if the cooldown for this exact string has elapsed.
  ///
  /// Returns `true` if the message was actually spoken, `false` if it was
  /// suppressed by the cooldown.
  Future<bool> speak(String message) async {
    if (!_initialised) await init();

    final now = DateTime.now().millisecondsSinceEpoch;
    final lastSpoken = _cooldowns[message] ?? 0;

    if (now - lastSpoken < cooldownMs) {
      return false; // Cooldown active — skip
    }

    _cooldowns[message] = now;
    await _tts.speak(message);
    return true;
  }

  /// Stop any in-progress speech immediately.
  Future<void> stop() async {
    await _tts.stop();
  }

  /// Clear cooldown history (e.g. at the start of a new session).
  void resetCooldowns() {
    _cooldowns.clear();
  }

  /// Release TTS resources.
  Future<void> dispose() async {
    await _tts.stop();
    _cooldowns.clear();
    _initialised = false;
  }
}
