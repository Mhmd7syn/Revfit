import 'package:flutter/services.dart';

/// On native platforms, speech is handled by flutter_tts in TtsService.
/// These functions are no-ops here.
void playSpeech(String message) {}
void cancelSpeech() {}

void playErrorSound() {
  SystemSound.play(SystemSoundType.alert);
}
