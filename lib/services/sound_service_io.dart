import 'package:flutter/services.dart';

const _platform = MethodChannel('com.gym2/sound');

/// On native platforms, speech is handled by flutter_tts in TtsService.
/// These functions are no-ops here.
void playSpeech(String message) {}
void cancelSpeech() {}

/// Fires a strong haptic pulse and a native beep sound on Android/iOS.
///
/// HapticFeedback.heavyImpact() gives the user a physical cue.
/// We use a custom MethodChannel to trigger Android's native ToneGenerator
/// without relying on outdated third-party packages.
void playErrorSound() {
  HapticFeedback.heavyImpact();
  try {
    _platform.invokeMethod('beep');
  } catch (_) {
    // Ignore if platform channel fails or is unsupported (e.g. iOS simulator)
  }
}
