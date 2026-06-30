// lib/services/tts_service.dart
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_tts/flutter_tts.dart';
import 'sound_service.dart';

/// Lightweight wrapper that provides voice feedback during pose analysis.
///
/// - On **web** (Chrome): uses the browser's built-in Web Speech API
///   (`window.speechSynthesis`) which does NOT require a prior user gesture
///   and is fully supported in Chrome/Edge/Firefox.
/// - On **native** (Android / iOS / macOS / Windows / Linux): uses
///   `flutter_tts` for full text-to-speech.
///
/// Features:
/// - Per-message cooldown to avoid repeating the same correction too often
/// - Non-blocking: new messages interrupt old ones on web
class TtsService {
  TtsService._();
  static final TtsService instance = TtsService._();

  final FlutterTts _tts = FlutterTts();
  bool _initialised = false;

  /// Per-message cooldown tracking: message → last spoken timestamp (ms).
  final Map<String, int> _cooldowns = {};

  /// Minimum time (ms) before the same message can be spoken again.
  static const int cooldownMs = 4000;

  // ── Initialisation ──────────────────────────────────────────────────

  Future<void> init() async {
    if (_initialised) return;
    if (!kIsWeb) {
      // flutter_tts is only functional on native platforms
      await _tts.setLanguage('en-US');
      await _tts.setSpeechRate(0.5);
      await _tts.setPitch(1.0);
      await _tts.setVolume(1.0);
    }
    _initialised = true;
  }

  // ── Public API ──────────────────────────────────────────────────────

  /// Speak [message] aloud if the per-message cooldown has elapsed.
  ///
  /// On **web**: delegates to `window.speechSynthesis` (no autoplay restriction).
  /// On **native**: delegates to `flutter_tts`.
  ///
  /// Returns `true` if speech was triggered, `false` if cooldown was active.
  Future<bool> speak(String message) async {
    if (!_initialised) await init();

    final now = DateTime.now().millisecondsSinceEpoch;
    final lastSpoken = _cooldowns[message] ?? 0;

    if (now - lastSpoken < cooldownMs) {
      return false; // Still within cooldown — suppress
    }

    _cooldowns[message] = now;

    playErrorSound();

    return true;
  }

  /// Stop any in-progress speech immediately.
  Future<void> stop() async {
    if (kIsWeb) {
      cancelSpeech(); // Web Speech API cancel
    } else {
      await _tts.stop();
    }
  }

  /// Clear cooldown history (call at the start of each new session).
  void resetCooldowns() {
    _cooldowns.clear();
  }

  /// Release all TTS resources.
  Future<void> dispose() async {
    await stop();
    _cooldowns.clear();
    _initialised = false;
  }
}
