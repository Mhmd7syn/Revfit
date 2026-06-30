// ignore_for_file: avoid_web_libraries_in_flutter
import 'dart:js_interop';

// ── Web Audio API Interop ───────────────────────────────────────────────────

@JS('AudioContext')
@staticInterop
class _AudioContext {
  external factory _AudioContext();
}

extension _AudioContextExtension on _AudioContext {
  external _OscillatorNode createOscillator();
  external _GainNode createGain();
  external _AudioNode get destination;
  external JSNumber get currentTime;
}

@JS()
@staticInterop
class _AudioNode {}

extension _AudioNodeExtension on _AudioNode {
  external void connect(_AudioNode destination);
}

@JS()
@staticInterop
class _OscillatorNode extends _AudioNode {}

extension _OscillatorNodeExtension on _OscillatorNode {
  external set type(JSString value);
  external _AudioParam get frequency;
  external void start([JSNumber? when]);
  external void stop([JSNumber? when]);
}

@JS()
@staticInterop
class _GainNode extends _AudioNode {}

extension _GainNodeExtension on _GainNode {
  external _AudioParam get gain;
}

@JS()
@staticInterop
class _AudioParam {}

extension _AudioParamExtension on _AudioParam {
  external set value(JSNumber val);
  external void exponentialRampToValueAtTime(JSNumber value, JSNumber endTime);
}

// ── Public API ───────────────────────────────────────────────────────────────

void playErrorSound() {
  try {
    final ctx = _AudioContext();
    
    final osc = ctx.createOscillator();
    final gain = ctx.createGain();
    
    osc.type = 'square'.toJS;
    osc.frequency.value = 250.0.toJS;
    
    osc.connect(gain);
    gain.connect(ctx.destination);
    
    try {
      osc.start(0.toJS);
    } catch (_) {
      try {
        osc.start();
      } catch (_) {}
    }
    
    final stopTime = (ctx.currentTime.toDartDouble + 0.25).toJS;
    gain.gain.exponentialRampToValueAtTime(0.00001.toJS, stopTime);
    
    try {
      osc.stop(stopTime);
    } catch (_) {}
  } catch (_) {}
}

void playSpeech(String message) {}
void cancelSpeech() {}
